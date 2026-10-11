import os, tempfile
from core.project_db import ProjectDB
from integrations.project_payload import snapshot
from integrations.powerbi_connector import PowerBIConnector

with tempfile.TemporaryDirectory() as td:
    path=os.path.join(td,'x.mcdm')
    ProjectDB.create_project(path,'V5','QUANTITATIVE_SURVEY',{'auth_mode':'Free','questions':[]},[])
    db=ProjectDB(path)
    p=snapshot(db)
    assert p['meta']['project_name']=='V5'
    assert p['respondents']==[] and p['responses']==[]
    try: PowerBIConnector({'push_url':'http://unsafe'}).test(); raise AssertionError('HTTPS guard failed')
    except ValueError: pass
    db.close()
print('V5.0 INTEGRATION FOUNDATION PASS | snapshot | Power BI HTTPS guard')
