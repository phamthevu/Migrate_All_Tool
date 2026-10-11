from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from .instance_identity import get_instance_id

def utc_now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def record_hash(value):
    raw=json.dumps(value,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()
def response_metadata(project_id,row):
    local_id=str(row.get('source_response_id') or row.get('id') or '')
    instance=get_instance_id()
    return {
      'source_instance_id':instance,
      'source_record_id':local_id,
      'source_record_key':f'{project_id}:{instance}:{local_id}',
      'record_hash':record_hash(row),
      'source_created_at':row.get('submitted_at'),
      'source_updated_at':row.get('merged_at') or row.get('submitted_at'),
      'snapshot_at':utc_now(),
      'is_deleted':False,
    }
