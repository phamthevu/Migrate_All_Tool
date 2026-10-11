import warnings
import numpy as np
import pandas as pd
from semopy import Model,calc_stats
from .criteria import Checks
from .analysis_common import measurement,discriminant,path_target,indirect_table,range_checks


def syntax(spec):
    by=spec.by_id
    lines=[f'{n.name} =~ '+ ' + '.join(n.columns) for n in spec.nodes]
    for node in spec.nodes:
        edges=spec.incoming(node.id)
        if edges:lines.append(f'{node.name} ~ '+ ' + '.join(by[e.source].name for e in edges))
    return '\n'.join(lines)


def fit_cb(data,spec,point_only=False,check_r2=True):
    text=syntax(spec);model=Model(text)
    with warnings.catch_warnings(record=True) as caught:
        fit=model.fit(data,obj='MLW',solver='SLSQP',options={'maxiter':1500,'ftol':1e-8})
    if not fit.success:raise ValueError('CB-SEM failed to converge: '+str(fit.message))
    beta=model.mx_beta;inv=np.linalg.inv(np.eye(len(beta))-beta);cov=inv@model.mx_psi@inv.T
    names=list(model.names_beta[0]);idx={name:i for i,name in enumerate(names)};by=spec.by_id
    coef={e.id:float(beta[idx[by[e.target].name],idx[by[e.source].name]]*np.sqrt(cov[idx[by[e.source].name],idx[by[e.source].name]]/cov[idx[by[e.target].name],idx[by[e.target].name]])) for e in spec.edges}
    if point_only:
        if np.linalg.eigvalsh(cov).min()<=1e-10 or min(np.diag(model.mx_theta).min(),np.diag(model.mx_psi).min())<=1e-8 or not all(np.isfinite(v) for v in coef.values()):raise ValueError('CB bootstrap fit is inadmissible.')
        return coef
    checks=Checks(spec.criteria);est=model.inspect(std_est=True)
    observed=model.vars['observed'];s=np.cov(data[observed].to_numpy(),rowvar=False,bias=True);sigma=model.calc_sigma()[0]
    checks.guard('CB-SEM','Positive covariance',np.linalg.eigvalsh(sigma).min()>1e-10 and np.linalg.eigvalsh(cov).min()>1e-10)
    variance=est[(est.op=='~~')&(est.lval==est.rval)]
    checks.guard('CB-SEM','No Heywood',bool((variance.Estimate>1e-8).all()))
    residual=(s-sigma)/np.sqrt(np.outer(np.diag(s),np.diag(s)));srmr=float(np.sqrt(np.mean(residual[np.tril_indices(len(s))]**2)))
    stats=calc_stats(model).iloc[0];fitrow={k:float(stats[k]) for k in ('DoF','chi2','chi2 p-value','CFI','TLI','NFI','GFI','AGFI','RMSEA')}
    fitrow['CMIN/DF']=fitrow['chi2']/fitrow['DoF'] if fitrow['DoF']>0 else np.nan;fitrow['SRMR']=srmr
    checks.guard('CB-SEM','Positive DoF',fitrow['DoF']>0)
    for key in ('CFI','TLI','NFI','GFI','AGFI','RMSEA','SRMR','CMIN/DF'):checks.add('CB-SEM',key,fitrow[key])
    checks.add('CB-SEM','Chi-square p',fitrow['chi2 p-value'])
    loadings={};node_ave={}
    for n in spec.nodes:
        block=est[(est.op=='~')&(est.rval==n.name)&est.lval.isin(n.columns)]
        for _,row in block.iterrows():
            loadings[row.lval]=float(row['Est. Std'])
            p=pd.to_numeric(row['p-value'],errors='coerce')
            if np.isfinite(p):checks.add(row.lval,'Loading p',p,required=spec.criteria['Loading p']['required'] and n.reliable)
        checks.guard(n.name,'Loading identifiable',len(block)==n.items)
        checks.guard(n.name,'Loadings below 1',bool((abs(block['Est. Std'])<1).all()))
        node_ave[n.name]=float(np.mean([loadings[c]**2 for c in n.columns]))
    rel,items=measurement(data,spec,loadings,checks);disc=discriminant(data,spec,checks)
    for _,r in disc.iterrows():
        a,b=r.A,r.B;lc=float(cov[idx[a],idx[b]]/np.sqrt(cov[idx[a],idx[a]]*cov[idx[b],idx[b]]))
        fl=abs(lc)<min(np.sqrt(node_ave[a]),np.sqrt(node_ave[b]));required=spec.criteria['Fornell-Larcker']['required'] and next(n.reliable for n in spec.nodes if n.name==a) and next(n.reliable for n in spec.nodes if n.name==b)
        checks.add(a+' / '+b,'Fornell-Larcker',float(fl),required=required)
        disc.loc[(disc.A==a)&(disc.B==b),'Latent correlation']=lc
        disc.loc[(disc.A==a)&(disc.B==b),'Fornell Larcker pass']=fl
        disc.loc[(disc.A==a)&(disc.B==b),'Pass']=bool(r.Pass and (fl or not required))
    r2rows=[];paths=[]
    for n in spec.nodes:
        edges=spec.incoming(n.id)
        if not edges:continue
        i=idx[n.name];r2=1-model.mx_psi[i,i]/cov[i,i]
        if check_r2:range_checks(n,r2,checks)
        r2rows.append({'Target':n.name,'R2':r2,'R2 min':n.r2_min,'R2 max':n.r2_max,'Metric':'Latent implied R2','R':float(np.sqrt(max(0,r2))),'R min':np.sqrt(n.r2_min),'R max':np.sqrt(n.r2_max),'Target metric':n.r_metric,'Target min':n.target_min,'Target max':n.target_max})
        parents=[by[e.source].name for e in edges];pc=cov[np.ix_([idx[x] for x in parents],[idx[x] for x in parents])];pc=pc/np.sqrt(np.outer(np.diag(pc),np.diag(pc)))
        vif=np.diag(np.linalg.inv(pc))
        for j,e in enumerate(edges):
            source=by[e.source].name;row=est[(est.op=='~')&(est.lval==n.name)&(est.rval==source)].iloc[0]
            p=float(row['p-value']);scope=source+' → '+n.name
            path_target(e,coef[e.id],p,checks,scope);checks.add(scope,'VIF',vif[j],required=True,threshold=spec.vif_max,direction='max')
            paths.append({'Path':e.id,'Source':source,'Target':n.name,'Kind':'linear','Expected':e.expected,'Beta':coef[e.id],'p':p,'VIF':vif[j]})
    fitrow['Pass']=checks.passed
    reports={'SEM Fit':pd.DataFrame([fitrow]),'SEM Estimates':est,'Measurement':rel,'Indicator Quality':items,'Discriminant':disc,'Structural R2':pd.DataFrame(r2rows),'Paths':pd.DataFrame(paths),'Acceptance':checks.frame(),'SEM Warnings':pd.DataFrame({'Message':[str(w.message) for w in caught]})}
    reports['Indirect Effects']=indirect_table(spec,coef)
    return reports,checks.passed,text,coef
