import numpy as np
import pandas as pd
from scipy import stats
from .quantitative import alpha


def standardize(values):
    values=np.asarray(values,float);sd=values.std(axis=0,ddof=0)
    if np.any(sd<1e-10) or not np.isfinite(values).all():raise ValueError('Data contains constant columns or nonfinite values.')
    return (values-values.mean(axis=0))/sd


def measurement(data,spec,loadings,checks):
    rows=[];indicators=[]
    for node in spec.nodes:
        block=data[node.columns].to_numpy(float)
        if node.items==1 and spec.method=='REGRESSION':
            rows.append({'Construct':node.name,'Expected scale':'Observed variable','Alpha':np.nan,'Alpha target pass':True,'CR':np.nan,'AVE':np.nan,'Pass':True,'Note':'Single observed variable; reliability not applicable'})
            indicators.append({'Construct':node.name,'Item':node.columns[0],'Loading':np.nan,'CITC':np.nan});continue
        a=alpha(block)
        lam=np.array([loadings[c] for c in node.columns],float)
        theta=1-lam**2;cr=float(lam.sum()**2/(lam.sum()**2+theta.sum()));ave=float((lam**2).mean())
        alpha_ok=node.alpha_min<=a<=node.alpha_max if node.reliable else a<node.alpha_min
        checks.guard(node.name,'Alpha target',alpha_ok)
        if spec.method!='REGRESSION':
            for c,l in zip(node.columns,lam):
                checks.add(c,'Loading',abs(l),required=spec.criteria['Loading']['required'] and node.reliable)
            checks.add(node.name,'Composite reliability',cr,required=spec.criteria['Composite reliability']['required'] and node.reliable)
            checks.add(node.name,'AVE',ave,required=spec.criteria['AVE']['required'] and node.reliable)
        for i,c in enumerate(node.columns):
            r=stats.pearsonr(block[:,i],np.delete(block,i,axis=1).sum(axis=1)).statistic
            if node.reliable:checks.add(c,'CITC',r,required=True,threshold=.30,direction='min')
            indicators.append({'Construct':node.name,'Item':c,'Loading':lam[i],'CITC':r})
        rows.append({'Construct':node.name,'Expected scale':'PASS' if node.reliable else 'FAIL','Alpha':a,'Alpha min':node.alpha_min,'Alpha max':node.alpha_max,'Alpha target pass':alpha_ok,'CR':cr,'AVE':ave,'Min loading':float(abs(lam).min()),'Pass':bool(alpha_ok and all(r['Pass'] or not r['Required'] for r in checks.rows if r['Scope'] in [node.name]+node.columns))})
    return pd.DataFrame(rows),pd.DataFrame(indicators)


def discriminant(data,spec,checks,latent_corr=None):
    rows=[]
    for i,a in enumerate(spec.nodes):
        for b in spec.nodes[i+1:]:
            corr=data[a.columns+b.columns].corr().to_numpy();k=a.items
            between=abs(corr[:k,k:]).mean();aa=abs(corr[:k,:k][np.triu_indices(k,1)]).mean();bb=abs(corr[k:,k:][np.triu_indices(b.items,1)]).mean()
            htmt=float(between/np.sqrt(aa*bb)) if aa*bb>1e-12 else np.nan
            required=spec.criteria['HTMT']['required'] and a.reliable and b.reliable and spec.method!='REGRESSION'
            checks.add(f'{a.name} / {b.name}','HTMT',htmt,required=required)
            rows.append({'A':a.name,'B':b.name,'HTMT':htmt,'Pass':bool(not required or np.isfinite(htmt) and htmt<=spec.criteria['HTMT']['value'])})
    return pd.DataFrame(rows)


