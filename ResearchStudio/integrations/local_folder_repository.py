from __future__ import annotations
from pathlib import Path
import shutil
from .snapshot_package import create_snapshot_package
from .artifact_naming import project_key
class LocalSyncFolderRepository:
    def __init__(self,cfg): self.cfg=cfg or {}
    def _root(self):
        p=Path(self.cfg.get('folder') or '').expanduser()
        if not str(self.cfg.get('folder') or '').strip(): raise RuntimeError('Sync folder is required.')
        return p
    def test(self):
        p=self._root(); p.mkdir(parents=True,exist_ok=True); probe=p/'.research_studio_write_test'; probe.write_text('ok'); probe.unlink(); return {'ok':True,'folder':str(p.resolve())}
    def upload_files(self,paths,project_name=None):
        root=self._root(); root.mkdir(parents=True,exist_ok=True); target=root/(project_name or 'project'); target.mkdir(parents=True,exist_ok=True)
        out=[]
        for raw in paths:
            p=Path(raw); dst=target/p.name; shutil.copy2(p,dst); out.append(str(dst))
        return {'uploaded':len(out),'files':out}
    def sync(self,project_db):
        pkg=create_snapshot_package(project_db); target=self._root()/project_key(project_db)/'snapshots'/pkg['snapshot_id']; target.mkdir(parents=True,exist_ok=True)
        out=[]
        for raw in pkg['files']:
            p=Path(raw); dst=target/p.name; shutil.copy2(p,dst); out.append(str(dst))
        return {'project_key':project_key(project_db),'snapshot_id':pkg['snapshot_id'],'uploaded':len(out),'files':out}
