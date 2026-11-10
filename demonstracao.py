from pathlib import Path
import threading,webbrowser,sys
import app
from core import Store
from seed_demo import seed
folder=Path(__file__).resolve().parent/'ensaio';folder.mkdir(exist_ok=True)
app.store=Store(folder/'ficticio.sqlite')
with app.store.connect() as c: exists=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
if not exists:app.store.create_user('teste','SomenteTeste123!','administrador')
seed(app.store)
port=18889
try: server=app.ThreadingHTTPServer(('127.0.0.1',port),app.Handler)
except OSError:
 print('A porta 18889 esta ocupada. Feche outra demonstracao e tente novamente.');sys.exit(1)
url='http://127.0.0.1:'+str(port)+'/'
print('CLINICA - DEMONSTRACAO LOCAL. Use somente dados ficticios.')
print('Usuario: teste | Senha: SomenteTeste123!')
print('Endereco: '+url+' | Mantenha esta janela aberta.')
print('Para encerrar, pressione Ctrl+C nesta janela.')
if '--sem-navegador' not in sys.argv:threading.Timer(1,lambda:webbrowser.open(url)).start()
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close()
