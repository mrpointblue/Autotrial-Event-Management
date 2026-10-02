import os
from contextvars import ContextVar
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass

DATA_DIR = Path(os.environ.get('DATA_DIR', 'data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
_default_engine = create_engine(f"sqlite:///{DATA_DIR / 'autotrial.sqlite3'}", connect_args={'check_same_thread': False, 'timeout': 15})

@event.listens_for(_default_engine, 'connect')
def configure_sqlite(connection, _):
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA journal_mode=WAL')


current_tenant = ContextVar('current_tenant', default=None)
current_user = ContextVar('current_user', default=None)
_engines = {}

def tenant_dir():
    tenant=current_tenant.get()
    if not tenant or tenant['is_default']: return DATA_DIR
    path=DATA_DIR/'organizers'/tenant['id']
    path.mkdir(parents=True,exist_ok=True)
    return path

def get_engine():
    directory=tenant_dir()
    if directory==DATA_DIR: return _default_engine
    key=str(directory)
    if key not in _engines:
        result=create_engine(f"sqlite:///{directory/'autotrial.sqlite3'}",connect_args={'check_same_thread':False,'timeout':15})
        event.listen(result,'connect',configure_sqlite)
        _engines[key]=result
    return _engines[key]

class EngineProxy:
    def __getattr__(self,name): return getattr(get_engine(),name)
engine=EngineProxy()

def SessionLocal():
    return sessionmaker(bind=get_engine(),expire_on_commit=False)()

def get_db():
    with SessionLocal() as session:
        yield session
