"""Shared-profile generation with observed, all-pair agreement checks."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.stats import rankdata
from .config_loader import validate_scale
from .generator import parse_advance
from . import ahp, dematel

@dataclass
class BatchResult:
    answers: list
    numeric: list
    factor_scores: pd.DataFrame
    summary: pd.DataFrame
    pearson: pd.DataFrame
    spearman: pd.DataFrame
    settings: dict
    cell_pearson: pd.DataFrame | None = None


def unit(v):
    v=np.asarray(v,float)
    if not v.size:return None
    v=v-v.mean()
    norm=np.linalg.norm(v)
    return v/norm if norm>1e-12 else None


def correlation_table(vectors,names,rank=False):
    x=np.array([rankdata(v) if rank else v for v in vectors],float)
    centered=x-x.mean(axis=1,keepdims=True)
    norms=np.linalg.norm(centered,axis=1)
    values=centered@centered.T/np.where(np.outer(norms,norms)>1e-12,np.outer(norms,norms),np.nan)
    return pd.DataFrame(np.clip(values,-1,1),index=names,columns=names)


def generate_batch(rows, cols, fuzzy_df, adv_df, mode, output, count=5, *, seed=42,
                   weights=None, noise=.15, max_cr=.1, discrete=True,
                   consensus=.96, min_pearson=.6, min_spearman=.6,
                   attempts=250, order_ranks=None, min_order=.8, max_pearson=1., max_spearman=1., progress=None, cancel=None, dematel_profiles=None):
    if not isinstance(count,int) or not 1<=count<=1000: raise ValueError('Answer count must be 1–1,000.')
    if not np.isfinite([consensus,min_pearson,max_pearson,min_spearman,max_spearman]).all() or not 0<=consensus<=1 or not 0<=min_pearson<=max_pearson<=1 or not 0<=min_spearman<=max_spearman<=1:
        raise ValueError('Consensus must be in [0,1]; Pearson / Spearman require 0 ≤ min ≤ max ≤1.')
    if mode not in ('NORMAL','DELPHI','TOPSIS','DEMATEL','AHP'): raise ValueError('Invalid method.')
    if mode in ('DEMATEL','AHP') and list(rows)!=list(cols): raise ValueError('AHP / DEMATEL requires matching axes in the same order.')
    if not rows or not cols: raise ValueError('Row and column names are required.')
    if len(rows)<2 and count>1 and (min_pearson>0 or min_spearman>0 or max_pearson<1 or max_spearman<1):
        raise ValueError('At least 2 rows / criteria are needed to check rank agreement.')
    if len(set(rows))!=len(rows) or len(set(cols))!=len(cols): raise ValueError('Row / column names must be unique.')
    if output not in ('LING','FUZZY','CRISP'): raise ValueError('Invalid output format.')
    if order_ranks is not None:
        order_ranks=np.asarray(order_ranks,float)
        if order_ranks.shape!=(len(rows),) or set(order_ranks)!=set(range(1,len(rows)+1)) or not 0<=min_order<=1:
            raise ValueError('Order ranks must be 1..row count and thresholds in [0,1].')
    if not isinstance(attempts,int) or attempts<1:raise ValueError('Attempts must be positive.')
    rng=np.random.default_rng(seed)
    m,n=len(rows),len(cols)
    base_weights=np.ones(m) if weights is None else np.asarray(weights,float)
    if base_weights.shape!=(m,) or not np.isfinite(base_weights).all() or (base_weights<=0).any():
        raise ValueError('Row weights must be positive, finite and match the row count.')
    base_weights=base_weights/base_weights.sum()
    if mode=='AHP' and base_weights.max()/base_weights.min()>9+1e-10: raise ValueError('AHP max/min weight ratio must be ≤9.')
    ar,ac=parse_advance(adv_df,rows,cols)
    if order_ranks is not None and mode!='AHP':
        for high in [r for r in rows if ar.get(r)=='High']:
            for low in [r for r in rows if ar.get(r)=='Low']:
                if order_ranks[rows.index(high)]>order_ranks[rows.index(low)]:
                    raise ValueError(f'Order conflicts with Advance: {high} High is ranked below {low} Low. Correct Order / Advance or disable Order.')
    scale=validate_scale(fuzzy_df)
    levels=sorted(scale.Level.unique()); third=max(1,int(np.ceil(len(levels)/3)))
    # Each row has a shared tendency; each cell also has a shared preference.
    row_profile=rng.normal(size=m) if order_ranks is None else np.linspace(-1.6,1.6,m)[(m-order_ranks).astype(int)]
    if not np.allclose(base_weights,base_weights[0]): row_profile+=2*unit(np.log(base_weights))*np.sqrt(m)
    shared=(.8*row_profile[:,None]+.25*rng.normal(size=(1,n))+.35*rng.normal(size=(m,n)))/np.sqrt(.8**2+.25**2+.35**2)
    if mode=='DEMATEL' and dematel_profiles is not None:
        if min(levels)<0:raise ValueError('DEMATEL scale levels must be nonnegative.')
        prominence,role=dematel.profile_arrays(rows,dematel_profiles,base_weights)
        # Source activity and target receptivity both contribute to each directed edge.
        shared=.65*(prominence[:,None]+prominence[None,:])+.8*(role[:,None]-role[None,:])+.3*rng.normal(size=(m,n))
        order_ranks=None  # DEMATEL uses loose groups, never an exact ranking gate.
    cell_scales={}
    for i,r in enumerate(rows):
        for j,c in enumerate(cols):
            prefer=ar.get(r) or ac.get(c)
            allowed=levels[-third:] if prefer=='High' else levels[:third] if prefer=='Low' else levels
            sub=scale[scale.Level.isin(allowed)].sort_values(['Level','Lingustic'])
            p=sub.Probability.to_numpy(float)
            if p.sum()<=0: raise ValueError(f'Probability in group {prefer} sums to 0.')
            cell_scales[i,j]=(sub.reset_index(drop=True),np.cumsum(p/p.sum()))
    answers=[];numeric=[];scores=[];cell_units=[];score_units=[];rank_units=[];log=[]
    pearson_required=min_pearson>0 or max_pearson<1
    spearman_required=min_spearman>0 or max_spearman<1
    bounded=max_pearson<1 or max_spearman<1
    def correlations(vector,previous):
        return np.array([float(vector@v) if vector is not None and v is not None else np.nan for v in previous])
    def range_check(values,low,high,required):
        if not required or not len(values):return True,0.
        if not np.isfinite(values).all():return False,1.
        deviation=np.maximum(low-values,0)+np.maximum(values-high,0)
        return bool(np.max(deviation)<=1e-10),float(deviation.mean())
    for a in range(count):
        best=None;best_key=None;effective_consensus=float(np.clip(consensus,.001,.999));judgment_noise=noise*.7 if bounded else noise
        for attempt in range(attempts):
            if cancel and cancel.is_set():raise InterruptedError('Cancelled; no output file written.')
            if progress and (attempt%20==0):progress(f'MCDM: answer {a+1}/{count} • attempt {attempt+1}/{attempts} • range checks')
            stats={}
            if mode=='AHP':
                # Respondent preferences vary, while reciprocal judgments and CR remain checked.
                spread=(.85*np.sqrt(1-effective_consensus)) if bounded else 0.
                logw=np.log(base_weights)+spread*rng.normal(size=m)
                if np.ptp(logw)>np.log(9):logw=(logw-logw.mean())*np.log(9)/np.ptp(logw)
                respondent_weights=np.exp(logw-logw.max());respondent_weights/=respondent_weights.sum()
                mat,stats=ahp.generate(rows,respondent_weights,rng,judgment_noise,max_cr,discrete,attempts=30)
                stats['respondent_target_weights']=respondent_weights;stats['target_weights']=base_weights
                stats['max_weight_error']=float(np.max(abs(stats['weights']-base_weights)))
                score=stats['weights'];cells=np.log(mat.to_numpy()[np.triu_indices(m,1)]);shown=ahp.render(mat,output)
            else:
                # Row-level heterogeneity prevents averaging many columns into identical ranks.
                respondent_noise=(.45*rng.normal(size=(m,1))+.45*rng.normal(size=(1,n))+.8*rng.normal(size=(m,n))) if mode=='DEMATEL' and dematel_profiles is not None else .8*rng.normal(size=(m,1))+.6*rng.normal(size=(m,n))
                z=np.sqrt(effective_consensus)*shared+np.sqrt(1-effective_consensus)*respondent_noise
                u=ndtr(z);values=np.zeros((m,n));labels=[]
                for i,r in enumerate(rows):
                    line=[]
                    for j,c in enumerate(cols):
                        if mode=='DEMATEL' and i==j:
                            line.append('(0; 0; 0)' if output=='FUZZY' else 0);continue
                        sub,cdf=cell_scales[i,j]
                        item=sub.iloc[min(int(np.searchsorted(cdf,u[i,j],side='right')),len(sub)-1)]
                        values[i,j]=item.Level
                        line.append(item.Fuzzy if output=='FUZZY' else item.Lingustic if output=='LING' else float(item.Level))
                    labels.append(line)
                mat=pd.DataFrame(values,index=rows,columns=cols);shown=pd.DataFrame(labels,index=rows,columns=cols)
                mask=~np.eye(m,dtype=bool) if mode=='DEMATEL' else np.ones((m,n),bool)
                cells=values[mask];score=values.sum(axis=1)/(n-1 if mode=='DEMATEL' and n>1 else n)
                if mode=='DEMATEL':
                    try:
                        report=dematel.evaluate(values,rows)
                        if dematel_profiles is not None:score=report['R+C'].to_numpy()
                        stats['DEMATEL results']=report;stats['DEMATEL target failures']=dematel.target_checks(report,dematel_profiles)
                    except ValueError:
                        stats['DEMATEL target failures']=len(rows)*2+1
            cu,su,ru=unit(cells),unit(score),unit(rankdata(score))
            order_corr=float(ru@unit(-order_ranks)) if order_ranks is not None and ru is not None and unit(-order_ranks) is not None else np.nan
            cell_values=correlations(cu,cell_units);factor_values=correlations(su,score_units);rank_values=correlations(ru,rank_units)
            gates=[range_check(cell_values,min_pearson,max_pearson,pearson_required and len(cells)>=2),
                   range_check(factor_values,min_pearson,max_pearson,pearson_required),
                   range_check(rank_values,min_spearman,max_spearman,spearman_required)]
            order_pass=order_ranks is None or min_order<=0 or (np.isfinite(order_corr) and order_corr>=min_order-1e-10)
            gates.append((order_pass,0. if order_pass else 1. if not np.isfinite(order_corr) else min_order-order_corr))
            varying=not (count>1 and ((pearson_required and (su is None or (len(cells)>=2 and cu is None))) or (spearman_required and ru is None)))
            gates.append((varying,0. if varying else 1.));cr_pass=stats.get('CR',0)<=max_cr+1e-12
            gates.append((cr_pass,max(0.,stats.get('CR',0)-max_cr)))
            failed=sum(not ok for ok,_ in gates)+stats.get('DEMATEL target failures',0);distance=sum(d for _,d in gates)+stats.get('DEMATEL target failures',0)
            duplicate=any(np.array_equal(mat.to_numpy(),previous.to_numpy()) for previous in numeric)
            if bounded and duplicate:failed+=1;distance+=1.
            key=(-distance,-failed)
            def extrema(v):return (float(v.min()),float(v.max())) if len(v) and np.isfinite(v).all() else (np.nan,np.nan)
            cell_min,cell_max=extrema(cell_values);factor_min,factor_max=extrema(factor_values);rank_min,rank_max=extrema(rank_values)
            record={'Answer':f'Ans {a+1}','Attempts':attempt+1,'Selected attempt':attempt+1,
                'Min cell Pearson vs earlier':cell_min,'Max cell Pearson vs earlier':cell_max,
                'Min factor Pearson vs earlier':factor_min,'Max factor Pearson vs earlier':factor_max,
                'Min factor Spearman vs earlier':rank_min,'Max factor Spearman vs earlier':rank_max,
                'Pearson min target':min_pearson,'Pearson max target':max_pearson,'Spearman min target':min_spearman,'Spearman max target':max_spearman,
                'DEMATEL target failures':stats.get('DEMATEL target failures',0),'CI':stats.get('CI',np.nan),'CR':stats.get('CR',np.nan),'Order Spearman':order_corr,'Max weight error':stats.get('max_weight_error',np.nan),
                'Duplicate earlier answer':duplicate,'Range deviation':distance,'Required failed checks':failed,'Pass':failed==0,
                'Effective consensus':effective_consensus,'Cell Pearson range pass':gates[0][0],'Factor Pearson range pass':gates[1][0],'Spearman range pass':gates[2][0],'Order pass':order_pass,'CR pass':cr_pass,'Variation pass':varying}
            if best_key is None or key>best_key:best,best_key=(shown,mat,score,cu,su,ru,stats,record),key
            if not failed:break
            # Two-sided feedback: over-consistency requires more respondent variation.
            over=(len(cell_values) and np.isfinite(cell_max) and cell_max>max_pearson+1e-10) or (np.isfinite(factor_max) and factor_max>max_pearson+1e-10) or (np.isfinite(rank_max) and rank_max>max_spearman+1e-10) or (bounded and duplicate)
            under=(np.isfinite(cell_min) and cell_min<min_pearson-1e-10) or (np.isfinite(factor_min) and factor_min<min_pearson-1e-10) or (np.isfinite(rank_min) and rank_min<min_spearman-1e-10)
            if mode=='AHP':
                if np.isfinite(cell_min) and cell_min<min_pearson:judgment_noise*=.85
                elif np.isfinite(cell_max) and cell_max>max_pearson:judgment_noise=min(noise,judgment_noise*1.15+.005)
                over=(np.isfinite(factor_max) and factor_max>max_pearson+1e-10) or (np.isfinite(rank_max) and rank_max>max_spearman+1e-10) or (bounded and duplicate)
                under=(np.isfinite(factor_min) and factor_min<min_pearson-1e-10) or (np.isfinite(rank_min) and rank_min<min_spearman-1e-10)
            step=.04
            if over and not under:effective_consensus-=step
            elif under and not over:effective_consensus+=step
            else:effective_consensus+=rng.uniform(-.06,.06)
            effective_consensus=float(np.clip(effective_consensus,.02,.98 if bounded else .999))
        shown,mat,score,cu,su,ru,stats,record=best
        if record['Required failed checks']:record['Attempts']=attempts
        shown.attrs.update(stats);answers.append(shown);numeric.append(mat);scores.append(score)
        cell_units.append(cu);score_units.append(su);rank_units.append(ru);log.append(record)
        if progress:progress(f'MCDM: answer {a+1}/{count} • '+('ranges passed' if record['Pass'] else 'best effort; review range failures'))
    names=[f'Ans {i+1}' for i in range(count)]
    settings={'Synthetic':True,'Version':'5.3.1','Required criteria passed':all(r['Pass'] for r in log),'Best effort':not all(r['Pass'] for r in log),'Selection policy':'Smallest range deviation then fewest failed checks; per answer','Mode':mode,'Output':output,'Seed':seed,'Consensus':consensus,'Min Pearson':min_pearson,'Max Pearson':max_pearson,'Min Spearman':min_spearman,'Max Spearman':max_spearman,'AHP noise':noise,'Max AHP CR':max_cr,'Discrete Saaty':discrete,'Order ranks':order_ranks.tolist() if order_ranks is not None else None,'Min Order Spearman':min_order if order_ranks is not None else None,
              'DEMATEL profiles':dematel_profiles if mode=='DEMATEL' else None,'DEMATEL methodology':'Scalar DEMATEL on configured Level, max row/column normalization; not spherical-fuzzy UDF calculations' if mode=='DEMATEL' else None,'Factor score':'DEMATEL total prominence R+C' if mode=='DEMATEL' and dematel_profiles is not None else 'AHP eigenvector weight' if mode=='AHP' else 'Row mean of Level, excluding DEMATEL diagonal',
              'Probability note':'Relative sampling weights; adaptive consensus and range acceptance change realized frequencies',
              'Range scope':'All answer pairs; Pearson on cells and factor scores, Spearman on factor ranks; diagonals excluded',
              'Feasibility note':'Few criteria, tied/discrete ranks, many answers or strict Order can make two-sided pairwise ranges infeasible; best effort retains failures'}
    if mode=='DEMATEL':
        try:
            aggregate=dematel.evaluate(np.mean([x.to_numpy() for x in numeric],axis=0),rows)
            settings['DEMATEL aggregate target failures']=dematel.target_checks(aggregate,dematel_profiles)
            settings['DEMATEL aggregate results']=aggregate.reset_index(names='Criterion').to_dict('records')
            if settings['DEMATEL aggregate target failures']:
                settings['Required criteria passed']=False;settings['Best effort']=True
        except ValueError as exc:
            settings['DEMATEL aggregate error']=str(exc);settings['Required criteria passed']=False;settings['Best effort']=True
    return BatchResult(answers,numeric,pd.DataFrame(scores,index=names,columns=rows),pd.DataFrame(log),
                       correlation_table(scores,names),correlation_table(scores,names,rank=True),settings,
                       correlation_table([np.log(mat.to_numpy()[np.triu_indices(m,1)]) if mode=='AHP' else mat.to_numpy()[~np.eye(m,dtype=bool) if mode=='DEMATEL' else np.ones((m,n),bool)] for mat in numeric],names))
