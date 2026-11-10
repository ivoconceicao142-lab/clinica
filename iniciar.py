import app, threading, webbrowser, sys, urllib.request, traceback
from pathlib import Path

def main():
 print('CLINICA - INICIALIZACAO COM DIAGNOSTICO',flush=True)
 print('Pasta: '+str(Path(__file__).resolve().parent),flush=True)
 try:
  port_file=app.DATA/'porta-local.txt'
  port=int(port_file.read_text()) if port_file.exists() else 0
  server=app.ThreadingHTTPServer(('127.0.0.1',port),app.Handler)
 except OSError as exc:
  print('Nao foi possivel iniciar o servidor: '+str(exc),flush=True)
  print('Feche a janela anterior desta clinica e tente novamente.');return
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 url='http://127.0.0.1:'+str(server.server_port)+'/'
 try:
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  for route in ('','api/setup'):
   with opener.open(url+route,timeout=8) as response:
    if response.status!=200:raise RuntimeError('Resposta HTTP '+str(response.status))
    response.read()
  port_file.write_text(str(server.server_port),encoding='ascii')
  print('TESTE LOCAL OK: pagina e cadastro responderam.',flush=True)
  print('Abra '+url+' e mantenha esta janela aberta.',flush=True)
  if '--sem-navegador' not in sys.argv:webbrowser.open(url)
  while thread.is_alive():thread.join(1)
 except KeyboardInterrupt:print('Sistema encerrado.')
 except Exception as exc:
  print('TESTE LOCAL FALHOU: '+str(exc),flush=True)
  print('Envie uma foto desta mensagem. Nao altere firewall nem apague dados.',flush=True)
  Path('erro-inicializacao.log').write_text(traceback.format_exc(),encoding='utf-8')
 finally:server.shutdown();server.server_close()
if __name__=='__main__':
 try:main()
 except Exception:
  traceback.print_exc()

