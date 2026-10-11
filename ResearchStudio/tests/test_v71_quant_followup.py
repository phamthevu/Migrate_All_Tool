import json, tempfile
from pathlib import Path
from core.project_db import ProjectDB
from integrations.snapshot_staging import build_snapshot
from integrations.postgres_repository import PostgreSQLRepository
from integrations.concurrency import should_block_revision

def cfg():
    return {'auth_mode':'Free','questions':[{'question_id':'Q1','question_text':'Use ERP?','question_type':'YES_NO','required':True},{'question_id':'Q2','question_text':'Years','question_type':'INTEGER','required':False}]}

def test_quant_followup_flatten_and_config_immutable():
    with tempfile.TemporaryDirectory() as td:
        f=Path(td)/'q.mcdm'; ProjectDB.create_project(str(f),'Q','QUANTITATIVE_SURVEY',cfg(),[]); db=ProjectDB(str(f)); before=db.get_meta()['config_hash']
        rid=db.create_free_respondent('A'); db.save_response(rid,{'Q1':{'answer':'Yes','followups':[{'id':'FU_1','question':'Which ERP?','answer':'SAP'}]},'Q2':3})
        _,_,_,_,rows,vals=build_snapshot(db); assert len(rows)==1 and len(vals)==2
        q1=next(x for x in vals if x['row_code']=='Q1'); packed=json.loads(q1['raw_code']); assert packed['answer']=='Yes' and packed['followups'][0]['answer']=='SAP'
        assert db.get_meta()['config_hash']==before; db.close()

def test_schema_binding_is_immutable_after_first_bind():
    with tempfile.TemporaryDirectory() as td:
        f=Path(td)/'q.mcdm'; ProjectDB.create_project(str(f),'Q','QUANTITATIVE_SURVEY',cfg(),[]); db=ProjectDB(str(f)); db.update_storage_binding(db_schema='research_a')
        repo=PostgreSQLRepository({'schema':'research_b'}); schema,_=repo._targets(db); assert schema=='research_a'; db.close()

def test_append_is_not_revision_blocked_but_overwrite_is():
    assert not should_block_revision('append',False,4,99,True)
    assert should_block_revision('overwrite',False,4,5,True)
    assert not should_block_revision('overwrite',True,4,5,True)
