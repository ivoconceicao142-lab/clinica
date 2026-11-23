import io,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from core import Store
import app

class AccessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'test.sqlite')
  self.a=self.s.create_user('admin','SenhaFicticia123!','administrador')
  self.u=self.s.create_user('recepcao','SenhaFicticia123!','recepcao');self.actor={'id':self.a,'role':'administrador'}
  with self.s.connect() as c:
   for uid in (self.a,self.u):c.execute('INSERT INTO sessions VALUES(?,?,?)',(uid,uid,time.time()+3600))
 def tearDown(self):self.tmp.cleanup()
 def test_deactivate_reactivate_preserves_user(self):
  self.s.manage_user(self.actor,self.u,'deactivate');self.assertIsNone(self.s.login('recepcao','SenhaFicticia123!'))
  with self.s.connect() as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM sessions WHERE "user"=?',(self.u,)).fetchone()[0],0)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM users').fetchone()[0],2)
  self.s.manage_user(self.actor,self.u,'activate');self.assertIsNotNone(self.s.login('recepcao','SenhaFicticia123!'))
 def test_password_and_private_audit(self):
  pwd='NovaSenhaFicticia456!';self.s.manage_user(self.actor,self.u,'password',pwd)
  self.assertIsNone(self.s.login('recepcao','SenhaFicticia123!'));self.assertIsNotNone(self.s.login('recepcao',pwd))
  with self.s.connect() as c:
   audit=str([dict(r) for r in c.execute('SELECT * FROM audit')]);self.assertNotIn(pwd,audit);self.assertNotIn('salt',audit);self.assertNotIn('hash',audit)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM sessions WHERE "user"=?',(self.u,)).fetchone()[0],0)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM sessions WHERE "user"=?',(self.a,)).fetchone()[0],1)
 def test_permissions_and_invalid_input(self):
  for actor,target,action,pwd in [({'id':self.u,'role':'administrador'},self.a,'password','SenhaFicticia123!'),(self.actor,self.a,'deactivate',None),(self.actor,self.u,'password','curta'),(self.actor,'missing','activate',None),(self.actor,self.u,'unknown',None)]:
   with self.assertRaises(ValueError):self.s.manage_user(actor,target,action,pwd)
  self.assertIsNotNone(self.s.login('admin','SenhaFicticia123!'));self.assertIsNotNone(self.s.login('recepcao','SenhaFicticia123!'))
 def test_inactive_admin_cannot_mutate(self):
  with self.s.connect() as c:c.execute('UPDATE users SET active=0 WHERE id=?',(self.a,))
  with self.assertRaises(ValueError):self.s.manage_user(self.actor,self.u,'deactivate')
 def test_api(self):
  old=app.store;app.store=self.s
  try:
   def post(user,body):
    h=app.Handler.__new__(app.Handler);raw=json.dumps(body).encode();h.headers={'Host':'127.0.0.1:19029','Origin':'http://127.0.0.1:19029','X-Clinica-Request':'1','Content-Length':str(len(raw))};h.server=SimpleNamespace(server_port=19029);h.path='/api/users/manage';h.rfile=io.BytesIO(raw);h.session=lambda:user;out=[];h.send=lambda obj,status=200,cookie=None:out.append(status);h.do_POST();return out[0]
   b={'id':self.u,'action':'deactivate'}
   self.assertEqual(post(None,b),401);self.assertEqual(post({'id':self.u,'role':'recepcao'},b),403);self.assertEqual(post(self.actor,b),200)
  finally:app.store=old
