from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

class Store:
    def __init__(self,path='data/app.sqlite3'):
        self.path=str(path)
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, state TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS locations (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    def locations(self):
        with self.connect() as db:
            return {i:json.loads(p) for i,p in db.execute('SELECT id,payload FROM locations ORDER BY id')}
    def add_location(self,location):
        with self.connect() as db:
            db.execute('INSERT INTO locations VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(location['id'],json.dumps(location)))
    def load(self,identifier):
        with self.connect() as db:
            row=db.execute('SELECT state FROM conversations WHERE id=?',(identifier,)).fetchone() if identifier else None
        if identifier and not row:raise ValueError('Unknown conversation; start a new conversation')
        return (identifier or str(uuid4())),(json.loads(row[0]) if row else {})
    def save(self,identifier,state):
        with self.connect() as db:
            db.execute('INSERT INTO conversations VALUES (?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state',(identifier,json.dumps(state)))
