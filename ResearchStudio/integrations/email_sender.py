from __future__ import annotations
import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path

class SMTPSender:
    def __init__(self, cfg): self.cfg = cfg or {}
    def _truthy(self, key, default=False):
        v=self.cfg.get(key, default)
        return str(v).strip().lower() in ('1','true','yes','on')
    def _connect(self, timeout=20):
        c=self.cfg; host=c.get('host'); port=int(c.get('port') or (465 if self._truthy('ssl') else 587))
        if not host: raise RuntimeError('SMTP host is required.')
        if self._truthy('ssl'):
            s=smtplib.SMTP_SSL(host,port,timeout=timeout)
        else:
            s=smtplib.SMTP(host,port,timeout=timeout)
            if self._truthy('starttls', True): s.starttls()
        if c.get('user'): s.login(c.get('user'),c.get('password') or '')
        return s
    def test(self):
        # A successful SMTP/TLS/authenticated session is sufficient. Some providers
        # reject/close NOOP even though SEND works, which caused false negatives in V5.3.
        with self._connect(10) as s:
            peer = getattr(s, 'sock', None)
            return {'ok': True, 'authenticated': bool(self.cfg.get('user')), 'mode': 'SSL' if self._truthy('ssl') else ('STARTTLS' if self._truthy('starttls', True) else 'PLAIN'), 'message': 'SMTP connection/authentication succeeded.'}
    def send(self,to,subject,body,html=None,attachments=None,cc=None,bcc=None):
        c=self.cfg; m=EmailMessage(); sender=c.get('from_email') or c.get('user')
        if not sender: raise RuntimeError('From email or SMTP user is required.')
        recipients=self._normalize(to); cc_list=self._normalize(cc); bcc_list=self._normalize(bcc)
        if not recipients: raise RuntimeError('At least one recipient is required.')
        m['From']=sender; m['To']=', '.join(recipients); m['Subject']=subject or ''
        if cc_list: m['Cc']=', '.join(cc_list)
        m.set_content(body or '')
        if html: m.add_alternative(html,subtype='html')
        attached=[]
        for raw in attachments or []:
            p=Path(raw)
            if not p.is_file(): raise FileNotFoundError(str(p))
            ctype,_=mimetypes.guess_type(str(p)); ctype=ctype or 'application/octet-stream'; maintype,subtype=ctype.split('/',1)
            m.add_attachment(p.read_bytes(),maintype=maintype,subtype=subtype,filename=p.name); attached.append(p.name)
        envelope=recipients+cc_list+bcc_list
        with self._connect(30) as s: s.send_message(m,to_addrs=envelope)
        return {'sent':len(envelope),'to':recipients,'cc':cc_list,'bcc':bcc_list,'attachments':attached}
    @staticmethod
    def _normalize(value):
        if not value: return []
        if isinstance(value,(list,tuple,set)): vals=value
        else: vals=str(value).replace(';',',').split(',')
        return [str(x).strip() for x in vals if str(x).strip()]
