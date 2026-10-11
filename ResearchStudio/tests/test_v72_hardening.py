import json, tempfile
from pathlib import Path
import integrations.config_store as cs

def test_credentials_persist_via_keyring_across_reload(monkeypatch):
    class KR:
        d={}
        @classmethod
        def set_password(cls,s,u,p): cls.d[(s,u)]=p
        @classmethod
        def get_password(cls,s,u): return cls.d.get((s,u))
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(cs,'CONFIG_FILE',Path(td)/'connections.json')
        monkeypatch.setattr(cs,'APP_DIR',Path(td))
        monkeypatch.setattr(cs,'_keyring',lambda:KR)
        cs.save_profiles({'postgres':{'host':'db.local','user':'vu','password':'secret-123'},'s3':{'secret_key':'s3-secret'}})
        raw=json.loads(cs.CONFIG_FILE.read_text())
        assert 'password' not in raw['postgres'] and 'secret_key' not in raw['s3']
        loaded=cs.load_profiles()
        assert loaded['postgres']['password']=='secret-123'
        assert loaded['s3']['secret_key']=='s3-secret'

def test_qual_answer_height_reduced():
    src=Path('ui/tab_qual_interview.py').read_text(encoding='utf-8')
    assert 'setMinimumHeight(63)' in src
    assert 'setMinimumHeight(51)' in src

def test_friendly_popup_has_summary_action_details():
    src=Path('ui/friendly_message.py').read_text(encoding='utf-8')
    for x in ('What you can do:','Technical details','Copy Details'):
        assert x in src
