import json
"""Synthetic reflective scales and one-outcome teaching models.
All acceptance rules are evaluated on the generated observed data.
"""
from dataclasses import dataclass
import re
import warnings
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import linear_sum_assignment
from sklearn.decomposition import FactorAnalysis, PCA
from threadpoolctl import threadpool_limits

@dataclass(frozen=True)
class Construct:
    name: str
    items: int = 4
    accepted: bool = True
    outcome: bool = False
    @property
    def columns(self): return [f'{self.name}_{i+1}' for i in range(self.items)]

@dataclass
class QuantResult:
    data: pd.DataFrame
    scores: pd.DataFrame
    reports: dict
    model: str
    settings: dict


def alpha(x):
    x=np.asarray(x,float); k=x.shape[1]
    total=x.sum(axis=1).var(ddof=1)
    return k/(k-1)*(1-x.var(axis=0,ddof=1).sum()/total) if k>1 and total>1e-12 else np.nan


def reliability(data,groups):
    records=[]; item_rows=[]
    for g in groups:
        x=data[g.columns].to_numpy(float); a=alpha(x); citc=[]
        for i,c in enumerate(g.columns):
            rest=np.delete(x,i,axis=1)
            r=stats.pearsonr(x[:,i],rest.sum(axis=1)).statistic
            citc.append(r)
            item_rows.append({'Construct':g.name,'Item':c,'CITC':r,'Alpha if deleted':alpha(rest)})
        records.append({'Construct':g.name,'Expected':'PASS' if g.accepted else 'FAIL','Alpha':a,'Min CITC':min(citc),'Observed':'PASS' if a>=.7 and min(citc)>=.3 else 'FAIL'})
    return pd.DataFrame(records),pd.DataFrame(item_rows)


def efa(data,groups,extraction="PCA"):
    columns=[c for g in groups for c in g.columns]; x=data[columns].to_numpy(float)
    z=(x-x.mean(axis=0))/x.std(axis=0,ddof=1); n,p=z.shape; k=len(groups)
    corr=np.corrcoef(z,rowvar=False); inv=np.linalg.inv(corr)
    partial=-inv/np.sqrt(np.outer(np.diag(inv),np.diag(inv)))
    np.fill_diagonal(partial,0); r=corr.copy(); np.fill_diagonal(r,0)
    sq=r*r; psq=partial*partial
    kmo=sq.sum()/(sq.sum()+psq.sum()); item_kmo=sq.sum(axis=0)/(sq.sum(axis=0)+psq.sum(axis=0))
    sign,logdet=np.linalg.slogdet(corr)
    if sign<=0: raise ValueError('The correlation matrix is not positive definite.')
    chi=-(n-1-(2*p+5)/6)*logdet; bart=stats.chi2.sf(chi,p*(p-1)/2)
    if extraction=='PCA':
        from .rotation import varimax
        fitted=PCA(n_components=k,svd_solver='full').fit(z)
        loads=varimax(fitted.components_.T*np.sqrt(fitted.explained_variance_))
    else:
        fitted=FactorAnalysis(n_components=k,rotation='varimax',max_iter=2000,tol=1e-5,random_state=0,svd_method='lapack').fit(z)
        if fitted.n_iter_>=2000: raise ValueError('EFA did not converge.')
        loads=fitted.components_.T
    # Factor labels are arbitrary. Match factors to declared constructs without relabeling items.
    means=np.array([[abs(loads[[columns.index(c) for c in g.columns],f]).mean() for f in range(k)] for g in groups])
    rr,cc=linear_sum_assignment(-means)
    permutation=cc[np.argsort(rr)]; loads=loads[:,permutation]
    for f,g in enumerate(groups):
        if loads[[columns.index(c) for c in g.columns],f].mean()<0: loads[:,f]*=-1
    rows=[]; passed=True
    for i,c in enumerate(columns):
        own=next(j for j,g in enumerate(groups) if c in g.columns)
        ownload=abs(loads[i,own]); other=max(np.delete(abs(loads[i]),own),default=0.)
        communality=float((loads[i]**2).sum())
        ok=ownload>=.5 and ownload-other>=.2 and communality>=.3 and item_kmo[i]>=.5
        passed &= ok
        rows.append({'Item':c,'Construct':groups[own].name,'Own loading':ownload,'Max cross loading':other,'Gap':ownload-other,'Communality':communality,'Item KMO':item_kmo[i],'Pass':bool(ok),**{f'Factor {g.name}':loads[i,j] for j,g in enumerate(groups)}})
    eig=np.linalg.eigvalsh(corr)[::-1]
    explained=float((loads**2).sum()/p)
    retained_count=int((eig>1).sum())
    summary=pd.DataFrame([{'KMO':kmo,'Bartlett chi2':chi,'Bartlett p':bart,'Factors requested':k,'Eigenvalues > 1':retained_count,'Explained variance':explained,
                           'Pass':bool(passed and kmo>=.6 and bart<.05 and explained>=.5 and retained_count==k)}])
    return summary,pd.DataFrame(rows),pd.DataFrame({'Eigenvalue':eig})


