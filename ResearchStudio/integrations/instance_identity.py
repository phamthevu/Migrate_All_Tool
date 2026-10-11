from __future__ import annotations
import json, uuid, socket, getpass, os
from pathlib import Path
APP_DIR=(Path(os.getenv('LOCALAPPDATA'))/'ResearchStudio') if os.getenv('LOCALAPPDATA') else Path.home()/'.research_studio'; FILE=APP_DIR/'instance.json'
def get_identity():
    APP_DIR.mkdir(parents=True,exist_ok=True); d={}
    if FILE.exists():
        try:d=json.loads(FILE.read_text(encoding='utf-8'))
        except Exception:d={}
    changed=False
    if not d.get('instance_id'): d['instance_id']='INS_'+uuid.uuid4().hex; changed=True
    if not d.get('instance_name'): d['instance_name']=socket.gethostname(); changed=True
    if not d.get('owner_name'): d['owner_name']=getpass.getuser(); changed=True
    if changed: FILE.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
    return d
def get_instance_id(): return get_identity()['instance_id']
def save_identity(instance_name,owner_name):
    d=get_identity(); d['instance_name']=str(instance_name).strip() or d['instance_name']; d['owner_name']=str(owner_name).strip() or d['owner_name']; FILE.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8'); return d
