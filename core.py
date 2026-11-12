"""Núcleo independente da clínica. Valores financeiros em centavos."""
import sqlite3, json, uuid, hashlib, secrets, datetime, re
from pathlib import Path

ROLES={'administrador','dentista','recepcao','financeiro','estoque'}
ACCESS={
 'pacientes':{'administrador','dentista','recepcao'},
 'pessoas':{'administrador','dentista','recepcao','estoque'},
 'agenda':{'administrador','dentista','recepcao'},
 'clinico':{'administrador','dentista'},
 'titulos':{'administrador','financeiro'},
 'pagamentos':{'administrador','financeiro'},
 'materiais':{'administrador','estoque'},
 'movimentos':{'administrador','estoque'},
}
FIELDS={
 'pacientes':{'nome','matricula','telefone','responsavel','ativo'},
 'pessoas':{'nome','tipo','registro','ativo'},
 'agenda':{'paciente','profissional','sala','inicio','fim','status','motivo'},
 'clinico':{'paciente','tipo','conteudo','referencia'},
 'titulos':{'descricao','tipo','valor','vencimento'},
 'pagamentos':{'titulo','valor','tipo','referencia','motivo'},
 'materiais':{'nome','codigo','unidade','minimo','ativo'},
 'movimentos':{'material','lote','validade','tipo','quantidade','motivo'},
}
APPEND={'clinico','pagamentos','movimentos'}
QUESTIONS={'doencas','tratamento','medicamentos','alergias','cirurgias','cicatrizacao','anestesia','sangramento','gravidez','tabaco','alcool'}
FIELDS['clinico']|={'respostas','queixa','historia','odontologico','familiar','profissional','data','estado'}
FIELDS['titulos']|={'desconto','acrescimo','vinculo','servico','cancelado','motivo_cancelamento'}
FIELDS['pagamentos']|={'data','forma','confirmado'}

ACCESS['funcionarios']={'administrador'}
FIELDS['funcionarios']={'nome','matricula','cargo','registro','ativo'}

class Connection(sqlite3.Connection):
 def __exit__(self,*args):
  try:return super().__exit__(*args)
  finally:self.close()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(password,salt):return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def password_ok(p): return isinstance(p,str) and 12<=len(p)<=200

