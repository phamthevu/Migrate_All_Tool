from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import inspect
import ast
from pathlib import Path
import sys
import numpy as np
import pandas as pd

@dataclass
class Step:
    title: str
    formula: str
    explanation: str
    table: pd.DataFrame
    book_ref: str

RI = {1:0.0,2:0.0,3:0.58,4:0.90,5:1.12,6:1.24,7:1.32,8:1.41,9:1.45,10:1.49,11:1.51,12:1.48,13:1.56,14:1.57,15:1.59}


def _frame(matrix, names):
    return pd.DataFrame(matrix, index=names, columns=names if np.asarray(matrix).shape[1] == len(names) else None)

def _scores_table(names, vals, score_name, high_best=True):
    df = pd.DataFrame({'Alternative':names,score_name:np.asarray(vals,dtype=float)})
    df['Rank'] = df[score_name].rank(method='min',ascending=not high_best).astype(int)
    return df.sort_values(['Rank','Alternative']).reset_index(drop=True)

def _check(matrix, directions):
    x=np.asarray(matrix,dtype=float)
    if x.ndim != 2 or not x.shape[0] or not x.shape[1]: raise ValueError('Decision matrix is empty.')
    if not np.isfinite(x).all(): raise ValueError('Decision values must all be numeric and finite.')
    if len(directions)!=x.shape[1] or any(d not in ('Benefit','Cost') for d in directions): raise ValueError('Each criterion must have direction Benefit or Cost.')
    return x

def _normalise_sum_weights(weights, n):
    w=np.asarray(weights,dtype=float)
    if w.shape!=(n,) or not np.isfinite(w).all() or (w<0).any() or w.sum()<=0: raise ValueError('Weights must be nonnegative numeric values with a positive total.')
    return w/w.sum()

def calculate_ahp(criteria, pairwise):
    a=np.asarray(pairwise,dtype=float); n=len(criteria)
    if a.shape!=(n,n) or not np.isfinite(a).all() or (a<=0).any(): raise ValueError('AHP pairwise matrix must be a positive square matrix matching the criteria.')
    if not np.allclose(a*a.T,1,rtol=1e-4,atol=1e-4): raise ValueError('AHP pairwise values must be reciprocal: a[j,i] = 1 / a[i,j].')
    n=len(criteria); geom=np.prod(a,axis=1)**(1/n); w=geom/geom.sum()
    aw=a@w; ratios=aw/w; lam=float(ratios.mean()); ci=(lam-n)/(n-1) if n>1 else 0.0; cr=ci/RI.get(n,np.nan) if n>2 else 0.0
    steps=[
      Step('1. Pairwise comparison matrix','aᵢⱼ > 0; aᵢⱼ = 1/aⱼᵢ; aᵢᵢ = 1','Read the imported Saaty comparison matrix and verify reciprocity.',pd.DataFrame(a,index=criteria,columns=criteria),'Chapter 3, pp. 36–39'),
      Step('2. Geometric mean by row','gᵢ = (∏ⱼ aᵢⱼ)^(1/n)','The book presents the nth root of each row product as a close approximation to the eigenvector.',pd.DataFrame({'Criterion':criteria,'Row product':np.prod(a,axis=1),'nth root gᵢ':geom}),'Chapter 3, p. 36'),
      Step('3. Normalize criterion weights','wᵢ = gᵢ / ∑ₖ gₖ','Normalize the row geometric means so the weights sum to one.',pd.DataFrame({'Criterion':criteria,'Weight':w}),'Chapter 3, p. 36'),
      Step('4. Consistency check','Aw; λᵢ = (Aw)ᵢ / wᵢ; λmax = mean(λᵢ)','The book estimates λmax from the average componentwise ratio.',pd.DataFrame({'Criterion':criteria,'(Aw)ᵢ':aw,'λᵢ':ratios}),'Chapter 3, pp. 37–39'),
      Step('5. CI and CR','CI = (λmax − n)/(n − 1); CR = CI/RI','CR below 0.10 is the common guideline described in the book. RI values are Saaty’s table.',pd.DataFrame([{'n':n,'λmax':lam,'CI':ci,'RI':RI.get(n,np.nan),'CR':cr,'Status':'Consistent (CR ≤ 0.10)' if cr<=0.1 else 'Review judgments (CR > 0.10)'}]),'Chapter 3, pp. 37–38')]
    return w,steps

def calculate_swara(criteria, swara_rows):
    # rows are criterion names sorted from most to least important and s_j values for relative importance over preceding criterion
    order=list(swara_rows)
    if set(order)!=set(criteria) or len(order)!=len(criteria): raise ValueError('SWARA order must include every criterion exactly once.')
    s=np.array([float(swara_rows[c]) for c in order],dtype=float)
    if len(s) and abs(s[0])>1e-12: raise ValueError('For the first SWARA criterion, set s₁ to 0; there is no preceding criterion.')
    if (s[1:]<0).any() or (s[1:]>=1).any(): raise ValueError('SWARA relative-importance coefficients after the first row must be in [0, 1).')
    k=np.ones(len(order)); q=np.ones(len(order))
    for j in range(1,len(order)): k[j]=1+s[j]; q[j]=q[j-1]/k[j]
    w=q/q.sum(); bycrit={c:float(v) for c,v in zip(order,w)}
    table=pd.DataFrame({'Rank':np.arange(1,len(order)+1),'Criterion':order,'sⱼ':s,'kⱼ=1+sⱼ':k,'qⱼ=qⱼ₋₁/kⱼ':q,'Weight':w})
    steps=[Step('1. Order criteria','Most important → least important','Use the expert ordering. SWARA is a subjective weighting method.',table[['Rank','Criterion']],'Chapter 16, Fig. 16.1, pp. 281–282'),Step('2. Relative importance','sⱼ = relative importance of criterion j over criterion j−1','The book explains comparison to the preceding criterion in Fig. 16.1; enter s₁=0 for the first criterion.',table[['Criterion','sⱼ']],'Chapter 16, Fig. 16.1, p. 282'),Step('3. Coefficient and recalculated weight','k₁=1, q₁=1; kⱼ=1+sⱼ; qⱼ=qⱼ₋₁/kⱼ; wⱼ=qⱼ/∑q','The book describes determining kⱼ and recalculating and normalizing weights in its procedure figure. These displayed equations operationalize those steps.',table,'Chapter 16, Fig. 16.1, p. 282')]
    return np.array([bycrit[c] for c in criteria]),steps

def calculate_entropy_weights(criteria, matrix, directions):
    """Shannon-entropy objective weighting as a data-driven alternative."""
    x=_check(matrix,directions)
    if x.shape[1]!=len(criteria): raise ValueError('Matrix columns must match criteria.')
    # Orient cost criteria so larger values always mean stronger performance.
    z=x.copy()
    for j,d in enumerate(directions):
        if d=='Cost':
            if (z[:,j]<=0).any(): raise ValueError('Entropy cost transformation requires positive values.')
            z[:,j]=1/z[:,j]
    if (z<0).any(): raise ValueError('Entropy weighting requires nonnegative, oriented criterion values.')
    sums=z.sum(axis=0)
    if (sums<=0).any(): raise ValueError('Entropy weighting needs a positive sum for every criterion.')
    p=z/sums; m=len(x)
    if m<2: raise ValueError('Entropy weighting requires at least two alternatives.')
    k=1/np.log(m); terms=np.where(p>0,p*np.log(np.where(p>0,p,1)),0)
    e=-k*terms.sum(axis=0); div=1-e
    if div.sum()<=1e-14: raise ValueError('All criteria have identical distributions; entropy weights are undefined.')
    w=div/div.sum()
    table=pd.DataFrame({'Criterion':criteria,'Entropy eⱼ':e,'Divergence 1−eⱼ':div,'Weight':w})
    return w,[Step('1. Orient and normalize performances','pᵢⱼ = zᵢⱼ / ∑ᵢ zᵢⱼ','Cost criteria are reciprocally oriented; normalize each criterion column to proportions.',pd.DataFrame(p,columns=criteria,index=[f'A{i+1}' for i in range(m)]),'Shannon entropy weighting; see method note'),Step('2. Calculate entropy and divergence','eⱼ=−(1/ln m)∑ᵢpᵢⱼln(pᵢⱼ); dⱼ=1−eⱼ','Zero proportions contribute 0 by the continuous-limit convention.',table[['Criterion','Entropy eⱼ','Divergence 1−eⱼ']],'Shannon entropy weighting; see method note'),Step('3. Normalize objective weights','wⱼ=dⱼ/∑ⱼdⱼ','Higher variation across alternatives yields greater entropy divergence and weight.',table,'Shannon entropy weighting; see method note')]

def _orient_minmax(matrix,directions):
    x=_check(matrix,directions); lo=x.min(axis=0); span=np.ptp(x,axis=0)
    z=np.ones_like(x,dtype=float)
    for j,d in enumerate(directions):
        if span[j]>1e-14: z[:,j]=(x[:,j]-lo[j])/span[j] if d=='Benefit' else (x[:,j].max()-x[:,j])/span[j]
    return x,z

