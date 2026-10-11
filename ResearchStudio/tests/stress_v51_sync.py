import os,tempfile,random,string
from core.project_db import ProjectDB
from integrations.sync_manager import SyncStateStore,DataSyncManager,project_fingerprint
import integrations.sync_manager as sm

class FakeConnector:
    calls=0
    fail=False
    def __init__(self,cfg): pass
    def sync(self,db):
        FakeConnector.calls+=1
        if FakeConnector.fail: raise RuntimeError('simulated network failure')
        return {'responses':db.conn.execute('SELECT COUNT(*) FROM responses').fetchone()[0]}

def add_response(db,i):
    rid=db.add_respondent('u'+str(i),'p','User '+str(i),'Org')
    db.save_response(rid,{'q':i,'text':'x'*20})

with tempfile.TemporaryDirectory() as td:
    p=os.path.join(td,'stress.mcdm'); state=os.path.join(td,'sync.sqlite')
    ProjectDB.create_project(p,'V51','QUANTITATIVE_SURVEY',{'auth_mode':'Free','questions':[]},[]); db=ProjectDB(p)
    store=SyncStateStore(state)
    mgr=DataSyncManager(db,store=store,profiles={'postgres':{},'s3':{},'powerbi':{}})
    mgr._connector=lambda d: FakeConnector({})
    assert all(x['status']=='LOCAL' for x in mgr.status())
    # 10k deterministic fingerprint calculations: no mutation => identical.
    f=project_fingerprint(db)
    for _ in range(10000): assert project_fingerprint(db)==f
    # First all destinations sync.
    out=mgr.sync_all(); assert all(x['status']=='SYNCED' for x in out); assert FakeConnector.calls==3
    # 1k repeated sync cycles unchanged => all skipped, zero extra remote calls.
    for _ in range(1000):
        out=mgr.sync_all(); assert all(x['status']=='SKIPPED' for x in out)
    assert FakeConnector.calls==3
    # Mutation marks all destinations UNSYNCED dynamically.
    add_response(db,1); sts=mgr.status(); assert all(x['status']=='UNSYNCED' for x in sts)
    mgr.sync_one('postgres'); assert FakeConnector.calls==4
    st={x['destination']:x['status'] for x in mgr.status()}; assert st['postgres']=='SYNCED' and st['s3']=='UNSYNCED' and st['powerbi']=='UNSYNCED'
    # Failure is isolated and persisted; retry succeeds.
    FakeConnector.fail=True
    try: mgr.sync_one('s3'); raise AssertionError('failure expected')
    except RuntimeError: pass
    assert {x['destination']:x['status'] for x in mgr.status()}['s3']=='FAILED'
    FakeConnector.fail=False; r=mgr.retry_failed(); assert r and r[0]['status']=='SYNCED'
    # 500 response mutations + sync; no duplicate call on immediate repeat.
    for i in range(2,502): add_response(db,i)
    before=FakeConnector.calls; mgr.sync_one('postgres'); assert FakeConnector.calls==before+1
    mgr.sync_one('postgres'); assert FakeConnector.calls==before+1
    assert len(mgr.history())>0
    db.close()
print('V5.1 STRESS PASS | 10,000 fingerprints | 1,000 no-change sync cycles | 501 responses | failure/retry | per-destination dirty state')
