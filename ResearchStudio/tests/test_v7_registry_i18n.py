import tempfile
from pathlib import Path
from integrations.storage_identity import new_storage_key,table_names
from integrations.concurrency import SyncConflictError
from ui.i18n import set_language,tr
from core.project_db import ProjectDB

def test_v7_i18n_display_only():
 set_language('vi'); assert tr('Project ID')=='Mã dự án'; assert tr('Storage Key: abc').startswith('Khóa lưu trữ:'); set_language('en'); assert tr('Project ID')=='Project ID'
def test_v7_project_remote_revision_and_stable_key():
 with tempfile.TemporaryDirectory() as td:
  f=Path(td)/'x.mcdm'; ProjectDB.create_project(str(f),'ERP Selection','QUANTITATIVE_SURVEY',{'auth_mode':'Free','questions':[]},[])
  db=ProjectDB(str(f)); m=db.get_meta(); assert m['storage_key']; assert 'db_remote_revision' in m; key=m['storage_key']; db.close(); db=ProjectDB(str(f)); assert db.get_meta()['storage_key']==key; db.close()
def test_v7_conflict_error():
 e=SyncConflictError(2,3,'abc'); assert 'REMOTE PROJECT HAS CHANGED' in str(e) and 'database revision=3' in str(e)
def test_v7_table_isolation():
 assert table_names(new_storage_key('Same')) != table_names(new_storage_key('Same'))
