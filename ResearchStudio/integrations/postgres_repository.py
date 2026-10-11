from datetime import datetime, timezone
from .snapshot_staging import build_snapshot, build_quant_flat_rows
from .storage_identity import table_names, safe_identifier, quant_flat_name
from .concurrency import SyncConflictError, should_block_revision

def _utcnow(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

class PostgreSQLRepository:
 def __init__(self,cfg): self.cfg=cfg or {}
 def _connect(self):
  try: import psycopg2
  except ImportError as e: raise RuntimeError('Install: pip install psycopg2-binary') from e
  c=self.cfg; return psycopg2.connect(host=c.get('host'),port=int(c.get('port') or 5432),dbname=c.get('database'),user=c.get('user'),password=c.get('password'),sslmode=c.get('sslmode') or 'prefer',connect_timeout=int(c.get('timeout') or 8))
 def _schema(self): return safe_identifier(self.cfg.get('schema') or 'public','public')
 def test(self):
  with self._connect() as c:
   with c.cursor() as q: q.execute('SELECT current_database(), current_user, version()'); x=q.fetchone(); return {'ok':True,'database':x[0],'user':x[1],'server':x[2],'schema':self._schema()}
 def list_schemas(self):
  with self._connect() as c:
   with c.cursor() as q:
    q.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' AND schema_name <> 'information_schema' ORDER BY schema_name")
    return [x[0] for x in q.fetchall()]
 def _targets(self,db):
  m=db.get_meta() or {}; key=m.get('storage_key') or m.get('project_id')
  # Once bound, a project keeps its schema even if the connection profile later changes.
  schema=safe_identifier(m.get('db_schema') or self._schema(),'public')
  return schema,table_names(key)
 def status(self,db):
  schema,t=self._targets(db); m=db.get_meta() or {}; remote=None
  with self._connect() as c:
   with c.cursor() as q:
    out={}
    for k,n in t.items():
     q.execute('SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s)',(schema,n)); out[k]=bool(q.fetchone()[0])
    q.execute('SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s)',(schema,'rs_projects'))
    if q.fetchone()[0]:
     q.execute(f'SELECT revision,last_sync_at FROM "{schema}"."rs_projects" WHERE storage_key=%s',(m.get('storage_key'),)); r=q.fetchone()
     if r: remote={'revision':int(r[0]),'last_sync_at':str(r[1]) if r[1] else None}
  return {'schema':schema,'tables':{k:{'name':f'{schema}.{n}','exists':out.get(k,False)} for k,n in t.items()},'registry':remote,'local_revision':m.get('db_remote_revision')}
 def sync(self,db,mode=None,force=False):
  mode=(mode or self.cfg.get('sync_mode') or 'overwrite').lower()
  if mode not in {'overwrite','append'}: raise ValueError('sync_mode must be overwrite or append')
  d,i,sid,at,rows,vals=build_snapshot(db); iid=i['instance_id']; schema,t=self._targets(db); m=db.get_meta() or {}; key=m.get('storage_key'); local_rev=m.get('db_remote_revision')
  with self._connect() as c:
   with c.cursor() as q:
    q.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    REG=f'"{schema}"."rs_projects"'; HIST=f'"{schema}"."rs_sync_history"'
    q.execute(f'''CREATE TABLE IF NOT EXISTS {REG}(storage_key text PRIMARY KEY,project_id text NOT NULL,project_name text,project_type text,created_at timestamptz,modified_at timestamptz,last_sync_at timestamptz,db_schema text,table_prefix text,created_by_instance text,last_sync_instance text,status text NOT NULL DEFAULT 'ACTIVE',revision bigint NOT NULL DEFAULT 0)''')
    q.execute(f'''CREATE TABLE IF NOT EXISTS {HIST}(sync_id text PRIMARY KEY,storage_key text,project_id text,source_instance_id text,started_at timestamptz,completed_at timestamptz,mode text,revision_before bigint,revision_after bigint,status text,error_message text)''')
    q.execute(f'SELECT revision FROM {REG} WHERE storage_key=%s FOR UPDATE',(key,)); rr=q.fetchone()
    if rr is None:
     remote_rev=0
     q.execute(f'''INSERT INTO {REG}(storage_key,project_id,project_name,project_type,created_at,modified_at,db_schema,table_prefix,created_by_instance,last_sync_instance,status,revision) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE',0)''',(key,m.get('project_id'),m.get('project_name'),m.get('project_type'),m.get('created_at'),m.get('modified_at'),schema,key,iid,iid))
    else: remote_rev=int(rr[0])
    # OVERWRITE is destructive and requires optimistic-concurrency match. APPEND is immutable snapshot history,
    # so concurrent machines may append; SELECT ... FOR UPDATE serializes the registry revision increment.
    if should_block_revision(mode,force,local_rev,remote_rev,rr is not None): raise SyncConflictError(local_rev,remote_rev,key)
    new_rev=remote_rev+1
    R=f'"{schema}"."{t["runs"]}"'; P=f'"{schema}"."{t["responses"]}"'; V=f'"{schema}"."{t["values"]}"'
    q.execute(f'CREATE TABLE IF NOT EXISTS {R}(snapshot_id text primary key,snapshot_at timestamptz not null,project_id text,project_name text,project_type text,source_instance_id text,source_instance_name text,source_owner text,response_count integer,value_count integer)')
    q.execute(f'CREATE TABLE IF NOT EXISTS {P}(snapshot_id text,snapshot_at timestamptz,project_id text,project_name text,project_type text,source_instance_id text,source_instance_name text,source_owner text,local_response_id text,respondent_id text,source_updated_at text,record_hash text)')
    q.execute(f'CREATE TABLE IF NOT EXISTS {V}(snapshot_id text,snapshot_at timestamptz,project_id text,project_name text,project_type text,source_instance_id text,source_instance_name text,source_owner text,local_response_id text,respondent_id text,source_updated_at text,record_hash text,row_index integer,column_index integer,row_code text,column_code text,raw_code text,numerical_value text,z_a_code text,z_b_code text,z_a_value text,z_b_value text)')
    if mode=='overwrite':
     for table in (V,P,R): q.execute(f'DELETE FROM {table} WHERE source_instance_id=%s',(iid,))
    q.execute(f'INSERT INTO {R} VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(sid,at,m.get('project_id'),m.get('project_name'),m.get('project_type'),iid,i.get('instance_name'),i.get('owner_name'),len(rows),len(vals)))
    for r in rows:q.execute(f'INSERT INTO {P} VALUES('+','.join(['%s']*12)+')',tuple(r.values()))
    for v in vals:q.execute(f'INSERT INTO {V} VALUES('+','.join(['%s']*22)+')',tuple(v.values()))
    if str(m.get('project_type')).upper()=='QUANTITATIVE_SURVEY':
     F=f'"{schema}"."{quant_flat_name(key)}"'; flat_cols,flat_rows=build_quant_flat_rows(db,sid,at); safe_cols=[safe_identifier(x,'field') for x in flat_cols]
     base_cols=['snapshot_id','snapshot_at','source_instance_id','local_response_id','respondent_id','submitted_at']
     q.execute(f'CREATE TABLE IF NOT EXISTS {F}(snapshot_id text,snapshot_at text,source_instance_id text,local_response_id text,respondent_id text,submitted_at text)')
     for col in safe_cols:q.execute(f'ALTER TABLE {F} ADD COLUMN IF NOT EXISTS "{col}" text')
     if mode=='overwrite':q.execute(f'DELETE FROM {F} WHERE source_instance_id=%s',(iid,))
     names=base_cols+safe_cols; ph=','.join(['%s']*len(names)); quoted=','.join('"'+x+'"' for x in names)
     for fr in flat_rows:q.execute(f'INSERT INTO {F} ({quoted}) VALUES ({ph})',[fr.get(x) if x!='source_instance_id' else iid for x in base_cols]+[fr.get(x) for x in flat_cols])
    now=_utcnow(); q.execute(f'''UPDATE {REG} SET project_name=%s,project_type=%s,modified_at=%s,last_sync_at=%s,db_schema=%s,table_prefix=%s,last_sync_instance=%s,status='ACTIVE',revision=%s WHERE storage_key=%s''',(m.get('project_name'),m.get('project_type'),m.get('modified_at'),now,schema,key,iid,new_rev,key))
    q.execute(f'''INSERT INTO {HIST}(sync_id,storage_key,project_id,source_instance_id,started_at,completed_at,mode,revision_before,revision_after,status,error_message) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'SUCCESS',NULL)''',(sid,key,m.get('project_id'),iid,at,now,mode,remote_rev,new_rev))
  db.update_storage_binding(db_connection_id='postgres',db_database=self.cfg.get('database'),db_schema=schema,db_table_prefix=key,db_remote_revision=new_rev)
  return {'mode':mode,'snapshot_id':sid,'responses':len(rows),'values':len(vals),'source_instance_id':iid,'schema':schema,'tables':t,'revision_before':remote_rev,'revision_after':new_rev}
