from .snapshot_staging import build_snapshot
from .storage_identity import table_names
class MySQLRepository:
 def __init__(self,cfg):self.cfg=cfg or {}
 def _conn(self):
  try:import pymysql
  except ImportError as e:raise RuntimeError('Install: pip install pymysql') from e
  c=self.cfg;return pymysql.connect(host=c.get('host'),port=int(c.get('port') or 3306),user=c.get('user'),password=c.get('password'),database=c.get('database'),connect_timeout=int(c.get('timeout') or 8),charset='utf8mb4',autocommit=False)
 def test(self):
  with self._conn() as c:q=c.cursor();q.execute('SELECT DATABASE(),CURRENT_USER(),VERSION()');x=q.fetchone();return {'ok':True,'database':x[0],'user':x[1],'server':x[2]}
 def _tables(self,db):return table_names((db.get_meta() or {}).get('storage_key') or (db.get_meta() or {}).get('project_id'))
 def status(self,db):
  t=self._tables(db);out={}
  with self._conn() as c:
   q=c.cursor()
   for k,n in t.items():q.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s',(n,));out[k]=bool(q.fetchone()[0])
  return {'schema':self.cfg.get('database'),'tables':{k:{'name':n,'exists':out[k]} for k,n in t.items()}}
 def sync(self,db,mode=None):
  mode=(mode or self.cfg.get('sync_mode') or 'overwrite').lower();d,i,sid,at,rows,vals=build_snapshot(db);iid=i['instance_id'];t=self._tables(db)
  if mode not in {'overwrite','append'}:raise ValueError('sync_mode must be overwrite or append')
  with self._conn() as c:
   q=c.cursor()
   try:
    q.execute(f"CREATE TABLE IF NOT EXISTS `{t['runs']}`(snapshot_id varchar(64) PRIMARY KEY,snapshot_at varchar(64),project_id varchar(128),project_name varchar(500),project_type varchar(100),source_instance_id varchar(128),source_instance_name varchar(255),source_owner varchar(255),response_count int,value_count int)")
    q.execute(f"CREATE TABLE IF NOT EXISTS `{t['responses']}`(snapshot_id varchar(64),snapshot_at varchar(64),project_id varchar(128),project_name varchar(500),project_type varchar(100),source_instance_id varchar(128),source_instance_name varchar(255),source_owner varchar(255),local_response_id varchar(128),respondent_id varchar(128),source_updated_at varchar(64),record_hash varchar(64))")
    q.execute(f"CREATE TABLE IF NOT EXISTS `{t['values']}`(snapshot_id varchar(64),snapshot_at varchar(64),project_id varchar(128),project_name varchar(500),project_type varchar(100),source_instance_id varchar(128),source_instance_name varchar(255),source_owner varchar(255),local_response_id varchar(128),respondent_id varchar(128),source_updated_at varchar(64),record_hash varchar(64),row_index int,column_index int,row_code varchar(128),column_code varchar(128),raw_code text,numerical_value text,z_a_code text,z_b_code text,z_a_value text,z_b_value text)")
    if mode=='overwrite':
     for n in (t['values'],t['responses'],t['runs']):q.execute(f'DELETE FROM `{n}` WHERE source_instance_id=%s',(iid,))
    q.execute(f"INSERT INTO `{t['runs']}` VALUES("+','.join(['%s']*10)+')',(sid,at,d['meta']['project_id'],d['meta'].get('project_name'),d['meta'].get('project_type'),iid,i.get('instance_name'),i.get('owner_name'),len(rows),len(vals)))
    for r in rows:q.execute(f"INSERT INTO `{t['responses']}` VALUES("+','.join(['%s']*12)+')',tuple(r.values()))
    for v in vals:q.execute(f"INSERT INTO `{t['values']}` VALUES("+','.join(['%s']*22)+')',tuple(v.values()))
    c.commit()
   except Exception:c.rollback();raise
  db.update_storage_binding(db_connection_id='mysql',db_database=self.cfg.get('database'),db_table_prefix=(db.get_meta() or {}).get('storage_key'))
  return {'mode':mode,'snapshot_id':sid,'responses':len(rows),'values':len(vals),'source_instance_id':iid,'tables':t}