def terms(scores,spec,target_id):
    """Centered, standardized terms. Orthogonal powers residualize on lower powers."""
    nodes=spec.by_id;edges=spec.incoming(target_id);result={};raw={};transforms=[]
    for edge in sorted(edges,key=lambda e:({'linear':1,'quadratic':2,'cubic':3,'interaction':4}[e.kind],e.id)):
        x=standardize(scores[nodes[edge.source].name].to_numpy())
        if edge.kind=='linear':v=x
        elif edge.kind=='interaction':v=x*standardize(scores[nodes[edge.moderator].name].to_numpy())
        else:v=x**(2 if edge.kind=='quadratic' else 3)
        description='centered and standardized'
        if edge.kind in ('quadratic','cubic') and spec.polynomial_basis=='ORTHOGONAL':
            lower=[np.ones(len(x)),x]+([x*x] if edge.kind=='cubic' else [])
            basis=np.column_stack(lower);projection=np.linalg.lstsq(basis,v,rcond=None)[0];v=v-basis@projection
            description='orthogonal residualization on lower powers; projection='+','.join(f'{b:.8g}' for b in projection)
        result[edge.id]=standardize(v);raw[edge.id]=v
        transforms.append({'Path':edge.id,'Target':nodes[target_id].name,'Kind':edge.kind,'Transform':description})
    return pd.DataFrame(result,index=scores.index),pd.DataFrame(transforms)


def path_target(edge,beta,p,checks,scope,ci_low=None,ci_high=None):
    # A free path is estimated/reported but imposes no significance/sign/beta target.
    if edge.expected=='free':return
    if edge.expected=='null':
        checks.add(scope,'Null path p',p,required=True,threshold=checks.rules['Path p']['value'],direction='min')
        if ci_low is not None:checks.guard(scope,'Null bootstrap CI includes 0',ci_low<=0<=ci_high)
        return
    checks.add(scope,'Path p',p)
    checks.guard(scope,'Path sign',beta*edge.sign>0)
    checks.add(scope,'Abs beta min',abs(beta),required=True,threshold=edge.beta_min,direction='min')
    checks.add(scope,'Abs beta max',abs(beta),required=True,threshold=edge.beta_max,direction='max')
    if ci_low is not None and checks.rules['Path p']['required']:checks.guard(scope,'Bootstrap CI excludes 0',ci_low>0 or ci_high<0)


def range_checks(node,r2,checks):
    value=float(np.sqrt(max(0,r2))) if node.r_metric=='R' else float(r2)
    metric='R' if node.r_metric=='R' else 'R2'
    checks.add(node.name,metric+' min',value,required=True,threshold=node.target_min,direction='min')
    checks.add(node.name,metric+' max',value,required=True,threshold=node.target_max,direction='max')
    return {'R':float(np.sqrt(max(0,r2))),'R min':np.sqrt(node.r2_min),'R max':np.sqrt(node.r2_max),'Target metric':node.r_metric,'Target min':node.target_min,'Target max':node.target_max}

