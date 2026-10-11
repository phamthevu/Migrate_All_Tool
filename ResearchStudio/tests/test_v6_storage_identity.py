from pathlib import Path
from tempfile import TemporaryDirectory
from core.project_db import ProjectDB
from integrations.storage_identity import table_names

def make(path,name):
    ProjectDB.create_project(str(path),name,'QUANTITATIVE_SURVEY',{'auth_mode':'Free','questions':[]},[])
    return ProjectDB(str(path))

def test_v6_unique_storage_identity_and_reopen():
    with TemporaryDirectory() as td:
        a=make(Path(td)/'a.mcdm','ERP Selection 2026'); b=make(Path(td)/'b.mcdm','ERP Selection 2026')
        ka=a.get_meta()['storage_key']; kb=b.get_meta()['storage_key']
        assert ka != kb and ka.startswith('erp_selection_2026_')
        assert set(table_names(ka))=={'runs','responses','values'}
        a.close(); a=ProjectDB(str(Path(td)/'a.mcdm')); assert a.get_meta()['storage_key']==ka

def test_v6_legacy_project_gets_stable_key():
    with TemporaryDirectory() as td:
        p=Path(td)/'legacy.mcdm'
        import sqlite3, json
        c=sqlite3.connect(p)
        c.executescript("""
        CREATE TABLE project_meta(project_id TEXT PRIMARY KEY,project_name TEXT,project_type TEXT,config_hash TEXT,config_json TEXT,schema_version INTEGER,created_at TEXT,modified_at TEXT);
        CREATE TABLE respondents(respondent_id TEXT PRIMARY KEY);
        CREATE TABLE responses(id INTEGER PRIMARY KEY,response_json TEXT);
        CREATE TABLE merge_log(id INTEGER PRIMARY KEY);
        """)
        c.execute("INSERT INTO project_meta VALUES(?,?,?,?,?,?,?,?)",('PRJ_OLD','Legacy','MCDM','x','{}',1,'x','x'));c.commit();c.close()
        db=ProjectDB(str(p)); generated=db.get_meta()['storage_key']; assert generated.startswith('legacy_');db.close()
        db=ProjectDB(str(p)); assert db.get_meta()['storage_key']==generated