def regression(scores,groups):
    import statsmodels.api as sm
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from statsmodels.stats.diagnostic import het_breuschpagan
    from statsmodels.stats.stattools import durbin_watson
    ygroup=next(g for g in groups if g.outcome); predictors=[g for g in groups if not g.outcome]
    x=scores[[g.name for g in predictors]]; y=scores[ygroup.name]
    z=(x-x.mean())/x.std(ddof=1); zy=(y-y.mean())/y.std(ddof=1)
    design=sm.add_constant(z); fit=sm.OLS(zy,design).fit()
    robust=fit.get_robustcov_results(cov_type='HC3')
    rows=[]
    for i,g in enumerate(predictors,1):
        vif=variance_inflation_factor(design.to_numpy(),i)
        pearson=stats.pearsonr(scores[g.name],y)
        p=float(fit.pvalues.iloc[i]); hp=float(robust.pvalues[i]); beta=float(fit.params.iloc[i])
        ok=(p<.05 and hp<.05 and beta>0) if g.accepted else (p>=.05 and hp>=.05)
        rows.append({'Construct':g.name,'Expected':'PASS' if g.accepted else 'FAIL','Beta standardized':beta,'p':p,'HC3 p':hp,'VIF':vif,'Pearson with Y':pearson.statistic,'Pearson p':pearson.pvalue,'Matches target':bool(ok and vif<5 and (pearson.statistic>0 and pearson.pvalue<.05 if g.accepted else pearson.pvalue>=.05))})
    bp=het_breuschpagan(fit.resid,design)[1]
    summary=pd.DataFrame([{'R':np.sqrt(fit.rsquared),'R2':fit.rsquared,'Adjusted R2':fit.rsquared_adj,'F':fit.fvalue,'F p':fit.f_pvalue,'Durbin Watson':durbin_watson(fit.resid),'Breusch Pagan p':bp,'Residual skew':stats.skew(fit.resid),'Residual excess kurtosis':stats.kurtosis(fit.resid)}])
    return summary,pd.DataFrame(rows)


def model_text(groups):
    kept=[g for g in groups if g.accepted]
    y=next(g for g in kept if g.outcome)
    return '\n'.join([f'{g.name} =~ '+ ' + '.join(g.columns) for g in kept]+[f'{y.name} ~ '+ ' + '.join(g.name for g in kept if not g.outcome)])


def sem_checks(data,groups,criteria=None,alpha_min=.7,alpha_max=.8,vif_max=2):
    # Quick Quanti defines its R² range on observed OLS, while Advanced CB uses latent R².
    from .criteria import validate_rules
    from .model_spec import ModelSpec,Node,Edge
    from .cbsem import fit_cb
    kept=[g for g in groups if g.accepted];y=next(g for g in kept if g.outcome)
    spec=ModelSpec(criteria=validate_rules(criteria),vif_max=vif_max,
                   nodes=[Node(g.name,g.name,g.items,alpha_min=alpha_min,alpha_max=alpha_max) for g in kept],
                   edges=[Edge('path'+g.name,g.name,y.name,beta_min=0,beta_max=1.5) for g in kept if not g.outcome])
    reports,passed,text,_=fit_cb(data,spec,check_r2=False)
    reports['SEM Reliability']=reports['Measurement'].copy()
    reports['SEM Discriminant']=reports['Discriminant'].copy()
    reports['SEM Paths']=reports['Paths'].copy()
    reports['SEM Acceptance']=reports.pop('Acceptance')
    return reports,passed,text


