import contextlib, io, unittest
from unittest.mock import MagicMock as Mock, patch
from scripts import notificar_backup as n
URL='https://hc-ping.com/00000000-0000-0000-0000-000000000000'
class Tests(unittest.TestCase):
 def test_success_empty_body(self):
  opener=Mock();opener.open.return_value.__enter__.return_value.status=200
  self.assertTrue(n.notify(URL,opener));request=opener.open.call_args.args[0]
  self.assertEqual(request.data,b'');self.assertEqual(request.method,'POST');self.assertEqual(opener.open.call_count,1)
 def test_invalid_no_network(self):
  opener=Mock()
  for url in ['',URL+'/start',URL+'/fail',URL+'?x=1',URL.replace('https:','http:'),URL.replace('hc-ping.com','other.test')]:self.assertFalse(n.notify(url,opener))
  opener.open.assert_not_called()
 def test_retries(self):
  opener=Mock();opener.open.side_effect=OSError('secret');sleep=Mock()
  self.assertFalse(n.notify(URL,opener,sleep));self.assertEqual(opener.open.call_count,3);self.assertEqual(sleep.call_count,2)
 def test_response_and_redirect(self):
  opener=Mock();opener.open.return_value.__enter__.return_value.status=500
  self.assertFalse(n.notify(URL,opener,lambda _:None))
  self.assertIsNone(n.NoRedirect().redirect_request(None,None,302,'',{},'https://other.test'))
 def test_logs_no_secret_and_exit_failure(self):
  output=io.StringIO()
  with patch.dict(n.os.environ,{'BACKUP_HEALTHCHECK_URL':URL}),patch.object(n,'notify',return_value=False),contextlib.redirect_stdout(output):self.assertEqual(n.main(),1)
  self.assertNotIn(URL,output.getvalue())
if __name__=='__main__':unittest.main(verbosity=2)