def calculate_critic_weights(criteria,matrix,directions):
    x,z=_orient_minmax(matrix,directions)
    if x.shape[1]!=len(criteria) or len(x)<2: raise ValueError('CRITIC requires matching criterion columns and at least two alternatives.')
    sigma=z.std(axis=0,ddof=0); corr=np.eye(z.shape[1])
    for i in range(z.shape[1]):
        for j in range(i+1,z.shape[1]):
            corr[i,j]=corr[j,i]=np.corrcoef(z[:,i],z[:,j])[0,1] if sigma[i]>1e-14 and sigma[j]>1e-14 else 0.0
    corr=np.nan_to_num(corr,nan=0.0); conflict=(1-corr).sum(axis=1); info=sigma*conflict
    if info.sum()<=1e-14: raise ValueError('CRITIC has no contrast information; all criteria are constant or redundant.')
    w=info/info.sum(); table=pd.DataFrame({'Criterion':criteria,'Std. deviation':sigma,'Conflict sum':conflict,'Information Cⱼ':info,'Weight':w})
    return w,[Step('1. Benefit-oriented normalization','zᵢⱼ=(xᵢⱼ−min xⱼ)/(max xⱼ−min xⱼ); reverse for Cost','Scale all columns to [0,1]. Constant criteria are represented by 1 and contribute no contrast.',pd.DataFrame(z,columns=criteria),'Diakoulaki et al. (1995), CRITIC'),Step('2. Contrast and conflict','Cⱼ=σⱼ∑ₖ(1−rⱼₖ)','CRITIC combines standard deviation (contrast) with inter-criterion correlation (conflict).',table[['Criterion','Std. deviation','Conflict sum','Information Cⱼ']],'Diakoulaki et al. (1995), CRITIC'),Step('3. Normalize information quantities','wⱼ=Cⱼ/∑ₖCₖ','Normalize each criterion information quantity to obtain objective weights.',table,'Diakoulaki et al. (1995), CRITIC')]

def calculate_merec_weights(criteria,matrix,directions):
    x=_check(matrix,directions)
    if x.shape[1]!=len(criteria) or len(x)<2 or (x<=0).any(): raise ValueError('MEREC requires positive values, at least two alternatives, and matching criteria.')
    n,k=x.shape; norm=np.column_stack([x[:,j]/x[:,j].max() if d=='Benefit' else x[:,j].min()/x[:,j] for j,d in enumerate(directions)])
    if (norm<=0).any(): raise ValueError('MEREC logarithms require positive normalized values.')
    overall=np.log1p(np.abs(np.log(norm)).mean(axis=1)); removed=np.empty((n,k))
    for j in range(k): removed[:,j]=np.log1p(np.delete(np.abs(np.log(norm)),j,axis=1).mean(axis=1))
    effects=np.abs(removed-overall[:,None]).sum(axis=0)
    if effects.sum()<=1e-14: raise ValueError('MEREC removal effects are all zero; objective weights cannot be distinguished.')
    w=effects/effects.sum(); table=pd.DataFrame({'Criterion':criteria,'Removal effect Eⱼ':effects,'Weight':w})
    return w,[Step('1. Normalize decision matrix','Benefit: nᵢⱼ=xᵢⱼ/max xⱼ; Cost: nᵢⱼ=min xⱼ/xᵢⱼ','MEREC uses positive normalized values before logarithmic aggregation.',pd.DataFrame(norm,columns=criteria),'Keshavarz-Ghorabaee et al. (2021), MEREC'),Step('2. Overall performance by alternative','Sᵢ=ln[1+(1/m)∑ⱼ|ln(nᵢⱼ)|]','Compute each alternative’s overall logarithmic performance.',pd.DataFrame({'Alternative':[f'A{i+1}' for i in range(n)],'Sᵢ':overall}),'Keshavarz-Ghorabaee et al. (2021), MEREC'),Step('3. Criterion-removal effects','S′ᵢⱼ=ln[1+(1/m)∑ₖ≠ⱼ|ln(nᵢₖ)|]; Eⱼ=∑ᵢ|S′ᵢⱼ−Sᵢ|','Remove one criterion at a time and aggregate the change in overall performance.',pd.DataFrame(removed,columns=criteria),'Keshavarz-Ghorabaee et al. (2021), MEREC'),Step('4. Normalize removal effects','wⱼ=Eⱼ/∑ₖEₖ','Convert removal effects into objective weights.',table,'Keshavarz-Ghorabaee et al. (2021), MEREC')]

def calculate_std_weights(criteria,matrix,directions):
    x,z=_orient_minmax(matrix,directions)
    if x.shape[1]!=len(criteria) or len(x)<2: raise ValueError('Standard-deviation weights require matching criteria and at least two alternatives.')
    sd=z.std(axis=0,ddof=0)
    if sd.sum()<=1e-14: raise ValueError('All criteria are constant; standard-deviation weights are undefined.')
    w=sd/sd.sum(); table=pd.DataFrame({'Criterion':criteria,'Std. deviation':sd,'Weight':w})
    return w,[Step('1. Normalize criteria','Min–max normalization, oriented so higher is better','Convert all values to a common [0,1] scale.',pd.DataFrame(z,columns=criteria),'Standard-deviation objective weighting'),Step('2. Calculate dispersion','σⱼ=√[∑ᵢ(zᵢⱼ−z̄ⱼ)²/n]','More variation across alternatives gives a larger objective weight.',table[['Criterion','Std. deviation']],'Standard-deviation objective weighting'),Step('3. Normalize dispersion','wⱼ=σⱼ/∑ₖσₖ','Normalize column dispersion to sum to one.',table,'Standard-deviation objective weighting')]

def calculate_psi_weights(criteria,matrix,directions):
    """Preference Selection Index objective weights (Maniya & Bhatt, 2010)."""
    x,z=_orient_minmax(matrix,directions)
    if x.shape[1]!=len(criteria) or len(x)<2: raise ValueError('PSI requires matching criteria and at least two alternatives.')
    # PSI uses ratio-normalized decision values; constant criteria carry no preference variation.
    norm=np.column_stack([x[:,j]/x[:,j].max() if directions[j]=='Benefit' else x[:,j].min()/x[:,j] for j in range(x.shape[1])])
    if not np.isfinite(norm).all(): raise ValueError('PSI normalization produced non-finite values.')
    mean=norm.mean(axis=0); variation=((norm-mean)**2).sum(axis=0); preference=1-variation
    # Keep raw PSI indices visible; project negative quantities to zero so the
    # returned vector satisfies the nonnegative-weight contract used by ranking methods.
    preference=np.maximum(preference,0)
    if preference.sum()<=1e-14: raise ValueError('PSI preference indices sum to zero; inspect the decision matrix.')
    w=preference/preference.sum(); table=pd.DataFrame({'Criterion':criteria,'Mean normalized value':mean,'Preference variation φⱼ':variation,'Preference index Ωⱼ':preference,'Weight ψⱼ':w})
    return w,[Step('1. Normalize decision matrix','Benefit: rᵢⱼ=xᵢⱼ/maxᵢxᵢⱼ; Cost: rᵢⱼ=minᵢxᵢⱼ/xᵢⱼ','Orient criterion values using the PSI ratio normalization.',pd.DataFrame(norm,columns=criteria),'Maniya & Bhatt (2010), PSI'),Step('2. Calculate preference variation','φⱼ=∑ᵢ(rᵢⱼ−r̄ⱼ)²','Measure the variation of each normalized criterion around its mean.',table[['Criterion','Mean normalized value','Preference variation φⱼ']],'Maniya & Bhatt (2010), PSI'),Step('3. Preference index and weights','Ωⱼ=1−φⱼ; ψⱼ=Ωⱼ/∑ₖΩₖ','To satisfy the app’s nonnegative-weight contract, negative Ωⱼ are truncated to zero before normalization; inspect raw Ωⱼ in the table.',table,'Maniya & Bhatt (2010), PSI; nonnegative projection is an implementation safeguard')]

def calculate_fucom_weights(criteria,order,comparative_priorities):
    """FUCOM weights from ranked criteria and adjacent comparative priorities."""
    from scipy.optimize import minimize
    order=list(order); n=len(criteria); phi=np.asarray(comparative_priorities,dtype=float)
    if len(order)!=n or len(set(order))!=n or set(order)!=set(criteria): raise ValueError('FUCOM order must contain every criterion exactly once, most to least important.')
    if phi.shape!=(max(0,n-1),) or not np.isfinite(phi).all() or (phi<1).any(): raise ValueError('FUCOM needs one finite adjacent comparative priority ≥1 for every consecutive criterion pair.')
    if n==1: return np.ones(1),[Step('1. Criterion order','Most important → least important','Only one criterion has weight 1.',pd.DataFrame({'Criterion':order,'Weight':[1.0]}),'Pamučar et al. (2018), FUCOM')]
    initial=np.ones(n,dtype=float)
    for i in range(1,n): initial[i]=initial[i-1]/phi[i-1]
    initial/=initial.sum(); x0=np.r_[initial,1.0]
    def deviations(x):
        w=x[:n]; xi=x[-1]; vals=[]
        for i in range(n-1): vals.extend([xi-(w[i]/w[i+1]-phi[i]),xi+(w[i]/w[i+1]-phi[i])])
        for i in range(n-2):
            target=phi[i]*phi[i+1]; vals.extend([xi-(w[i]/w[i+2]-target),xi+(w[i]/w[i+2]-target)])
        return np.asarray(vals)
    result=minimize(lambda x:x[-1],x0,method='SLSQP',bounds=[(1e-9,1.0)]*n+[(0.0,10.0)],constraints=[{'type':'eq','fun':lambda x:float(x[:n].sum()-1)},{'type':'ineq','fun':deviations}],options={'maxiter':1000,'ftol':1e-12})
    if not result.success or not np.isfinite(result.x).all(): raise ValueError(f'FUCOM optimization failed: {result.message}')
    w=result.x[:n]; xi=float(result.x[-1]); by_name=dict(zip(order,w)); output=np.array([by_name[c] for c in criteria])
    adjacent=pd.DataFrame({'Rank':np.arange(1,n+1),'Criterion':order,'Priority to next':[*phi,np.nan],'Weight':w})
    consistency=pd.DataFrame([{'Maximum deviation χ*':xi,'Weight sum':w.sum(),'Adjacent comparisons':len(phi)}])
    return output,[Step('1. Rank criteria','C₁ ≻ C₂ ≻ … ≻ Cₙ','Order criteria from most to least important.',adjacent[['Rank','Criterion']],'Pamučar, Stević & Sremac (2018), FUCOM, Step 1'),Step('2. Adjacent comparative priorities','φₖ/(ₖ₊₁)=wₖ/wₖ₊₁','Enter preference of each criterion over the next criterion in the ranked list.',adjacent[['Rank','Criterion','Priority to next']],'Pamučar, Stević & Sremac (2018), FUCOM, Step 2'),Step('3. Full-consistency optimization','min χ; |wₖ/wₖ₊₁−φₖ/(ₖ₊₁)|≤χ; |wₖ/wₖ₊₂−φₖ/(ₖ₊₁)φₖ₊₁/(ₖ₊₂)|≤χ; ∑w=1','Minimize deviations from adjacent priorities and their transitive products.',consistency,'Pamučar, Stević & Sremac (2018), FUCOM, Eq. 6'),Step('4. Criterion weights','wⱼ≥0; ∑ⱼwⱼ=1','Return FUCOM weights aligned to the workbook criterion order.',pd.DataFrame({'Criterion':criteria,'FUCOM weight':output}), 'Pamučar, Stević & Sremac (2018), FUCOM')]