class Store:
 def __init__(self,path):
  self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.connect() as c:
   c.executescript('''PRAGMA journal_mode=WAL;
   CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT UNIQUE, role TEXT, salt TEXT, hash TEXT, active INTEGER);
   CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, kind TEXT, version INTEGER, data TEXT, author TEXT, updated TEXT);
   CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY, at TEXT, actor TEXT, action TEXT, record_id TEXT, before TEXT, after TEXT);
   CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, actor TEXT, fingerprint TEXT, result TEXT);
   CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user TEXT, expires REAL);
   ''')
 def connect(self):
  c=sqlite3.connect(self.path,timeout=15,factory=Connection);c.row_factory=sqlite3.Row;return c
 def create_user(self,name,password,role,actor='configuracao'):
  name=name.strip().lower()
  if not re.fullmatch(r'[a-z0-9._-]{3,40}',name) or not password_ok(password) or role not in ROLES: raise ValueError('Usuário: 3 a 40 letras/números. Senha: mínimo 12 caracteres. Perfil obrigatório.')
  salt=secrets.token_hex(16); uid=str(uuid.uuid4())
  with self.connect() as c:
   c.execute('INSERT INTO users VALUES(?,?,?,?,?,1)',(uid,name,role,salt,digest(password,salt)))
   c.execute('INSERT INTO audit(at,actor,action,record_id,after) VALUES(?,?,?,?,?)',(now(),actor,'criar_usuario',uid,json.dumps({'nome':name,'perfil':role})))
  return uid
 def login(self,name,password):
  with self.connect() as c:r=c.execute('SELECT * FROM users WHERE name=? AND active=1',(name.lower().strip(),)).fetchone()
  if not r or not secrets.compare_digest(r['hash'],digest(password,r['salt'])):return None
  return {'id':r['id'],'name':r['name'],'role':r['role']}
 def records(self,c,kind):return [dict(id=r['id'],version=r['version'],data=json.loads(r['data']),author=r['author'],author_name=r['author_name'],updated=r['updated']) for r in c.execute('SELECT r.*, u.name AS author_name FROM records r LEFT JOIN users u ON u.id=r.author WHERE r.kind=? ORDER BY r.updated DESC',(kind,))]
 def snapshot(self,user):
  with self.connect() as c:return {k:self.records(c,k) for k,roles in ACCESS.items() if user['role'] in roles}
 def apply(self,user,op):
  if not isinstance(op,dict):raise ValueError('Operação inválida.')
  kind=op.get('kind'); rid=op.get('record'); oid=op.get('id'); d=op.get('data'); base=op.get('base')
  if kind not in ACCESS or user['role'] not in ACCESS[kind]:raise ValueError('Sem permissão para este módulo.')
  for ident in (rid,oid):
   try:uuid.UUID(ident)
   except Exception:raise ValueError('Identificador inválido.')
  if not isinstance(d,dict) or set(d)-FIELDS[kind] or type(base)!=int or base<0:raise ValueError('Campos ou versão inválidos.')
  if len(json.dumps(d))>20000:raise ValueError('Registro excede o limite.')
  fp=hashlib.sha256(json.dumps(op,sort_keys=True).encode()).hexdigest()
  with self.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   done=c.execute('SELECT * FROM operations WHERE id=?',(oid,)).fetchone()
   if done:
    if done['actor']!=user['id'] or done['fingerprint']!=fp:raise ValueError('Identificador de operação reutilizado com outro conteúdo.')
    return json.loads(done['result'])
   old=c.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()
   if old and (old['kind']!=kind or old['version']!=base):raise ValueError('Conflito: registro alterado em outro aparelho. Confira antes de reenviar.')
   if not old and base!=0:raise ValueError('Conflito: registro não encontrado.')
   if old and kind in APPEND and not (kind=='clinico' and json.loads(old['data']).get('estado')=='rascunho'):raise ValueError('Histórico imutável. Registre complemento ou estorno, preservando o original.')
   def text(key,required=True):
    val=d.get(key,'')
    if not isinstance(val,str) or len(val)>12000 or (required and not val.strip()):raise ValueError('Preencha corretamente: '+key)
    return val.strip()
   def integer(key,minimum=0):
    v=d.get(key)
    if type(v)!=int or not minimum<=v<=1000000000:raise ValueError('Valor inteiro inválido: '+key)
    return v
   def ref(key,target):
    row=c.execute('SELECT * FROM records WHERE id=? AND kind=?',(text(key),target)).fetchone()
    if not row:raise ValueError('Cadastro relacionado não encontrado: '+key)
    return json.loads(row['data'])
   def date(key):
    try:datetime.date.fromisoformat(text(key))
    except Exception:raise ValueError('Data inválida: '+key)
   def unique(key):
    v=text(key).casefold()
    for r in self.records(c,kind):
     if r['id']!=rid and r['data'].get(key,'').strip().casefold()==v:raise ValueError('Já existe cadastro com '+key+' igual.')
   if kind in {'pacientes','pessoas','materiais','funcionarios'}:
    text('nome')
    if type(d.get('ativo'))!=bool:raise ValueError('Informe ativo ou inativo.')
   if kind=='funcionarios':
    unique('matricula');text('cargo');text('registro',False)
   if kind=='pacientes':unique('matricula');text('telefone',False);text('responsavel',False)
   if kind=='pessoas':
    if text('tipo') not in {'profissional','fornecedor'}:raise ValueError('Tipo de pessoa inválido.')
    text('registro',False)
   if kind=='agenda':
    patient=ref('paciente','pacientes'); professional=ref('profissional','pessoas');text('sala');text('motivo',False)
    if not patient['ativo'] or not professional['ativo'] or professional['tipo']!='profissional':raise ValueError('Paciente ou profissional inativo/inválido.')
    try:
     start=datetime.datetime.fromisoformat(text('inicio'));end=datetime.datetime.fromisoformat(text('fim'))
     if start.tzinfo or end.tzinfo or end<=start or end-start>datetime.timedelta(hours=12):raise ValueError()
    except Exception:raise ValueError('Horário inválido. Use início e fim locais, duração até 12 horas.')
    if text('status') not in {'agendado','confirmado','chegou','atendido','faltou','cancelado'}:raise ValueError('Situação inválida.')
    if old and (json.loads(old['data'])['inicio']!=d['inicio'] or d['status']=='cancelado') and not d.get('motivo','').strip():raise ValueError('Informe o motivo da remarcação/cancelamento.')
    if d['status'] not in {'cancelado','faltou'}:
     for r in self.records(c,kind):
      v=r['data']
      if r['id']!=rid and v['status'] not in {'cancelado','faltou'} and (v['profissional']==d['profissional'] or v['sala']==d['sala'] or v['paciente']==d['paciente']) and start<datetime.datetime.fromisoformat(v['fim']) and end>datetime.datetime.fromisoformat(v['inicio']):raise ValueError('Conflito de agenda: paciente, profissional ou sala ocupado.')
   if kind=='clinico':
    ref('paciente','pacientes');text('conteudo',d.get('tipo')!='anamnese');text('referencia',False)
    if 'estado' in d:
     if d['estado'] not in {'rascunho','finalizado'}:raise ValueError('Estado clínico inválido.')
     date('data');pro=ref('profissional','pessoas')
     if pro['tipo']!='profissional':raise ValueError('Selecione um profissional.')
    if d.get('tipo')=='anamnese' and 'estado' in d:
     text('queixa',d['estado']=='finalizado');text('historia',False);text('odontologico',False);text('familiar',False)
     answers=d.get('respostas')
     if not isinstance(answers,dict) or set(answers)!=QUESTIONS:raise ValueError('Questionário incompleto.')
     for q,a in answers.items():
      if not isinstance(a,dict) or a.get('valor') not in {'Sim','Não','Não informado'} or not isinstance(a.get('detalhe'),str):raise ValueError('Resposta inválida: '+q)
      if d['estado']=='finalizado' and a['valor']=='Sim' and not a['detalhe'].strip():raise ValueError('Detalhe a resposta: '+q)
    if old and json.loads(old['data'])['paciente']!=d['paciente']:raise ValueError('Não é permitido trocar o paciente do registro.')
    if text('tipo') not in {'anamnese','evolucao','plano','consentimento','correcao'}:raise ValueError('Tipo clínico inválido.')
    if d.get('referencia'):
     previous=ref('referencia','clinico')
     if previous['paciente']!=d['paciente']:raise ValueError('Referência pertence a outro paciente.')
   if kind=='titulos':
    text('descricao');integer('valor',1);date('vencimento')
    if text('tipo') not in {'receber','pagar'}:raise ValueError('Tipo financeiro inválido.')
    for k in ('desconto','acrescimo'):
     if k in d:integer(k)
    if d.get('desconto',0)>d['valor']:raise ValueError('Desconto superior ao valor original.')
    if d.get('vinculo'):
     if not c.execute("SELECT id FROM records WHERE id=? AND kind IN ('pacientes','pessoas')",(d['vinculo'],)).fetchone():raise ValueError('Vínculo não encontrado.')
    if old:
     before=json.loads(old['data'])
     if any(before.get(k)!=d.get(k) for k in set(before)|set(d) if k not in {'cancelado','motivo_cancelamento'}):raise ValueError('Só o cancelamento é permitido. Preserve os valores originais.')
     if before.get('cancelado') or d.get('cancelado') is not True:raise ValueError('Cancelamento inválido.')
    if d.get('cancelado'):
     text('motivo_cancelamento')
     paid=sum((1 if r['data']['tipo']=='pagamento' else -1)*r['data']['valor'] for r in self.records(c,'pagamentos') if r['data']['titulo']==rid)
     if paid:raise ValueError('Estorne os pagamentos antes de cancelar.')
   if kind=='pagamentos':
    title=ref('titulo','titulos');value=integer('valor',1);text('motivo');text('referencia',False)
    if d.get('confirmado') is not True:raise ValueError('Confirme explicitamente a movimentação financeira.')
    date('data')
    if text('forma') not in {'Pix','Dinheiro','Cartão','Transferência','Boleto','Outro'}:raise ValueError('Forma inválida.')
    if title.get('cancelado'):raise ValueError('Conta cancelada.')
    payments=self.records(c,'pagamentos');total=sum((1 if r['data']['tipo']=='pagamento' else -1)*r['data']['valor'] for r in payments if r['data']['titulo']==d['titulo'])
    if d.get('tipo')=='pagamento':
     if total+value>title['valor']-title.get('desconto',0)+title.get('acrescimo',0):raise ValueError('Pagamento ultrapassa o saldo do título.')
    elif d.get('tipo')=='estorno':
     original=ref('referencia','pagamentos')
     reverted=sum(r['data']['valor'] for r in payments if r['data'].get('referencia')==d['referencia'] and r['data']['tipo']=='estorno')
     if original['tipo']!='pagamento' or original['titulo']!=d['titulo'] or value+reverted>original['valor']:raise ValueError('Estorno superior ao pagamento ou referência inválida.')
    else:raise ValueError('Tipo de pagamento inválido.')
   if kind=='materiais':unique('codigo');text('unidade');integer('minimo')
   if kind=='movimentos':
    material=ref('material','materiais');text('lote');date('validade');integer('quantidade',1);text('motivo')
    if not material['ativo']:raise ValueError('Material inativo.')
    if d.get('tipo') not in {'entrada','saida'}:raise ValueError('Tipo de movimento inválido.')
    same=[r['data'] for r in self.records(c,kind) if r['data']['material']==d['material'] and r['data']['lote']==d['lote']]
    if any(r['validade']!=d['validade'] for r in same):raise ValueError('Lote com validade diferente da registrada.')
    balance=sum((1 if r['tipo']=='entrada' else -1)*r['quantidade'] for r in same)
    if d['tipo']=='saida' and d['quantidade']>balance:raise ValueError('Saldo insuficiente neste lote. Operação não gravada.')
   version=base+1;when=now();raw=json.dumps(d,ensure_ascii=False)
   c.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?,?,?)',(rid,kind,version,raw,user['id'],when))
   c.execute('INSERT INTO audit(at,actor,action,record_id,before,after) VALUES(?,?,?,?,?,?)',(when,user['id'],'salvar_'+kind,rid,old['data'] if old else None,raw))
   result={'id':rid,'version':version}
   c.execute('INSERT INTO operations VALUES(?,?,?,?)',(oid,user['id'],fp,json.dumps(result)))
   return result
 def backup(self,dest):
  with self.connect() as source,sqlite3.connect(dest,factory=Connection) as target:source.backup(target)
  with sqlite3.connect(dest,factory=Connection) as c:
   if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup inválido.')
