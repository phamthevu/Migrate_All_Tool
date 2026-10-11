import json,warnings,copy
import numpy as np
import pandas as pd
from scipy.stats import norm,skew,kurtosis
from threadpoolctl import threadpool_limits
from .quantitative import QuantResult
from .criteria import Checks,loading_floor,validate_rules
from .analysis_common import standardize,terms,measurement,discriminant,ols,indirect_table,indirect_chains
from .search_strategy import calibrated_noise,quality,mark_result,stopped_result
from .cbsem import fit_cb,syntax
from .plssem import evaluate_pls


def simulate(spec,rng,targets,alpha_targets=None,edge_targets=None):
    by=spec.by_id;latent={};truth=[]
    for id in spec.topological():
        node=by[id];edges=spec.incoming(id)
        if not edges:
            basis=np.column_stack(list(latent.values())) if latent else None
            latent[node.name]=calibrated_noise(rng,spec.rows,basis)[:,0];continue
        scores=pd.DataFrame(latent);x,_=terms(scores,spec,id);x=x[[e.id for e in edges]]
        w=np.array([0 if e.expected=='null' else (edge_targets or {}).get(e.id,max(.05,(e.beta_min+min(.70,e.beta_max))/2))*e.sign for e in edges])
        signal=x.to_numpy()@w;variance=np.var(signal)
        if variance<1e-12:
            y=calibrated_noise(rng,spec.rows,x.to_numpy())[:,0]
        else:
            w=w*np.sqrt(targets[id]/variance)
            y=x.to_numpy()@w+np.sqrt(1-targets[id])*calibrated_noise(rng,spec.rows,x.to_numpy())[:,0]
        latent[node.name]=standardize(y)
        for e,b in zip(edges,w):truth.append({'Path':e.id,'Source':by[e.source].name,'Target':node.name,'Kind':e.kind,'Generating beta':b})
    data={};floor=loading_floor(spec.criteria) if spec.method!='REGRESSION' else 0.
    for n in spec.nodes:
        desired=(alpha_targets or {}).get(n.id,(n.alpha_min+n.alpha_max)/2)
        r=desired/(n.items-desired*(n.items-1))
        if spec.scale!='CONTINUOUS':r=min(.96,r*1.10)
        # A little safety above an enabled AVE/loading boundary; reported estimates decide acceptance.
        lam=min(.985,max(np.sqrt(r),floor+.015 if floor else 0.))
        errors=calibrated_noise(rng,spec.rows,latent[n.name],n.items)
        for j,c in enumerate(n.columns):
            l=np.clip(lam+rng.uniform(-.008,.008),.1,.985)
            raw=l*latent[n.name]+np.sqrt(1-l*l)*errors[:,j] if n.reliable else rng.normal(size=spec.rows)
            if spec.scale=='CONTINUOUS':data[c]=4+.8*raw
            else:
                q=5 if spec.scale=='LIKERT5' else 7;threshold=norm.ppf(np.linspace(0,1,q+1)[1:-1]);data[c]=np.digitize(raw,threshold)+1
    return pd.DataFrame(data),pd.DataFrame(truth)


def cb_indirect_bootstrap(data,spec,coef,rng,progress,cancel):
    chains=indirect_chains(spec)
    if not chains or not spec.bootstrap_indirect:return indirect_table(spec,coef),None
    samples={e.id:[] for e in spec.edges};failed=0
    for b in range(spec.bootstrap):
        if cancel and cancel.is_set():raise InterruptedError('CB-SEM bootstrap cancelled.')
        ids=rng.integers(0,len(data),len(data))
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',RuntimeWarning)
                coefficients=fit_cb(data.iloc[ids].reset_index(drop=True),spec,point_only=True)
            if not all(np.isfinite(v) for v in coefficients.values()):raise ValueError('Nonfinite bootstrap estimate.')
        except (ValueError,np.linalg.LinAlgError):failed+=1;continue
        for key in samples:samples[key].append(coefficients[key])
        if progress and (b%10==0 or b+1==spec.bootstrap):progress(f'CB-SEM indirect bootstrap {b+1}/{spec.bootstrap}')
    if failed>.05*spec.bootstrap:raise ValueError('More than 5% of CB bootstrap fits failed; confidence intervals are not accepted.')
    return indirect_table(spec,coef,samples),pd.DataFrame([{'Requested':spec.bootstrap,'Successful':spec.bootstrap-failed,'Use':'Indirect effects percentile 95%; not an acceptance gate'}])