def calculate_bwm_weights(criteria,best_idx,worst_idx,best_to_others,others_to_worst):
    from scipy.optimize import linprog
    n=len(criteria); abo=np.asarray(best_to_others,dtype=float); aow=np.asarray(others_to_worst,dtype=float)
    if not (0<=best_idx<n and 0<=worst_idx<n) or best_idx==worst_idx: raise ValueError('BWM best and worst criteria must be distinct valid criterion indices.')
    if abo.shape!=(n,) or aow.shape!=(n,) or not np.isfinite(abo).all() or not np.isfinite(aow).all() or (abo<1).any() or (aow<1).any(): raise ValueError('BWM comparison vectors must have one finite value ≥1 per criterion.')
    if not np.isclose(abo[best_idx],1) or not np.isclose(aow[worst_idx],1): raise ValueError('BWM self-comparisons must equal 1.')
    # min ξ subject to both absolute preference-ratio deviations ≤ ξ, and ∑w=1.
    rows=[]
    for j in range(n):
        r=np.zeros(n+1); r[best_idx]=1; r[j]-=abo[j]; r[-1]=-1; rows.append(r)
        r=np.zeros(n+1); r[best_idx]=-1; r[j]+=abo[j]; r[-1]=-1; rows.append(r)
        r=np.zeros(n+1); r[j]=1; r[worst_idx]-=aow[j]; r[-1]=-1; rows.append(r)
        r=np.zeros(n+1); r[j]=-1; r[worst_idx]+=aow[j]; r[-1]=-1; rows.append(r)
    objective=np.zeros(n+1); objective[-1]=1; eq=np.zeros((1,n+1)); eq[0,:n]=1
    result=linprog(objective,A_ub=np.asarray(rows),b_ub=np.zeros(len(rows)),A_eq=eq,b_eq=[1],bounds=[(0,None)]*n+[(0,None)],method='highs')
    if not result.success: raise ValueError(f'BWM linear optimization failed: {result.message}')
    w=result.x[:n]; xi=result.x[-1]; table=pd.DataFrame({'Criterion':criteria,'Best-to-criterion':abo,'Criterion-to-worst':aow,'Weight':w})
    summary=pd.DataFrame([{'Best criterion':criteria[best_idx],'Worst criterion':criteria[worst_idx],'Optimal max deviation ξ*':xi}])
    return w,[Step('1. Identify best and worst criteria','Best B; Worst W','Select the single best and worst criterion and provide two comparison vectors.',summary,'Rezaei (2015), Best-Worst Method'),Step('2. Best-to-others and others-to-worst','aᴮⱼ≈wᴮ/wⱼ; aⱼᵂ≈wⱼ/wᵂ','Use the imported 1–9 preference vectors.',table[['Criterion','Best-to-criterion','Criterion-to-worst']],'Rezaei (2015), Best-Worst Method'),Step('3. Minimize maximum deviation','min ξ; |wᴮ−aᴮⱼwⱼ|≤ξ; |wⱼ−aⱼᵂwᵂ|≤ξ; ∑ⱼwⱼ=1','Solve the linear minimax BWM model and display its optimal deviation.',table,'Rezaei (2015), linear BWM model'),Step('4. Final criterion weights','wⱼ≥0; ∑ⱼwⱼ=1','The optimal weights are returned in the original criterion order.',table,'Rezaei (2015), Best-Worst Method')]

def _criterion_table(criteria,directions,weights):
    return pd.DataFrame({'Criterion':criteria,'Direction':directions,'Weight':weights})

def _run_saw(x,names,criteria,directions,w):
    if (x<=0).any(): raise ValueError('The book’s SAW ratio normalization requires positive values.')
    best=x.max(axis=0); worst=x.min(axis=0)
    norm=np.column_stack([x[:,j]/best[j] if directions[j]=='Benefit' else worst[j]/x[:,j] for j in range(x.shape[1])])
    weighted=norm*w; scores=weighted.sum(axis=1)
    return [Step('1. Decision matrix','X = [xᵢⱼ]','Imported alternatives × criteria performance matrix.',pd.DataFrame(x,index=names,columns=criteria),'Chapter 2, pp. 28–29'),Step('2. Normalize benefit and cost criteria','rᵢⱼ = xᵢⱼ / maxᵢ(xᵢⱼ) [Benefit]; rᵢⱼ = minᵢ(xᵢⱼ) / xᵢⱼ [Cost]','The worked example uses benefit ratio normalization and the reciprocal minimum-to-value ratio for cost.',pd.DataFrame(norm,index=names,columns=criteria),'Chapter 2, p. 29'),Step('3. Weighted normalized matrix','vᵢⱼ = wⱼ rᵢⱼ','Multiply each normalized criterion by its weight.',pd.DataFrame(weighted,index=names,columns=criteria),'Chapter 2, p. 29'),Step('4. Additive score and rank','Sᵢ = ∑ⱼ wⱼ rᵢⱼ','Rank alternatives by descending weighted sum.',_scores_table(names,scores,'SAW score'),'Chapter 2, pp. 28–29')]

def _run_topsis(x,names,criteria,directions,w):
    den=np.sqrt((x*x).sum(axis=0))
    if (den==0).any(): raise ValueError('TOPSIS cannot normalize a criterion whose values are all zero.')
    r=x/den; v=r*w
    ideal=np.array([v[:,j].max() if d=='Benefit' else v[:,j].min() for j,d in enumerate(directions)])
    anti=np.array([v[:,j].min() if d=='Benefit' else v[:,j].max() for j,d in enumerate(directions)])
    dp=np.sqrt(((v-ideal)**2).sum(axis=1)); dm=np.sqrt(((v-anti)**2).sum(axis=1)); c=dm/(dp+dm)
    return [Step('1. Vector normalization','rᵢⱼ = xᵢⱼ / √(∑ᵢ xᵢⱼ²)','Standardize each criterion using the square root of its sum of squares.',pd.DataFrame(r,index=names,columns=criteria),'Chapter 5, pp. 83–84'),Step('2. Weight normalized values','vᵢⱼ = wⱼ rᵢⱼ','Apply the criterion weights.',pd.DataFrame(v,index=names,columns=criteria),'Chapter 5, p. 84'),Step('3. Positive and negative ideals','A⁺ⱼ=max(vᵢⱼ) for Benefit; min(vᵢⱼ) for Cost; A⁻ is the reverse','Select the best and worst value for each criterion according to direction.',pd.DataFrame([ideal,anti],index=['A⁺','A⁻'],columns=criteria),'Chapter 5, p. 85'),Step('4. Separation from ideal solutions','Dᵢ⁺=√∑ⱼ(vᵢⱼ−A⁺ⱼ)²; Dᵢ⁻=√∑ⱼ(vᵢⱼ−A⁻ⱼ)²','Calculate Euclidean distance from both ideal points.',pd.DataFrame({'Alternative':names,'D⁺':dp,'D⁻':dm}),'Chapter 5, p. 85'),Step('5. Relative closeness and rank','Cᵢ⁺ = Dᵢ⁻/(Dᵢ⁺+Dᵢ⁻)','Higher closeness is better.',_scores_table(names,c,'Closeness'),'Chapter 5, p. 85')]

def _run_moora(x,names,criteria,directions):
    den=np.sqrt((x*x).sum(axis=0))
    if (den==0).any(): raise ValueError('MOORA cannot normalize a criterion whose values are all zero.')
    r=x/den; signs=np.array([1 if d=='Benefit' else -1 for d in directions]); y=(r*signs).sum(axis=1)
    ref=np.array([r[:,j].max() if d=='Benefit' else r[:,j].min() for j,d in enumerate(directions)])
    dist=np.abs(r-ref); cheb=dist.max(axis=1)
    ref_table=pd.DataFrame(dist,index=names,columns=criteria); ref_table.index.name='Alternative'; ref_table['Max deviation'] = cheb; ref_table['Rank'] = pd.Series(cheb,index=names).rank(method='min',ascending=True).astype(int); ref_table=ref_table.reset_index()
    return [Step('1. Decision matrix','X = [xᵢⱼ]','Create the alternatives-by-objectives matrix.',pd.DataFrame(x,index=names,columns=criteria),'Chapter 11, p. 191'),Step('2. Ratio-system normalization','x*ᵢⱼ = xᵢⱼ / √(∑ᵢ xᵢⱼ²)','Normalize each objective into a dimensionless measure.',pd.DataFrame(r,index=names,columns=criteria),'Chapter 11, pp. 191–192'),Step('3. Ratio-system assessment','y*ᵢ = ∑ Benefit x*ᵢⱼ − ∑ Cost x*ᵢⱼ','Rank ratio-system assessment values descending.',_scores_table(names,y,'MOORA ratio score'),'Chapter 11, p. 193'),Step('4. Reference-point deviation','dᵢⱼ = |rⱼ − x*ᵢⱼ|; Tᵢ = maxⱼ dᵢⱼ','Compare normalized values with the direction-specific ideal reference point using the book’s min–max (Tchebycheff) criterion.',ref_table,'Chapter 11, p. 193')]

