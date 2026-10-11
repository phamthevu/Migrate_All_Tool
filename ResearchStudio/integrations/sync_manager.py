from __future__ import annotations
import hashlib, json, sqlite3, inspect
from datetime import datetime, timezone
from pathlib import Path
from .project_payload import snapshot
from .config_store import APP_DIR, load_profiles
from .postgres_repository import PostgreSQLRepository
from .s3_repository import S3Repository
from .powerbi_connector import PowerBIConnector
from .health_check import connector_preflight
from .activity_store import add_activity

STATE_DB = APP_DIR / 'sync_state.sqlite3'
DESTINATIONS = ('postgres','s3','powerbi')

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

def project_fingerprint(project_db):
    data=snapshot(project_db)
    # Exclude mutable remote/audit notions; local research data drives dirty state.
    payload={'meta':{k:v for k,v in data['meta'].items() if k not in ('modified_at',)},'config':data['config'],'respondents':data['respondents'],'responses':data['responses'],'merge_log':data['merge_log']}
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

class SyncStateStore:
    def __init__(self,path=STATE_DB):
        APP_DIR.mkdir(parents=True,exist_ok=True); self.path=Path(path); self._init()
    def _conn(self):
        c=sqlite3.connect(str(self.path)); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self._conn() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS sync_state(
              project_id TEXT NOT NULL,destination TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'LOCAL',
              last_fingerprint TEXT,last_sync_at TEXT,last_attempt_at TEXT,records INTEGER NOT NULL DEFAULT 0,
              last_error TEXT,retry_count INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(project_id,destination));
            CREATE TABLE IF NOT EXISTS sync_log(
              id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT NOT NULL,destination TEXT NOT NULL,
              started_at TEXT NOT NULL,finished_at TEXT,status TEXT NOT NULL,records INTEGER NOT NULL DEFAULT 0,
              fingerprint TEXT,error TEXT,result_json TEXT);
            CREATE INDEX IF NOT EXISTS ix_sync_log_project ON sync_log(project_id,id DESC);
            ''')
    def ensure(self,pid):
        with self._conn() as c:
            for d in DESTINATIONS: c.execute("INSERT OR IGNORE INTO sync_state(project_id,destination,status) VALUES(?,?,'LOCAL')",(pid,d))
    def rows(self,pid,current_fingerprint=None):
        self.ensure(pid)
        with self._conn() as c: rows=[dict(r) for r in c.execute('SELECT * FROM sync_state WHERE project_id=? ORDER BY destination',(pid,))]
        if current_fingerprint:
            for r in rows:
                if r['status']=='SYNCED' and r['last_fingerprint']!=current_fingerprint: r['status']='UNSYNCED'
                elif r['status']=='LOCAL' and r['last_fingerprint']: r['status']='UNSYNCED'
        return rows
    def begin(self,pid,dest,fp):
        t=_now(); self.ensure(pid)
        with self._conn() as c:
            c.execute("UPDATE sync_state SET status='SYNCING',last_attempt_at=?,last_error=NULL WHERE project_id=? AND destination=?",(t,pid,dest))
            cur=c.execute("INSERT INTO sync_log(project_id,destination,started_at,status,fingerprint) VALUES(?,?,?,'SYNCING',?)",(pid,dest,t,fp)); return cur.lastrowid
    def success(self,pid,dest,fp,records,result,log_id):
        t=_now()
        with self._conn() as c:
            c.execute("UPDATE sync_state SET status='SYNCED',last_fingerprint=?,last_sync_at=?,last_attempt_at=?,records=?,last_error=NULL,retry_count=0 WHERE project_id=? AND destination=?",(fp,t,t,records,pid,dest))
            c.execute("UPDATE sync_log SET finished_at=?,status='SYNCED',records=?,result_json=? WHERE id=?",(t,records,json.dumps(result,ensure_ascii=False,default=str),log_id))
    def fail(self,pid,dest,error,log_id):
        t=_now(); msg=str(error)[:4000]
        with self._conn() as c:
            c.execute("UPDATE sync_state SET status='FAILED',last_attempt_at=?,last_error=?,retry_count=retry_count+1 WHERE project_id=? AND destination=?",(t,msg,pid,dest))
            c.execute("UPDATE sync_log SET finished_at=?,status='FAILED',error=? WHERE id=?",(t,msg,log_id))
    def history(self,pid,limit=200):
        with self._conn() as c: return [dict(r) for r in c.execute('SELECT * FROM sync_log WHERE project_id=? ORDER BY id DESC LIMIT ?',(pid,int(limit)))]

class DataSyncManager:
    def __init__(self,project_db,store=None,profiles=None):
        if not project_db: raise RuntimeError('Open a project before syncing.')
        self.db=project_db; self.store=store or SyncStateStore(); self.profiles=profiles or load_profiles()
        self.meta=self.db.get_meta() or {}; self.pid=self.meta.get('project_id')
        if not self.pid: raise RuntimeError('Project ID is missing.')
        self.store.ensure(self.pid)
    def status(self): return self.store.rows(self.pid,project_fingerprint(self.db))
    def history(self,limit=200): return self.store.history(self.pid,limit)
    def _connector(self,d):
        cls={'postgres':PostgreSQLRepository,'s3':S3Repository,'powerbi':PowerBIConnector}[d]
        return cls(self.profiles.get(d,{}) )
    def sync_one(self,destination,force=False):
        if destination not in DESTINATIONS: raise ValueError('Unknown destination: '+str(destination))
        pre=connector_preflight(destination,self.db,self.profiles)
        if not pre['ok']:
            raise RuntimeError('Pre-flight failed. '+'; '.join(f"{x['name']}: {x['detail']}" for x in pre['checks'] if not x['ok']))
        fp=project_fingerprint(self.db); current={r['destination']:r for r in self.store.rows(self.pid,fp)}[destination]
        if not force and current['status']=='SYNCED' and current.get('last_fingerprint')==fp:
            return {'destination':destination,'status':'SKIPPED','reason':'No local changes','records':0}
        log_id=self.store.begin(self.pid,destination,fp)
        try:
            connector=self._connector(destination)
            params=inspect.signature(connector.sync).parameters
            result=(connector.sync(self.db,force=force) if 'force' in params else connector.sync(self.db)) or {}
            records=int(result.get('responses',result.get('rows',0)) or 0)
            self.store.success(self.pid,destination,fp,records,result,log_id)
            add_activity('SUCCESS',f'{destination} sync completed',json.dumps(result,default=str),self.pid)
            return {'destination':destination,'status':'SYNCED','records':records,'result':result}
        except Exception as e:
            self.store.fail(self.pid,destination,e,log_id); add_activity('ERROR',f'{destination} sync failed',str(e),self.pid); raise
    def sync_all(self,force=False):
        out=[]
        for d in DESTINATIONS:
            try: out.append(self.sync_one(d,force=force))
            except Exception as e: out.append({'destination':d,'status':'FAILED','error':str(e)})
        return out
    def retry_failed(self):
        failed=[r['destination'] for r in self.status() if r['status']=='FAILED']
        out=[]
        for d in failed:
            try: out.append(self.sync_one(d,force=True))
            except Exception as e: out.append({'destination':d,'status':'FAILED','error':str(e)})
        return out
