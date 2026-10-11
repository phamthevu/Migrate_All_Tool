from pathlib import Path
from integrations.health_check import dependency_health

def test_english_only():
    assert not Path('i18n').exists()
    assert not Path('ui/i18n.py').exists()
    s=Path('ui/main_window.py').read_text()
    assert 'Vietnamese' not in s and 'set_language' not in s

def test_keyring_core_dependency():
    assert 'keyring' in Path('requirements-core.txt').read_text().lower()

def test_system_health_contract():
    rows=dependency_health()
    names={x['component'] for x in rows}
    assert 'Credential backend' in names and 'PostgreSQL' in names and 'S3 / MinIO' in names

def test_preflight_wired_before_sync():
    s=Path('integrations/sync_manager.py').read_text()
    assert s.index('connector_preflight(destination') < s.index('self.store.begin')

def test_backup_before_merge():
    s=Path('ui/main_window.py').read_text()
    assert s.index("backup_project(self.project_db,'before_merge')") < s.index('merge_other_projects(compatible)')
