import unittest,tempfile,threading,json,http.client
from pathlib import Path
import app
from core import Store
class SetupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();app.store=Store(Path(self.tmp.name)/'t.sqlite');self.s=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);self.t=threading.Thread(target=self.s.serve_forever,daemon=True);self.t.start()
 def tearDown(self):self.s.shutdown();self.s.server_close();self.tmp.cleanup()
 def req(self,path,body=None,origin=True):
  c=http.client.HTTPConnection('127.0.0.1',self.s.server_port);headers={'Host':f'127.0.0.1:{self.s.server_port}'}
  if body is not None:
   headers.update({'Content-Type':'application/json','X-Clinica-Request':'1'})
   if origin:headers['Origin']='http://'+headers['Host']
  c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers);r=c.getresponse();status=r.status;data=json.loads(r.read());c.close();return status,data
 def test_setup_login_and_no_recreation(self):
  self.assertTrue(self.req('/api/setup')[1]['needed']);b=dict(name='avaliador',password='SenhaFicticia123!',confirm='SenhaFicticia123!',examples=True)
  self.assertEqual(self.req('/api/setup',b)[0],200);self.assertFalse(self.req('/api/setup')[1]['needed']);self.assertEqual(self.req('/api/setup',b)[0],409)
  self.assertEqual(self.req('/api/login',dict(name='avaliador',password=b['password']))[0],200)
  u=app.store.login('avaliador',b['password']);self.assertEqual(len(app.store.snapshot(u)['pacientes']),2)
 def test_validation_and_origin(self):
  b=dict(name='admin',password='curta',confirm='curta');self.assertEqual(self.req('/api/setup',b)[0],400);self.assertEqual(self.req('/api/setup',b,False)[0],403);self.assertTrue(self.req('/api/setup')[1]['needed'])
 def test_empty_setup(self):
  b=dict(name='admin',password='SenhaFicticia123!',confirm='SenhaFicticia123!',examples=False);self.assertEqual(self.req('/api/setup',b)[0],200);self.assertEqual(app.store.snapshot(app.store.login('admin',b['password']))['pacientes'],[])
if __name__=='__main__':unittest.main()
