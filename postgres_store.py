"""PostgreSQL persistente: reutiliza as regras do Store local."""
import secrets, sqlite3, time, hashlib
from core import Store

class Row(dict):
 def __getitem__(self,key):
  return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)

def row_factory(cursor):
 names=[c.name for c in cursor.description] if cursor.description else []
 return lambda values:Row(zip(names,values))

class PGConnection:
 def __init__(self,dsn):
  import psycopg
  self.db=psycopg.connect(dsn,row_factory=row_factory,connect_timeout=8,options='-c statement_timeout=15000 -c lock_timeout=10000')
 def __enter__(self):
  try:
   # Trava transacional compartilhada por instâncias: preserva validações
   # de saldo, agenda, matrícula e idempotência (duas pessoas por clínica).
   self.db.execute('SELECT pg_advisory_xact_lock(714231906)')
   return self
  except Exception:self.db.close();raise
 def __exit__(self,*args):return self.db.__exit__(*args)
 def execute(self,sql,args=()):
  import psycopg
  if sql=='BEGIN IMMEDIATE':return self.db.execute('SELECT 1')
  if sql.startswith('INSERT OR REPLACE INTO records'):
   sql='INSERT INTO records VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=EXCLUDED.kind,version=EXCLUDED.version,data=EXCLUDED.data,author=EXCLUDED.author,updated=EXCLUDED.updated'
  try:return self.db.execute(sql.replace('s.user=', 's."user"=').replace('?', '%s'),args)
  except psycopg.IntegrityError as exc:raise sqlite3.IntegrityError('Cadastro duplicado ou referência inválida.') from exc

class PostgresStore(Store):
 def __init__(self,dsn):
  from urllib.parse import urlparse,parse_qs
  parsed=urlparse(dsn)
  if parsed.scheme not in ('postgres','postgresql') or parse_qs(parsed.query).get('sslmode',[''])[0] not in ('require','verify-ca','verify-full'):raise ValueError('A conexão PostgreSQL deve exigir TLS.')
  self.dsn=dsn
  with self.connect() as c:
   for sql in [
    'CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT UNIQUE,role TEXT,salt TEXT,hash TEXT,active INTEGER)',
    'CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,kind TEXT,version INTEGER,data TEXT,author TEXT,updated TEXT)',
    'CREATE TABLE IF NOT EXISTS audit(seq BIGSERIAL PRIMARY KEY,at TEXT,actor TEXT,action TEXT,record_id TEXT,before TEXT,after TEXT)',
    'CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,actor TEXT,fingerprint TEXT,result TEXT)',
    'CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,"user" TEXT,expires DOUBLE PRECISION)',
    'CREATE TABLE IF NOT EXISTS clinic_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS login_attempts(key TEXT PRIMARY KEY,started DOUBLE PRECISION,hits INTEGER)',
    'CREATE INDEX IF NOT EXISTS records_kind_idx ON records(kind)']:
    c.execute(sql)
   c.execute("INSERT INTO clinic_metadata VALUES('installation',?) ON CONFLICT(key) DO NOTHING",(secrets.token_hex(16),))
   self.installation=c.execute("SELECT value FROM clinic_metadata WHERE key='installation'").fetchone()[0]
 def connect(self):return PGConnection(self.dsn)
 def backup(self,dest):raise ValueError('No ambiente online, use o backup PostgreSQL do provedor. Nenhum backup local foi criado.')
 def allow_login(self,name):
  key=hashlib.sha256(name.strip().lower().encode()).hexdigest();now=time.time()
  with self.connect() as c:
   c.execute('DELETE FROM login_attempts WHERE started<?',(now-900,))
   row=c.execute('SELECT hits FROM login_attempts WHERE key=?',(key,)).fetchone()
   if row and row['hits']>=10:return False
   c.execute('INSERT INTO login_attempts VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET hits=login_attempts.hits+1',(key,now))
   return True
 def bootstrap(self,name,password):
  # Mantém a trava entre a verificação e a criação sem outra conexão.
  from core import ROLES,password_ok,digest,now
  import re,uuid,json
  name=name.strip().lower()
  if not re.fullmatch(r'[a-z0-9._-]{3,40}',name) or not password_ok(password):raise ValueError('Usuário inválido ou senha inferior a 12 caracteres.')
  with self.connect() as c:
   if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]:raise ValueError('Já existe usuário; cadastro inicial bloqueado.')
   uid=str(uuid.uuid4());salt=secrets.token_hex(16)
   c.execute('INSERT INTO users VALUES(?,?,?,?,?,1)',(uid,name,'administrador',salt,digest(password,salt)))
   c.execute('INSERT INTO audit(at,actor,action,record_id,after) VALUES(?,?,?,?,?)',(now(),'configuracao','criar_usuario',uid,json.dumps({'nome':name,'perfil':'administrador'})))
   return uid
