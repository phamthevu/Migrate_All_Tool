from __future__ import annotations
import json

def snapshot(project_db):
    meta=project_db.get_meta() or {}
    config=project_db.get_config_dict()
    respondents=project_db.get_respondents()
    rows=project_db.conn.execute("SELECT * FROM responses ORDER BY id").fetchall()
    responses=[]
    for r in rows:
        d=dict(r)
        try: d["response"] = json.loads(d.pop("response_json"))
        except Exception: d["response"] = d.pop("response_json", "")
        responses.append(d)
    merges=[dict(r) for r in project_db.conn.execute("SELECT * FROM merge_log ORDER BY id").fetchall()]
    return {"meta":meta,"config":config,"respondents":respondents,"responses":responses,"merge_log":merges}
