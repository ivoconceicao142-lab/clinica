import argparse, getpass, hashlib, json, os, secrets, threading, time, tempfile, sqlite3, shutil
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urlparse
from core import Store,ACCESS

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'dados';DATA.mkdir(exist_ok=True)
store=Store(DATA/'clinica.sqlite')
attempts={};lock=threading.Lock()
PUBLIC=os.environ.get('CLINICA_ORIGIN','')
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,obj,status=200,cookie=None):
  raw=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.headers_common();self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)))
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(raw)
 def headers_common(self):
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
  self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
 def origin(self):return PUBLIC or 'http://'+self.headers.get('Host','')
 def host_valid(self):
  expected=urlparse(PUBLIC).netloc if PUBLIC else '127.0.0.1:'+str(self.server.server_port)
  return self.headers.get('Host')==expected
 def session(self):
  try:cookie=SimpleCookie(self.headers.get('Cookie',''));token=cookie['clinica_session'].value
  except Exception:return None
  with store.connect() as c:r=c.execute('SELECT u.id,u.name,u.role FROM sessions s JOIN users u ON s.user=u.id WHERE s.token=? AND s.expires>? AND u.active=1',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
  return dict(r) if r else None
 def do_GET(self):
  if not self.host_valid():return self.send({'error':'Endereço não autorizado.'},403)
  path=urlparse(self.path).path
  if path.startswith('/api/'):
   u=self.session()
   if not u:return self.send({'error':'Entre novamente para sincronizar.'},401)
   if path=='/api/state':return self.send({'user':u,'records':store.snapshot(u),'serverTime':time.time()})
   if path=='/api/audit':
    if u['role']!='administrador':return self.send({'error':'Sem permissão.'},403)
    with store.connect() as c:rows=[dict(r) for r in c.execute('SELECT seq,at,actor,action,record_id,before,after FROM audit ORDER BY seq DESC LIMIT 500')]
    return self.send({'audit':rows})
   if path=='/api/users':
    if u['role']!='administrador':return self.send({'error':'Sem permissão.'},403)
    with store.connect() as c:rows=[dict(r) for r in c.execute('SELECT id,name,role,active FROM users')]
    return self.send({'users':rows})
   return self.send({'error':'Não encontrado.'},404)
  files={'/':'index.html','/app.js':'app.js','/v2.js':'v2.js','/modules.js':'modules.js','/style.css':'style.css','/sw.js':'sw.js','/manifest.json':'manifest.json'}
  if path not in files:return self.send({'error':'Não encontrado.'},404)
  file=ROOT/'web'/files[path];raw=file.read_bytes();self.send_response(200);self.headers_common()
  self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'application/javascript','css':'text/css','json':'application/json'}[file.suffix[1:]])
  self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_POST(self):
  try:
   if not self.host_valid() or self.headers.get('Origin')!=self.origin() or self.headers.get('X-Clinica-Request')!='1':return self.send({'error':'Origem inválida. Reabra o sistema.'},403)
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=1000000:return self.send({'error':'Pedido muito grande ou vazio.'},400)
   body=json.loads(self.rfile.read(length));path=urlparse(self.path).path
   if path=='/api/login':
    ident=self.client_address[0]
    with lock:
     hits=[t for t in attempts.get(ident,[]) if t>time.time()-900];attempts[ident]=hits
     if len(hits)>=10:return self.send({'error':'Muitas tentativas. Aguarde 15 minutos.'},429)
     hits.append(time.time())
    u=store.login(str(body.get('name','')),str(body.get('password','')))
    if not u:return self.send({'error':'Usuário ou senha inválidos.'},401)
    token=secrets.token_urlsafe(32)
    with store.connect() as c:c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],time.time()+8*3600))
    return self.send({'user':u},cookie='clinica_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+('; Secure' if PUBLIC.startswith('https://') else ''))
   u=self.session()
   if not u:return self.send({'error':'Sessão expirada. Entre online para sincronizar.'},401)
   if path=='/api/logout':
    cookie=SimpleCookie(self.headers.get('Cookie',''))
    with store.connect() as c:c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(cookie['clinica_session'].value.encode()).hexdigest(),))
    return self.send({'ok':True},cookie='clinica_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
   if path=='/api/sync':
    ops=body.get('operations')
    if not isinstance(ops,list) or len(ops)>100:return self.send({'error':'Envie no máximo 100 operações.'},400)
    results=[]
    for op in ops:
     try:results.append({'id':op.get('id'),'ok':True,'result':store.apply(u,op)})
     except (ValueError,sqlite3.IntegrityError) as e:
      results.append({'id':op.get('id'),'ok':False,'error':str(e)});break
    return self.send({'results':results,'records':store.snapshot(u)})
   if path=='/api/users':
    if u['role']!='administrador':return self.send({'error':'Somente administrador.'},403)
    uid=store.create_user(body.get('name',''),body.get('password',''),body.get('role',''),u['id']);return self.send({'id':uid})
   if path=='/api/backup':
    if u['role']!='administrador':return self.send({'error':'Somente administrador.'},403)
    folder=ROOT/'backups';folder.mkdir(exist_ok=True);dest=folder/('clinica-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(2)+'.sqlite');store.backup(dest)
    return self.send({'message':'Backup verificado salvo na pasta backups da clínica. Proteja essa pasta com criptografia do disco.','file':dest.name})
   return self.send({'error':'Não encontrado.'},404)
  except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e:self.send({'error':str(e)},400)
  except Exception:self.send({'error':'Falha interna. Operação não confirmada; preserve a fila e tente novamente.'},500)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--criar-admin',action='store_true');parser.add_argument('--restaurar');parser.add_argument('--port',type=int,default=8889);args=parser.parse_args()
 if args.criar_admin:
  with store.connect() as c:exists=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
  if exists:raise SystemExit('Já há usuários. Novos usuários devem ser criados pelo administrador na interface.')
  name=input('Nome do administrador (sem espaços): ');pwd=getpass.getpass('Senha com pelo menos 12 caracteres: ')
  if pwd!=getpass.getpass('Repita a senha: '):raise SystemExit('As senhas não conferem.')
  store.create_user(name,pwd,'administrador');print('Administrador criado.');return
 if args.restaurar:
  src=Path(args.restaurar).resolve()
  if src==store.path.resolve():raise SystemExit('Selecione outro arquivo.')
  with sqlite3.connect(f'file:{src.as_posix()}?mode=ro',uri=True) as c:
   if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Arquivo inválido.')
   tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   if not {'users','records','operations','audit','sessions'}<=tables:raise SystemExit('Não é um backup desta clínica.')
   if input('Feche o servidor e todos os aparelhos. Digite RESTAURAR para confirmar: ')!='RESTAURAR':return
   backup=ROOT/'backups';backup.mkdir(exist_ok=True);store.backup(backup/('antes-restauracao-'+time.strftime('%Y%m%d%H%M%S')+'.sqlite'))
   with store.connect() as dest:c.backup(dest);dest.execute('DELETE FROM sessions')
  print('Restaurado. Limpe os cofres offline de todos os aparelhos antes de voltar a trabalhar.');return
 with store.connect() as c:exists=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
 if not exists:raise SystemExit('Execute CONFIGURAR.cmd para criar seu administrador primeiro.')
 if PUBLIC and not PUBLIC.startswith('https://'):raise SystemExit('A origem pública deve usar HTTPS.')
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
 print('Clínica - ambiente de desenvolvimento: http://127.0.0.1:'+str(server.server_port),flush=True)
 print('Não use pacientes reais. Mantenha esta janela aberta.',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:server.server_close()
if __name__=='__main__':main()

