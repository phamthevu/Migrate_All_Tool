"""Directed synthetic DEMATEL, with independent prominence and net-role targets."""
import numpy as np
import pandas as pd


def evaluate(values, names):
    a=np.asarray(values,float)
    if a.shape!=(len(names),len(names)) or not np.isfinite(a).all() or (a<0).any():
        raise ValueError('DEMATEL requires a finite nonnegative square matrix.')
    if not np.allclose(np.diag(a),0):raise ValueError('DEMATEL direct diagonal must be zero.')
    s=max(a.sum(axis=0).max(),a.sum(axis=1).max())
    if s<=0:raise ValueError('DEMATEL needs at least one positive influence.')
    x=a/s
    if max(abs(np.linalg.eigvals(x)))>=1-1e-10:
        raise ValueError('DEMATEL normalization does not converge; vary the influence matrix.')
    t=np.linalg.solve((np.eye(len(a))-x).T,x.T).T
    r,c=t.sum(axis=1),t.sum(axis=0);prom=r+c;net=r-c
    return pd.DataFrame({'R':r,'C':c,'R+C':prom,'Weight':prom/prom.sum(),'R-C':net,
        'Role':np.where(net>1e-9,'CAUSE',np.where(net< -1e-9,'EFFECT','BALANCED')),
        'Prominence group':np.where(prom>=prom.mean(),'HIGH','LOW'),
        'Region':np.where(prom>=prom.mean(),np.where(net>=0,'I','IV'),np.where(net>=0,'II','III'))},index=names)


def profile_arrays(names, profiles=None, weights=None):
    profiles=profiles or {};p=[];q=[]
    for i,name in enumerate(names):
        item=profiles.get(name,{})
        group=str(item.get('Prominence','AUTO')).upper();role=str(item.get('Role','AUTO')).upper()
        strength=float(item.get('Strength',.65))
        if group not in ('AUTO','HIGH','MEDIUM','LOW','RANK') or role not in ('AUTO','CAUSE','EFFECT','BALANCED') or not np.isfinite(strength) or not 0<=strength<=1:
            raise ValueError('DEMATEL profiles require valid prominence / role and strength in [0,1].')
        p.append({'HIGH':.85,'MEDIUM':0.,'LOW':-.85,'AUTO':0.,'RANK':0.}[group])
        q.append((1 if role=='CAUSE' else -1 if role=='EFFECT' else 0 if role=='BALANCED' else (1 if i%2==0 else -1))*(.25+.75*strength))
    p=np.array(p);q=np.array(q)
    # Rank is a soft prominence target; ties are allowed. It never assigns net role.
    ranks=[]
    for i,name in enumerate(names):
        rank=float(profiles.get(name,{}).get('Rank',i+1))
        if not np.isfinite(rank) or not 1<=rank<=len(names):raise ValueError('DEMATEL rank must be in 1..factor count; ties are allowed.')
        ranks.append(rank)
        if profiles.get(name,{}).get('Prominence','AUTO').upper()=='RANK':p[i]=.85*(1-2*(rank-1)/max(1,len(names)-1))
    if weights is not None:
        w=np.log(np.asarray(weights,float));w-=w.mean()
        if np.ptp(w)>0:
            w=w/max(abs(w))*.7
            for i,name in enumerate(names):
                if profiles.get(name,{}).get('Prominence','AUTO').upper()=='AUTO':p[i]=w[i]
    return p,q


def target_checks(report,profiles):
    checks=[];mean=report['R+C'].mean()
    for name,item in (profiles or {}).items():
        row=report.loc[name];role=item.get('Role','AUTO').upper();group=item.get('Prominence','AUTO').upper()
        if role=='CAUSE':checks.append(row['R-C']>1e-9)
        elif role=='EFFECT':checks.append(row['R-C']< -1e-9)
        elif role=='BALANCED':checks.append(abs(row['R-C'])/row['R+C']<=.1)
        if group=='HIGH':checks.append(row['R+C']>=mean)
        elif group=='LOW':checks.append(row['R+C']<mean)
    return sum(not bool(x) for x in checks)