def ols(scores,spec,checks,apply_p=True):
    import statsmodels.api as sm
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from statsmodels.stats.diagnostic import het_breuschpagan
    from statsmodels.stats.stattools import durbin_watson
    rows=[];summary=[];blocks=[];transforms=[];designs=[]
    nodes=spec.by_id
    for node in spec.nodes:
        edges=spec.incoming(node.id)
        if not edges:continue
        x,transform=terms(scores,spec,node.id);transforms.append(transform)
        ordered=[e.id for e in edges];x=x[ordered];z=standardize(scores[node.name].to_numpy())
        design=sm.add_constant(x);values=design.to_numpy()
        if np.linalg.matrix_rank(values)<values.shape[1]:raise ValueError(f'{node.name}: predictors are linearly dependent; estimation is not possible.')
        fit=sm.OLS(z,design).fit();hc3=fit.get_robustcov_results(cov_type='HC3')
        summary.append({'Target':node.name,'R':np.sqrt(max(0,fit.rsquared)),'R2':fit.rsquared,'Adjusted R2':fit.rsquared_adj,'R2 min':node.r2_min,'R2 max':node.r2_max,'F p':fit.f_pvalue,'Durbin Watson':durbin_watson(fit.resid),'Breusch Pagan p':het_breuschpagan(fit.resid,values)[1]})
        summary[-1].update(range_checks(node,fit.rsquared,checks))
        for i,e in enumerate(edges,1):
            beta=float(fit.params.iloc[i]);p=float(fit.pvalues.iloc[i]);vif=float(variance_inflation_factor(values,i));scope=f'{nodes[e.source].name} → {node.name} [{e.kind}]'
            checks.add(scope,'VIF',vif,required=True,threshold=spec.vif_max,direction='max')
            if apply_p:
                path_target(e,beta,p,checks,scope)
                if e.expected=='significant':checks.add(scope,'HC3 path p',float(hc3.pvalues[i]),required=spec.criteria['Path p']['required'],threshold=spec.criteria['Path p']['value'],direction='max')
                if e.expected=='null':checks.add(scope,'HC3 null p',float(hc3.pvalues[i]),required=True,threshold=spec.criteria['Path p']['value'],direction='min')
            reduced=sm.OLS(z,design.drop(columns=e.id)).fit();f2=(fit.rsquared-reduced.rsquared)/(1-fit.rsquared)
            rows.append({'Path':e.id,'Source':nodes[e.source].name,'Target':node.name,'Kind':e.kind,'Moderator':nodes[e.moderator].name if e.moderator else '', 'Expected':e.expected,'Beta':beta,'p':p,'HC3 p':float(hc3.pvalues[i]),'VIF':vif,'f2 fixed scores':f2,'Block':e.block})
        previous=None;previous_r2=0.
        for block in sorted({e.block for e in edges}):
            cols=[e.id for e in edges if e.block<=block];sub=sm.OLS(z,sm.add_constant(x[cols])).fit()
            f,p,df=sub.compare_f_test(previous) if previous is not None else (np.nan,np.nan,np.nan)
            blocks.append({'Target':node.name,'Block':block,'Terms':', '.join(cols),'R2':sub.rsquared,'Adjusted R2':sub.rsquared_adj,'Delta R2':sub.rsquared-previous_r2,'F change':f,'p change':p,'df change':df})
            previous=sub;previous_r2=sub.rsquared
        renamed=x.rename(columns={e.id:f'{node.name}_{e.id}' for e in edges});designs.append(renamed)
    return {'Structural R2':pd.DataFrame(summary),'Paths':pd.DataFrame(rows),'Regression Blocks':pd.DataFrame(blocks),'Term Transforms':pd.concat(transforms,ignore_index=True),'Derived Terms':pd.concat(designs,axis=1)}


def indirect_chains(spec):
    chains=[]
    def visit(start,current,path):
        if len(path)>=2:chains.append((start,current,path[:]))
        if len(chains)>200:raise ValueError('Too many indirect paths (>200). Simplify the model before bootstrapping.')
        for e in spec.edges:
            if e.source==current and e.kind=='linear':visit(start,e.target,path+[e.id])
    for node in spec.nodes:visit(node.id,node.id,[])
    return chains


def indirect_table(spec,coefficients,samples=None):
    rows=[];by=spec.by_id
    for start,target,chain in indirect_chains(spec):
        estimate=float(np.prod([coefficients[e] for e in chain]));row={'Source':by[start].name,'Target':by[target].name,'Chain':' → '.join(chain),'Indirect beta':estimate,'Inference':'Point estimate only'}
        if samples is not None:
            v=np.prod(np.column_stack([samples[e] for e in chain]),axis=1);lo,hi=np.percentile(v,[2.5,97.5]);se=v.std(ddof=1)
            row.update({'SE bootstrap':se,'CI 2.5%':lo,'CI 97.5%':hi,'CI excludes 0':bool(lo>0 or hi<0),'Inference':'Full refit percentile bootstrap'})
        rows.append(row)
    return pd.DataFrame(rows,columns=['Source','Target','Chain','Indirect beta','Inference']+(['SE bootstrap','CI 2.5%','CI 97.5%','CI excludes 0'] if samples is not None else []))
