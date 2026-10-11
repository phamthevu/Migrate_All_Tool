from unittest.mock import patch
from integrations.postgres_repository import PostgreSQLRepository
from integrations.sqlserver_repository import SQLServerRepository
from integrations.mysql_repository import MySQLRepository

ROWS=[{'snapshot_id':'S1','snapshot_at':'2026-01-01T00:00:00Z','project_id':'P1','project_name':'Proj','project_type':'quant','source_instance_id':'I1','source_instance_name':'PC','source_owner':'Owner','local_response_id':'1','respondent_id':'R1','source_updated_at':'2026-01-01','record_hash':'abc'}]
VALS=[dict(ROWS[0],row_index=0,column_index=0,row_code='F1',column_code='F2',raw_code='(H; Lk)',numerical_value='(1; 0.9)',z_a_code='H',z_b_code='Lk',z_a_value='1',z_b_value='0.9')]
SNAP=({'meta':{'project_id':'P1','project_name':'Proj','project_type':'quant'}},{'instance_id':'I1','instance_name':'PC','owner_name':'Owner'},'S1','2026-01-01T00:00:00Z',ROWS,VALS)
class Cursor:
 def __init__(self): self.sql=[]
 def execute(self,sql,*args): self.sql.append((sql,args)); return self
 def fetchone(self): return ('db','user','server')
 def __enter__(self): return self
 def __exit__(self,*a): pass
class Conn:
 def __init__(self): self.cur=Cursor();self.commits=0;self.rollbacks=0
 def cursor(self): return self.cur
 def commit(self): self.commits+=1
 def rollback(self): self.rollbacks+=1
 def __enter__(self): return self
 def __exit__(self,*a): pass

def check(repo_cls,conn_attr,module):
 for mode,expect_delete in [('overwrite',True),('append',False)]:
  for _ in range(1000):
   c=Conn(); repo=repo_cls({'sync_mode':mode})
   setattr(repo,conn_attr,lambda c=c:c)
   with patch(module+'.build_snapshot',return_value=SNAP): out=repo.sync(object())
   sql='\n'.join(x[0] for x in c.cur.sql).upper()
   has_delete='DELETE FROM RS_STG_RESPONSE_VALUES' in sql and 'DELETE FROM RS_STG_RESPONSES' in sql and 'DELETE FROM RS_STG_SNAPSHOT_RUNS' in sql
   assert has_delete==expect_delete,(repo_cls.__name__,mode,sql)
   assert out['mode']==mode and out['responses']==1 and out['values']==1
   if repo_cls is not PostgreSQLRepository: assert c.commits==1

check(PostgreSQLRepository,'_connect','integrations.postgres_repository')
check(SQLServerRepository,'_conn','integrations.sqlserver_repository')
check(MySQLRepository,'_conn','integrations.mysql_repository')
print('V5.6 DB MODE STRESS PASS | 3 DBs x 2 modes x 1,000 cycles = 6,000 sync simulations')
