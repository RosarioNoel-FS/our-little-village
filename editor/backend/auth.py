import hashlib, hmac, json, re, secrets, sqlite3, time
from contextlib import contextmanager
from pathlib import Path

class Denied(Exception): pass
class Limited(Denied): pass

def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def password_hash(password, salt=None):
    if not isinstance(password,str) or not 14<=len(password)<=128: raise Denied('Use a passphrase between 14 and 128 characters.')
    salt=salt or secrets.token_hex(16)
    result=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=32768,r=8,p=1,maxmem=64*1024*1024).hex()
    return salt+':'+result

def verify_password(password, stored):
    try:
        salt,_=stored.split(':');actual=password_hash(password,salt)
        return hmac.compare_digest(actual,stored)
    except (ValueError,TypeError,Denied): return False

class Auth:
    def __init__(self,state):
        self.path=Path(state)/'staff.sqlite3';self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.path.parent.chmod(0o700)
        key=self.path.parent/'session.key'
        if not key.exists():
            try:
                with key.open('xb') as f:f.write(secrets.token_bytes(32))
                key.chmod(0o600)
            except FileExistsError:pass
        self.key=key.read_bytes()
        with self.db() as db:
            db.executescript('''
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS invites(hash TEXT PRIMARY KEY,email TEXT NOT NULL,name TEXT NOT NULL,expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires REAL NOT NULL,touched REAL NOT NULL);
CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY,count INTEGER NOT NULL,start REAL NOT NULL);
CREATE TABLE IF NOT EXISTS drafts(user_id TEXT PRIMARY KEY,data TEXT NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at REAL NOT NULL,user_id TEXT,action TEXT NOT NULL,detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,request_id TEXT NOT NULL,request_hash TEXT NOT NULL,data TEXT NOT NULL,UNIQUE(user_id,request_id));
''')
        self.path.chmod(0o600)
        self.dummy=password_hash('dummy authentication comparison passphrase')
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=20);db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON');yield db;db.commit()
        except Exception:db.rollback();raise
        finally:db.close()
    def audit(self,user,action,detail=''):
        with self.db() as db:db.execute('INSERT INTO audit(at,user_id,action,detail) VALUES(?,?,?,?)',(time.time(),user,action,detail[:500]))
    def rate(self,key,limit=6,seconds=900):
        key=digest(key);now=time.time()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM attempts WHERE key=?',(key,)).fetchone()
            count=row['count']+1 if row and now-row['start']<seconds else 1
            start=row['start'] if row and now-row['start']<seconds else now
            db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?)',(key,count,start))
        if count>limit:raise Limited('Too many attempts. Please try again in 15 minutes.')
    def invite(self,email,name):
        email=email.strip().lower()
        if not re.fullmatch(r'[^\s@]{1,100}@[^\s@]{1,150}',email) or not 1<=len(name.strip())<=80:raise Denied('Enter a valid email and staff name.')
        token=secrets.token_urlsafe(32)
        with self.db() as db:
            if db.execute('SELECT 1 FROM users WHERE email=? AND active=1',(email,)).fetchone():raise Denied('This staff account already exists. Revoke it before issuing a reset invitation.')
            db.execute('DELETE FROM invites WHERE email=?',(email,))
            db.execute('INSERT INTO invites VALUES(?,?,?,?,0)',(digest(token),email,name.strip(),time.time()+86400))
        self.audit(None,'invite-created',email);return token
    def enroll(self,token,password,ip):
        self.rate('enroll:'+ip,10)
        if not isinstance(token,str) or len(token)>100:raise Denied('This invitation is invalid or expired.')
        hashed=password_hash(password)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            invite=db.execute('SELECT * FROM invites WHERE hash=?',(digest(token),)).fetchone()
            if not invite or invite['used'] or invite['expires']<time.time():raise Denied('This invitation is invalid or expired.')
            user_id=secrets.token_hex(16)
            old=db.execute('SELECT id FROM users WHERE email=?',(invite['email'],)).fetchone()
            if old:
                user_id=old['id'];db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
                db.execute('UPDATE users SET name=?,password=?,active=1 WHERE id=?',(invite['name'],hashed,user_id))
            else:db.execute('INSERT INTO users VALUES(?,?,?,?,1)',(user_id,invite['email'],invite['name'],hashed))
            db.execute('UPDATE invites SET used=1 WHERE hash=?',(digest(token),))
        self.audit(user_id,'enrolled');return self.new_session(user_id)
    def login(self,email,password,ip):
        if not isinstance(email,str) or not isinstance(password,str):raise Denied('Email or passphrase was not recognized.')
        email=email.strip().lower();self.rate('login-ip:'+ip,30);self.rate('login:'+email+':'+ip,6)
        with self.db() as db:row=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        valid=verify_password(password,row['password'] if row else self.dummy)
        if not row or not row['active'] or not valid:
            self.audit(None,'login-failed',digest(email));raise Denied('Email or passphrase was not recognized.')
        self.audit(row['id'],'login');return self.new_session(row['id'])
    def new_session(self,user_id):
        token=secrets.token_urlsafe(32);now=time.time()
        with self.db() as db:db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),user_id,now+8*3600,now))
        return token
    def session(self,token):
        if not token or len(token)>100:return None
        now=time.time()
        with self.db() as db:
            row=db.execute('SELECT u.id,u.name,u.email,s.expires,s.touched FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.hash=? AND u.active=1',(digest(token),)).fetchone()
            if not row or row['expires']<now or row['touched']<now-3600:return None
            db.execute('UPDATE sessions SET touched=? WHERE hash=?',(now,digest(token)))
        return dict(id=row['id'],name=row['name'])
    def csrf(self,token):return hmac.new(self.key,('csrf:'+token).encode(),hashlib.sha256).hexdigest()
    def check_csrf(self,token,value):
        if not isinstance(value,str) or not hmac.compare_digest(self.csrf(token),value):raise Denied('Please refresh the editor before trying again.')
    def logout(self,token):
        with self.db() as db:db.execute('DELETE FROM sessions WHERE hash=?',(digest(token),))
    def revoke(self,email):
        with self.db() as db:
            row=db.execute('SELECT id FROM users WHERE email=?',(email.strip().lower(),)).fetchone()
            if not row:raise Denied('Staff account not found.')
            db.execute('UPDATE users SET active=0 WHERE id=?',(row['id'],));db.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
        self.audit(row['id'],'revoked')