def _run_copras(x,names,criteria,directions,w):
    if (x<0).any(): raise ValueError('COPRAS-G requires nonnegative interval endpoints; this numeric template treats each value as [x, x].')
    colsum=x.sum(axis=0)
    if (colsum==0).any(): raise ValueError('COPRAS-G cannot normalize a criterion with a zero column sum.')
    # Degenerate intervals [x,x]: book's midpoint normalization reduces to x / sum_i x.
    norm=x/colsum; weighted=norm*w
    benefit=[j for j,d in enumerate(directions) if d=='Benefit']; cost=[j for j,d in enumerate(directions) if d=='Cost']
    p=weighted[:,benefit].sum(axis=1) if benefit else np.zeros(len(names)); rr=weighted[:,cost].sum(axis=1) if cost else np.zeros(len(names))
    if cost:
        if (rr<=0).any(): raise ValueError('COPRAS-G requires positive cost sums to calculate relative significance.')
        rmin=rr.min(); q=p+(rmin*rr.sum())/(rr*sum(rmin/rr))
    else: rmin=0.; q=p
    return [Step('1. Numeric values as degenerate intervals','[xᵢⱼ, xᵢⱼ]','COPRAS-G in the book uses interval-valued criteria. A scalar workbook cell is treated as the degenerate interval [x,x].',pd.DataFrame(x,index=names,columns=criteria),'Chapter 13, pp. 220–221'),Step('2. Normalize each interval','For [x,x]: x̄ᵢⱼ = xᵢⱼ / ∑ᵢ xᵢⱼ','For degenerate intervals, the book’s lower and upper formulas produce the same normalized value.',pd.DataFrame(norm,index=names,columns=criteria),'Chapter 13, p. 221'),Step('3. Weighted normalized matrix','x̂ᵢⱼ = x̄ᵢⱼ wⱼ','Multiply normalized values by criterion weights.',pd.DataFrame(weighted,index=names,columns=criteria),'Chapter 13, p. 222'),Step('4. Benefit Pᵢ and cost Rᵢ sums','Pᵢ=∑Benefit x̂ᵢⱼ; Rᵢ=∑Cost x̂ᵢⱼ','Separate benefit and cost contributions.',pd.DataFrame({'Alternative':names,'Pᵢ':p,'Rᵢ':rr}),'Chapter 13, p. 222'),Step('5. Relative significance and rank','Qᵢ = Pᵢ + [Rmin ∑ᵢRᵢ] / [Rᵢ ∑ᵢ(Rmin/Rᵢ)]','Higher Q is better. If there are no cost criteria, Qᵢ=Pᵢ.',_scores_table(names,q,'COPRAS-G Qᵢ'),'Chapter 13, pp. 222–223')]

def _run_aras(x,names,criteria,directions,w):
    if (x<=0).any(): raise ValueError('ARAS cost normalization uses reciprocals, so values must be positive.')
    # Add an ideal alternative row, then normalize all rows (including ideal).
    x0=np.array([x[:,j].max() if d=='Benefit' else x[:,j].min() for j,d in enumerate(directions)])
    aug=np.vstack([x0,x]); trans=aug.copy()
    for j,d in enumerate(directions):
        if d=='Cost': trans[:,j]=1/trans[:,j]
    norm=trans/trans.sum(axis=0); weighted=norm*w; sums=weighted.sum(axis=1); utility=sums[1:]/sums[0]
    idx=['A₀ (optimal)']+list(names)
    return [Step('1. Decision matrix + optimal row','x₀ⱼ = maxᵢ xᵢⱼ (Benefit); minᵢ xᵢⱼ (Cost)','Add the direction-specific optimal value as row A₀.',pd.DataFrame(aug,index=idx,columns=criteria),'Chapter 14, pp. 240–241'),Step('2. Normalize criteria','Benefit: x̄ᵢⱼ=xᵢⱼ/∑ᵢ₌₀ᵐxᵢⱼ; Cost: first x′ᵢⱼ=1/xᵢⱼ, then normalize','For costs the book applies the two-stage reciprocal transformation.',pd.DataFrame(norm,index=idx,columns=criteria),'Chapter 14, p. 241'),Step('3. Weighted normalized matrix','x̂ᵢⱼ = x̄ᵢⱼ wⱼ; ∑ⱼ wⱼ=1','Apply normalized criterion weights.',pd.DataFrame(weighted,index=idx,columns=criteria),'Chapter 14, pp. 241–242'),Step('4. Optimality function','Sᵢ = ∑ⱼ x̂ᵢⱼ','Sum the weighted normalized performance ratings.',pd.DataFrame({'Alternative':idx,'Sᵢ':sums}),'Chapter 14, p. 242'),Step('5. Degree of utility and rank','Kᵢ = Sᵢ/S₀','Compare each alternative’s optimality with the optimal row; higher utility is better.',_scores_table(names,utility,'ARAS utility Kᵢ'),'Chapter 14, Fig. 14.1, p. 242')]

def _run_waspas(x,names,criteria,directions,w,lam=0.5):
    if not (0<=lam<=1): raise ValueError('WASPAS λ must be between 0 and 1.')
    if (x<=0).any(): raise ValueError('WASPAS WPM requires positive values.')
    hi=x.max(axis=0); lo=x.min(axis=0)
    norm=np.column_stack([x[:,j]/hi[j] if d=='Benefit' else lo[j]/x[:,j] for j,d in enumerate(directions)])
    q1=(norm*w).sum(axis=1); q2=np.prod(norm**w,axis=1); q=lam*q1+(1-lam)*q2
    return [Step('1. Linear normalization','x̄ᵢⱼ=xᵢⱼ/maxᵢ(xᵢⱼ) [Benefit]; minᵢ(xᵢⱼ)/xᵢⱼ [Cost]','Normalize benefit and cost criteria for the WSM and WPM parts.',pd.DataFrame(norm,index=names,columns=criteria),'Chapter 15, p. 255'),Step('2. Weighted sum model (WSM)','Qᵢ⁽¹⁾ = ∑ⱼ x̄ᵢⱼ wⱼ','Calculate the additive component.',pd.DataFrame({'Alternative':names,'Q⁽¹⁾':q1}),'Chapter 15, p. 254'),Step('3. Weighted product model (WPM)','Qᵢ⁽²⁾ = ∏ⱼ (x̄ᵢⱼ)^wⱼ','Calculate the multiplicative component.',pd.DataFrame({'Alternative':names,'Q⁽²⁾':q2}),'Chapter 15, p. 255'),Step('4. Aggregated assessment and rank',f'Qᵢ = λQᵢ⁽¹⁾ + (1−λ)Qᵢ⁽²⁾; λ={lam:g}','The book defines λ in [0,1]. The interface exposes λ; default is 0.5. The book separately presents variance-based λ optimization in Eqs. 15.4–15.6.',_scores_table(names,q,'WASPAS Qᵢ'),'Chapter 15, pp. 255–256')]

def _run_vikor(x,names,criteria,directions,w,v=0.5):
    if not (0<=v<=1): raise ValueError('VIKOR strategy weight v must be between 0 and 1.')
    best=np.array([x[:,j].max() if d=='Benefit' else x[:,j].min() for j,d in enumerate(directions)])
    worst=np.array([x[:,j].min() if d=='Benefit' else x[:,j].max() for j,d in enumerate(directions)])
    rng=best-worst
    regret=np.zeros_like(x,dtype=float)
    for j,d in enumerate(directions):
        if abs(rng[j])<1e-14: continue
        regret[:,j]=w[j]*(best[j]-x[:,j])/rng[j]
    s=regret.sum(axis=1); r=regret.max(axis=1)
    smin,smax=s.min(),s.max(); rmin,rmax=r.min(),r.max()
    q=np.zeros(len(names))
    if smax>smin: q += v*(s-smin)/(smax-smin)
    if rmax>rmin: q += (1-v)*(r-rmin)/(rmax-rmin)
    table=pd.DataFrame({'Alternative':names,'Sᵢ':s,'Rᵢ':r,'Qᵢ':q})
    table['Rank by S']=table['Sᵢ'].rank(method='min').astype(int); table['Rank by R']=table['Rᵢ'].rank(method='min').astype(int); table['Rank by Q']=table['Qᵢ'].rank(method='min').astype(int)
    table=table.sort_values(['Rank by Q','Alternative']).reset_index(drop=True)
    if len(names)>1:
        qsorted=np.sort(q); adv=qsorted[1]-qsorted[0]; dq=1/(len(names)-1); best_q=int(np.argmin(q)); stability=(best_q==int(np.argmin(s)) or best_q==int(np.argmin(r)))
        conclusion='Compromise recommendation passes C1 and C2.' if adv>=dq and stability else 'C1/C2 not both satisfied; treat close alternatives as a compromise set.'
    else: adv=np.nan; dq=np.nan; stability=True; conclusion='Only one alternative.'
    return [Step('1. Best and worst criterion values','f*ⱼ=maxᵢ fᵢⱼ / minᵢ fᵢⱼ by direction; f⁻ⱼ is the opposite','Identify ideal and anti-ideal performance for every criterion.',pd.DataFrame([best,worst],index=['f*','f⁻'],columns=criteria),'Chapter 8, p. 131'),Step('2. Regret matrix','dᵢⱼ = wⱼ(f*ⱼ−fᵢⱼ)/(f*ⱼ−f⁻ⱼ) [Benefit]; reverse for Cost','Normalize weighted distance from the ideal. This is equivalent to the book’s expression after orienting cost criteria.',pd.DataFrame(regret,index=names,columns=criteria),'Chapter 8, p. 131'),Step('3. Group utility S and individual regret R','Sᵢ=∑ⱼdᵢⱼ; Rᵢ=maxⱼdᵢⱼ','S measures aggregate group regret; R measures the largest criterion regret.',pd.DataFrame({'Alternative':names,'Sᵢ':s,'Rᵢ':r}),'Chapter 8, p. 131'),Step('4. VIKOR index and compromise checks',f'Qᵢ=v(Sᵢ−S*)/(S⁻−S*)+(1−v)(Rᵢ−R*)/(R⁻−R*); v={v:g}','Lower Q is better. C1 acceptable advantage: Q(second)−Q(best) ≥ 1/(m−1). C2: best Q also ranks first by S or R.',table,'Chapter 8, pp. 131–132')]

