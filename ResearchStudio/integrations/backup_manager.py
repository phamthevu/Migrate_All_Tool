from pathlib import Path
from datetime import datetime
import shutil
from .config_store import APP_DIR
def backup_project(db,reason='manual',retention=10):
 m=db.get_meta() or {};key=m.get('storage_key') or m.get('project_id') or 'project';d=APP_DIR/'Backups'/key;d.mkdir(parents=True,exist_ok=True);db.conn.commit();out=d/f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{reason}.mcdm";shutil.copy2(db.db_path,out);fs=sorted(d.glob('*.mcdm'),key=lambda x:x.stat().st_mtime,reverse=True)
 for x in fs[max(1,int(retention)):]:
  try:x.unlink()
  except OSError:pass
 return str(out)
