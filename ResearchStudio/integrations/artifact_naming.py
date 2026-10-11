from __future__ import annotations
from .storage_identity import safe_identifier

SNAPSHOT_DIR = 'snapshots'

def project_key(project_db):
    m=project_db.get_meta() or {}
    return safe_identifier(m.get('storage_key') or m.get('project_id') or 'project')

def snapshot_basename(project_db, stamp):
    return f'{project_key(project_db)}_{stamp}'

def project_snapshot_prefix(project_db, snapshot_id=None):
    base=f'{project_key(project_db)}/{SNAPSHOT_DIR}'
    return f'{base}/{snapshot_id}' if snapshot_id else base