def _run_cocoso(x,names,criteria,directions,w,lam=0.5):
    if not (0<=lam<=1): raise ValueError('CoCoSo λ must be within [0, 1].')
    _,r=_orient_minmax(x,directions); r=np.maximum(r,1e-12); s=(r*w).sum(axis=1); p=np.power(r,w).sum(axis=1)
    ka=(p+s)/(p+s).sum(); kb=s/s.min()+p/p.min(); kc=(lam*s+(1-lam)*p)/(lam*s.max()+(1-lam)*p.max())
    score=np.cbrt(ka*kb*kc)+(ka+kb+kc)/3
    detail=pd.DataFrame({'Alternative':names,'Sᵢ (WSM)':s,'Pᵢ (WPM)':p,'kᵢₐ':ka,'kᵢᵦ':kb,'kᵢ꜀':kc,'CoCoSo score':score})
    return [Step('1. Benefit-oriented normalization','rᵢⱼ=(xᵢⱼ−min xⱼ)/(max xⱼ−min xⱼ); reverse for Cost','Scale criteria to [0,1]; a constant criterion is mapped to 1.',pd.DataFrame(r,index=names,columns=criteria),'Yazdani et al. (2019), CoCoSo'),Step('2. Weighted sum and power measures','Sᵢ=∑ⱼwⱼrᵢⱼ; Pᵢ=∑ⱼrᵢⱼ^wⱼ','Combine additive and power-weighted performance.',pd.DataFrame({'Alternative':names,'Sᵢ':s,'Pᵢ':p}),'Yazdani et al. (2019), CoCoSo'),Step('3. Three compromise measures','kᵢₐ=(Sᵢ+Pᵢ)/∑(S+P); kᵢᵦ=Sᵢ/minS+Pᵢ/minP; kᵢ꜀=[λSᵢ+(1−λ)Pᵢ]/[λmaxS+(1−λ)maxP]','Calculate the relative measures that combine additive and multiplicative viewpoints.',detail[['Alternative','kᵢₐ','kᵢᵦ','kᵢ꜀']], 'Yazdani et al. (2019), CoCoSo'),Step('4. Combined compromise score and rank',f'kᵢ=(kᵢₐkᵢᵦkᵢ꜀)^(1/3)+(kᵢₐ+kᵢᵦ+kᵢ꜀)/3; λ={lam:g}','Higher CoCoSo score is better.',_scores_table(names,score,'CoCoSo score'),'Yazdani et al. (2019), CoCoSo')]

def _run_edas(x,names,criteria,directions,w):
    avg=x.mean(axis=0)
    if np.isclose(avg,0).any(): raise ValueError('EDAS average-reference formulas require nonzero criterion averages.')
    pda=np.maximum(0,(x-avg)/np.abs(avg)); nda=np.maximum(0,(avg-x)/np.abs(avg))
    for j,d in enumerate(directions):
        if d=='Cost': pda[:,j],nda[:,j]=nda[:,j].copy(),pda[:,j].copy()
    sp=(pda*w).sum(axis=1); sn=(nda*w).sum(axis=1)
    nsp=sp/sp.max() if sp.max()>1e-14 else np.zeros_like(sp); nsn=1-sn/sn.max() if sn.max()>1e-14 else np.ones_like(sn)
    score=(nsp+nsn)/2
    detail=pd.DataFrame({'Alternative':names,'SPᵢ':sp,'SNᵢ':sn,'NSPᵢ':nsp,'NSNᵢ':nsn,'ASᵢ':score})
    return [Step('1. Average solution','AVⱼ=∑ᵢxᵢⱼ/n','Calculate average performance for every criterion.',pd.DataFrame([avg],columns=criteria,index=['Average']),'Keshavarz-Ghorabaee et al. (2015), EDAS'),Step('2. Positive and negative distances','PDAᵢⱼ=max(0,(xᵢⱼ−AVⱼ)/AVⱼ); NDAᵢⱼ=max(0,(AVⱼ−xᵢⱼ)/AVⱼ); reverse for Cost','Measure positive and negative distance from the average solution.',pd.DataFrame(pda,index=names,columns=criteria).add_prefix('PDA ' ).join(pd.DataFrame(nda,index=names,columns=criteria).add_prefix('NDA ')),'Keshavarz-Ghorabaee et al. (2015), EDAS'),Step('3. Weighted sums and normalization','SPᵢ=∑ⱼwⱼPDAᵢⱼ; SNᵢ=∑ⱼwⱼNDAᵢⱼ; NSPᵢ=SPᵢ/maxSP; NSNᵢ=1−SNᵢ/maxSN','Normalize positive/negative distances across alternatives.',detail[['Alternative','SPᵢ','SNᵢ','NSPᵢ','NSNᵢ']],'Keshavarz-Ghorabaee et al. (2015), EDAS'),Step('4. Appraisal score and rank','ASᵢ=(NSPᵢ+NSNᵢ)/2','Higher appraisal score is better.',_scores_table(names,score,'EDAS score'),'Keshavarz-Ghorabaee et al. (2015), EDAS')]

def _run_marcos(x,names,criteria,directions,w):
    if (x<=0).any(): raise ValueError('MARCOS ratio normalization requires positive decision values.')
    ai=np.array([x[:,j].max() if d=='Benefit' else x[:,j].min() for j,d in enumerate(directions)]); aa=np.array([x[:,j].min() if d=='Benefit' else x[:,j].max() for j,d in enumerate(directions)])
    aug=np.vstack([ai,x,aa]); norm=aug.copy()
    for j,d in enumerate(directions): norm[:,j]=aug[:,j]/ai[j] if d=='Benefit' else ai[j]/aug[:,j]
    weighted=norm*w; sums=weighted.sum(axis=1); ki_minus=sums[1:-1]/sums[-1]; ki_plus=sums[1:-1]/sums[0]
    fplus=ki_minus/(ki_minus+ki_plus); fminus=ki_plus/(ki_minus+ki_plus)
    score=(ki_minus+ki_plus)/(1+(1-fplus)/fplus+(1-fminus)/fminus)
    detail=pd.DataFrame({'Alternative':names,'Kᵢ⁻':ki_minus,'Kᵢ⁺':ki_plus,'f(Kᵢ⁺)':fplus,'f(Kᵢ⁻)':fminus,'MARCOS utility':score})
    labels=['Ideal']+list(names)+['Anti-ideal']
    return [Step('1. Add ideal and anti-ideal alternatives','AIⱼ=max/min by direction; AAⱼ is the opposite','Append ideal and anti-ideal reference alternatives.',pd.DataFrame(aug,index=labels,columns=criteria),'Stević et al. (2020), MARCOS'),Step('2. Normalize and weight','Benefit: xᵢⱼ/AIⱼ; Cost: AIⱼ/xᵢⱼ; vᵢⱼ=wⱼnᵢⱼ','Calculate the weighted extended decision matrix.',pd.DataFrame(weighted,index=labels,columns=criteria),'Stević et al. (2020), MARCOS'),Step('3. Utility degrees','Kᵢ⁻=Sᵢ/S_AA; Kᵢ⁺=Sᵢ/S_AI','Compare each alternative with anti-ideal and ideal reference solutions.',detail[['Alternative','Kᵢ⁻','Kᵢ⁺']],'Stević et al. (2020), MARCOS'),Step('4. Utility function and rank','f(Kᵢ)=(Kᵢ⁻+Kᵢ⁺)/[1+(1−f(Kᵢ⁺))/f(Kᵢ⁺)+(1−f(Kᵢ⁻))/f(Kᵢ⁻)]','Higher MARCOS utility is better.',_scores_table(names,score,'MARCOS utility'),'Stević et al. (2020), MARCOS')]

