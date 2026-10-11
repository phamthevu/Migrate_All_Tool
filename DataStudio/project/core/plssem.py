"""Ordinary PLS path modeling: reflective Mode A, path weighting, full-refit bootstrap.
This is not PLSc and does not claim proprietary SmartPLS numerical equivalence.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm
from .analysis_common import standardize,measurement,discriminant,ols,path_target,indirect_table
from .criteria import Checks


def fit_pls(data,spec,max_iter=500,tol=1e-7):
    by=spec.by_id;order=spec.topological()
    blocks={n.id:standardize(data[n.columns].to_numpy(float)) for n in spec.nodes}
    weights={i:np.ones(by[i].items) for i in order};scores={}
    def score(i,w):
        value=blocks[i]@w;sd=value.std()
        if sd<1e-10:raise ValueError('PLS produced a constant composite.')
        return value/sd,w/sd
    for i in order:scores[i],weights[i]=score(i,weights[i])
    for iteration in range(max_iter):
        updated={};difference=0.
        for i in order:
            proxy=np.zeros(len(data));parents=spec.parents(i)
            if parents:
                x=np.column_stack([scores[p] for p in parents]);b=np.linalg.lstsq(x,scores[i],rcond=None)[0];proxy+=x@b
            for edge in spec.edges:
                if edge.source==i:
                    child=scores[edge.target];proxy+=np.mean(scores[i]*child)*child
            if np.linalg.norm(proxy)<1e-10:proxy=scores[i]
            w=blocks[i].T@proxy/len(data)
            y,w=score(i,w)
            if np.mean(y*blocks[i][:,0])<0:y=-y;w=-w
            difference=max(difference,float(np.max(abs(weights[i]-w))));updated[i]=(y,w)
        for i,(y,w) in updated.items():scores[i]=y;weights[i]=w
        if difference<tol:break
    else:raise ValueError('PLS Mode A did not converge after 500 iterations.')
    score_df=pd.DataFrame({by[i].name:scores[i] for i in order})
    loading={c:float(np.mean(blocks[n.id][:,j]*scores[n.id])) for n in spec.nodes for j,c in enumerate(n.columns)}
    # Scores already standardized; direct inner coefficients are OLS on the converged composites.
    coefficients={};r2={}
    for node in spec.nodes:
        edges=spec.incoming(node.id)
        if not edges:continue
        x=np.column_stack([scores[e.source] for e in edges]);y=scores[node.id];b=np.linalg.lstsq(x,y,rcond=None)[0]
        for e,v in zip(edges,b):coefficients[e.id]=float(v)
        r2[node.id]=float(1-np.mean((y-x@b)**2))
    return score_df,loading,coefficients,r2,weights,iteration+1


def evaluate_pls(data,spec,bootstrap_rng,progress=None,cancel=None,always_infer=False,point_only=False):
    scores,loading,coef,r2,weights,iterations=fit_pls(data,spec);checks=Checks(spec.criteria)
    rel,items=measurement(data,spec,loading,checks);disc=discriminant(data,spec,checks)
    ave=dict(zip(rel.Construct,rel.AVE))
    for _,row in disc.iterrows():
        correlation=float(scores[row.A].corr(scores[row.B]));fl=abs(correlation)<min(np.sqrt(ave[row.A]),np.sqrt(ave[row.B]))
        required=spec.criteria['Fornell-Larcker']['required'] and next(n.reliable for n in spec.nodes if n.name==row.A) and next(n.reliable for n in spec.nodes if n.name==row.B)
        checks.add(row.A+' / '+row.B,'Fornell-Larcker',float(fl),required=required)
        disc.loc[(disc.A==row.A)&(disc.B==row.B),'Composite correlation']=correlation
        disc.loc[(disc.A==row.A)&(disc.B==row.B),'Fornell Larcker pass']=fl
        disc.loc[(disc.A==row.A)&(disc.B==row.B),'Pass']=bool(row.Pass and (fl or not required))
    reports=ols(scores,spec,checks,apply_p=False)
    reports.update({'Measurement':rel,'Indicator Quality':items,'Discriminant':disc,'Construct Pearson':scores.corr(),'PLS Algorithm':pd.DataFrame([{'Algorithm':'Ordinary PLS-PM / Mode A / path weighting','Iterations':iterations,'Tolerance':1e-7,'Converged':True}])})
    # Apply sign/beta constraints before expensive inference.
    for e in spec.edges:
        if e.expected=='significant':
            checks.guard(e.id,'Path sign',coef[e.id]*e.sign>0)
            checks.add(e.id,'Abs beta min',abs(coef[e.id]),required=True,threshold=e.beta_min,direction='min')
            checks.add(e.id,'Abs beta max',abs(coef[e.id]),required=True,threshold=e.beta_max,direction='max')
    if point_only:
        reports['Acceptance']=checks.frame()
        reports['Paths']['p']=np.nan
        reports['Inference Status']=pd.DataFrame([{'Status':'PENDING','Reason':'Point checks only; bootstrap not performed'}])
        return reports,checks.passed,scores
    if not checks.passed and not always_infer:
        reports['Acceptance']=checks.frame();return reports,False,scores
    samples={e.id:[] for e in spec.edges};loading_samples={c:[] for c in data};failed=0
    for b in range(spec.bootstrap):
        if cancel and cancel.is_set():raise InterruptedError('PLS bootstrap cancelled.')
        ids=bootstrap_rng.integers(0,len(data),len(data))
        try:_,l,c,_,_,_=fit_pls(data.iloc[ids].reset_index(drop=True),spec)
        except (ValueError,np.linalg.LinAlgError):failed+=1;continue
        for e in spec.edges:samples[e.id].append(c[e.id])
        for col in data:loading_samples[col].append(l[col])
        if progress and (b%5==0 or b+1==spec.bootstrap):progress(f'PLS full-refit bootstrap {b+1}/{spec.bootstrap}')
    checks.guard('PLS','Bootstrap ≥95% successful',failed<=.05*spec.bootstrap)
    if failed>.05*spec.bootstrap:
        reports['Paths']['p']=np.nan
        reports['Bootstrap']=pd.DataFrame([{'Requested':spec.bootstrap,'Successful':spec.bootstrap-failed,'Status':'FAILED','Reason':'Fewer than 95% successful resamples; bootstrap inference unavailable'}])
        reports['Acceptance']=checks.frame();return reports,False,scores
    for e in spec.edges:
        v=np.asarray(samples[e.id]);se=v.std(ddof=1);p=float(2*norm.sf(abs(coef[e.id]/se))) if se>0 else 0.
        lo,hi=np.percentile(v,[2.5,97.5]);scope=e.id
        path_target(e,coef[e.id],p,checks,scope,float(lo),float(hi))
        ix=reports['Paths'].Path==e.id
        for key,val in {'p':p,'SE bootstrap':se,'CI 2.5%':lo,'CI 97.5%':hi,'Bootstrap successful':len(v)}.items():reports['Paths'].loc[ix,key]=val
    for n in spec.nodes:
        for c in n.columns:
            v=np.asarray(loading_samples[c]);se=v.std(ddof=1);p=float(2*norm.sf(abs(loading[c]/se))) if se>0 else 0.
            checks.add(c,'Loading p',p,required=spec.criteria['Loading p']['required'] and n.reliable)
            items.loc[items.Item==c,'Loading bootstrap p']=p
    reports['Indirect Effects']=indirect_table(spec,coef,samples)
    reports['Outer Weights']=pd.DataFrame([{'Construct':n.name,'Item':c,'Weight':w} for n in spec.nodes for c,w in zip(n.columns,weights[n.id])])
    reports['Bootstrap']=pd.DataFrame([{'Requested':spec.bootstrap,'Successful':spec.bootstrap-failed,'p method':'Normal approximation using full-refit bootstrap SE','CI':'Percentile 95%','Seed policy':'Independent stream derived from generation seed'}])
    reports['Acceptance']=checks.frame()
    return reports,checks.passed,scores
