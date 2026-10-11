import numpy as np
import pandas as pd

RI = {1:0,2:0,3:.58,4:.90,5:1.12,6:1.24,7:1.32,8:1.41,9:1.45,10:1.49,11:1.51,12:1.48,13:1.56,14:1.57,15:1.59}
SAATY = np.array([1/x for x in range(9,1,-1)] + list(range(1,10)), dtype=float)

def analyze(matrix):
    a = np.asarray(matrix, dtype=float)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or not a.size:
        raise ValueError('AHP requires a nonempty square matrix.')
    n = len(a)
    if n > 15: raise ValueError('CR supports 1–15 criteria; split larger sets into groups.')
    if not np.isfinite(a).all() or (a <= 0).any(): raise ValueError('AHP requires positive finite values.')
    if not np.allclose(a * a.T, 1) or not np.allclose(np.diag(a),1):
        raise ValueError('AHP requires aji=1/aij and diagonal=1.')
    vals, vecs = np.linalg.eig(a)
    idx = np.argmax(vals.real)
    lam = float(vals[idx].real)
    w = np.abs(vecs[:,idx].real); w /= w.sum()
    ci = max(0., (lam-n)/(n-1)) if n > 1 else 0.
    cr = ci/RI[n] if n > 2 else 0.
    return {'weights':w,'lambda_max':lam,'CI':ci,'CR':cr}

def generate(names, weights=None, rng=None, noise=.15, max_cr=.1, discrete=True, attempts=500):
    rng = rng or np.random.default_rng()
    n = len(names)
    if not 1 <= n <= 15: raise ValueError('AHP supports 1–15 criteria.')
    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    if w.shape != (n,) or not np.isfinite(w).all() or (w<=0).any(): raise ValueError('AHP weights must be positive and match the criterion count.')
    if not np.isfinite([noise,max_cr]).all() or not 0<=noise<=1 or not 0<=max_cr<=1:
        raise ValueError('Noise and CR must be in [0,1].')
    w = w/w.sum()
    if w.max()/w.min() > 9+1e-10: raise ValueError('The maximum/minimum weight ratio must not exceed 9.')
    if not isinstance(attempts,int) or attempts<1:raise ValueError('Attempts must be positive.')
    best=None
    for trial in range(attempts):
        a = np.eye(n)
        for i in range(n):
            for j in range(i+1,n):
                v = np.clip(w[i]/w[j]*np.exp(rng.normal(0,noise*(1-trial/max(attempts,1)))),1/9,9)
                if discrete: v = SAATY[np.argmin(abs(np.log(SAATY/v)))]
                a[i,j]=v; a[j,i]=1/v
        stats = analyze(a)
        stats['target_weights']=w
        stats['max_weight_error']=float(np.max(abs(stats['weights']-w)))
        if best is None or stats['CR']<best[1]['CR']:best=(pd.DataFrame(a,index=names,columns=names),stats)
        if stats['CR'] <= max_cr+1e-12:
            stats['target_weights']=w
            stats['max_weight_error']=float(np.max(abs(stats['weights']-w)))
            return pd.DataFrame(a,index=names,columns=names), stats
    best[1]['CR target passed']=False
    return best

def render(matrix, mode):
    if mode == 'CRISP': return matrix.copy()
    if mode not in ('LING','FUZZY'): raise ValueError('Invalid AHP output.')
    def cell(v):
        if mode == 'LING': return 'Equal' if v == 1 else f'{v:.8g} × importance'
        if v == 1: return '(1; 1; 1)'
        inverse = v < 1
        x = 1/v if inverse else v
        l,m,u = max(1,x-1),x,min(9,x+1)
        if inverse: l,m,u=1/u,1/m,1/l
        return f'({l:.12g}; {m:.12g}; {u:.12g})'
    return matrix.map(cell) if hasattr(matrix,'map') else matrix.applymap(cell)
