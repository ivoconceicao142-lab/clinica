import hashlib, io, json, tempfile, time, unittest, uuid
from pathlib import Path
from types import SimpleNamespace
import app
from core import Store, ACCESS, ROLES

class SecurityReview(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.old=app.store; self.s=app.store=Store(Path(self.tmp.name)/'db.sqlite'); self.tokens={}; self.users={}
  for role in ROLES:
   uid=self.s.create_user(role,'SomenteTeste123!',role); token=role+'-token'; self.tokens[role]=token; self.users[role]={'id':uid,'role':role}
   with self.s.connect() as c:c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,time.time()+3600))
 def tearDown(self):
  app.store=self.old; self.tmp.cleanup()
 def request(self,role,path,body=None,origin=True):
  h=app.Handler.__new__(app.Handler); h.server=SimpleNamespace(server_port=19029); h.path=path; h.headers={'Host':'127.0.0.1:19029','Cookie':'clinica_session='+self.tokens.get(role,'invalid')}; out=[]
  h.send=lambda obj,status=200,cookie=None:out.append((status,obj)); h.client_address=('127.0.0.1',1000)
  if body is None:h.do_GET()
  else:
   raw=json.dumps(body).encode(); h.rfile=io.BytesIO(raw); h.headers.update({'Content-Length':str(len(raw)),'Origin':'http://127.0.0.1:19029' if origin else 'https://invalid.test','X-Clinica-Request':'1'}); h.do_POST()
  return out[0]
 def test_read_matrix_real_sessions(self):
  for role in ROLES:
   with self.subTest(role=role):
    status,data=self.request(role,'/api/state'); self.assertEqual(status,200); self.assertEqual(set(data['records']),{k for k,v in ACCESS.items() if role in v})
    for endpoint in ('audit','users'):self.assertEqual(self.request(role,'/api/'+endpoint)[0],200 if role=='administrador' else 403)
  self.assertEqual(self.request(None,'/api/state')[0],401)
 def test_denied_writes_ignore_claimed_role(self):
  for role in ROLES:
   for kind,allowed in ACCESS.items():
    if role in allowed:continue
    op={'id':str(uuid.uuid4()),'record':str(uuid.uuid4()),'base':0,'kind':kind,'data':{}}
    status,data=self.request(role,'/api/sync',{'operations':[op],'role':'administrador','user':self.users['administrador']})
    self.assertEqual(status,200); self.assertFalse(data['results'][0]['ok']); self.assertIn('Sem permissão',data['results'][0]['error'])
  with self.s.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM records').fetchone()[0],0)
 def test_session_revocation_and_origin(self):
  self.assertEqual(self.request('administrador','/api/sync',{'operations':[]},False)[0],403)
  self.s.manage_user(self.users['administrador'],self.users['recepcao']['id'],'deactivate')
  self.assertEqual(self.request('recepcao','/api/state')[0],401); self.assertEqual(self.request('recepcao','/api/sync',{'operations':[]})[0],401)
  self.s.manage_user(self.users['administrador'],self.users['dentista']['id'],'password','OutraSenhaTeste123!')
  self.assertEqual(self.request('dentista','/api/state')[0],401)
if __name__=='__main__':unittest.main(verbosity=2)
