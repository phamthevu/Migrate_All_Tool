from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
import sys
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo

APP_DIR=Path(__file__).resolve().parents[1]
ROOT=APP_DIR.parent
def shared_root():
    return Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else ROOT
TEMPLATE=shared_root()/'Templates'/'Template'/'MCDMStudio'/'MCDM_Input_Template.xlsx'
DEMO=shared_root()/'Templates'/'Demo Data'/'MCDMStudio'/'MCDM_Demo_Data.xlsx'

def _style(ws, header=1):
    ws.freeze_panes=f'A{header+1}'; ws.auto_filter.ref=ws.dimensions
    for cell in ws[header]:
        cell.font=Font(color='FFFFFF',bold=True); cell.fill=PatternFill('solid',fgColor='174C69'); cell.alignment=Alignment(wrap_text=True)
    for col in ws.columns:
        letter=col[0].column_letter; width=min(30,max(12,max((len(str(c.value or '')) for c in col),default=0)+2)); ws.column_dimensions[letter].width=width

def generate_template(path=TEMPLATE, demo=False):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    wb=Workbook(); info=wb.active; info.title='Instructions'
    rows=[['MCDMStudio numeric workbook','Fill only yellow cells. Keep sheet names and headers unchanged.'],['Purpose','Enter alternatives, numeric criterion performances, direction, and optional weights.'],['Step 1 - Decision Matrix','One alternative per row; one numeric criterion per column. Avoid blank/negative cells unless method supports them.'],['Step 2 - Criteria','List criteria in the same order as Decision Matrix columns; choose Benefit or Cost.'],['Step 3 - Weights','Weights include subjective AHP, ANP, SWARA, BWM and objective Entropy, CRITIC, MEREC, Standard deviation.'],['Step 4 - AHP Pairwise','Use Saaty 1–9 scale, reciprocal values (e.g. 3 and 1/3), diagonal = 1.'],['Step 5 - SWARA','Sort criteria from most to least important; set rank; s1=0; sⱼ is relative importance vs preceding criterion.'],['Step 6 - BWM','Mark one BWM best and one BWM worst criterion; enter each comparison vector on the 1–9 scale.'],['Step 7 - DEMATEL Direct Relations','Enter average expert influence on a 0–4 scale. Diagonal must be zero; nodes match criterion names.'],['Step 8 - ISM SSIM','Enter V/A/X/O in the upper triangle: i→j / j→i / both / none. Keep diagonal blank.'],['Step 9 - ANP Weighted Supermatrix','Enter the already weighted, column-stochastic supermatrix (each column sums to 1); nodes match criteria.'],['Outputs','In the app, choose a method and export all displayed calculations to Excel.'],['MCDMStudio','Educational numeric demonstration. Verify assumptions and judgment quality before research use.']]
    for row in rows: info.append(row)
    info.column_dimensions['A'].width=28; info.column_dimensions['B'].width=105
    info['A1'].font=Font(size=15,bold=True,color='174C69')
    matrix=wb.create_sheet('Decision Matrix'); matrix.append(['Alternative','C1','C2','C3','C4'])
    if demo:
        for row in [['A1',80,70,75,60],['A2',65,90,80,70],['A3',90,60,65,85],['A4',75,80,90,75]]: matrix.append(row)
    else: matrix.append(['Alternative 1','','','',''])
    crit=wb.create_sheet('Criteria'); crit.append(['Criterion','Direction','Manual weight','BWM best?','BWM worst?','Best-to-criterion','Criterion-to-worst']);
    bwm=[('Y','',1,7),('','Y',7,1),('','',3,5),('','',5,3)] if demo else [('', '',1,1) for _ in range(4)]
    for (c,d,w),bw in zip([('C1','Benefit',0.3),('C2','Cost',0.25),('C3','Benefit',0.25),('C4','Benefit',0.2)],bwm): crit.append([c,d,w,*bw])
    pair=wb.create_sheet('AHP Pairwise'); pair.append(['Criterion','C1','C2','C3','C4'])
    vals=[[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]]
    if demo: vals=[[1,3,2,4],[1/3,1,1/2,2],[1/2,2,1,3],[1/4,1/2,1/3,1]]
    for c,row in zip(['C1','C2','C3','C4'],vals): pair.append([c]+row)
    sw=wb.create_sheet('SWARA'); sw.append(['Rank','Criterion','s (relative importance)'])
    for i,c in enumerate(['C1','C2','C3','C4'],1): sw.append([i,c,0 if i==1 else 0.1])
    direct=wb.create_sheet('DEMATEL Direct Relations'); direct.append(['Factor','C1','C2','C3','C4'])
    vals=[[0,2,1,0],[1,0,3,1],[0,2,0,2],[1,0,1,0]] if demo else [[0,'','',''],['',0,'',''],['','',0,''],['','','',0]]
    for c,row in zip(['C1','C2','C3','C4'],vals): direct.append([c]+row)
    ssim=wb.create_sheet('ISM SSIM'); ssim.append(['Element','C1','C2','C3','C4'])
    vals=[['','V','V','V'],['','', 'V','V'],['','','','V'],['','','','']] if demo else [['','','',''],['','','',''],['','','',''],['','','','']]
    for c,row in zip(['C1','C2','C3','C4'],vals): ssim.append([c]+row)
    anp=wb.create_sheet('ANP Weighted Supermatrix'); anp.append(['Element','C1','C2','C3','C4'])
    vals=[[.4,.2,.2,.1],[.3,.4,.2,.2],[.2,.2,.4,.3],[.1,.2,.2,.4]] if demo else [[.25,.25,.25,.25] for _ in range(4)]
    for c,row in zip(['C1','C2','C3','C4'],vals): anp.append([c]+row)
    for ws in wb.worksheets:
        if ws.title!='Instructions':
            _style(ws)
            for row in ws.iter_rows(min_row=2):
                for c in row[1:]: c.fill=PatternFill('solid',fgColor='FFF2CC')
    wb.save(path); return path

