"""Backup read-only; credentials and plaintext never printed or persisted."""
import base64
import datetime
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b'CLINICA-BACKUP-01\n'
ACCOUNT = 'fcsistema.backup@gmail.com'
SCOPE = 'https://www.googleapis.com/auth/drive.file'
API = 'https://www.googleapis.com/drive/v3/'

def key(password, salt):
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())

def encrypt(raw, password):
    salt, nonce = os.urandom(16), os.urandom(12)
    header = MAGIC + salt + nonce
    return header + AESGCM(key(password, salt)).encrypt(nonce, raw, header)

def decrypt(blob, password):
    if not blob.startswith(MAGIC):
        raise ValueError('format')
    offset = len(MAGIC)
    header = blob[:offset+28]
    return AESGCM(key(password, blob[offset:offset+16])).decrypt(
        blob[offset+16:offset+28], blob[offset+28:], header)

def database_env(dsn):
    p = urllib.parse.urlsplit(dsn)
    q = urllib.parse.parse_qs(p.query)
    if (p.scheme not in ('postgres', 'postgresql') or not p.hostname
            or not p.hostname.endswith('.neon.tech') or '-pooler' in p.hostname
            or not p.username or not p.password or not p.path.strip('/')
            or p.port not in (None, 5432)
            or q.get('sslmode', [''])[0] not in ('require', 'verify-ca', 'verify-full')):
        raise ValueError('connection')
    # Only the database credential is inherited by PostgreSQL subprocesses.
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'SYSTEMROOT') if k in os.environ}
    env.update(PGHOST=p.hostname, PGPORT='5432', PGUSER=urllib.parse.unquote(p.username),
               PGPASSWORD=urllib.parse.unquote(p.password), PGDATABASE=urllib.parse.unquote(p.path[1:]),
               PGSSLMODE=q['sslmode'][0], PGCONNECT_TIMEOUT='30', PGAPPNAME='clinica_backup',
               PGOPTIONS='-c default_transaction_read_only=on')
    if 'channel_binding' in q:
        env['PGCHANNELBINDING'] = q['channel_binding'][0]
    return env

def request(url, token=None, data=None, method=None, content_type=None):
    headers = {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if content_type:
        headers['Content-Type'] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=180) as response:
        return response.read(), response.headers

def json_request(url, token=None, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    raw, _ = request(url, token, data, content_type='application/json')
    return json.loads(raw)

def drive_token(auth):
    if auth['account'] != ACCOUNT or auth['scope'] != SCOPE:
        raise ValueError('account or scope')
    data = urllib.parse.urlencode(dict(grant_type='refresh_token',
        client_id=auth['client_id'], client_secret=auth['client_secret'],
        refresh_token=auth['refresh_token'])).encode()
    raw, _ = request('https://oauth2.googleapis.com/token', data=data,
                     content_type='application/x-www-form-urlencoded')
    token = json.loads(raw)['access_token']
    about = json_request(API + 'about?fields=user(emailAddress)', token)
    if about['user']['emailAddress'].lower() != ACCOUNT:
        raise ValueError('wrong Drive account')
    return token

def folder(token):
    query = "trashed = false and mimeType = 'application/vnd.google-apps.folder' and appProperties has { key='clinicaBackup' and value='v1' }"
    result = json_request(API + 'files?' + urllib.parse.urlencode(
        dict(q=query, fields='files(id),nextPageToken', pageSize=100)), token)
    files = result.get('files', [])
    if len(files) > 1 or result.get('nextPageToken'):
        raise ValueError('ambiguous folder')
    if files:
        return files[0]['id']
    return json_request(API + 'files?fields=id', token, dict(
        name='Clinica - Backups automaticos', mimeType='application/vnd.google-apps.folder',
        appProperties={'clinicaBackup': 'v1'}))['id']

def upload(token, parent, blob):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    metadata = dict(name='clinica-' + stamp + '.backup.aes', parents=[parent])
    _, headers = request('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&fields=id',
        token, json.dumps(metadata).encode(), content_type='application/json')
    location = headers['Location']
    parsed = urllib.parse.urlsplit(location)
    if parsed.scheme != 'https' or parsed.netloc != 'www.googleapis.com':
        raise ValueError('unexpected upload URL')
    raw, _ = request(location, token, blob, method='PUT', content_type='application/octet-stream')
    file_id = json.loads(raw)['id']
    downloaded, _ = request(API + 'files/' + urllib.parse.quote(file_id, safe='') + '?alt=media', token)
    if hashlib.sha256(downloaded).digest() != hashlib.sha256(blob).digest():
        raise ValueError('Drive integrity')

def main():
    stage = 'configuracao'
    try:
        stage = 'BACKUP_PASSWORD: ausente ou menor que 16 caracteres'
        password = os.environ.pop('BACKUP_PASSWORD')
        if len(password) < 16:
            raise ValueError('password length')
        stage = 'BACKUP_DATABASE_URL: ausente ou conexao direta invalida'
        env = database_env(os.environ.pop('BACKUP_DATABASE_URL').strip())
        stage = 'DRIVE_AUTH_ENCRYPTED: ausente ou formato invalido'
        encoded = ''.join(os.environ.pop('DRIVE_AUTH_ENCRYPTED').split())
        encrypted_auth = base64.b64decode(encoded, validate=True)
        if not encrypted_auth.startswith(MAGIC):
            raise ValueError('authorization format')
        stage = 'DRIVE_AUTH_PASSWORD: ausente, senha incorreta ou autorizacao danificada'
        auth = json.loads(decrypt(encrypted_auth, os.environ.pop('DRIVE_AUTH_PASSWORD')))
        stage = 'autorizacao do Drive'
        token = drive_token(auth)
        stage = 'exportacao PostgreSQL'
        result = subprocess.run(['pg_dump', '--format=custom', '--no-owner', '--no-privileges',
            '--no-password', '--lock-wait-timeout=15000'], env=env, capture_output=True, timeout=900)
        if result.returncode or not result.stdout.startswith(b'PGDMP'):
            raise ValueError('dump')
        raw = result.stdout
        stage = 'conferencia do arquivo'
        result = subprocess.run(['pg_restore', '--list'], input=raw, capture_output=True, timeout=120)
        if result.returncode:
            raise ValueError('archive')
        blob = encrypt(raw, password)
        if decrypt(blob, password) != raw:
            raise ValueError('encryption')
        stage = 'envio e conferencia no Drive'
        upload(token, folder(token), blob)
        print('SUCESSO: backup criptografado enviado e baixado novamente com integridade conferida.')
        print('Nenhum registro do banco foi alterado. Restauracao completa desta copia nao executada.')
        return 0
    except Exception:
        # No traceback, response body, database stderr or credentials in public logs.
        print('FALHA na etapa: ' + stage + '. Nao considere esta execucao um backup validado.')
        return 1

if __name__ == '__main__':
    sys.exit(main())
