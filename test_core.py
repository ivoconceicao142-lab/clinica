import unittest,tempfile,uuid,sqlite3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from core import Store,Connection,QUESTIONS

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'teste.sqlite');self.u={'id':'teste','role':'administrador'}
 def tearDown(self):self.tmp.cleanup()
 def op(self,k,d,r=None,b=0):return dict(id=str(uuid.uuid4()),record=r or str(uuid.uuid4()),kind=k,data=d,base=b)
 def add(self,k,d):
  o=self.op(k,d);self.s.apply(self.u,o);return o['record']
 def test_login(self):
  self.s.create_user('teste','SenhaFicticia123!','dentista');self.assertIsNone(self.s.login('teste','errada'));self.assertEqual(self.s.login('teste','SenhaFicticia123!')['role'],'dentista')
 def test_unique_version_idempotency(self):
  d=dict(nome='Pessoa fictícia',matricula='001',telefone='',responsavel='',ativo=True);o=self.op('pacientes',d)
  a=self.s.apply(self.u,o);self.assertEqual(a,self.s.apply(self.u,o))
  with self.assertRaises(ValueError):self.add('pacientes',d)
  d=dict(d,nome='Alterado');self.s.apply(self.u,self.op('pacientes',d,o['record'],1))
  with self.assertRaises(ValueError):self.s.apply(self.u,self.op('pacientes',d,o['record'],1))
  self.assertEqual(self.s.snapshot(self.u)['pacientes'][0]['data']['matricula'],'001')
 def test_permission(self):
  with self.assertRaises(ValueError):self.s.apply({'id':'r','role':'recepcao'},self.op('clinico',{}))
  self.assertNotIn('clinico',self.s.snapshot({'role':'recepcao'}))
 def test_agenda_and_clinical(self):
  p=self.add('pacientes',dict(nome='Teste',matricula='01',ativo=True));d=self.add('pessoas',dict(nome='Dentista teste',tipo='profissional',ativo=True))
  row=dict(paciente=p,profissional=d,sala='1',inicio='2026-11-01T09:00',fim='2026-11-01T10:00',status='agendado',motivo='')
  r=self.add('agenda',row)
  with self.assertRaises(ValueError):self.add('agenda',row)
  with self.assertRaises(ValueError):self.s.apply(self.u,self.op('agenda',dict(row,inicio='2026-11-01T08:00'),r,1))
  self.s.apply(self.u,self.op('agenda',dict(row,status='cancelado',motivo='Teste'),r,1));self.add('agenda',row)
  c=dict(paciente=p,tipo='anamnese',conteudo='Dados fictícios',referencia='');r=self.add('clinico',c)
  with self.assertRaises(ValueError):self.s.apply(self.u,self.op('clinico',c,r,1))
  self.add('clinico',dict(c,tipo='correcao',referencia=r))
 def test_financial(self):
  t=self.add('titulos',dict(descricao='Teste',tipo='receber',valor=10000,vencimento='2026-11-01'))
  d=dict(titulo=t,valor=6000,tipo='pagamento',referencia='',motivo='Teste',confirmado=True,data='2026-10-30',forma='Pix');r=self.add('pagamentos',d)
  with self.assertRaises(ValueError):self.add('pagamentos',d)
  self.add('pagamentos',dict(d,tipo='estorno',referencia=r))
  with self.assertRaises(ValueError):self.add('pagamentos',dict(d,tipo='estorno',referencia=r))
 def test_stock_concurrent(self):
  m=self.add('materiais',dict(nome='Material fictício',codigo='M01',unidade='un',minimo=2,ativo=True))
  d=dict(material=m,lote='L1',validade='2030-01-01',tipo='entrada',quantidade=10,motivo='Teste');self.add('movimentos',d)
  def withdraw(i):
   try:self.add('movimentos',dict(d,tipo='saida',quantidade=7));return True
   except ValueError:return False
  with ThreadPoolExecutor(2) as pool:self.assertEqual(sum(pool.map(withdraw,range(2))),1)
  self.assertEqual(len(self.s.snapshot(self.u)['movimentos']),2)
 def test_backup_restore(self):
  self.add('pacientes',dict(nome='Teste',matricula='001',ativo=True));p=Path(self.tmp.name)/'backup.sqlite';self.s.backup(p)
  restored=Store(Path(self.tmp.name)/'restaurado.sqlite')
  with sqlite3.connect(p,factory=Connection) as source,restored.connect() as dest:source.backup(dest)
  self.assertEqual(self.s.snapshot(self.u),restored.snapshot(self.u))
 def test_structured_anamnesis(self):
  p=self.add('pacientes',dict(nome='Teste',matricula='001',ativo=True));pro=self.add('pessoas',dict(nome='Dentista',tipo='profissional',ativo=True))
  d=dict(paciente=p,profissional=pro,tipo='anamnese',conteudo='',referencia='',data='2026-10-30',estado='rascunho',queixa='Teste',historia='',odontologico='',familiar='',respostas={k:dict(valor='Não informado',detalhe='') for k in QUESTIONS})
  r=self.add('clinico',d);d=dict(d,estado='finalizado');self.s.apply(self.u,self.op('clinico',d,r,1))
  with self.assertRaises(ValueError):self.s.apply(self.u,self.op('clinico',d,r,2))
  self.add('clinico',dict(d,referencia=r));self.assertEqual(len(self.s.snapshot(self.u)['clinico']),2)
 def test_cancel_confirmation_discount(self):
  d=dict(descricao='Teste',tipo='pagar',valor=10000,desconto=1000,acrescimo=500,vencimento='2026-10-30');t=self.add('titulos',d)
  pay=dict(titulo=t,valor=9500,tipo='pagamento',referencia='',motivo='Teste',confirmado=True,data='2026-10-30',forma='Pix')
  with self.assertRaises(ValueError):self.add('pagamentos',dict(pay,confirmado=False))
  r=self.add('pagamentos',pay)
  with self.assertRaises(ValueError):self.add('pagamentos',dict(pay,valor=1))
  cancel=dict(d,cancelado=True,motivo_cancelamento='Teste')
  with self.assertRaises(ValueError):self.s.apply(self.u,self.op('titulos',cancel,t,1))
  self.add('pagamentos',dict(pay,tipo='estorno',referencia=r));self.s.apply(self.u,self.op('titulos',cancel,t,1))
  with self.assertRaises(ValueError):self.add('pagamentos',pay)

if __name__=='__main__':unittest.main(verbosity=2)
