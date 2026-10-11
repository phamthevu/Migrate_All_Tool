import importlib.util
from .config_store import APP_DIR,credential_backend_status,load_profiles
MODULES={'Excel':'openpyxl','Secure credentials':'keyring','PostgreSQL':'psycopg2','SQL Server':'pyodbc','MySQL':'pymysql','S3 / MinIO':'boto3','SFTP':'paramiko','MongoDB':'pymongo','Azure Blob':'azure.storage.blob','Google APIs':'google.auth'}
def dependency_health():
 r=[]
 for a,m in MODULES.items():
  try:ok=importlib.util.find_spec(m) is not None
  except:ok=False
  r.append({'component':a,'status':'READY' if ok else 'MISSING','detail':m})
 c=credential_backend_status();r.append({'component':'Credential backend','status':'READY' if c['ok'] else 'UNAVAILABLE','detail':c['detail']});return r
def connector_preflight(dest,db,profiles=None):
 p=profiles or load_profiles();c=p.get(dest,{});m=db.get_meta() or {};x=[('Project identity',bool(m.get('project_id') and m.get('storage_key')),'Project ID / Storage Key')]
 if dest=='postgres':x += [('Host',bool(c.get('host')),c.get('host') or 'Missing'),('Database',bool(c.get('database')),c.get('database') or 'Missing'),('User',bool(c.get('user')),c.get('user') or 'Missing'),('Credential',bool(c.get('password')),'Loaded securely' if c.get('password') else 'Missing')]
 if dest=='s3':x += [('Bucket',bool(c.get('bucket')),c.get('bucket') or 'Missing'),('Access key',bool(c.get('access_key')),'Configured' if c.get('access_key') else 'Missing'),('Secret key',bool(c.get('secret_key')),'Loaded securely' if c.get('secret_key') else 'Missing')]
 if dest=='powerbi':x += [('Push URL',bool(c.get('push_url')),c.get('push_url') or 'Missing')]
 return {'ok':all(v for _,v,_ in x),'checks':[{'name':a,'ok':v,'detail':d} for a,v,d in x]}