def _run_codas(x,names,criteria,directions,w,tau=0.02):
    if not (0<=tau<=1): raise ValueError('CODAS τ threshold must be within [0, 1].')
    den=np.sqrt((x*x).sum(axis=0))
    if (den<=0).any(): raise ValueError('CODAS vector normalization cannot use a zero-only criterion.')
    z=x/den
    for j,d in enumerate(directions):
        if d=='Cost': z[:,j]=-z[:,j]
    v=z*w; negative=v.min(axis=0); delta=v-negative
    eu=np.sqrt((delta**2).sum(axis=1)); tax=np.abs(delta).sum(axis=1); n=len(names); h=np.zeros((n,n))
    for i in range(n):
        for k in range(n):
            diff=eu[i]-eu[k]; gate=1.0 if abs(diff)>=tau else 0.0; h[i,k]=diff+gate*(tax[i]-tax[k])
    score=h.sum(axis=1); detail=pd.DataFrame({'Alternative':names,'Euclidean Eᵢ':eu,'Taxicab Tᵢ':tax,'CODAS score':score})
    return [Step('1. Vector normalization and orientation','nᵢⱼ=xᵢⱼ/√∑ᵢxᵢⱼ²; reverse Cost criteria','Normalize and orient all criteria before weighting.',pd.DataFrame(v,index=names,columns=criteria),'Ghorabaee et al. (2016), CODAS'),Step('2. Negative-ideal distances','Eᵢ=√∑ⱼ(vᵢⱼ−nsⱼ)²; Tᵢ=∑ⱼ|vᵢⱼ−nsⱼ|','Calculate Euclidean primary and Taxicab secondary distances from the negative ideal.',detail[['Alternative','Euclidean Eᵢ','Taxicab Tᵢ']],'Ghorabaee et al. (2016), CODAS'),Step('3. Relative assessment matrix',f'hᵢₖ=(Eᵢ−Eₖ)+ψ(Eᵢ−Eₖ)(Tᵢ−Tₖ); τ={tau:g}','The threshold function activates Taxicab distance when Euclidean differences are sufficiently large.',pd.DataFrame(h,index=names,columns=names),'Ghorabaee et al. (2016), CODAS'),Step('4. Assessment score and rank','Hᵢ=∑ₖhᵢₖ','Higher CODAS assessment is better.',_scores_table(names,score,'CODAS score'),'Ghorabaee et al. (2016), CODAS')]

def _run_mairca(x,names,criteria,directions,w):
    _,norm=_orient_minmax(x,directions); m=len(names); theoretical=np.tile(w/m,(m,1)); real=theoretical*norm; gap=theoretical-real; q=gap.sum(axis=1)
    return [Step('1. Normalize performances','Benefit-oriented min–max normalization','Scale performance values so larger normalized values indicate better alternatives.',pd.DataFrame(norm,index=names,columns=criteria),'MAIRCA method; Pamučar et al.'),Step('2. Theoretical and real rating matrices','tₚᵢⱼ=(1/m)wⱼ; tᵣᵢⱼ=tₚᵢⱼnᵢⱼ','Assume equal prior probability for every alternative, then adjust by normalized performance.',pd.DataFrame(theoretical,index=names,columns=criteria).add_prefix('Tp ').join(pd.DataFrame(real,index=names,columns=criteria).add_prefix('Tr ')),'MAIRCA method'),Step('3. Gap matrix and total gap','Gᵢⱼ=tₚᵢⱼ−tᵣᵢⱼ; Qᵢ=∑ⱼGᵢⱼ','Smaller total gaps indicate a closer match to the ideal-real comparison.',pd.DataFrame(gap,index=names,columns=criteria),'MAIRCA method'),Step('4. Ranking','Rank ascending by Qᵢ','Lower MAIRCA total gap is better.',_scores_table(names,q,'MAIRCA gap',high_best=False),'MAIRCA method')]

def _run_mabac(x,names,criteria,directions,w):
    """MABAC comparison with the border approximation area."""
    _,norm=_orient_minmax(x,directions); weighted=(norm+1)*w
    border=np.exp(np.log(weighted).mean(axis=0))
    distance=weighted-border; score=distance.sum(axis=1)
    return [Step('1. Benefit-oriented normalization','Benefit: (xᵢⱼ−min xⱼ)/(max xⱼ−min xⱼ)+1; Cost: (max xⱼ−xᵢⱼ)/(max xⱼ−min xⱼ)+1','Normalize each criterion to a positive comparable scale.',pd.DataFrame(norm+1,index=names,columns=criteria),'Pamučar & Ćirović (2015), MABAC'),Step('2. Weighted normalized matrix','vᵢⱼ=wⱼ(nᵢⱼ+1)','Apply criterion weights to the normalized matrix.',pd.DataFrame(weighted,index=names,columns=criteria),'Pamučar & Ćirović (2015), MABAC'),Step('3. Border approximation area','gⱼ=(∏ᵢvᵢⱼ)^(1/m)','Calculate the geometric mean border value for each criterion.',pd.DataFrame([border],index=['BAA'],columns=criteria),'Pamučar & Ćirović (2015), MABAC'),Step('4. Distances from border and ranking','qᵢⱼ=vᵢⱼ−gⱼ; Sᵢ=∑ⱼqᵢⱼ','Positive distances indicate that an alternative lies above the border on that criterion; rank total distance descending.',pd.DataFrame(distance,index=names,columns=criteria).assign(**{'MABAC score':score}).join(_scores_table(names,score,'Score').set_index('Alternative')['Rank']),'Pamučar & Ćirović (2015), MABAC')]

def _run_gra(x,names,criteria,directions,w,rho=0.5):
    """Crisp Grey Relational Analysis using a normalized ideal reference sequence."""
    _,norm=_orient_minmax(x,directions)
    if not 0<rho<=1: raise ValueError('GRA distinguishing coefficient rho must be in (0, 1].')
    reference=norm.max(axis=0); delta=np.abs(reference-norm); dmin=float(delta.min()); dmax=float(delta.max())
    if dmax<=1e-14: coefficients=np.ones_like(delta)
    else: coefficients=(dmin+rho*dmax)/(delta+rho*dmax)
    grade=coefficients@w
    normalized_table=pd.DataFrame(np.vstack([norm,reference]),index=[*names,'Reference'],columns=criteria)
    return [Step('1. Normalize and define reference sequence','Benefit-oriented min–max; x₀ⱼ=maxᵢ zᵢⱼ','Create a normalized ideal reference sequence for the criteria.',normalized_table,'Grey Relational Analysis'),Step('2. Absolute deviations','Δᵢⱼ=|x₀ⱼ−zᵢⱼ|','Measure each alternative’s deviation from the reference sequence.',pd.DataFrame(delta,index=names,columns=criteria),'Grey Relational Analysis'),Step('3. Grey relational coefficients',f'ξᵢⱼ=(Δmin+ρΔmax)/(Δᵢⱼ+ρΔmax); ρ={rho:g}','Transform deviations into relational closeness coefficients.',pd.DataFrame(coefficients,index=names,columns=criteria),'Grey Relational Analysis'),Step('4. Grey relational grade and ranking','Γᵢ=∑ⱼwⱼξᵢⱼ','Aggregate criterion coefficients using the supplied weights; higher grade is better.',_scores_table(names,grade,'Grey relational grade'),'Grey Relational Analysis')]

def _run_piv(x,names,criteria,directions,w):
    den=np.sqrt((x*x).sum(axis=0))
    if (den<=1e-14).any(): raise ValueError('PIV cannot vector-normalize a criterion whose values are all zero.')
    norm=x/den; weighted=norm*w
    ideal=np.array([weighted[:,j].max() if d=='Benefit' else weighted[:,j].min() for j,d in enumerate(directions)])
    proximity=np.abs(weighted-ideal); total=proximity.sum(axis=1)
    return [Step('1. Vector normalization','nᵢⱼ=xᵢⱼ/√(∑ᵢxᵢⱼ²)','Normalize each criterion column by its Euclidean norm.',pd.DataFrame(norm,index=names,columns=criteria),'Mufazzal & Muzakkir (2018), PIV, Eq. 9'),Step('2. Weighted normalized values','vᵢⱼ=wⱼnᵢⱼ','Apply criterion weights to normalized performance values.',pd.DataFrame(weighted,index=names,columns=criteria),'Mufazzal & Muzakkir (2018), PIV, Eq. 10'),Step('3. Weighted proximity indices','uᵢⱼ=vmaxⱼ−vᵢⱼ (Benefit); vᵢⱼ−vminⱼ (Cost)','Measure each alternative’s deviation from the direction-specific ideal best.',pd.DataFrame(proximity,index=names,columns=criteria),'Mufazzal & Muzakkir (2018), PIV, Eq. 11'),Step('4. Overall proximity and ranking','dᵢ=∑ⱼuᵢⱼ','Smaller total proximity indicates a closer alternative to the ideal; rank ascending.',_scores_table(names,total,'PIV proximity dᵢ',high_best=False),'Mufazzal & Muzakkir (2018), PIV, Eq. 12')]

