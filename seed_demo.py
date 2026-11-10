"""Dados exclusivamente fictícios, apenas no ensaio local."""
import uuid
from datetime import date,timedelta
from core import QUESTIONS

def seed(store):
 u=store.login('teste','SomenteTeste123!')
 if not u or store.snapshot(u)['pacientes']:return
 def add(k,d):
  rid=str(uuid.uuid4());store.apply(u,dict(id=str(uuid.uuid4()),record=rid,kind=k,data=d,base=0));return rid
 day=date.today();p=add('pacientes',dict(nome='Ana Exemplo — fictícia',matricula='DEMO01',telefone='',responsavel='',ativo=True))
 p2=add('pacientes',dict(nome='Bruno Exemplo — fictício',matricula='DEMO02',telefone='',responsavel='',ativo=True))
 pro=add('pessoas',dict(nome='Dentista Demonstração',tipo='profissional',registro='FICTÍCIO',ativo=True))
 for i,pat in enumerate([p,p2]):add('agenda',dict(paciente=pat,profissional=pro,sala='Sala 1',inicio=f'{day}T{9+i:02}:00',fim=f'{day}T{9+i:02}:40',status='confirmado',motivo='Ensaio'))
 add('clinico',dict(paciente=p,profissional=pro,tipo='anamnese',conteudo='Registro de demonstração, sem paciente real.',referencia='',data=str(day),estado='rascunho',queixa='Avaliação fictícia',historia='',odontologico='',familiar='',respostas={k:dict(valor='Não informado',detalhe='') for k in QUESTIONS}))
 t=add('titulos',dict(descricao='Avaliação fictícia',tipo='receber',valor=20000,desconto=0,acrescimo=0,vinculo=p,servico='Demonstração',vencimento=str(day)))
 add('pagamentos',dict(titulo=t,valor=5000,tipo='pagamento',referencia='',motivo='Recebimento fictício',confirmado=True,data=str(day),forma='Pix'))
 add('titulos',dict(descricao='Material de demonstração',tipo='pagar',valor=8500,vencimento=str(day+timedelta(days=3))))
 m=add('materiais',dict(nome='Luvas — exemplo',codigo='DEMO-LV',unidade='caixa',minimo=5,ativo=True))
 add('movimentos',dict(material=m,lote='FICTICIO01',validade=str(day+timedelta(days=20)),tipo='entrada',quantidade=3,motivo='Entrada de ensaio'))
