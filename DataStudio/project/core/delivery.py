import json, os, tempfile, zipfile
from pathlib import Path
import pandas as pd
from .exporter import export_excel

def settings_frame(settings):
    return pd.DataFrame({'Parameter':list(settings),'Value':[str(v) for v in settings.values()]})

def batch_sheets(result,prefix='Ans',scale=None,advance=None,weights=None,order=None):
    sheets={}
    def put(name,df):
        if name.casefold() in {x.casefold() for x in sheets}: raise ValueError(f'Duplicate sheet name: {name}. Change the prefix.')
        sheets[name]=df
    for i,(df,numeric) in enumerate(zip(result.answers,result.numeric),1):
        put(f'{prefix} {i}',df)
        if result.settings['Output']!='CRISP': put(f'Numeric {i}',numeric)
    for name,df in [('Agreement Summary',result.summary),('Factor Scores',result.factor_scores),('Factor Pearson',result.pearson),('Cell Pearson',result.cell_pearson),('Factor Spearman',result.spearman),('Demo Metadata',settings_frame(result.settings)),('Used Scale',scale),('Used Advance',advance),('Used Weights',weights),('Used Order',order)]:
        if df is not None: put(name,df)
    if result.settings.get('DEMATEL aggregate results'):put('DEMATEL Results',pd.DataFrame(result.settings['DEMATEL aggregate results']))
    if result.settings.get('DEMATEL profiles'):put('DEMATEL Targets',pd.DataFrame.from_dict(result.settings['DEMATEL profiles'],orient='index'))
    if result.settings['Mode']=='AHP':
        put('AHP Weights',pd.DataFrame([{'Answer':i,'Criterion':c,'Target':t,'Actual':w} for i,df in enumerate(result.answers,1) for c,t,w in zip(df.index,df.attrs['target_weights'],df.attrs['weights'])]))
    return sheets

def mcdm_data_sheets(result,prefix='CODE'):
    return {f'{prefix} {i}':df for i,df in enumerate(result.answers,1)}

def mcdm_report_sheets(result,scale=None,advance=None,weights=None,order=None):
    sheets=batch_sheets(result,'CODE',scale,advance,weights,order)
    return {name:df for name,df in sheets.items() if not name.startswith(('CODE ', 'Numeric '))}

def quant_sheets(result):
    return {'Data':result.data,'Construct Scores':result.scores,**result.reports,'Demo Metadata':settings_frame(result.settings),'Model Specification':pd.DataFrame({'Line':result.model.splitlines()})}

def export_amos_bundle(path,result,cancel=None):
    if not result.settings['CB SEM']: raise ValueError('Validate CB-SEM before exporting an AMOS bundle.')
    import pyreadstat
    dest=Path(path);fd,tmp=tempfile.mkstemp(suffix='.zip',dir=dest.parent);os.close(fd)
    try:
        with tempfile.TemporaryDirectory() as work:
            root=Path(work);result.data.to_csv(root/'demo_data.csv',index=False,encoding='utf-8-sig')
            pyreadstat.write_sav(result.data,str(root/'demo_data.sav'),file_label='IMPORTED CSV DATA' if result.settings.get('Origin')=='IMPORTED CSV' else 'SYNTHETIC DEMO DATA',variable_measure={c:'scale' if result.settings['Scale']=='CONTINUOUS' else 'ordinal' for c in result.data})
            export_excel(root/'validation.xlsx',quant_sheets(result),cancel=cancel)
            (root/'model_specification.txt').write_text(('IMPORTED CSV DATA' if result.settings.get('Origin')=='IMPORTED CSV' else 'SYNTHETIC DEMO')+'\n\n'+result.model+'\n\nSEMOPY syntax for reference; draw this model in AMOS.\nExcluded groups are not part of the retained SEM.\nCheck AMOS results separately.\n',encoding='utf-8')
            (root/'generation_settings.json').write_text(json.dumps(result.settings,ensure_ascii=False,indent=2),encoding='utf-8')
            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
                for f in root.iterdir():z.write(f,f.name)
        if cancel and cancel.is_set():raise InterruptedError('Cancelled; no AMOS bundle written.')
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
