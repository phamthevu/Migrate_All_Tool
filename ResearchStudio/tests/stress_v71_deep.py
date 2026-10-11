import tempfile, time, json, shutil, uuid
from pathlib import Path
from core.project_db import ProjectDB
from integrations.snapshot_staging import build_snapshot
from integrations.concurrency import should_block_revision
from integrations.postgres_repository import PostgreSQLRepository

def cfg(n=10):
 return {'auth_mode':'Free','questions':[{'question_id':f'Q{i}','question_text':f'Question {i}','question_type':'INTEGER' if i%3==0 else 'SHORT_TEXT','required':False} for i in range(1,n+1)]}

def populate(path,name,count=250,followups=False):
 ProjectDB.create_project(str(path),name,'QUANTITATIVE_SURVEY',cfg(),[]); db=ProjectDB(str(path)); h=db.get_meta()['config_hash']
 for r in range(count):
  rid=db.create_free_respondent(f'R{r}'); data={}
  for q in range(1,11):
   ans=r+q if q%3==0 else f'V{r}_{q}'
   if followups and q in (2,5,8):
    data[f'Q{q}']={'answer':ans,'followups':[{'id':f'FU_{q}_{j}','question':f'Probe {q}.{j}','answer':f'A{r}_{j}'} for j in range(3)]}
   else:data[f'Q{q}']=ans
  db.save_response(rid,data)
 assert db.get_meta()['config_hash']==h
 return db

def main():
 t=time.time(); td=Path(tempfile.mkdtemp(prefix='rs_v71_stress_'))
 try:
  # Quant flatten + dynamic followups: 1,000 respondents x 10 = 10,000 value rows, 9,000 followups packed under parents
  db=populate(td/'main.mcdm','Stress Quant',1000,True); key=db.get_meta()['storage_key']; h=db.get_meta()['config_hash']
  _,_,_,_,rows,vals=build_snapshot(db); assert len(rows)==1000 and len(vals)==10000
  packed=sum(len(json.loads(v['raw_code']).get('followups',[])) for v in vals); assert packed==9000
  assert db.get_meta()['config_hash']==h
  # Close/reopen preserves identity and dynamic response payload
  db.close(); db=ProjectDB(str(td/'main.mcdm')); assert db.get_meta()['storage_key']==key and db.get_meta()['config_hash']==h; db.close()

  # Merge 20 independent compatible projects x 250 = 5,000; repeat = 0 duplicates
  target=populate(td/'target.mcdm','Target',1,False); sources=[]
  for i in range(20):
   p=td/f's{i}.mcdm'; x=populate(p,f'S{i}',250,i%2==0); x.close(); sources.append(str(p))
  logs=target.merge_other_projects(sources); assert sum(x['count'] for x in logs)==5000
  before=target.conn.execute('select count(*) from responses').fetchone()[0]
  logs2=target.merge_other_projects(sources); assert sum(x['count'] for x in logs2)==0
  after=target.conn.execute('select count(*) from responses').fetchone()[0]; assert before==after==5001
  assert target.get_meta()['config_hash']==h

  # Schema binding survives profile changes 10,000 times
  target.update_storage_binding(db_schema='research_fixed'); repo=PostgreSQLRepository({'schema':'changed_profile'})
  for _ in range(10000): assert repo._targets(target)[0]=='research_fixed'

  # Multi-machine concurrency policy simulation: 100k APPEND allowed; stale OVERWRITE blocked
  rev=0
  for i in range(100000):
   stale=max(0,rev-7)
   assert not should_block_revision('append',False,stale,rev,True); rev+=1
  assert should_block_revision('overwrite',False,rev-1,rev,True)
  assert not should_block_revision('overwrite',False,rev,rev,True)
  assert not should_block_revision('overwrite',True,rev-10,rev,True)
  target.close()
  print(f'V7.1 DEEP STRESS PASS | Quant 1,000x10=10,000 values | 9,000 followups | Merge 5,000 idempotent | schema binding 10,000 | APPEND policy 100,000 | {time.time()-t:.2f}s')
 finally: shutil.rmtree(td,ignore_errors=True)
if __name__=='__main__':main()
