import unittest,os,subprocess,sys
from unittest.mock import Mock
from postgres_store import Row,row_factory,PGConnection
class CloudTests(unittest.TestCase):
 def test_cloud_import_never_creates_directory(self):
  code="from pathlib import Path; from unittest.mock import patch; import os; os.environ['VERCEL']='1'; os.environ.pop('DATABASE_URL',None);\nwith patch.object(Path,'mkdir',side_effect=AssertionError('tentou gravar')):\n import app\n assert app.store is None\n assert app.handler is app.Handler\n"
  subprocess.run([sys.executable,'-c',code],check=True)
 def test_diagnostics_never_emit_exception_secrets(self):
  code="""
import os,io,json,contextlib
os.environ['VERCEL']='1'
import app
cases=[('password authentication failed','authentication_failed'),('timeout expired','connection_timeout'),('unsupported startup parameter: options','startup_parameter_unsupported'),('unknown error','unclassified')]
for message,expected in cases:
 out=io.StringIO()
 with contextlib.redirect_stderr(out):app.log_failure(RuntimeError(message+' SECRET_SENTINEL postgresql://user:password@private.example/db'))
 result=out.getvalue()
 assert 'SECRET_SENTINEL' not in result and 'private.example' not in result and 'password@' not in result
 assert json.loads(result)['category']==expected
"""
  subprocess.run([sys.executable,'-c',code],check=True)
 def test_rows_support_existing_access(self):
  r=Row([('name','ana'),('active',1)]);self.assertEqual(r[0],'ana');self.assertEqual(r['active'],1)
  self.assertEqual(row_factory(Mock(description=None))([]),{})
 def test_statement_translation(self):
  # Driver mínimo simulado: verifica SQL sem alegar integração PostgreSQL.
  import types
  from unittest.mock import patch
  conn=PGConnection.__new__(PGConnection);conn.db=Mock()
  driver=types.SimpleNamespace(IntegrityError=type('IntegrityError',(Exception,),{}))
  with patch.dict(sys.modules,{'psycopg':driver}):
   conn.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?,?,?)',(1,2,3,4,5,6))
   sql,args=conn.db.execute.call_args.args;self.assertIn('ON CONFLICT(id)',sql);self.assertNotIn('?',sql);self.assertEqual(len(args),6)
   conn.execute('SELECT s.user FROM sessions s JOIN users u ON s.user=u.id')
   self.assertIn('s."user"=u.id',conn.db.execute.call_args.args[0])
if __name__=='__main__':unittest.main()
