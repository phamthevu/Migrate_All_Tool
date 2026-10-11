from .snapshot_staging import build_snapshot
from .storage_identity import table_names,safe_identifier
class SQLServerRepository:
 def __init__(self,cfg):self.cfg=cfg or {}
 def _conn(self):
  try:import pyodbc
  except ImportError as e:raise RuntimeError('Install pyodbc and Microsoft ODBC Driver 18 for SQL Server.') from e
  c=self.cfg;drv=c.get('driver') or 'ODBC Driver 18 for SQL Server';server=f"{c.get('host','localhost')},{c.get('port') or 1433}";auth=(c.get('auth_mode') or 'sql').lower();base=f'DRIVER={{{drv}}};SERVER={server};DATABASE={c.get("database","")};Encrypt={c.get("encrypt") or "yes"};TrustServerCertificate={c.get("trust_server_certificate") or "yes"};Connection Timeout={int(c.get("timeout") or 8)};';return pyodbc.connect(base+('Trusted_Connection=yes;' if auth=='windows' else f'UID={c.get("user","")};PWD={c.get("password","")};'),timeout=int(c.get('timeout') or 8))
 def _schema(self,db=None):
  m=(db.get_meta() or {}) if db else {}; return safe_identifier(m.get('db_schema') or self.cfg.get('schema') or 'dbo','dbo')
 def _tables(self,db):return table_names((db.get_meta() or {}).get('storage_key') or (db.get_meta() or {}).get('project_id'))
 def test(self):
  with self._conn() as c:q=c.cursor();x=q.execute('SELECT DB_NAME(), SUSER_SNAME(), @@VERSION').fetchone();return {'ok':True,'database':x[0],'user':x[1],'server':str(x[2])[:180],'schema':self._schema()}
 def list_schemas(self):
  with self._conn() as c:return [r[0] for r in c.cursor().execute('SELECT name FROM sys.schemas ORDER BY name').fetchall()]
 def status(self,db):
  schema=self._schema(db);t=self._tables(db);out={}
  with self._conn() as c:
   q=c.cursor()
   for k,n in t.items():out[k]=bool(q.execute('SELECT CASE WHEN OBJECT_ID(?,\'U\') IS NULL THEN 0 ELSE 1 END',f'{schema}.{n}').fetchone()[0])
  return {'schema':schema,'tables':{k:{'name':f'{schema}.{n}','exists':out[k]} for k,n in t.items()}}
 def sync(self,db,mode=None):
  mode=(mode or self.cfg.get('sync_mode') or 'overwrite').lower();d,i,sid,at,rows,vals=build_snapshot(db);iid=i['instance_id'];schema=self._schema(db);t=self._tables(db)
  if mode not in {'overwrite','append'}:raise ValueError('sync_mode must be overwrite or append')
  R=f'[{schema}].[{t["runs"]}]';P=f'[{schema}].[{t["responses"]}]';V=f'[{schema}].[{t["values"]}]'
  with self._conn() as c:
   q=c.cursor()
   try:
    q.execute(f"IF SCHEMA_ID('{schema}') IS NULL EXEC('CREATE SCHEMA [{schema}]')")
    q.execute(f"IF OBJECT_ID('{schema}.{t['runs']}','U') IS NULL CREATE TABLE {R}(snapshot_id nvarchar(64) PRIMARY KEY,snapshot_at nvarchar(64),project_id nvarchar(128),project_name nvarchar(500),project_type nvarchar(100),source_instance_id nvarchar(128),source_instance_name nvarchar(255),source_owner nvarchar(255),response_count int,value_count int)")
    q.execute(f"IF OBJECT_ID('{schema}.{t['responses']}','U') IS NULL CREATE TABLE {P}(snapshot_id nvarchar(64),snapshot_at nvarchar(64),project_id nvarchar(128),project_name nvarchar(500),project_type nvarchar(100),source_instance_id nvarchar(128),source_instance_name nvarchar(255),source_owner nvarchar(255),local_response_id nvarchar(128),respondent_id nvarchar(128),source_updated_at nvarchar(64),record_hash nvarchar(64))")
    q.execute(f"IF OBJECT_ID('{schema}.{t['values']}','U') IS NULL CREATE TABLE {V}(snapshot_id nvarchar(64),snapshot_at nvarchar(64),project_id nvarchar(128),project_name nvarchar(500),project_type nvarchar(100),source_instance_id nvarchar(128),source_instance_name nvarchar(255),source_owner nvarchar(255),local_response_id nvarchar(128),respondent_id nvarchar(128),source_updated_at nvarchar(64),record_hash nvarchar(64),row_index int,column_index int,row_code nvarchar(128),column_code nvarchar(128),raw_code nvarchar(max),numerical_value nvarchar(max),z_a_code nvarchar(max),z_b_code nvarchar(max),z_a_value nvarchar(max),z_b_value nvarchar(max))")
    if mode=='overwrite':
     for table in (V,P,R):q.execute(f'DELETE FROM {table} WHERE source_instance_id=?',iid)
    q.execute(f'INSERT INTO {R} VALUES(?,?,?,?,?,?,?,?,?,?)',sid,at,d['meta']['project_id'],d['meta'].get('project_name'),d['meta'].get('project_type'),iid,i.get('instance_name'),i.get('owner_name'),len(rows),len(vals))
    for r in rows:q.execute(f'INSERT INTO {P} VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',*tuple(r.values()))
    for v in vals:q.execute(f'INSERT INTO {V} VALUES('+','.join(['?']*22)+')',*tuple(v.values()))
    c.commit()
   except Exception:c.rollback();raise
  db.update_storage_binding(db_connection_id='sqlserver',db_database=self.cfg.get('database'),db_schema=schema,db_table_prefix=(db.get_meta() or {}).get('storage_key'))
  return {'mode':mode,'snapshot_id':sid,'responses':len(rows),'values':len(vals),'source_instance_id':iid,'schema':schema,'tables':t}
