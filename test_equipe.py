import unittest,uuid
from test_core import Tests
class EquipeTests(Tests):
 def test_funcionario(self):
  rid=str(uuid.uuid4());data=dict(nome='Pessoa Fictícia',matricula='0001',cargo='Recepção',registro='',ativo=True)
  def op(record,base,d):return dict(id=str(uuid.uuid4()),record=record,kind='funcionarios',base=base,data=d)
  self.s.apply(self.u,op(rid,0,data));self.assertEqual(self.s.snapshot(self.u)['funcionarios'][0]['data']['matricula'],'0001')
  with self.assertRaises(ValueError):self.s.apply(self.u,op(str(uuid.uuid4()),0,data))
  with self.assertRaises(ValueError):self.s.apply(dict(id='outro',role='recepcao'),op(str(uuid.uuid4()),0,data))
  self.assertNotIn('funcionarios',self.s.snapshot(dict(id='outro',role='recepcao')))
  self.s.apply(self.u,op(rid,1,dict(data,ativo=False)))
  self.assertFalse(self.s.snapshot(self.u)['funcionarios'][0]['data']['ativo'])
if __name__=='__main__':unittest.main()
