import unittest, tempfile, json
from pathlib import Path
from core import Store
class AuthorTests(unittest.TestCase):
 def test_existing_records_and_inactive_author(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(Path(tmp)/'test.db')
   uid=store.create_user('autor_teste','SenhaFicticia123!','dentista')
   with store.connect() as c:
    c.execute('UPDATE users SET active=0 WHERE id=?',(uid,))
    for rid,author in [('old',uid),('unknown','missing')]:
     c.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(rid,'clinico',3,json.dumps({'conteudo':'Ficticio'}),author,'2026-11-11'))
   rows={r['id']:r for r in store.snapshot({'role':'dentista'})['clinico']}
   self.assertEqual(rows['old']['author_name'],'autor_teste')
   self.assertEqual(rows['old']['author'],uid)
   self.assertEqual(rows['old']['version'],3)
   self.assertIsNone(rows['unknown']['author_name'])
   self.assertNotIn('hash',rows['old'])
   self.assertNotIn('clinico',store.snapshot({'role':'recepcao'}))
if __name__=='__main__':unittest.main()
