from __future__ import annotations
from pathlib import Path
import uuid
from .snapshot_package import create_snapshot_package
from .storage_identity import safe_identifier
from .artifact_naming import project_key
class S3Repository:
 def __init__(self,cfg): self.cfg=cfg or {}
 def _client(self):
  try: import boto3
  except ImportError as e: raise RuntimeError('S3 connector is not installed. Run: pip install boto3') from e
  kw={'region_name':self.cfg.get('region') or None}
  if self.cfg.get('endpoint_url'):kw['endpoint_url']=self.cfg['endpoint_url']
  if self.cfg.get('access_key'):kw['aws_access_key_id']=self.cfg['access_key']
  if self.cfg.get('secret_key'):kw['aws_secret_access_key']=self.cfg['secret_key']
  return boto3.client('s3',**kw)
 def test(self):
  b=self.cfg.get('bucket');
  if not b:raise ValueError('Bucket is required.')
  self._client().head_bucket(Bucket=b);return f'Bucket reachable: {b}'
 def project_prefix(self,db):
  m=db.get_meta() or {}; base=(self.cfg.get('prefix') or 'research-studio').strip('/'); key=project_key(db); return f'{base}/{key}'
 def status(self,db):
  b=self.cfg.get('bucket'); prefix=self.project_prefix(db)+'/'
  if not b:return {'exists':False,'bucket':'','prefix':prefix}
  r=self._client().list_objects_v2(Bucket=b,Prefix=prefix,MaxKeys=1);return {'exists':bool(r.get('KeyCount',0)),'bucket':b,'prefix':prefix}
 def sync(self,project_db):
  package=create_snapshot_package(project_db); bucket=self.cfg.get('bucket')
  if not bucket:raise ValueError('Bucket is required.')
  project_prefix=self.project_prefix(project_db); stamp=package['stamp']; snapshot_id=package['snapshot_id']; client=self._client();results=[]
  content_types={'.json':'application/json','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
  for raw in package['files']:
   p=Path(raw);key=f'{project_prefix}/snapshots/{snapshot_id}/{p.name}';body=p.read_bytes();client.put_object(Bucket=bucket,Key=key,Body=body,ContentType=content_types.get(p.suffix,'application/octet-stream'));results.append({'key':key,'bytes':len(body),'name':p.name})
  project_db.update_storage_binding(s3_connection_id='s3',s3_bucket=bucket,s3_base_prefix=(self.cfg.get('prefix') or 'research-studio').strip('/'),s3_project_prefix=project_prefix)
  return {'bucket':bucket,'project_prefix':project_prefix,'snapshot_id':snapshot_id,'files':results,'count':len(results)}
