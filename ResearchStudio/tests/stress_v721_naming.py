import tempfile
from pathlib import Path
from core.project_db import ProjectDB
from integrations.snapshot_package import create_snapshot_package
from integrations.artifact_naming import project_key
from integrations.storage_identity import table_names
CFG={'auth_mode':'Free','questions':[]}
def test_stress_1000_projects_unique_canonical_names():
    with tempfile.TemporaryDirectory() as td:
        keys=set()
        for i in range(1000):
            p=Path(td)/f'{i}.mcdm'; ProjectDB.create_project(str(p),'Same Project','QUANTITATIVE_SURVEY',CFG,[]); db=ProjectDB(str(p)); k=project_key(db)
            assert k not in keys; keys.add(k); t=table_names(k); assert all(v.startswith(k+'_') for v in t.values()); db.close()
        assert len(keys)==1000