def generate_advanced(spec,progress=None,cancel=None):
    spec.validate();spec.criteria=validate_rules(spec.criteria)
    inference_spec=copy.deepcopy(spec);inference_spec.bootstrap=min(spec.bootstrap,100)
    stream=np.random.SeedSequence(spec.seed);generation_stream,bootstrap_stream=stream.spawn(2)
    rng=np.random.default_rng(generation_stream);boot_rng=np.random.default_rng(bootstrap_stream)
    targets={}
    by=spec.by_id
    for node in spec.nodes:
        if not spec.incoming(node.id):continue
        desired=(node.r2_min+node.r2_max)/2
        attenuation=1. if spec.method=='CB-SEM' else ((node.alpha_min+node.alpha_max)/2)*np.mean([(by[p].alpha_min+by[p].alpha_max)/2 for p in spec.parents(node.id)])
        targets[node.id]=float(np.clip(desired/attenuation,.02,.95))
    last='';last_table=None;best=None;best_key=None;best_attempt=0;history=[];confirmations=0
    # Limit expensive bootstrap confirmations; the final best candidate is still inferred.
    confirmation_limit=3
    alpha_targets={n.id:(n.alpha_min+n.alpha_max)/2 for n in spec.nodes}
    edge_targets={e.id:max(.05,(e.beta_min+min(.70,e.beta_max))/2) for e in spec.edges}
    for attempt in range(1,spec.attempts+1):
        if cancel and cancel.is_set():
            if best is not None:return stopped_result(best,best_attempt,len(history),history)
            raise InterruptedError('Stopped before any candidate was generated.')
        if progress:progress(f'{spec.method}: attempt {attempt}/{spec.attempts} • point checks (no bootstrap)')
        with threadpool_limits(limits=1):
            data,truth=simulate(spec,rng,targets,alpha_targets,edge_targets)
            scores=pd.DataFrame({n.name:data[n.columns].mean(axis=1) for n in spec.nodes})
            checks=Checks(spec.criteria)
            # Update measurement parameters from observed reliability, retaining every candidate.
            from .quantitative import alpha
            alphas={n.id:alpha(data[n.columns]) for n in spec.nodes}
            for n in spec.nodes:
                if n.reliable:
                    alpha_targets[n.id]=float(np.clip(alpha_targets[n.id]+.6*((n.alpha_min+n.alpha_max)/2-alphas[n.id]),.5,.96))
            try:
                if spec.method=='CB-SEM':reports,passed,text,coef=fit_cb(data,spec)
                elif spec.method=='PLS-SEM':
                    reports,screen_passed,scores=evaluate_pls(data,spec,boot_rng,progress,cancel,point_only=True)
                    passed=False
                    if screen_passed and confirmations<confirmation_limit:
                        confirmations+=1
                        if progress:progress(f'PLS-SEM: candidate {attempt} passed point checks; bootstrap confirmation {confirmations}/{confirmation_limit}')
                        reports,passed,scores=evaluate_pls(data,inference_spec,boot_rng,lambda message:progress(f'Attempt {attempt}/{spec.attempts} • {message}') if progress else None,cancel,always_infer=True)
                    text=syntax(spec);coef=dict(zip(reports['Paths'].Path,reports['Paths'].Beta))
                else:
                    loads={c:float(data[c].corr(scores[n.name])) for n in spec.nodes for c in n.columns}
                    rel,items=measurement(data,spec,loads,checks);reports=ols(scores,spec,checks)
                    reports.update({'Measurement':rel,'Indicator Quality':items,'Acceptance':checks.frame()})
                    coef=dict(zip(reports['Paths'].Path,reports['Paths'].Beta));reports['Indirect Effects']=indirect_table(spec,coef)
                    text='\n'.join(f'{n.name} ~ '+ ' + '.join(f'{e.id}:{by[e.source].name} [{e.kind}]' for e in spec.incoming(n.id)) for n in spec.nodes if spec.incoming(n.id));passed=checks.passed
            except InterruptedError:
                passed=False;text=syntax(spec);coef={}
            except (ValueError,np.linalg.LinAlgError) as e:
                last=str(e);passed=False;coef={};text=syntax(spec)
                reports={'Acceptance':pd.DataFrame([{'Scope':spec.method,'Metric':'Model estimation','Required':True,'Pass':False,'Status':'FAIL'}]),
                    'Estimation Errors':pd.DataFrame([{'Reason':str(e)}]),
                    'Structural R2':pd.DataFrame([{'Target':n.name,'R':np.nan,'R2':np.nan} for n in spec.nodes if spec.incoming(n.id)])}
            path_report=reports.get('Paths',pd.DataFrame())
            if 'Beta' in path_report:
                for e in spec.edges:
                    found=path_report[path_report.Path==e.id]
                    if e.expected=='significant' and not found.empty:
                        actual=abs(float(found.Beta.iloc[0]))
                        if actual>1e-8 and not e.beta_min<=actual<=e.beta_max:
                            desired_beta=(e.beta_min+e.beta_max)/2
                            edge_targets[e.id]=float(np.clip(edge_targets[e.id]*(desired_beta/actual)**.5,.01,2.))
            r2_report=reports.get('Structural R2',pd.DataFrame())
            for _,row in r2_report.iterrows():
                node=next(n for n in spec.nodes if n.name==row.Target)
                desired=node.r2_max-.05*(node.r2_max-node.r2_min)
                if np.isfinite(row.R2) and not node.r2_min<=row.R2<=node.r2_max:targets[node.id]=float(np.clip(targets[node.id]+.5*(desired-row.R2),.02,.95))
            if spec.method=='CB-SEM' and coef and passed and confirmations<confirmation_limit:
                confirmations+=1
                try:
                    reports['Indirect Effects'],boot=cb_indirect_bootstrap(data,inference_spec,coef,boot_rng,lambda message:progress(f'Attempt {attempt}/{spec.attempts} • {message}') if progress else None,cancel)
                    if boot is not None:reports['Bootstrap']=boot
                except InterruptedError:
                    passed=False
                    reports['Inference Status']=pd.DataFrame([{'Status':'PENDING','Reason':'Indirect bootstrap stopped'}])
                except ValueError as e:
                    passed=False
                    reports['Bootstrap']=pd.DataFrame([{'Status':'FAILED','Reason':str(e)}])
                    reports['Acceptance']=pd.concat([reports['Acceptance'],pd.DataFrame([{'Scope':'CB-SEM','Metric':'Indirect bootstrap','Required':True,'Pass':False,'Status':'FAIL'}])],ignore_index=True)
            if spec.method=='CB-SEM' and coef and 'Indirect Effects' not in reports:
                reports['Indirect Effects']=indirect_table(spec,coef)
                if spec.bootstrap_indirect and indirect_chains(spec) and 'Bootstrap' not in reports:
                    passed=False
                    reports['Inference Status']=pd.DataFrame([{'Status':'PENDING','Reason':'Indirect bootstrap deferred until final selection'}])
            reports['Construct Pearson']=scores.corr();reports['Generating Parameters']=truth
            reports['Normality']=pd.DataFrame({'Item':data.columns,'Skew':skew(data,axis=0),'Excess kurtosis':kurtosis(data,axis=0)})
            reports['Model Nodes']=pd.DataFrame([vars(n) for n in spec.nodes]);reports['Model Edges']=pd.DataFrame([vars(e) for e in spec.edges])
            settings={'Synthetic':'SYNTHETIC DEMO','Version':'5.1.1','Bootstrap requested':spec.bootstrap,'Bootstrap used':inference_spec.bootstrap,'Method':spec.method,'CB SEM':spec.method=='CB-SEM','Scale':spec.scale,'Rows':spec.rows,'Seed':spec.seed,'Effective seed':stream.entropy,'Attempt accepted':attempt,'Model JSON':json.dumps(spec.to_dict(),ensure_ascii=False),'Model fingerprint':spec.fingerprint(),
                      'R2 definition':'Implied latent R2' if spec.method=='CB-SEM' else 'Converged PLS composite R2' if spec.method=='PLS-SEM' else 'OLS on observed construct means; per equation',
                      'PLS inference':'Ordinary PLS Mode A/path weighting; full-refit bootstrap; not PLSc/SmartPLS equivalence','Regression basis':spec.polynomial_basis,
                      'Inference scope':'Direct path gates; indirect CI descriptive; no omitted-path/causality guarantee','Validation rules':json.dumps(spec.criteria)}
            result=QuantResult(data,scores,reports,text,settings)
            key=quality(reports);history.append({'Attempt':attempt,'R':key[0],'Required failed checks':-key[1],'Passed':passed})
            if best_key is None or key>best_key:best,best_key,best_attempt=result,key,attempt
            if cancel and cancel.is_set():return stopped_result(best,best_attempt,attempt,history)
            if passed:return mark_result(result,True,attempt,attempt,history)
    if best is not None:
        if progress:progress(f'{spec.method}: search finished; finalizing best candidate {best_attempt} with R={best_key[0]:.3f}')
        try:
            with threadpool_limits(limits=1):
                if spec.method=='PLS-SEM' and 'Inference Status' in best.reports:
                    reports,passed,scores=evaluate_pls(best.data,inference_spec,boot_rng,lambda message:progress(f'Final candidate {best_attempt} • {message}') if progress else None,cancel,always_infer=True)
                    best.reports.update(reports);best.scores=scores
                    best.reports.pop('Inference Status',None)
                    best.reports['Construct Pearson']=scores.corr()
                elif spec.method=='CB-SEM' and 'Inference Status' in best.reports:
                    coef=dict(zip(best.reports['Paths'].Path,best.reports['Paths'].Beta))
                    try:
                        indirect,boot=cb_indirect_bootstrap(best.data,inference_spec,coef,boot_rng,lambda message:progress(f'Final candidate {best_attempt} • {message}') if progress else None,cancel)
                        best.reports['Indirect Effects']=indirect
                        if boot is not None:best.reports['Bootstrap']=boot
                    except ValueError as e:
                        best.reports['Bootstrap']=pd.DataFrame([{'Status':'FAILED','Reason':str(e)}])
                        best.reports['Acceptance']=pd.concat([best.reports['Acceptance'],pd.DataFrame([{'Scope':'CB-SEM','Metric':'Indirect bootstrap','Required':True,'Pass':False,'Status':'FAIL'}])],ignore_index=True)
                    best.reports.pop('Inference Status',None)
        except InterruptedError:
            return stopped_result(best,best_attempt,len(history),history)
        acceptance=best.reports['Acceptance']
        passed=bool((acceptance.Pass | ~acceptance.Required).all())
        # Inference failures remain visible; only final assessed results may be marked PASS.
        best.settings['Bootstrap confirmations during search']=confirmations
        best.settings['Search ranking scope']='Point checks for screened candidates; complete inference on final result'
        best.reports['Final Selection']=pd.DataFrame([{'Attempt':best_attempt,'R':quality(best.reports)[0],'Required failed checks':-quality(best.reports)[1],'Passed':passed}])
        return mark_result(best,passed,best_attempt,spec.attempts,history)
    raise RuntimeError('Generation produced no candidate; check input or generation diagnostics.')