def _run_electre1(x,names,criteria,directions,w,c_threshold=None,d_threshold=None):
    """ELECTRE I: concordance/discordance outranking; output is a relation, not a forced total order."""
    den=np.sqrt((x*x).sum(axis=0))
    if (den<=0).any(): raise ValueError('ELECTRE I cannot normalize a zero-only criterion.')
    z=x/den
    for j,d in enumerate(directions):
        if d=='Cost': z[:,j]=-z[:,j]
    y=z*w; n,k=y.shape; concord=np.zeros((n,n)); discord=np.zeros((n,n))
    for a in range(n):
        for b in range(n):
            if a==b: continue
            good=y[a]>=y[b]-1e-12
            concord[a,b]=w[good].sum()
            gaps=np.maximum(y[b]-y[a],0)
            span=np.ptp(y,axis=0).max()
            discord[a,b]=gaps.max()/span if span>1e-14 else 0.0
    cbar=float(np.mean(concord[~np.eye(n,dtype=bool)])) if n>1 else 1.0
    dbar=float(np.mean(discord[~np.eye(n,dtype=bool)])) if n>1 else 0.0
    ct=cbar if c_threshold is None else float(c_threshold); dt=dbar if d_threshold is None else float(d_threshold)
    if not (0<=ct<=1 and 0<=dt<=1): raise ValueError('ELECTRE I concordance and discordance thresholds must be within [0, 1].')
    outrank=(concord>=ct)&(discord<=dt); np.fill_diagonal(outrank,False)
    net=outrank.sum(axis=1)-outrank.sum(axis=0)
    table=pd.DataFrame({'Alternative':names,'Outranked by this alternative':outrank.sum(axis=1),'Outranks this alternative':outrank.sum(axis=0),'Net outranking count':net})
    return [Step('1. Vector-normalized decision matrix','rᵢⱼ=xᵢⱼ/√∑ᵢxᵢⱼ²; reverse cost direction','The textbook ELECTRE procedure uses vector normalization before weighting.',pd.DataFrame(z,index=names,columns=criteria),'Chapter 6, §6.2, pp. 94–95'),Step('2. Weighted matrix','yᵢⱼ=wⱼrᵢⱼ; ∑ⱼwⱼ=1','Apply criterion weights to normalized performances.',pd.DataFrame(y,index=names,columns=criteria),'Chapter 6, §6.2, p. 95'),Step('3. Concordance and discordance indices','Cₐᵦ=∑{wⱼ:yₐⱼ≥yᵦⱼ}; Dₐᵦ=maxⱼ(max(yᵦⱼ−yₐⱼ,0))/maxⱼ range(yⱼ)','This is the ELECTRE I threshold implementation; thresholds default to mean off-diagonal indices and remain user-editable in the API.',pd.DataFrame(concord,index=names,columns=names),'Chapter 6, §6.2, pp. 95–96'),Step('4. Outranking relation and kernel counts',f'a outranks b if Cₐᵦ≥{ct:.4g} and Dₐᵦ≤{dt:.4g}','ELECTRE I can leave alternatives incomparable. Net counts are descriptive and do not replace the outranking graph.',pd.DataFrame(outrank.astype(int),index=names,columns=names),'Chapter 6, §6.2, pp. 96 onward'),Step('5. Partial recommendation','Outranking graph; net count = outdegree − indegree','Use the relation to identify a reduced set; a complete ranking is not guaranteed.',table,'Chapter 6, §§6.1–6.2, pp. 93–96')]

def _run_promethee2(x,names,criteria,directions,w):
    """PROMETHEE II with the book's simplified linear preference function."""
    n,k=x.shape
    if n<2: raise ValueError('PROMETHEE II requires at least two alternatives.')
    oriented=x.copy()
    for j,d in enumerate(directions):
        if d=='Cost': oriented[:,j]=-oriented[:,j]
    lo=oriented.min(axis=0); span=np.ptp(oriented,axis=0)
    norm=np.divide(oriented-lo,span,out=np.zeros_like(oriented),where=span>1e-14)
    pref=np.zeros((n,n,k))
    for a in range(n):
        for b in range(n): pref[a,b,:]=np.maximum(norm[a]-norm[b],0)
    agg=np.einsum('abj,j->ab',pref,w)/w.sum(); phi_plus=agg.sum(axis=1)/(n-1); phi_minus=agg.sum(axis=0)/(n-1); net=phi_plus-phi_minus
    table=_scores_table(names,net,'Net flow ϕ')
    flow=pd.DataFrame({'Alternative':names,'Positive flow ϕ⁺':phi_plus,'Negative flow ϕ⁻':phi_minus,'Net flow ϕ':net})
    return [Step('1. Normalize benefit and cost criteria','Rᵢⱼ=(xᵢⱼ−min xⱼ)/(max xⱼ−min xⱼ); cost: (max xⱼ−xᵢⱼ)/(max xⱼ−min xⱼ)','Constant criteria map to zero preference difference.',pd.DataFrame(norm,index=names,columns=criteria),'Chapter 7, §7.2, pp. 120–121'),Step('2. Pairwise evaluative differences','Δⱼ(a,b)=Rₐⱼ−Rᵦⱼ','Compare every ordered pair of alternatives criterion by criterion.',pd.DataFrame(np.sum(pref,axis=2),index=names,columns=names),'Chapter 7, §7.2, p. 121'),Step('3. Simplified preference function','Pⱼ(a,b)=max(0, Rₐⱼ−Rᵦⱼ)','This implements the simplified preference function presented in the chapter (not all six generalized Brans functions).',pd.DataFrame(agg,index=names,columns=names),'Chapter 7, §7.2, p. 121'),Step('4. Positive, negative and net flows','ϕ⁺(a)=∑ᵦπ(a,b)/(n−1); ϕ⁻(a)=∑ᵦπ(b,a)/(n−1); ϕ=ϕ⁺−ϕ⁻','Positive flow measures outranking; negative flow measures being outranked.',flow,'Chapter 7, §7.2, p. 121'),Step('5. PROMETHEE II complete ranking','Rank descending by net flow ϕ','PROMETHEE II produces a complete preorder using net flows.',table,'Chapter 7, §7.2, p. 121')]

def _run_multimoora(x,names,criteria,directions):
    if (x<=0).any(): raise ValueError('MULTIMOORA multiplicative form requires positive values.')
    den=np.sqrt((x*x).sum(axis=0))
    if (den<=0).any(): raise ValueError('MULTIMOORA cannot normalize a zero-only criterion.')
    z=x/den; signs=np.array([1 if d=='Benefit' else -1 for d in directions]); ratio=(z*signs).sum(axis=1)
    b=[j for j,d in enumerate(directions) if d=='Benefit']; c=[j for j,d in enumerate(directions) if d=='Cost']
    product=np.prod(z[:,b],axis=1)/np.prod(z[:,c],axis=1) if c else np.prod(z[:,b],axis=1)
    reference=np.array([z[:,j].max() if d=='Benefit' else z[:,j].min() for j,d in enumerate(directions)])
    deviation=np.abs(z-reference).max(axis=1)
    rank1=pd.Series(ratio).rank(method='average',ascending=False).to_numpy(); rank2=pd.Series(deviation).rank(method='average',ascending=True).to_numpy(); rank3=pd.Series(product).rank(method='average',ascending=False).to_numpy()
    # Transparent rank-sum aggregation of the three subordinate MOORA rankings.
    agg=rank1+rank2+rank3
    out=pd.DataFrame({'Alternative':names,'Ratio system':ratio,'Reference-point max deviation':deviation,'Multiplicative form':product,'Ratio rank':rank1,'Reference-point rank':rank2,'Multiplicative rank':rank3,'Rank sum (lower better)':agg})
    out=out.sort_values(['Rank sum (lower better)','Alternative']).reset_index(drop=True); out['MULTIMOORA rank']=out['Rank sum (lower better)'].rank(method='min').astype(int)
    return [Step('1. Vector normalization','x*ᵢⱼ=xᵢⱼ/√∑ᵢxᵢⱼ²','Normalize alternatives for each objective.',pd.DataFrame(z,index=names,columns=criteria),'Chapter 11, §11.2, pp. 191–193'),Step('2. Ratio-system assessment','yᵢ=∑Benefit x*ᵢⱼ−∑Cost x*ᵢⱼ','Calculate the ratio-system component.',pd.DataFrame({'Alternative':names,'Ratio system':ratio}),'Chapter 11, §11.2, p. 193'),Step('3. Reference-point assessment','Tᵢ=maxⱼ|rⱼ−x*ᵢⱼ|; minimize Tᵢ','Calculate the MOORA reference-point vector and each alternative’s deviation.',pd.DataFrame({'Criterion':criteria,'Reference point':reference}), 'Chapter 11, §11.2, p. 193'),Step('4. Full multiplicative form','Uᵢ=∏Benefit x*ᵢⱼ / ∏Cost x*ᵢⱼ','Calculate the full multiplicative form using oriented benefit/cost groups.',pd.DataFrame({'Alternative':names,'Multiplicative form':product}),'Chapter 11, MULTIMOORA discussion'),Step('5. MULTIMOORA aggregation','Aggregate the ratio, reference-point and multiplicative component ranks','Rank-sum is the transparent aggregation convention used by this implementation; classic MULTIMOORA applies dominance theory.',out,'Chapter 11, MULTIMOORA discussion')]

def _run_dematel(direct,nodes):
    a=np.asarray(direct,dtype=float); n=len(nodes)
    if a.shape!=(n,n) or not np.isfinite(a).all() or (a<0).any() or (a>4).any(): raise ValueError('DEMATEL direct-relation matrix must be finite, in the 0–4 range, square, and match node names.')
    if not np.allclose(np.diag(a),0): raise ValueError('DEMATEL diagonal must be zero.')
    scale=min(1/max(a.sum(axis=1).max(),1e-15),1/max(a.sum(axis=0).max(),1e-15))*(1-1e-10); d=a*scale
    spectral=max(abs(np.linalg.eigvals(d)))
    if spectral>=1-1e-12: raise ValueError('DEMATEL normalization did not produce a convergent matrix.')
    t=np.linalg.solve(np.eye(n)-d,d); rows=t.sum(axis=1); cols=t.sum(axis=0); prominence=rows+cols; relation=rows-cols
    results=pd.DataFrame({'Factor':nodes,'Dispatching Rᵢ':rows,'Receiving Cᵢ':cols,'Prominence Rᵢ+Cᵢ':prominence,'Relation Rᵢ−Cᵢ':relation,'Role':np.where(relation>=0,'Cause','Effect')})
    return [Step('1. Initial direct-relation matrix','A=[aᵢⱼ], aᵢᵢ=0','Enter averaged expert influence scores on the book’s 0–4 scale.',pd.DataFrame(a,index=nodes,columns=nodes),'Chapter 9, §9.2, pp. 140–141'),Step('2. Normalize direct relations','D=sA; s=min(1/maxᵢ∑ⱼaᵢⱼ, 1/maxⱼ∑ᵢaᵢⱼ)','Normalize so the influence matrix converges.',pd.DataFrame(d,index=nodes,columns=nodes),'Chapter 9, §9.2, p. 141'),Step('3. Total relation matrix','T=D(I−D)⁻¹ = (I−D)⁻¹−I','The identity-adjusted form sums direct and indirect effects; the book’s typeset equation omits the final subtraction in one rendering, so the conventional total-relation formulation is shown.',pd.DataFrame(t,index=nodes,columns=nodes),'Chapter 9, §9.2, p. 141'),Step('4. Prominence and relation','Rᵢ=∑ⱼtᵢⱼ; Cᵢ=∑ⱼtⱼᵢ; prominence=Rᵢ+Cᵢ; relation=Rᵢ−Cᵢ','Positive relation indicates net cause; negative relation indicates net effect.',results,'Chapter 9, §9.2, pp. 141–142')]

