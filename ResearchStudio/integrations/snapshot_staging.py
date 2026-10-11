from __future__ import annotations
import uuid, json, re
from .project_payload import snapshot
from .instance_identity import get_identity
from .sync_metadata import response_metadata, utc_now

_PAIR = re.compile(r'^\s*\(?\s*(.*?)\s*;\s*(.*?)\s*\)?\s*$')

def split_z(value):
    if value is None: return '', ''
    s=str(value); m=_PAIR.match(s)
    return (m.group(1).strip(),m.group(2).strip()) if m else (s.strip(),'')

def _labels(config):
    factors=[str(x.get('code','')) for x in config.get('factors',[])]
    alts=[str(x.get('code','')) for x in config.get('alternatives',[])]
    model=str(config.get('model_type','')).upper()
    if model in {'DEMATEL','AHP'}: return factors,factors
    if model=='TOPSIS': return alts,factors
    if model=='DELPHI': return factors,['Rating']
    return [],[]

def _json(v): return json.dumps(v,ensure_ascii=False,separators=(',',':'),default=str)
def _scalar_num(v):
    if isinstance(v,bool) or v is None: return ''
    if isinstance(v,(int,float)): return str(v)
    try:
        s=str(v).strip(); float(s); return s
    except Exception:return ''

def _quant_question_map(cfg):
    return {str(q.get('question_id')):q for q in cfg.get('questions',[]) if q.get('question_id')}

def _append_quant(values,base,payload,cfg):
    qmap=_quant_question_map(cfg)
    for idx,(qid,stored) in enumerate(payload.items()):
        if str(qid) == '_comment': continue  # legacy V7.4 system field; intentionally ignored
        q=qmap.get(str(qid),{})
        # V7.1 representation: {answer:<base answer>, followups:[{id,question,answer},...]}
        if isinstance(stored,dict) and ('answer' in stored or 'followups' in stored):
            answer=stored.get('answer'); followups=stored.get('followups') or []
        else:
            answer=stored; followups=[]
        packed={'answer':answer,'followups':followups}
        v=base.copy(); v.update({
            'row_index':idx,'column_index':0,'row_code':str(qid),
            'column_code':str(q.get('question_text') or 'Answer'),
            'raw_code':_json(packed),'numerical_value':_scalar_num(answer),
            'z_a_code':'','z_b_code':'','z_a_value':'','z_b_value':''})
        values.append(v)

def _append_qual(values,base,payload):
    # Qual payload already contains initial/follow-up structures. Keep each top-level value losslessly.
    for idx,(qid,val) in enumerate(payload.items()):
        v=base.copy(); v.update({'row_index':idx,'column_index':0,'row_code':str(qid),'column_code':'Interview value','raw_code':_json(val),'numerical_value':'','z_a_code':'','z_b_code':'','z_a_value':'','z_b_value':''}); values.append(v)

def _append_mcdm(values,base,payload,cfg):
    row_labels,col_labels=_labels(cfg); use_z=bool(cfg.get('use_z_number'))
    codes=payload.get('code_matrix') or []; nums=payload.get('value_matrix') or []
    za_codes=payload.get('z_a_code_matrix') or []; zb_codes=payload.get('z_b_code_matrix') or []
    za_vals=payload.get('z_a_value_matrix') or []; zb_vals=payload.get('z_b_value_matrix') or []
    for ri,row in enumerate(codes):
        for ci,raw in enumerate(row):
            num=nums[ri][ci] if ri<len(nums) and ci<len(nums[ri]) else ''
            a_code,b_code=split_z(raw) if use_z else (str(raw),''); a_val,b_val=split_z(num) if use_z else (str(num),'')
            if ri<len(za_codes) and ci<len(za_codes[ri]): a_code=str(za_codes[ri][ci])
            if ri<len(zb_codes) and ci<len(zb_codes[ri]): b_code=str(zb_codes[ri][ci])
            if ri<len(za_vals) and ci<len(za_vals[ri]): a_val=str(za_vals[ri][ci])
            if ri<len(zb_vals) and ci<len(zb_vals[ri]): b_val=str(zb_vals[ri][ci])
            v=base.copy(); v.update({'row_index':ri,'column_index':ci,'row_code':row_labels[ri] if ri<len(row_labels) else str(ri),'column_code':col_labels[ci] if ci<len(col_labels) else str(ci),'raw_code':str(raw),'numerical_value':str(num),'z_a_code':a_code,'z_b_code':b_code,'z_a_value':a_val,'z_b_value':b_val}); values.append(v)

def build_snapshot(db):
    data=snapshot(db); ident=get_identity(); at=utc_now(); sid='SNP_'+uuid.uuid4().hex
    meta=data['meta']; pid=meta['project_id']; cfg=data.get('config') or {}; rows=[]; values=[]; ptype=str(meta.get('project_type') or '').upper()
    for r in data['responses']:
        md=response_metadata(pid,r); payload=r.get('response') if isinstance(r.get('response'),dict) else {}
        base={'snapshot_id':sid,'snapshot_at':at,'project_id':pid,'project_name':meta.get('project_name'),'project_type':meta.get('project_type'),'source_instance_id':ident['instance_id'],'source_instance_name':ident.get('instance_name'),'source_owner':ident.get('owner_name'),'local_response_id':md['source_record_id'],'respondent_id':r.get('respondent_id'),'source_updated_at':md['source_updated_at'],'record_hash':md['record_hash']}
        rows.append(base.copy())
        if ptype=='QUANTITATIVE_SURVEY': _append_quant(values,base,payload,cfg)
        elif ptype=='QUALITATIVE_INTERVIEW': _append_qual(values,base,payload)
        else: _append_mcdm(values,base,payload,cfg)
    return data,ident,sid,at,rows,values

def build_quant_flat_rows(db,snapshot_id=None,snapshot_at=None):
    """Wide quantitative rows for BI/SQL. One response = one row; no dynamic follow-up schema."""
    data=snapshot(db); cfg=data.get('config') or {}; questions=cfg.get('questions',[])
    columns=[]
    for q in questions:
        typ=str(q.get('question_type','')).upper()
        if typ in {'TITLE','SECTION','DESCRIPTION'}:continue
        if typ.startswith('MATRIX_'):columns.extend(str(x.get('item_id')) for x in q.get('matrix_items',[]) if x.get('item_id'))
        elif q.get('question_id'):columns.append(str(q.get('question_id')))
    def answer(v):return v.get('answer') if isinstance(v,dict) and ('answer' in v or 'followups' in v) else v
    out=[]
    for r in data.get('responses',[]):
        p=r.get('response') if isinstance(r.get('response'),dict) else {}; row={'snapshot_id':snapshot_id,'snapshot_at':snapshot_at,'local_response_id':str(r.get('source_response_id') or r.get('id')),'respondent_id':r.get('respondent_id'),'submitted_at':r.get('submitted_at')}
        for col in columns:
            val=None
            if col in p:val=answer(p.get(col))
            else:
                for q in questions:
                    if str(q.get('question_type','')).upper().startswith('MATRIX_'):
                        nested=answer(p.get(q.get('question_id'))) or {}
                        if isinstance(nested,dict) and col in nested:val=nested.get(col);break
            row[col]=_json(val) if isinstance(val,(dict,list)) else ('' if val is None else str(val))
        out.append(row)
    return columns,out