def validate(groups,n,r2_min,r2_max,scale,sem,max_attempts,alpha_min=.7,alpha_max=.8,vif_max=2,sem_criteria=None):
    if not isinstance(n,int) or not 100<=n<=10000: raise ValueError('Quantitative row count must be 100–10,000.')
    if not 2<=len(groups)<=10: raise ValueError('Use 2–10 constructs with exactly one outcome Y.')
    names=[g.name for g in groups]
    if len(set(names))!=len(names) or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*',x) for x in names):
        raise ValueError('Construct codes must be unique, start with a Latin letter and contain only letters/numbers (e.g. X1, Y).')
    if any(not isinstance(g.items,int) or not 3<=g.items<=10 for g in groups): raise ValueError('Each construct requires 3–10 indicators.')
    if sum(g.items for g in groups)>60: raise ValueError('Up to 60 indicators are supported.')
    if sum(g.outcome for g in groups)!=1: raise ValueError('Select exactly one outcome Y.')
    if any(g.outcome and not g.accepted for g in groups): raise ValueError('Outcome Y must be reliable for regression / SEM.')
    if not any(g.accepted and not g.outcome for g in groups): raise ValueError('At least one reliable predictor X is required.')
    if not np.isfinite([r2_min,r2_max]).all() or not 0<r2_min<r2_max<.9: raise ValueError('Use 0 < R² min < R² max < 0.90.')
    if scale not in ('LIKERT5','LIKERT7','CONTINUOUS'): raise ValueError('Invalid response scale.')
    if sem and n<200: raise ValueError('CB-SEM requires at least 200 rows.')
    if n<5*sum(g.items for g in groups): raise ValueError('Use at least 5 rows per indicator for EFA.')
    if not np.isfinite([alpha_min,alpha_max,vif_max]).all() or not .5<=alpha_min<alpha_max<.99 or not 1<vif_max<=10:
        raise ValueError('Use 0.5 ≤ alpha min < max < 0.99 and 1 < VIF max ≤10.')
    if sem:
        from .criteria import validate_rules,loading_floor
        validate_rules(sem_criteria)
    if not isinstance(max_attempts,int) or not 1<=max_attempts<=500: raise ValueError('Attempts must be 1–500.')


