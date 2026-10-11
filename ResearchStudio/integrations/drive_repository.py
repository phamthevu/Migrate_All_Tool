from __future__ import annotations
from pathlib import Path
from .snapshot_package import create_snapshot_package
from .artifact_naming import project_key

class GoogleDriveRepository:
    '''Google Drive legacy API connector. Project snapshots use canonical storage_key names.'''
    def __init__(self,cfg): self.cfg=cfg or {}
    def _service(self):
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError: raise RuntimeError('Install google-api-python-client and google-auth to use Google Drive.')
        f=self.cfg.get('service_account_json')
        if not f: raise RuntimeError('Service Account JSON is required.')
        if not Path(f).is_file(): raise FileNotFoundError(f)
        cred=service_account.Credentials.from_service_account_file(f,scopes=['https://www.googleapis.com/auth/drive.file'])
        return build('drive','v3',credentials=cred,cache_discovery=False)
    def test(self):
        svc=self._service(); folder=self.cfg.get('folder_id')
        if folder:
            info=svc.files().get(fileId=folder,fields='id,name,mimeType').execute(); return {'ok':True,'folder':info.get('name'),'folder_id':info.get('id')}
        svc.files().list(pageSize=1,fields='files(id,name)').execute(); return {'ok':True}
    def _ensure_folder(self,svc,name,parent=None):
        esc=name.replace("'","\\'"); q=f"name='{esc}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent:q+=f" and '{parent}' in parents"
        r=svc.files().list(q=q,pageSize=10,fields='files(id,name)').execute().get('files',[])
        if r:return r[0]['id']
        meta={'name':name,'mimeType':'application/vnd.google-apps.folder'}
        if parent:meta['parents']=[parent]
        return svc.files().create(body=meta,fields='id').execute()['id']
    def upload_file(self,path,name=None,parent_id=None):
        try: from googleapiclient.http import MediaFileUpload
        except ImportError: raise RuntimeError('Install google-api-python-client.')
        p=Path(path)
        if not p.is_file(): raise FileNotFoundError(str(p))
        svc=self._service(); meta={'name':name or p.name}; folder=parent_id or self.cfg.get('folder_id')
        if folder: meta['parents']=[folder]
        result=svc.files().create(body=meta,media_body=MediaFileUpload(str(p),resumable=True),fields='id,name,webViewLink').execute()
        return result
    def upload_files(self,paths,parent_id=None): return [self.upload_file(p,parent_id=parent_id) for p in paths]
    def sync(self,project_db):
        package=create_snapshot_package(project_db); svc=self._service(); root=self.cfg.get('folder_id')
        project_folder=self._ensure_folder(svc,project_key(project_db),root)
        snapshots=self._ensure_folder(svc,'snapshots',project_folder)
        snapshot_folder=self._ensure_folder(svc,package['snapshot_id'],snapshots)
        out=[]
        # reuse one service by direct creates
        from googleapiclient.http import MediaFileUpload
        for raw in package['files']:
            p=Path(raw); meta={'name':p.name,'parents':[snapshot_folder]}
            out.append(svc.files().create(body=meta,media_body=MediaFileUpload(str(p),resumable=True),fields='id,name,webViewLink').execute())
        return {'project_key':project_key(project_db),'snapshot_id':package['snapshot_id'],'files':out,'count':len(out)}
