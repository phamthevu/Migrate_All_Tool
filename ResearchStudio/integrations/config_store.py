from __future__ import annotations
import json, os
from pathlib import Path
APP_DIR = Path(os.getenv('LOCALAPPDATA') or (Path.home()/'.research_studio')) / ('ResearchStudio' if os.getenv('LOCALAPPDATA') else '')
CONFIG_FILE = APP_DIR / 'connections.json'
SERVICE='ResearchStudio'
SECRET_FIELDS={'postgres':{'password'},'sqlserver':{'password'},'mysql':{'password'},'s3':{'secret_key'},'adls':{'credential'},'smtp':{'password'},'ftp':{'password'},'sftp':{'password'},'webhook':{'bearer_token'},'powerbi':{'bearer_token'}}
DEFAULT={
 'postgres':{'host':'localhost','port':5432,'database':'research_studio','schema':'public','user':'postgres','password':'','sslmode':'prefer','timeout':8,'sync_mode':'overwrite'},
 'sqlserver':{'host':'localhost','port':1433,'database':'research_studio','schema':'dbo','auth_mode':'sql','user':'','password':'','driver':'ODBC Driver 18 for SQL Server','encrypt':'yes','trust_server_certificate':'yes','timeout':8,'sync_mode':'overwrite'},
 'mysql':{'host':'localhost','port':3306,'database':'research_studio','user':'','password':'','timeout':8,'sync_mode':'overwrite'},
 's3':{'endpoint_url':'','region':'ap-southeast-1','bucket':'','access_key':'','secret_key':'','prefix':'research-studio'},'drive':{'service_account_json':'','folder_id':''},'adls':{'account_url':'','credential':'','container':'','prefix':'research-studio'},'bigquery':{'project_id':'','responses_table':'research_studio.responses'},'powerbi':{'push_url':'','bearer_token':''},'smtp':{'host':'smtp.gmail.com','port':587,'user':'','password':'','from_email':'','starttls':'true','ssl':'false'},'sync_folder':{'folder':'','project_subfolder':'true'},'mongodb':{'uri':'mongodb://localhost:27017','database':'research_studio'},'ftp':{'host':'','port':21,'user':'','password':'','path':'/'},'sftp':{'host':'','port':22,'user':'','password':'','path':'/'},'webhook':{'url':'','bearer_token':''},'auto_snapshot':{'enabled':'false','interval_minutes':'30','destination':'postgres','sync_mode':'overwrite'}}
def _keyring():
 try:
  import keyring
  backend=keyring.get_keyring(); name=f'{backend.__class__.__module__}.{backend.__class__.__name__}'.lower()
  if 'fail' in name or getattr(backend,'priority',0)<=0:return None
  return keyring
 except Exception:return None
def credential_backend_status():
 kr=_keyring()
 if not kr:return {'ok':False,'detail':'No usable secure keyring backend. On Windows, install keyring and use Windows Credential Manager.'}
 try:return {'ok':True,'detail':str(kr.get_keyring())}
 except Exception as e:return {'ok':False,'detail':str(e)}
def _secret_name(profile,field): return f'{profile}:{field}'
def load_profiles():
 out=json.loads(json.dumps(DEFAULT)); data={}
 if CONFIG_FILE.exists():
  try:data=json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
  except Exception:data={}
 for k,v in data.items():
  if isinstance(v,dict):out.setdefault(k,{}).update(v)
 kr=_keyring()
 if kr:
  for profile,fields in SECRET_FIELDS.items():
   for field in fields:
    try:
     value=kr.get_password(SERVICE,_secret_name(profile,field))
     if value is not None:out.setdefault(profile,{})[field]=value
    except Exception:pass
 return out
def save_profiles(data):
 APP_DIR.mkdir(parents=True,exist_ok=True); current=load_profiles(); kr=_keyring()
 for profile,vals in (data or {}).items():
  if not isinstance(vals,dict):continue
  current.setdefault(profile,{})
  for field,value in vals.items():
   if field in SECRET_FIELDS.get(profile,set()):
    secret=str(value or '')
    if not secret:
     # Blank optional credentials must not make an otherwise unrelated profile unsaveable.
     if kr:
      try:
       existing=kr.get_password(SERVICE,_secret_name(profile,field))
       if existing is not None: kr.delete_password(SERVICE,_secret_name(profile,field))
      except Exception: pass
     current[profile].pop(field,None); continue
    if not kr: raise RuntimeError('Secure credential storage is unavailable. Install/configure keyring before saving secrets.')
    try:
     kr.set_password(SERVICE,_secret_name(profile,field),secret)
     # Read-after-write catches backends that accept set_password but do not persist.
     stored=kr.get_password(SERVICE,_secret_name(profile,field))
     if stored != secret: raise RuntimeError(f'Credential verification failed for {profile}.{field}')
     current[profile].pop(field,None); continue
    except Exception as e:
     raise RuntimeError(f'Could not securely persist {profile}.{field}: {e}') from e
   else:current[profile][field]=value
 # Ensure no known secret is written to JSON.
 for profile,fields in SECRET_FIELDS.items():
  for field in fields:current.setdefault(profile,{}).pop(field,None)
 CONFIG_FILE.write_text(json.dumps(current,indent=2,ensure_ascii=False),encoding='utf-8')
 try:os.chmod(CONFIG_FILE,0o600)
 except Exception:pass