def load_input(path):
    xls=pd.ExcelFile(path)
    if 'Decision Matrix' not in xls.sheet_names or 'Criteria' not in xls.sheet_names: raise ValueError("Workbook must include 'Decision Matrix' and 'Criteria' sheets. Use the MCDMStudio template.")
    dm=pd.read_excel(path,sheet_name='Decision Matrix').dropna(how='all')
    meta=pd.read_excel(path,sheet_name='Criteria').dropna(how='all')
    if dm.shape[1]<3 or meta.shape[1]<2: raise ValueError('The workbook needs an Alternative column and at least two criteria.')
    alt_col=dm.columns[0]; alternatives=dm[alt_col].astype(str).tolist()
    criteria=[str(c) for c in dm.columns[1:]]
    if meta.shape[0]!=len(criteria): raise ValueError('Criteria sheet must have one row for each decision-matrix criterion.')
    # map by criterion name while accepting order-aligned template labels
    names_col=meta.columns[0]; direction_col=meta.columns[1]
    rowmap={str(row[names_col]):row for _,row in meta.iterrows()}
    if set(criteria)<=set(rowmap): rows=[rowmap[c] for c in criteria]
    else: rows=[row for _,row in meta.iterrows()]
    directions=[str(row[direction_col]).strip().title() for row in rows]
    matrix=dm.iloc[:,1:].apply(pd.to_numeric,errors='coerce')
    if matrix.isna().any().any(): raise ValueError('Decision Matrix contains blank or non-numeric performance values.')
    if len(set(alternatives))!=len(alternatives): raise ValueError('Alternative names must be unique.')
    weight_col=meta.columns[2] if meta.shape[1]>=3 else None
    weights=[]
    for row in rows:
        v=row[weight_col] if weight_col else None
        weights.append(float(v) if pd.notna(v) else 0.)
    if sum(weights)<=0: weights=[1/len(criteria)]*len(criteria)
    swara={}
    if 'SWARA' in xls.sheet_names:
        sdf=pd.read_excel(path,sheet_name='SWARA').dropna(how='all')
        if sdf.shape[1]>=3:
            sdf=sdf.sort_values(sdf.columns[0]); swara={str(r.iloc[1]):float(r.iloc[2]) for _,r in sdf.iterrows() if pd.notna(r.iloc[1]) and pd.notna(r.iloc[2])}
    ahp=None
    if 'AHP Pairwise' in xls.sheet_names:
        pdf=pd.read_excel(path,sheet_name='AHP Pairwise')
        if pdf.shape[0]>=len(criteria) and pdf.shape[1]>=len(criteria)+1:
            ahp=pdf.iloc[:len(criteria),1:len(criteria)+1].apply(pd.to_numeric,errors='coerce').to_numpy()
    def read_square(sheet, numeric=False):
        if sheet not in xls.sheet_names:return None
        frame=pd.read_excel(path,sheet_name=sheet).dropna(how='all')
        if frame.shape[0]<len(criteria) or frame.shape[1]<len(criteria)+1:return None
        raw=frame.iloc[:len(criteria),1:len(criteria)+1]
        if numeric:
            vals=raw.apply(pd.to_numeric,errors='coerce').to_numpy(dtype=float)
            return vals if np.isfinite(vals).all() else None
        return raw.fillna('').to_numpy(dtype=object)
    bwm=None
    required={'BWM best?','BWM worst?','Best-to-criterion','Criterion-to-worst'}
    if required.issubset(set(meta.columns)):
        by_name={str(row[names_col]):row for _,row in meta.iterrows()}
        best_names=[str(row[names_col]) for _,row in meta.iterrows() if str(row['BWM best?']).strip().upper() in ('Y','YES','1','TRUE')]
        worst_names=[str(row[names_col]) for _,row in meta.iterrows() if str(row['BWM worst?']).strip().upper() in ('Y','YES','1','TRUE')]
        if len(best_names)==1 and len(worst_names)==1 and all(c in by_name for c in criteria):
            bwm={'best_idx':criteria.index(best_names[0]),'worst_idx':criteria.index(worst_names[0]),'best_to_others':[float(by_name[c]['Best-to-criterion']) for c in criteria],'others_to_worst':[float(by_name[c]['Criterion-to-worst']) for c in criteria]}
    result={'path':str(path),'alternatives':alternatives,'criteria':criteria,'directions':directions,'matrix':matrix.to_numpy(dtype=float),'weights':weights,'swara':swara,'ahp':ahp,'bwm':bwm,'dematel':read_square('DEMATEL Direct Relations',True),'ism':read_square('ISM SSIM',False),'anp':read_square('ANP Weighted Supermatrix',True),'preview':dm}
    xls.close()
    return result

