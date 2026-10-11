from __future__ import annotations
import json
from .project_payload import snapshot

class PowerBIConnector:
    """Push rows to a Power BI streaming/push endpoint supplied by the user."""
    def __init__(self,cfg): self.cfg=cfg
    def _requests(self):
        try: import requests
        except ImportError as e: raise RuntimeError("Power BI connector requires requests. Run: pip install requests") from e
        return requests
    def test(self):
        url=(self.cfg.get("push_url") or "").strip()
        if not url: raise ValueError("Power BI Push URL is required.")
        # Avoid sending fake rows during connection test; validate endpoint format only.
        if not url.lower().startswith("https://"): raise ValueError("Power BI Push URL must use HTTPS.")
        return "Push URL configured. Use Sync to perform a real push."
    def sync(self,project_db):
        url=(self.cfg.get("push_url") or "").strip()
        if not url: raise ValueError("Power BI Push URL is required.")
        data=snapshot(project_db); m=data["meta"]
        rows=[]
        for r in data["responses"]:
            rows.append({"project_id":m.get("project_id"),"project_name":m.get("project_name"),"project_type":m.get("project_type"),"respondent_id":r.get("respondent_id"),"response_id":str(r.get("source_response_id") or r.get("id")),"submitted_at":r.get("submitted_at"),"response_json":json.dumps(r.get("response"),ensure_ascii=False,default=str)})
        if not rows: return {"rows":0}
        headers={"Content-Type":"application/json"}
        if self.cfg.get("bearer_token"): headers["Authorization"]="Bearer "+self.cfg["bearer_token"].strip()
        req=self._requests()
        total=0
        for i in range(0,len(rows),500):
            chunk=rows[i:i+500]
            resp=req.post(url,headers=headers,json=chunk,timeout=30); resp.raise_for_status(); total+=len(chunk)
        return {"rows":total}
