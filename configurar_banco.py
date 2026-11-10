"""Configuração administrativa local do banco online; nenhuma senha é impressa."""
import getpass
from urllib.parse import urlparse,parse_qs
from postgres_store import PostgresStore

def main():
 print('Configure apenas um banco NOVO e exclusivo da clinica, antes da publicacao.')
 print('Nao usa nem migra o banco local. Nao coloque credenciais no GitHub ou no chat.')
 dsn=getpass.getpass('Conexao PostgreSQL fornecida pelo provedor (oculta): ')
 parsed=urlparse(dsn)
 if parsed.scheme not in ('postgresql','postgres'):raise SystemExit('Use uma conexao PostgreSQL.')
 if parse_qs(parsed.query).get('sslmode',[''])[0] not in ('require','verify-ca','verify-full'):raise SystemExit('A conexao precisa exigir TLS: sslmode=require ou verificacao mais forte.')
 name=input('Nome do administrador: ')
 pwd=getpass.getpass('Senha do administrador (minimo 12 caracteres): ')
 if pwd!=getpass.getpass('Repita a senha: '):raise SystemExit('Senhas diferentes. Nada alterado.')
 try:
  db=PostgresStore(dsn);db.bootstrap(name,pwd)
 except ValueError as exc:raise SystemExit(str(exc))
 except Exception:raise SystemExit('Falha na configuracao. Confira conexao, permissao e disponibilidade do banco; nao compartilhe a credencial.')
 print('Administrador criado no banco online. Nenhum dado local foi migrado.')
if __name__=='__main__':main()
