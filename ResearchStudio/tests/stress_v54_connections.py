import tempfile
from pathlib import Path
from integrations import sync_metadata
from integrations.local_folder_repository import LocalSyncFolderRepository
from integrations.email_sender import SMTPSender

class FakeSMTP:
    def __enter__(self): return self
    def __exit__(self,*a): return False
class FakeSender(SMTPSender):
    def _connect(self,timeout=20): return FakeSMTP()

def run():
    # Scenario 1: SMTP test must pass on authenticated connection without NOOP.
    r=FakeSender({'host':'smtp.example','user':'u','password':'p','starttls':'true'}).test()
    assert r['ok'] is True and r['authenticated'] is True

    # Scenario 2: 50k SCD2-ready row metadata generations are deterministic per machine.
    old=sync_metadata.get_instance_id
    try:
        sync_metadata.get_instance_id=lambda:'INS_A'
        a=[sync_metadata.response_metadata('PRJ_X',{'id':i,'response':{'v':i}}) for i in range(25000)]
        assert len({x['source_record_key'] for x in a})==25000
        sync_metadata.get_instance_id=lambda:'INS_B'
        b=[sync_metadata.response_metadata('PRJ_X',{'id':i,'response':{'v':i}}) for i in range(25000)]
        assert len({x['source_record_key'] for x in b})==25000
        assert not ({x['source_record_key'] for x in a}&{x['source_record_key'] for x in b})
        assert all(len(x['record_hash'])==64 for x in a[:100])
    finally: sync_metadata.get_instance_id=old

    # Scenario 3: Cloud sync folder works without any cloud API/GCP.
    with tempfile.TemporaryDirectory() as td:
        src=Path(td)/'sample.mcdm';src.write_bytes(b'x'*1024)
        out=Path(td)/'drive'
        repo=LocalSyncFolderRepository({'folder':str(out),'project_subfolder':'true'})
        assert repo.test()['ok']
        rr=repo.upload_files([src],'Project_A')
        assert rr['uploaded']==1 and (out/'Project_A'/'sample.mcdm').read_bytes()==src.read_bytes()

    # Scenario 4: changed row hash changes; unchanged row hash does not.
    x={'id':1,'response':{'score':3}}; y={'id':1,'response':{'score':4}}
    assert sync_metadata.record_hash(x)==sync_metadata.record_hash(dict(x))
    assert sync_metadata.record_hash(x)!=sync_metadata.record_hash(y)
    print('V5.4 STRESS PASS: SMTP auth-only test, 50k two-machine keys, local cloud folder, hashes')
if __name__=='__main__': run()
