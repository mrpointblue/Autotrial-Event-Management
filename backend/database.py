import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass

DATA_DIR = Path(os.environ.get('DATA_DIR', 'data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{DATA_DIR / 'autotrial.sqlite3'}", connect_args={'check_same_thread': False, 'timeout': 15})

@event.listens_for(engine, 'connect')
def configure_sqlite(connection, _):
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA journal_mode=WAL')

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    with SessionLocal() as session:
        yield session
