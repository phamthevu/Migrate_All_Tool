import sqlite3
from datetime import datetime,timezone
from .config_store import APP_DIR
DB=APP_DIR/'activity.sqlite3'
def add_activity(kind,summary,detail='',project_id=''):
 APP_DIR.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(str(DB)) as c:c.execute('CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY,at TEXT,kind TEXT,summary TEXT,detail TEXT,project_id TEXT)');c.execute('INSERT INTO activity(at,kind,summary,detail,project_id) VALUES(?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(timespec="seconds"),kind,summary,detail,project_id));c.execute('DELETE FROM activity WHERE id NOT IN (SELECT id FROM activity ORDER BY id DESC LIMIT 100)')
def recent(limit=100):
 if not DB.exists():return []
 with sqlite3.connect(str(DB)) as c:c.row_factory=sqlite3.Row;return [dict(x) for x in c.execute('SELECT * FROM activity ORDER BY id DESC LIMIT ?',(limit,))]
