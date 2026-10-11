from __future__ import annotations
import ftplib, urllib.request, json
class FTPConnector:
 def __init__(self,cfg): self.cfg=cfg or {}
 def test(self):
  with ftplib.FTP() as f:
   f.connect(self.cfg.get('host'),int(self.cfg.get('port') or 21),timeout=8); f.login(self.cfg.get('user') or '',self.cfg.get('password') or '')
   return {'ok':True,'welcome':f.getwelcome()}
class SFTPConnector:
 def __init__(self,cfg): self.cfg=cfg or {}
 def test(self):
  try: import paramiko
  except ImportError as e: raise RuntimeError('Install paramiko to use SFTP.') from e
  c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  try:
   c.connect(self.cfg.get('host'),port=int(self.cfg.get('port') or 22),username=self.cfg.get('user'),password=self.cfg.get('password'),timeout=8); return {'ok':True}
  finally: c.close()
class MongoConnector:
 def __init__(self,cfg): self.cfg=cfg or {}
 def test(self):
  try: from pymongo import MongoClient
  except ImportError as e: raise RuntimeError('Install pymongo to use MongoDB.') from e
  c=MongoClient(self.cfg.get('uri') or 'mongodb://localhost:27017',serverSelectionTimeoutMS=8000)
  try: return {'ok':bool(c.admin.command('ping').get('ok'))}
  finally: c.close()
class WebhookConnector:
 def __init__(self,cfg): self.cfg=cfg or {}
 def test(self):
  url=self.cfg.get('url')
  if not url: raise RuntimeError('Webhook URL is required.')
  req=urllib.request.Request(url,method='HEAD',headers={'User-Agent':'ResearchStudio/5.4'})
  try:
   with urllib.request.urlopen(req,timeout=8) as r: return {'ok':r.status<500,'status':r.status}
  except Exception as e: raise RuntimeError(f'Webhook endpoint test failed: {e}')
