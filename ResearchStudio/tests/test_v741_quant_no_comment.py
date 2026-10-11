import tempfile
from pathlib import Path
from core.project_db import ProjectDB
from core.project_excel import export_quantitative
from integrations.snapshot_staging import build_quant_flat_rows, build_snapshot
import openpyxl

def test_real_configured_comment_is_normal_question_but_no_system_comment():
 with tempfile.TemporaryDirectory() as td:
  f=Path(td)/"p.mcdm"; cfg={"auth_mode":"Free","questions":[{"question_id":"comment","question_text":"Your comment","question_type":"LONG_TEXT","required":False}]}
  ProjectDB.create_project(str(f),"Q","QUANTITATIVE_SURVEY",cfg,[]); db=ProjectDB(str(f)); rid=db.create_free_respondent("P"); db.save_response(rid,{"comment":"real answer","_comment":"legacy system value"})
  cols,rows=build_quant_flat_rows(db); assert cols==["comment"]; assert rows[0]["comment"]=="real answer"
  _,_,_,_,_,vals=build_snapshot(db); assert any(v["row_code"]=="comment" for v in vals); assert not any(v["row_code"]=="_comment" for v in vals)
  out=Path(td)/"q.xlsx"; export_quantitative(db,out); h=[c.value for c in openpyxl.load_workbook(out)["Data"][1]]; assert h.count("comment")==1 and "Comment" not in h
  db.close()
