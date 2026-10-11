from __future__ import annotations
import json,tempfile,uuid
from pathlib import Path
from datetime import datetime,timezone
from .project_payload import snapshot
from .artifact_naming import snapshot_basename
from core.project_excel import export_mcdm,export_quantitative,export_qualitative,project_type

def create_snapshot_package(project_db,output_dir=None,stamp=None):
 data=snapshot(project_db);stamp=stamp or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');snapshot_id=f"{stamp}_{uuid.uuid4().hex[:12]}";folder=Path(output_dir or tempfile.mkdtemp(prefix='research_studio_snapshot_'));folder.mkdir(parents=True,exist_ok=True);base=snapshot_basename(project_db,stamp);jp=folder/f'{base}.json';jp.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8');ptype=project_type(project_db);excel=[]
 if ptype=='QUANTITATIVE_SURVEY':
  p=folder/f'{base}_QUANTITATIVE.xlsx';export_quantitative(project_db,p);excel=[str(p)]
 elif ptype=='QUALITATIVE_INTERVIEW':
  p=folder/f'{base}_QUALITATIVE.xlsx';export_qualitative(project_db,p);excel=[str(p)]
 else:
  raw=folder/f'{base}_RAW_CODES.xlsx';num=folder/f'{base}_NUMERICAL_VALUES.xlsx';excel=export_mcdm(project_db,raw,num);raw_excel=str(raw);numerical_excel=str(num)
 out={'json':str(jp),'excel_files':excel,'files':[str(jp)]+excel,'snapshot_data':data,'stamp':stamp,'snapshot_id':snapshot_id,'project_key':snapshot_basename(project_db,'').rstrip('_'),'project_type':ptype}
 if ptype not in {'QUANTITATIVE_SURVEY','QUALITATIVE_INTERVIEW'}:out.update({'raw_excel':raw_excel,'numerical_excel':numerical_excel})
 return out
