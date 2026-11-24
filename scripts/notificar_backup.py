"""Envia somente um sinal vazio apos o backup e sua integridade serem confirmados."""
import os
import re
import sys
import time
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def notify(url, opener=None, sleep=time.sleep):
    # Restringe destino e formato; nao aceita URL de /start ou /fail.
    if not isinstance(url, str) or not re.fullmatch(r'https://hc-ping\.com/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', url.strip()):
        return False
    url=url.strip()
    opener=opener or urllib.request.build_opener(NoRedirect())
    for attempt in range(3):
        try:
            request=urllib.request.Request(url, data=b'', method='POST')
            with opener.open(request, timeout=10) as response:
                if response.status == 200:
                    return True
        except Exception:
            # A excecao pode conter a URL secreta; nunca imprimi-la.
            pass
        if attempt < 2:
            sleep(5)
    return False

def main():
    if notify(os.environ.get('BACKUP_HEALTHCHECK_URL','')):
        print('Monitor externo recebeu a confirmacao do backup verificado.')
        return 0
    print('Nao foi possivel confirmar o backup no monitor externo. Confira o segredo e a conectividade. Esta falha nao desfaz o backup concluido na etapa anterior.')
    return 1

if __name__ == '__main__':
    sys.exit(main())
