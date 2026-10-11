"""One-pass analysis of imported observations. Never search, synthesize or force a pass."""
import csv,hashlib,io,json,copy
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from scipy.stats import skew,kurtosis
from .quantitative import QuantResult
from .criteria import Checks
from .analysis_common import measurement,ols,indirect_table
from .cbsem import fit_cb,syntax
from .plssem import evaluate_pls
from .advanced_generate import cb_indirect_bootstrap

def read_csv(path,delimiter='auto',encoding='utf-8-sig',decimal='.'):
    p=Path(path)
    if p.stat().st_size>32*1024*1024:raise ValueError('CSV exceeds the 32 MB import limit.')
    raw=p.read_bytes();text=raw.decode(encoding)
    if delimiter=='auto':
        try:delimiter=csv.Sniffer().sniff(text[:8192],delimiters=',;\t').delimiter
        except csv.Error:delimiter=','
    header=next(csv.reader(io.StringIO(text),delimiter=delimiter),[])
    if not header or any(not h.strip() for h in header) or len({h.strip() for h in header})!=len(header):raise ValueError('CSV headers must be nonempty and unique (including after trimming).')
    for row in list(csv.reader(io.StringIO(text),delimiter=delimiter))[1:]:
        if row and len(row)!=len(header):raise ValueError('CSV records must have the same number of fields as the header.')
    frame=pd.read_csv(io.StringIO(text),sep=delimiter,decimal=decimal);frame.columns=[str(c).strip() for c in frame.columns]
    if not 1<=len(frame)<=10000 or len(frame.columns)>2000:raise ValueError('CSV supports 1–10,000 rows and at most 2,000 columns.')
    return frame,{'File':p.name,'SHA256':hashlib.sha256(raw).hexdigest(),'Delimiter':repr(delimiter),'Encoding':encoding,'Decimal':decimal,'Original rows':len(frame)}

def prepare_data(frame,spec,mapping,drop_missing=False):
    required=[c for n in spec.nodes for c in n.columns]
    if set(mapping)!=set(required):raise ValueError('Map every model indicator; update mapping after changing the diagram.')
    sources=[mapping[c] for c in required]
    if len(set(sources))!=len(sources) or any(c not in frame.columns for c in sources):raise ValueError('Select a unique existing CSV column for every indicator.')
    data=frame[sources].copy();data.columns=required
    for c in data:
        numeric=pd.to_numeric(data[c],errors='coerce')
        invalid=data[c].notna() & numeric.isna()
        if invalid.any():raise ValueError(f'{mapping[c]}: nonnumeric observations found; clean the source column first.')
        data[c]=numeric
    if np.isinf(data.to_numpy(float)).any():raise ValueError('Infinite observations are not supported.')
    incomplete=data.isna().any(axis=1);excluded=pd.DataFrame({'CSV data row (1-based)':np.flatnonzero(incomplete)+1})
    if incomplete.any() and not drop_missing:raise ValueError(f'{int(incomplete.sum())} rows contain missing mapped values. Clean the CSV or explicitly enable Drop incomplete rows.')
    data=data.loc[~incomplete].reset_index(drop=True)
    if (data.var(ddof=0)<=1e-10).any():raise ValueError('Mapped data contains constant indicators.')
    if spec.scale!='CONTINUOUS':
        maximum=5 if spec.scale=='LIKERT5' else 7
        if not ((data>=1)&(data<=maximum)&(data==np.floor(data))).all().all():raise ValueError(f'Mapped values must be integers 1–{maximum}; select CONTINUOUS for other numeric data.')
    return data,excluded

