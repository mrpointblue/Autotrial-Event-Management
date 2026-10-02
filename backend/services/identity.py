"""Central identity catalog; event data lives in isolated organizer stores."""
import hashlib,hmac,secrets,sqlite3,time,uuid
from contextlib import contextmanager
from backend.database import DATA_DIR

ROLES={'admin':'Administrator','organizer_admin':'Veranstalter-Administrator','editor':'Bearbeiter','reader':'Nur Lesen'}
@contextmanager
def catalog():
    with sqlite3.connect(DATA_DIR/'identity.sqlite3',timeout=15) as db:
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        yield db

def initialize_identity():
    with catalog() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS organizers(id TEXT PRIMARY KEY,name TEXT NOT NULL,address TEXT NOT NULL DEFAULT '',contact TEXT NOT NULL DEFAULT '',is_default INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,organizer_id TEXT REFERENCES organizers(id),active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),organizer_id TEXT NOT NULL REFERENCES organizers(id),expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(client TEXT PRIMARY KEY,count INTEGER NOT NULL,until REAL NOT NULL);
        ''')
        if not db.execute('SELECT 1 FROM organizers').fetchone():
            db.execute('INSERT INTO organizers(id,name,is_default) VALUES (?,?,1)',(str(uuid.uuid4()),'Standard-Veranstalter'))

def has_users():
    with catalog() as db:return bool(db.execute('SELECT 1 FROM users').fetchone())
def organizers():
    with catalog() as db:return [dict(r) for r in db.execute('SELECT * FROM organizers ORDER BY name')]
def hash_password(password):
    salt=secrets.token_bytes(16)
    digest=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1)
    return salt.hex()+':'+digest.hex()
def check_password(password,stored):
    salt,digest=stored.split(':')
    return hmac.compare_digest(hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex(),digest)
def authenticated(token):
    if not token:return None,None
    with catalog() as db:
        row=db.execute('SELECT u.*,s.organizer_id AS selected FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if not row:return None,None
        user=dict(row)
        user.pop('password',None)
        if user['role']!='admin' and user['selected']!=user['organizer_id']:return None,None
        tenant=db.execute('SELECT * FROM organizers WHERE id=?',(user['selected'],)).fetchone()
        return user,dict(tenant) if tenant else None
