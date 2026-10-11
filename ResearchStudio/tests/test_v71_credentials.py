import json
import integrations.config_store as cs
class KR:
 def __init__(self):self.d={}
 def set_password(self,s,u,p):self.d[(s,u)]=p
 def get_password(self,s,u):return self.d.get((s,u))
def test_secrets_not_written_to_json(tmp_path,monkeypatch):
 kr=KR(); monkeypatch.setattr(cs,'APP_DIR',tmp_path); monkeypatch.setattr(cs,'CONFIG_FILE',tmp_path/'connections.json'); monkeypatch.setattr(cs,'_keyring',lambda:kr)
 cs.save_profiles({'postgres':{'host':'db','password':'TOPSECRET'},'s3':{'secret_key':'S3SECRET','bucket':'b'}})
 raw=(tmp_path/'connections.json').read_text(); assert 'TOPSECRET' not in raw and 'S3SECRET' not in raw
 loaded=cs.load_profiles(); assert loaded['postgres']['password']=='TOPSECRET' and loaded['s3']['secret_key']=='S3SECRET'
