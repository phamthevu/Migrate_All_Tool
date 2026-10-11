import numpy as np
import pandas as pd
from .config_loader import validate_scale
from . import ahp

def parse_advance(df, rows, cols):
    ar,ac={},{}
    if df is None: return ar,ac
    for level in ('High','Low'):
        for value in df.get(level,pd.Series(dtype=object)).dropna():
            v=str(value).strip()
            if v not in rows and v not in cols: raise ValueError(f'Advance references missing names: {v}')
            for names,target in ((rows,ar),(cols,ac)):
                if v in names:
                    if v in target and target[v]!=level: raise ValueError(f'Advance: {v} is both High and Low.')
                    target[v]=level
    return ar,ac

def gen_matrix(rows, cols, fuzzy_df, adv_df, gen_mode, out_mode, *, rng=None, weights=None, noise=.15, max_cr=.1, discrete=True):
    rng = rng or np.random.default_rng()
    if gen_mode not in ('NORMAL','DEMATEL','AHP'): raise ValueError('Invalid mode.')
    if gen_mode in ('DEMATEL','AHP') and rows != cols:
        raise ValueError('AHP / DEMATEL requires identical row and column names in the same order.')
    if gen_mode == 'AHP':
        a,stats=ahp.generate(rows,weights,rng,noise,max_cr,discrete)
        out=ahp.render(a,out_mode); out.attrs.update(stats); out.attrs['crisp']=a
        return out
    if out_mode not in ('LING','FUZZY'): raise ValueError('NORMAL / DEMATEL supports LING or FUZZY.')
    scale=validate_scale(fuzzy_df)
    ar,ac=parse_advance(adv_df,rows,cols)
    levels=sorted(scale['Level'].unique())
    k=max(1,int(np.ceil(len(levels)/3)))
    data=[]
    for i,r in enumerate(rows):
        values=[]
        for j,c in enumerate(cols):
            if gen_mode=='DEMATEL' and i==j:
                values.append(0 if out_mode=='LING' else '(0; 0; 0)'); continue
            prefer=ar.get(r) or ac.get(c)
            allowed=levels[-k:] if prefer=='High' else levels[:k] if prefer=='Low' else levels
            sub=scale[scale.Level.isin(allowed)]
            p=sub.Probability.to_numpy(float)
            if p.sum()<=0: raise ValueError(f'No positive sampling probability in group {prefer}.')
            item=sub.iloc[rng.choice(len(sub),p=p/p.sum())]
            values.append(item['Lingustic' if out_mode=='LING' else 'Fuzzy'])
        data.append(values)
    return pd.DataFrame(data,index=rows,columns=cols)