def generate_quantitative(groups,n=300,*,r2_min=.45,r2_max=.65,scale='LIKERT7',sem=False,seed=42,max_attempts=80,alpha_min=.7,alpha_max=.8,vif_max=2,extraction='PCA',sem_criteria=None,progress=None,cancel=None):
    validate(groups,n,r2_min,r2_max,scale,sem,max_attempts,alpha_min,alpha_max,vif_max,sem_criteria)
    if extraction not in ('PCA','ML'): raise ValueError('EFA extraction must be PCA or ML.')
    from .criteria import validate_rules,loading_floor
    rules=validate_rules(sem_criteria)
    rng=np.random.default_rng(seed); target=(r2_min+r2_max)/2
    kept=[g for g in groups if g.accepted]; good_x=[g for g in groups if g.accepted and not g.outcome]
    ygroup=next(g for g in groups if g.outcome)
    from .search_strategy import calibrated_noise,quality,mark_result,stopped_result
    last=''; candidate_errors=0;best=None;best_key=None;best_attempt=0;history=[]
    tuned_alpha=(alpha_min+alpha_max)/2
    for attempt in range(1,max_attempts+1):
        if cancel and cancel.is_set():
            if best is not None:return stopped_result(best,best_attempt,len(history),history)
            raise InterruptedError('Stopped before any candidate was generated.')
        if progress: progress(f'Quantitative: attempt {attempt}/{max_attempts}, validating data…')
        # Continuous latent model; ordinal output is validated after discretization.
        with threadpool_limits(limits=1):
            alpha_target=tuned_alpha
            latent_x=calibrated_noise(rng,n,columns=len(good_x))
            mean_reliability=lambda k:alpha_target
            attenuation=np.mean([mean_reliability(g.items) for g in good_x])*mean_reliability(ygroup.items)
            desired_latent=np.clip(target/attenuation*(1.06 if scale!='CONTINUOUS' else 1),.1,.88)
            signal=latent_x.sum(axis=1)/np.sqrt(len(good_x))
            ylatent=np.sqrt(desired_latent)*signal+np.sqrt(1-desired_latent)*calibrated_noise(rng,n,latent_x)[:,0]
            latent_map={g.name:latent_x[:,i] for i,g in enumerate(good_x)}; latent_map[ygroup.name]=ylatent
            observed={}
            for g in groups:
                errors=calibrated_noise(rng,n,latent_map.get(g.name),g.items)
                for j,c in enumerate(g.columns):
                    if g.accepted:
                        r_item=alpha_target/(g.items-alpha_target*(g.items-1))
                        if scale!='CONTINUOUS': r_item=min(.95,r_item*1.10)
                        if sem: r_item=max(r_item,min(.97,(loading_floor(rules)+.015)**2*(1.10 if scale!='CONTINUOUS' else 1)))
                        lam=np.sqrt(r_item)+rng.uniform(-.008,.008)
                        raw=lam*latent_map[g.name]+np.sqrt(1-lam**2)*errors[:,j]
                    else: raw=rng.normal(size=n)
                    if scale=='CONTINUOUS': observed[c]=4+.8*raw
                    else:
                        q=5 if scale=='LIKERT5' else 7
                        # Fixed normal thresholds, preserving genuine sample variability.
                        thresholds=stats.norm.ppf(np.linspace(0,1,q+1)[1:-1])
                        observed[c]=np.digitize(raw,thresholds)+1
            data=pd.DataFrame(observed)
            if (data.var()<=1e-10).any(): continue
            scores=pd.DataFrame({g.name:data[g.columns].mean(axis=1) for g in groups})
            rel,items=reliability(data,groups)
            rel['Matches target']=[bool(alpha_min<=r['Alpha']<=alpha_max and r['Min CITC']>=.3) if r['Expected']=='PASS' else bool(r['Alpha']<alpha_min) for _,r in rel.iterrows()]
            matches=bool(rel['Matches target'].all())
            actual_alpha=rel.loc[rel.Expected=='PASS','Alpha'].mean()
            tuned_alpha=float(np.clip(tuned_alpha+.6*((alpha_min+alpha_max)/2-actual_alpha),.5,.95))
            reg,coeff=regression(scores,groups)
            r2=float(reg.iloc[0].R2)
            reg_pass=bool(r2_min<=r2<=r2_max and coeff['Matches target'].all() and (coeff['VIF']<vif_max).all() and reg.iloc[0]['F p']<.05)
            target=float(np.clip(target+.5*(r2_max-.05*(r2_max-r2_min)-r2),.05,.9))
            try:
                blocks=[]
                for scope,subset in [('Independent X',[g for g in kept if not g.outcome]),('Dependent Y',[g for g in kept if g.outcome])]:
                    es,el,ev=efa(data,subset,extraction)
                    es.insert(0,'Scope',scope);el.insert(0,'Scope',scope);ev.insert(0,'Scope',scope)
                    blocks.append((es,el,ev))
                efas=pd.concat([b[0] for b in blocks],ignore_index=True)
                efal=pd.concat([b[1] for b in blocks],ignore_index=True)
                eigen=pd.concat([b[2] for b in blocks],ignore_index=True)
            except (ValueError,np.linalg.LinAlgError) as e:
                efas=pd.DataFrame([{'Pass':False,'Reason':str(e)}]);efal=pd.DataFrame();eigen=pd.DataFrame()
            efa_pass=bool(efas['Pass'].all())
            normal=pd.DataFrame({'Item':data.columns,'Skew':stats.skew(data,axis=0),'Excess kurtosis':stats.kurtosis(data,axis=0)})
            normal['Pass']=(normal.Skew.abs()<=2)&(normal['Excess kurtosis'].abs()<=7)
            retained_columns=[c for g in kept for c in g.columns]
            centered=data[retained_columns].to_numpy(dtype=float,copy=True);centered-=centered.mean(axis=0)
            covariance=np.cov(centered,rowvar=False,bias=True)
            distance=np.einsum('ij,jk,ik->i',centered,np.linalg.inv(covariance),centered)
            p=len(retained_columns);b2=float(np.mean(distance**2));mardia_z=(b2-p*(p+2))/np.sqrt(8*p*(p+2)/n)
            multivariate=pd.DataFrame([{'Items':p,'Mardia kurtosis':b2,'Mardia kurtosis z':mardia_z,'Mahalanobis p<.001 count':int((stats.chi2.sf(distance,p)<.001).sum()),'Use':'Diagnostic; not a gate for ordinal or large-p data'}])
            reports={'Cronbach':rel,'Item Reliability':items,'EFA Summary':efas,'EFA Loadings':efal,'EFA Eigenvalues':eigen,'Regression Summary':reg,'Regression Paths':coeff,'Construct Pearson':scores.corr(),'Normality':normal,'Multivariate Diagnostics':multivariate,
                     'Excluded Groups':pd.DataFrame([{'Construct':g.name,'Reason':'Expected low reliability; excluded from EFA/CFA/SEM; remains in OLS as null predictor'} for g in groups if not g.accepted],columns=['Construct','Reason'])}
            text=model_text(groups)
            sem_pass=True
            if sem:
                try:
                    with warnings.catch_warnings(record=True) as caught:
                        sem_reports,passed,text=sem_checks(data,groups,rules,alpha_min,alpha_max,vif_max)
                    reports.update(sem_reports)
                    reports['SEM Warnings']=pd.DataFrame({'Message':[str(w.message) for w in caught]})
                except (ValueError,np.linalg.LinAlgError) as e:
                    sem_pass=False;reports['SEM Warnings']=pd.DataFrame({'Message':[str(e)]});passed=False
                sem_pass=bool(passed and normal['Pass'].all())
            settings={'Synthetic':'SYNTHETIC DEMO','Rows':n,'Scale':scale,'Seed':seed,'Attempt accepted':attempt,'R2 min':r2_min,'R2 max':r2_max,'CB SEM':sem,
                      'Alpha min':alpha_min,'Alpha max':alpha_max,'CITC min':.3,'EFA rotation':extraction+' / Varimax; X and Y tested separately, rejected groups removed','EFA loading min':.5,'EFA loading gap min':.2,'EFA communality min':.3,'KMO min':.6,'Variance explained min':.5,
                      'Regression p max':.05,'VIF max':vif_max,'CFA loading min':rules['Loading']['value'],'Composite reliability min':rules['Composite reliability']['value'],'AVE min':rules['AVE']['value'],'HTMT max':rules['HTMT']['value'],'SEM acceptance rules':json.dumps(rules),
                      'Version':'5.1.1','R2 definition':'Observed construct-mean OLS; Advanced CB-SEM uses latent implied R2','SEM estimator':'semopy MLW (covariance ML); AMOS must be checked separately',
                      'SEM scope':'Reflective constructs, one outcome, direct positive paths from all retained X','Failed-group scope':'Cronbach/CITC fail, OLS p >= .05; excluded from retained EFA/CFA/SEM'}
            stages=[]
            def gate(scope,metric,actual,threshold,direction='min'):
                passed=bool(np.isfinite(actual) and (actual>=threshold if direction=='min' else actual<=threshold))
                stages.append({'Scope':scope,'Metric':metric,'Actual':actual,'Target':threshold,'Direction':direction,'Required':True,'Pass':passed,'Status':'PASS' if passed else 'FAIL'})
            for _,row in rel.iterrows():
                g=next(g for g in groups if g.name==row.Construct)
                gate(g.name,'Alpha min' if g.accepted else 'Expected low Alpha',row.Alpha,alpha_min if g.accepted else np.nextafter(alpha_min,-np.inf),'min' if g.accepted else 'max')
                if g.accepted:
                    gate(g.name,'Alpha max',row.Alpha,alpha_max,'max')
                    gate(g.name,'CITC',row['Min CITC'],.3)
            for i,row in efas.iterrows():gate(str(row.get('Scope',i)),'EFA',float(bool(row.Pass)),1)
            if not efal.empty:
                for _,row in efal.iterrows():gate(row.Item,'EFA indicator',float(bool(row.Pass)),1)
            gate(ygroup.name,'R2 min',r2,r2_min);gate(ygroup.name,'R2 max',r2,r2_max,'max')
            gate(ygroup.name,'OLS F p',float(reg.iloc[0]['F p']),np.nextafter(.05,-np.inf),'max')
            for _,row in coeff.iterrows():
                gate(str(row.iloc[0]),'OLS path target',float(bool(row['Matches target'])),1)
                gate(str(row.iloc[0]),'VIF',row.VIF,np.nextafter(vif_max,-np.inf),'max')
            if sem:
                if 'SEM Acceptance' in reports:stages.extend(reports['SEM Acceptance'].to_dict('records'))
                gate('CB-SEM','SEM evaluation',float(sem_pass),1)
                for _,row in normal.iterrows():gate(row.Item,'Normality',float(bool(row.Pass)),1)
            reports['Acceptance']=pd.DataFrame(stages)
            passed=matches and efa_pass and reg_pass and sem_pass
            result=QuantResult(data,scores,reports,text,settings);key=quality(reports)
            history.append({'Attempt':attempt,'R':key[0],'Required failed checks':-key[1],'Passed':passed})
            if best_key is None or key>best_key:best,best_key,best_attempt=result,key,attempt
            if passed:return mark_result(result,True,attempt,attempt,history)
    if best is not None:return mark_result(best,False,best_attempt,max_attempts,history)
    raise RuntimeError('Generation produced no nonconstant candidate; check input or generation diagnostics.')
