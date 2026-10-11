import json
from pathlib import Path
import integrations.config_store as cs

class FakeKeyring:
    def __init__(self): self.data={}
    def set_password(self,service,name,value): self.data[(service,name)]=value
    def get_password(self,service,name): return self.data.get((service,name))
    def delete_password(self,service,name): self.data.pop((service,name),None)

def test_credentials_survive_save_reload_and_stay_out_of_json(tmp_path,monkeypatch):
    kr=FakeKeyring()
    monkeypatch.setattr(cs,'APP_DIR',tmp_path)
    monkeypatch.setattr(cs,'CONFIG_FILE',tmp_path/'connections.json')
    monkeypatch.setattr(cs,'_keyring',lambda:kr)
    p=cs.load_profiles(); p['postgres'].update({'host':'db.local','user':'alice','password':'top-secret'})
    cs.save_profiles(p)
    loaded=cs.load_profiles()
    assert loaded['postgres']['password']=='top-secret'
    assert loaded['postgres']['host']=='db.local'
    assert 'top-secret' not in (tmp_path/'connections.json').read_text(encoding='utf-8')

def test_blank_optional_secrets_do_not_require_keyring(tmp_path,monkeypatch):
    monkeypatch.setattr(cs,'APP_DIR',tmp_path)
    monkeypatch.setattr(cs,'CONFIG_FILE',tmp_path/'connections.json')
    monkeypatch.setattr(cs,'_keyring',lambda:None)
    p=cs.load_profiles(); p['postgres']['host']='db.local'; p['postgres']['password']=''
    cs.save_profiles(p)
    assert cs.load_profiles()['postgres']['host']=='db.local'
