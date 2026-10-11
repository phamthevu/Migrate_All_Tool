import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from integrations.email_sender import SMTPSender
from integrations.drive_repository import GoogleDriveRepository
from integrations.config_store import DEFAULT

class FakeSMTP:
    sent=0
    def __init__(self,*a,**k): pass
    def starttls(self): return (220,b'ok')
    def login(self,*a): return (235,b'ok')
    def noop(self): return (250,b'ok')
    def send_message(self,m,to_addrs=None):
        FakeSMTP.sent += 1
        assert len(list(m.iter_attachments())) >= 1
        assert to_addrs
    def __enter__(self): return self
    def __exit__(self,*a): pass

def run():
    assert 'drive' in DEFAULT and 'smtp' in DEFAULT
    with tempfile.TemporaryDirectory() as td:
        files=[]
        for i in range(25):
            p=Path(td)/f'f{i}.txt'; p.write_text('x'*100,encoding='utf-8'); files.append(str(p))
        sender=SMTPSender({'host':'smtp.test','port':587,'user':'u','password':'p','from_email':'a@test','starttls':'true'})
        with patch('smtplib.SMTP',FakeSMTP):
            assert sender.test()['ok']
            for i in range(1000):
                r=sender.send('x@test;y@test','Stress',f'run {i}',attachments=[files[i%25]])
                assert r['sent']==2 and len(r['attachments'])==1
        assert FakeSMTP.sent==1000
        repo=GoogleDriveRepository({})
        with patch.object(repo,'upload_file',side_effect=lambda p:{'id':'id-'+Path(p).stem,'name':Path(p).name}):
            for _ in range(1000):
                out=repo.upload_files(files)
                assert len(out)==25
    print('V5.3 EMAIL/DRIVE STRESS PASS: 1000 emails + 25,000 mocked Drive uploads')
if __name__=='__main__': run()
