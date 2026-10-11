"""Settings-only session recovery. Source files and results are not copied into autosave."""
import json,os,tempfile,shutil
from pathlib import Path

def state_path():
    base=os.environ.get('DEMO_DATA_STATE_DIR') or os.environ.get('APPDATA') or os.environ.get('XDG_STATE_HOME') or str(Path.home()/'.local'/'state')
    return Path(base)/'DemoDataStudio'/'autosave.json'

def write_session(path,payload):
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True);fd,temp=tempfile.mkstemp(dir=dest.parent,suffix='.tmp');os.close(fd)
    try:
        Path(temp).write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        if dest.exists():shutil.copy2(dest,str(dest)+'.bak')
        os.replace(temp,dest)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def read_session(path):
    p=Path(path)
    if p.stat().st_size>2*1024*1024:raise ValueError('Session file is too large.')
    obj=json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(obj,dict) or obj.get('session_version')!=1:raise ValueError('Unsupported session format.')
    from .model_spec import ModelSpec
    ModelSpec.from_dict(obj['model'])
    if not isinstance(obj.get('groups'),list) or len(obj['groups'])>10 or not isinstance(obj.get('settings'),dict):raise ValueError('Invalid session settings.')
    for key in ('advanced','ranges','criteria','quick_criteria','weights','csv'):
        if not isinstance(obj.get(key,{}),dict):raise ValueError(f'Invalid session section: {key}.')
    if 'advanced' not in obj:raise ValueError('Missing advanced settings.')
    if not isinstance(obj.get('probabilities',[]),list):raise ValueError('Invalid probabilities.')
    for group in obj['groups']:
        if not isinstance(group,dict) or not isinstance(group.get('name'),str) or not isinstance(group.get('items'),(str,int)) or not isinstance(group.get('accepted'),bool):raise ValueError('Invalid construct settings.')
    for key in ('ranges','criteria','quick_criteria'):
        if any(not isinstance(v,list) or len(v)!=(3 if key=='ranges' else 2) for v in obj.get(key,{}).values()):raise ValueError(f'Invalid {key} entries.')
    for key in ('settings','advanced','weights'):
        if any(not isinstance(v,(str,int,float,bool)) for v in obj.get(key,{}).values()):raise ValueError(f'Invalid {key} values.')
    csv=obj.get('csv',{})
    if csv.get('path') and any(not isinstance(csv.get(k),str) for k in ('path','encoding','delimiter','decimal')):raise ValueError('Invalid CSV source settings.')
    if not isinstance(csv.get('mapping',{}),dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in csv.get('mapping',{}).items()):raise ValueError('Invalid CSV mapping.')
    return obj