def write_results(path, method, input_data, weights, steps, params=None):
    with pd.ExcelWriter(path,engine='openpyxl') as writer:
        pd.DataFrame({'Property':['Method','Input file','Alternative count','Criterion count','Weight source','Parameters'],'Value':[method,input_data.get('path',''),len(input_data['alternatives']),len(input_data['criteria']),input_data.get('weight_source','Manual / template'),str(params or {})]}).to_excel(writer,sheet_name='Summary',index=False)
        pd.DataFrame({'Criterion':input_data['criteria'],'Direction':input_data['directions'],'Weight':weights}).to_excel(writer,sheet_name='Weights',index=False)
        pd.DataFrame(input_data['matrix'],index=input_data['alternatives'],columns=input_data['criteria']).rename_axis('Alternative').to_excel(writer,sheet_name='Input Matrix')
        for i,step in enumerate(steps,1):
            df=step.table.copy()
            if df.index.name is None and not isinstance(df.index,pd.RangeIndex): df=df.reset_index()
            sheet=f'Step {i:02d}'
            df.to_excel(writer,sheet_name=sheet,index=False)
            ws=writer.book[sheet]; ws.cell(row=1,column=max(1,len(df.columns)+1),value='Formula').font=__import__('openpyxl').styles.Font(bold=True,color='174C69')
            ws.cell(row=2,column=max(1,len(df.columns)+1),value=step.formula)
            ws.cell(row=3,column=max(1,len(df.columns)+1),value='Book reference: '+step.book_ref)
        for ws in writer.book.worksheets:
            ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
            for cell in ws[1]: cell.font=__import__('openpyxl').styles.Font(color='FFFFFF',bold=True); cell.fill=__import__('openpyxl').styles.PatternFill('solid',fgColor='174C69')
            for col in ws.columns:
                letter=col[0].column_letter; ws.column_dimensions[letter].width=min(45,max(12,max((len(str(c.value or '')) for c in col),default=0)+2))
