from __future__ import annotations
import hashlib,json,sqlite3
from datetime import datetime,timezone

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _hash(x): return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()
class RowCDC:
    '''Application-level row CDC. Tracks hashes and emits I/U/D tombstone events without changing research config.'''
    def __init__(self,path): self.path=str(path); self._init()
    def _c(self): c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self._c() as c: c.executescript('''CREATE TABLE IF NOT EXISTS cdc_row(project_id TEXT,entity TEXT,row_id TEXT,row_hash TEXT,version INTEGER NOT NULL DEFAULT 1,deleted INTEGER NOT NULL DEFAULT 0,updated_at TEXT,PRIMARY KEY(project_id,entity,row_id)); CREATE TABLE IF NOT EXISTS cdc_event(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT,entity TEXT,row_id TEXT,op TEXT,version INTEGER,event_at TEXT,payload_json TEXT);''')
    def capture(self,pid,entity,rows,id_field):
        current={str(r[id_field]):r for r in rows if r.get(id_field) is not None}; events=[]
        with self._c() as c:
            old={r['row_id']:dict(r) for r in c.execute('SELECT * FROM cdc_row WHERE project_id=? AND entity=?',(pid,entity))}
            for rid,row in current.items():
                h=_hash(row); prev=old.get(rid)
                if not prev or prev['deleted'] or prev['row_hash']!=h:
                    op='I' if not prev or prev['deleted'] else 'U'; ver=(prev['version']+1 if prev else 1); t=_now(); payload=json.dumps(row,ensure_ascii=False,default=str)
                    c.execute('INSERT INTO cdc_row VALUES(?,?,?,?,?,0,?) ON CONFLICT(project_id,entity,row_id) DO UPDATE SET row_hash=excluded.row_hash,version=excluded.version,deleted=0,updated_at=excluded.updated_at',(pid,entity,rid,h,ver,t)); c.execute('INSERT INTO cdc_event(project_id,entity,row_id,op,version,event_at,payload_json) VALUES(?,?,?,?,?,?,?)',(pid,entity,rid,op,ver,t,payload)); events.append((rid,op,ver))
            for rid,prev in old.items():
                if rid not in current and not prev['deleted']:
                    ver=prev['version']+1;t=_now(); c.execute('UPDATE cdc_row SET deleted=1,version=?,updated_at=? WHERE project_id=? AND entity=? AND row_id=?',(ver,t,pid,entity,rid)); c.execute('INSERT INTO cdc_event(project_id,entity,row_id,op,version,event_at,payload_json) VALUES(?,?,?,?,?,?,NULL)',(pid,entity,rid,'D',ver,t)); events.append((rid,'D',ver))
        return events
    def events(self,pid,after_id=0,limit=1000):
        with self._c() as c:return [dict(r) for r in c.execute('SELECT * FROM cdc_event WHERE project_id=? AND id>? ORDER BY id LIMIT ?',(pid,int(after_id),int(limit)))]