def analyze_csv(frame,spec,mapping,metadata,drop_missing=False,progress=None,cancel=None):
    data,excluded=prepare_data(frame,spec,mapping,drop_missing);spec=copy.deepcopy(spec);spec.rows=len(data);spec.validate(for_generation=False)
    if cancel and cancel.is_set():raise InterruptedError('CSV analysis cancelled.')
    stream=np.random.SeedSequence(spec.seed);rng=np.random.default_rng(stream.spawn(2)[1])
    if progress:progress(f'Analyzing imported CSV • {spec.method} • {len(data)} retained rows')
    with threadpool_limits(limits=1):
        scores=pd.DataFrame({n.name:data[n.columns].mean(axis=1) for n in spec.nodes})
        if spec.method=='CB-SEM':
            reports,passed,text,coef=fit_cb(data,spec)
            try:
                indirect,boot=cb_indirect_bootstrap(data,spec,coef,rng,progress,cancel);reports['Indirect Effects']=indirect
                if boot is not None:reports['Bootstrap']=boot
            except ValueError as error:
                reports['Indirect Effects']=indirect_table(spec,coef)
                reports['Bootstrap']=pd.DataFrame([{'Requested':spec.bootstrap,'Status':'FAILED','Details':str(error),'Use':'Point estimates retained; confidence intervals unavailable'}])
                checks=Checks(spec.criteria);checks.guard('CB-SEM','Indirect bootstrap usable',False)
                reports['Acceptance']=pd.concat([reports['Acceptance'],checks.frame()],ignore_index=True);passed=False
        elif spec.method=='PLS-SEM':reports,passed,scores=evaluate_pls(data,spec,rng,progress,cancel,always_infer=True);text=syntax(spec)
        else:
            checks=Checks(spec.criteria);loads={c:float(data[c].corr(scores[n.name])) for n in spec.nodes for c in n.columns}
            rel,items=measurement(data,spec,loads,checks);reports=ols(scores,spec,checks)
            reports.update({'Measurement':rel,'Indicator Quality':items,'Acceptance':checks.frame()});passed=checks.passed
            coef=dict(zip(reports['Paths'].Path,reports['Paths'].Beta));reports['Indirect Effects']=indirect_table(spec,coef)
            text='\n'.join(f'{n.name} ~ '+ ' + '.join(e.id for e in spec.incoming(n.id)) for n in spec.nodes if spec.incoming(n.id))
    if cancel and cancel.is_set():raise InterruptedError('CSV analysis cancelled.')
    reports.update({'Construct Pearson':scores.corr(),'Column Mapping':pd.DataFrame({'Indicator':list(mapping),'CSV column':list(mapping.values())}),
                    'Excluded CSV Rows':excluded,'Model Nodes':pd.DataFrame([vars(n) for n in spec.nodes]),'Model Edges':pd.DataFrame([vars(e) for e in spec.edges]),
                    'Normality':pd.DataFrame({'Item':data.columns,'Skew':skew(data,axis=0),'Excess kurtosis':kurtosis(data,axis=0)})})
    settings={'Synthetic':'IMPORTED CSV — provenance supplied by user','Origin':'IMPORTED CSV','Version':'5.0','Method':spec.method,'CB SEM':spec.method=='CB-SEM','Scale':spec.scale,'Rows':len(data),'Excluded rows':len(excluded),
              'Required criteria passed':bool(passed),'Model JSON':json.dumps(spec.to_dict(),ensure_ascii=False),'Model fingerprint':spec.fingerprint(),'Seed':spec.seed,'Effective seed':stream.entropy,
              'CSV metadata':json.dumps(metadata),'Column mapping':json.dumps(mapping),'Missing policy':'Drop incomplete rows' if drop_missing else 'Reject missing values',
              'Inference':'One fit of imported observations; targets are comparison criteria, not constraints imposed on data. Export includes failures. Ordinary PLS uses full-refit bootstrap; not PLSc.',
              'R definition':'sqrt(implied latent R2)' if spec.method=='CB-SEM' else 'sqrt(composite R2)' if spec.method=='PLS-SEM' else 'sqrt(OLS R2)'}
    return QuantResult(data,scores,reports,text,settings)
