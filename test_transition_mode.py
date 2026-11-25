import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
import app
from core import Store
class ModeTests(unittest.TestCase):
 def test_setup_reads_live_identity_and_mode(self):
  old=(app.store,app.CLOUD,app.PUBLIC,app.INSTALLATION)
  with tempfile.TemporaryDirectory() as tmp:
   try:
    app.store=Store(Path(tmp)/'db');app.CLOUD=True;app.PUBLIC='https://example.test';app.INSTALLATION='cached-old'
    with app.store.connect() as c:c.execute('CREATE TABLE clinic_metadata(key TEXT PRIMARY KEY,value TEXT)');c.execute("INSERT INTO clinic_metadata VALUES('installation','before')")
    def request():
     h=app.Handler.__new__(app.Handler);h.path='/api/setup';h.headers={'Host':'example.test'};out=[];h.send=lambda obj,status=200,cookie=None:out.append((status,obj));h.do_GET();return out[0]
    status,data=request();self.assertEqual(status,200);self.assertEqual(data['installation'],'before');self.assertFalse(data['productionReady'])
    with app.store.connect() as c:c.execute("UPDATE clinic_metadata SET value='after' WHERE key='installation'");c.execute("INSERT INTO clinic_metadata VALUES('production_ready','1')")
    status,data=request();self.assertEqual(data['installation'],'after');self.assertTrue(data['productionReady'])
   finally:app.store,app.CLOUD,app.PUBLIC,app.INSTALLATION=old
if __name__=='__main__':unittest.main()
