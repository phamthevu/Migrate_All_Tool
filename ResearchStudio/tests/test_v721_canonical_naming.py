import tempfile
from pathlib import Path
from core.project_db import ProjectDB
from integrations.snapshot_package import create_snapshot_package
from integrations.artifact_naming import project_key
from integrations.storage_identity import table_names
from integrations.local_folder_repository import LocalSyncFolderRepository

CFG={'auth_mode':'Free','questions':[{'Question_ID':'Q1','Question_Text':'A?','Question_Type':'SHORT_TEXT','Required':'No','Options':'','Min_Value':'','Max_Value':'','Default_Value':'','Validation':'','Description':'','Display_Order':1}]}

def make(td,name='ERP Selection 2026'):
    p=Path(td)/'p.mcdm'; ProjectDB.create_project(str(p),name,'QUANTITATIVE_SURVEY',CFG,[]); return ProjectDB(str(p))

def test_snapshot_filenames_match_db_prefix():
    with tempfile.TemporaryDirectory() as td:
        db=make(td); key=project_key(db); pkg=create_snapshot_package(db,Path(td)/'out',stamp='20260927T120000Z')
        assert table_names(key)['runs']==key+'_runs'
        assert Path(pkg['json']).name==key+'_20260927T120000Z.json'
        assert len(pkg['excel_files'])==1
        assert Path(pkg['excel_files'][0]).name==key+'_20260927T120000Z_QUANTITATIVE.xlsx'
        assert len(pkg['files'])==2
        assert pkg['snapshot_id'].startswith('20260927T120000Z_')
        db.close()

def test_same_display_name_never_collides():
    with tempfile.TemporaryDirectory() as td:
        a=make(Path(td)/'a'); b=make(Path(td)/'b')
        assert project_key(a)!=project_key(b)
        assert Path(create_snapshot_package(a,Path(td)/'oa',stamp='X')['json']).name != Path(create_snapshot_package(b,Path(td)/'ob',stamp='X')['json']).name
        a.close();b.close()

def test_local_sync_folder_uses_canonical_project_snapshot_tree():
    with tempfile.TemporaryDirectory() as td:
        db=make(Path(td)/'src'); root=Path(td)/'dest'; r=LocalSyncFolderRepository({'folder':str(root)}).sync(db); key=project_key(db)
        for f in r['files']:
            p=Path(f); assert p.parts[-5:-2] == (key,'snapshots',r['snapshot_id']) or (key in p.parts and 'snapshots' in p.parts)
            assert p.name.startswith(key+'_')
        db.close()
