from __future__ import annotations
import re, uuid

MAX_PREFIX_LEN = 42

def slugify(value: str) -> str:
    value = re.sub(r'[^a-zA-Z0-9]+', '_', str(value or '').strip().lower()).strip('_')
    return (value or 'project')[:MAX_PREFIX_LEN].rstrip('_')

def new_storage_key(project_name: str) -> str:
    return f"{slugify(project_name)}_{uuid.uuid4().hex[:6]}"

def safe_identifier(value: str, fallback='project') -> str:
    v = re.sub(r'[^a-zA-Z0-9_]+', '_', str(value or '')).strip('_').lower()
    if not v: v = fallback
    if v[0].isdigit(): v = 'p_' + v
    return v

def table_names(storage_key: str):
    p=safe_identifier(storage_key)
    return {'runs':f'{p}_runs','responses':f'{p}_responses','values':f'{p}_values'}

def quant_flat_name(storage_key: str):
    return f"{safe_identifier(storage_key)}_flat"