def _run_ism(ssim,nodes):
    symbols=np.asarray(ssim,dtype=object); n=len(nodes)
    if symbols.shape!=(n,n): raise ValueError('ISM SSIM must be a square matrix matching node names.')
    reach=np.eye(n,dtype=int)
    mapping={'V':(1,0),'A':(0,1),'X':(1,1),'O':(0,0),'-':(0,0),'':(0,0)}
    for i in range(n):
        for j in range(i+1,n):
            s=str(symbols[i,j]).strip().upper()
            if s not in mapping: raise ValueError('ISM SSIM cells must use V, A, X, O (or blank on diagonal).')
            reach[i,j],reach[j,i]=mapping[s]
    initial=reach.copy()
    # Boolean transitive closure.
    for k in range(n): reach=np.maximum(reach,reach[:,[k]]*reach[[k],:])
    remaining=set(range(n)); levels=[]; level_no=1
    while remaining:
        current=[]
        for i in sorted(remaining):
            r={j for j in remaining if reach[i,j]}; a={j for j in remaining if reach[j,i]}
            if r and r==r&a: current.append(i)
        if not current: raise ValueError('ISM level partition failed to progress; inspect SSIM.')
        levels.append(current); remaining-=set(current); level_no+=1
    level_of={i:lv+1 for lv,items in enumerate(levels) for i in items}
    # Top level is conventionally first partition; display level numbers from bottom to top for readability.
    displayed={i:len(levels)-lv for lv,items in enumerate(levels) for i in items}
    out=pd.DataFrame({'Element':nodes,'Level':[displayed[i] for i in range(n)],'Reachability set':['; '.join(nodes[j] for j in range(n) if reach[i,j]) for i in range(n)],'Antecedent set':['; '.join(nodes[j] for j in range(n) if reach[j,i]) for i in range(n)]})
    return [Step('1. Structural self-interaction matrix (SSIM)','V: i→j; A: j→i; X: both; O: no relation','Enter expert-derived contextual relations in the upper triangle.',pd.DataFrame(symbols,index=nodes,columns=nodes),'Chapter 18, §§18.2–18.3.2, pp. 312–315'),Step('2. Initial reachability matrix','V→(1,0); A→(0,1); X→(1,1); O→(0,0); diagonal=1','Convert the SSIM symbols into binary directed reachability.',pd.DataFrame(initial,index=nodes,columns=nodes),'Chapter 18, §18.3.3, p. 315'),Step('3. Final reachability matrix','R=R∨(R[:,k]∧R[k,:]) for k=1…n (transitive closure)','Add transitive links using Boolean matrix multiplication.',pd.DataFrame(reach,index=nodes,columns=nodes),'Chapter 18, §§18.2–18.3, pp. 312–316'),Step('4. Level partition','Reachability set ∩ antecedent set = reachability set','Iteratively remove top-level elements and repeat to identify all levels.',out,'Chapter 18, §18.2, p. 312'),Step('5. ISM hierarchy','Render directed edges after suppressing transitive links','The table contains levels and sets needed to draw the ISM digraph; expert validation remains part of the method.',out[['Element','Level']],'Chapter 18, §§18.2–18.3, pp. 312–318')]

def _run_anp(weighted_supermatrix,nodes):
    """Compute limiting priorities from a user-prepared weighted ANP supermatrix."""
    w=np.asarray(weighted_supermatrix,dtype=float); n=len(nodes)
    if w.shape!=(n,n) or not np.isfinite(w).all() or (w<0).any(): raise ValueError('ANP weighted supermatrix must be finite, nonnegative, square, and match node names.')
    sums=w.sum(axis=0)
    if (sums<=0).any() or not np.allclose(sums,1,atol=1e-5): raise ValueError('Every ANP weighted-supermatrix column must sum to 1 (stochastic).')
    power=np.eye(n); limit=None
    for _ in range(2000):
        power=power@w
        if np.max(np.abs(power-limit))<1e-11 if limit is not None else False:
            break
        limit=power.copy()
    else: raise ValueError('ANP supermatrix did not converge within 2,000 iterations; inspect periodic or reducible network structure.')
    priority=power.mean(axis=1); priority=priority/priority.sum()
    table=pd.DataFrame({'Element':nodes,'Limiting priority':priority}).sort_values('Limiting priority',ascending=False).reset_index(drop=True)
    return priority,[Step('1. Weighted supermatrix','Wᵃʷᵉⁱᵍʰᵗᵉᵈ is column stochastic: ∑ᵢwᵢⱼ=1','This module starts from the weighted supermatrix after cluster weights and local priorities have been combined.',pd.DataFrame(w,index=nodes,columns=nodes),'Chapter 4, §4.3, pp. 66–68'),Step('2. Raise supermatrix to limiting powers','Wᵏ as k→∞','Iterate powers until consecutive matrices converge; periodic/reducible networks may require component-level interpretation.',pd.DataFrame(power,index=nodes,columns=nodes),'Chapter 4, §4.3, p. 68'),Step('3. Limiting priorities','Normalize row averages of the converged limit matrix','Rank nodes by their normalized limiting priorities.',table,'Chapter 4, §4.3, p. 68')]

RANKING_METHODS={'SAW':_run_saw,'TOPSIS':_run_topsis,'MOORA':_run_moora,'MULTIMOORA':_run_multimoora,'COPRAS-G':_run_copras,'ARAS':_run_aras,'WASPAS':_run_waspas,'VIKOR':_run_vikor,'ELECTRE I':_run_electre1,'PROMETHEE II':_run_promethee2,'CoCoSo':_run_cocoso,'EDAS':_run_edas,'MARCOS':_run_marcos,'CODAS':_run_codas,'MAIRCA':_run_mairca,'MABAC':_run_mabac,'GRA':_run_gra,'PIV':_run_piv}

def get_audit_code(method):
    """Return the exact calculation function and shared guards shown in the UI."""
    fn={'AHP':calculate_ahp,'SWARA':calculate_swara,'Entropy weights':calculate_entropy_weights,'CRITIC':calculate_critic_weights,'MEREC':calculate_merec_weights,'Standard deviation':calculate_std_weights,'PSI weights':calculate_psi_weights,'FUCOM':calculate_fucom_weights,'BWM':calculate_bwm_weights,
        'DEMATEL':_run_dematel,'ISM':_run_ism,'ANP':_run_anp,
        'SAW':_run_saw,'TOPSIS':_run_topsis,'MOORA':_run_moora,'MULTIMOORA':_run_multimoora,
        'COPRAS-G':_run_copras,'ARAS':_run_aras,'WASPAS':_run_waspas,'VIKOR':_run_vikor,
        'ELECTRE I':_run_electre1,'PROMETHEE II':_run_promethee2,'CoCoSo':_run_cocoso,'EDAS':_run_edas,'MARCOS':_run_marcos,'CODAS':_run_codas,'MAIRCA':_run_mairca,'MABAC':_run_mabac,'GRA':_run_gra,'PIV':_run_piv}.get(method)
    if fn is None: return '# Select a method to inspect its calculation logic.'
    def source_of(obj):
        try: return inspect.getsource(obj)
        except (OSError,TypeError):
            src=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'core'/'methods.py'
            tree=ast.parse(src.read_text(encoding='utf-8')); name=obj.__name__
            node=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
            lines=src.read_text(encoding='utf-8').splitlines(); return '\n'.join(lines[node.lineno-1:node.end_lineno])
    shared='\n\n'.join(source_of(f) for f in (_check,_normalise_sum_weights,_scores_table,_orient_minmax))
    step_source=source_of(Step)
    extra='from scipy.optimize import linprog\n' if method=='BWM' else ''
    return f'# MCDMStudio calculation source: {method}\n# Dependencies: numpy, pandas. The implementation is copied directly from core/methods.py.\nfrom dataclasses import dataclass\nimport numpy as np\nimport pandas as pd\n{extra}\n{step_source}\n\n{source_of(fn)}\n\n# Shared input validation and ranking helpers\n{shared}\n\n# Random Index lookup used by AHP consistency calculations\nRI = {RI!r}\n'

def run_ranking(method, matrix, alternatives, criteria, directions, weights, **params):
    x=_check(matrix,directions); w=_normalise_sum_weights(weights,x.shape[1])
    if x.shape!=(len(alternatives),len(criteria)): raise ValueError('Matrix dimensions do not match alternative and criterion headers.')
    if method in ('MOORA','MULTIMOORA'): return RANKING_METHODS[method](x,alternatives,criteria,directions)
    if method=='CoCoSo': return _run_cocoso(x,alternatives,criteria,directions,w,params.get('lambda',0.5))
    if method=='CODAS': return _run_codas(x,alternatives,criteria,directions,w,params.get('tau',0.02))
    if method=='WASPAS': return _run_waspas(x,alternatives,criteria,directions,w,params.get('lambda',0.5))
    if method=='VIKOR': return _run_vikor(x,alternatives,criteria,directions,w,params.get('v',0.5))
    fn=RANKING_METHODS.get(method)
    if not fn: raise ValueError(f'Unsupported method: {method}')
    return fn(x,alternatives,criteria,directions,w)
