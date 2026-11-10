import io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
import app
from core import Store
class UserTests(unittest.TestCase):
 def test_user_api(self):
  with tempfile.TemporaryDirectory() as tmp:
   old=app.store;app.store=Store(Path(tmp)/'db.sqlite')
   try:
    def post(role,body):
     h=app.Handler.__new__(app.Handler);raw=json.dumps(body).encode();h.headers={'Host':'127.0.0.1:19029','Origin':'http://127.0.0.1:19029','X-Clinica-Request':'1','Content-Length':str(len(raw))};h.server=SimpleNamespace(server_port=19029);h.path='/api/users';h.rfile=io.BytesIO(raw);h.session=lambda:dict(id='admin',role=role);result=[];h.send=lambda obj,status=200,cookie=None:result.append((status,obj));h.do_POST();return result[0]
    b=dict(name='recepcao01',password='SenhaSomenteTeste123!',role='recepcao')
    self.assertEqual(post('recepcao',b)[0],403)
    self.assertEqual(post('administrador',dict(b,password='curta'))[0],400)
    self.assertEqual(post('administrador',b)[0],200)
    self.assertIsNotNone(app.store.login(b['name'],b['password']))
    self.assertEqual(post('administrador',b)[0],400)
   finally:app.store=old
if __name__=='__main__':unittest.main()
