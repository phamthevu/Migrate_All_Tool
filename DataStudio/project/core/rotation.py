import numpy as np

def varimax(loadings,gamma=1.,iterations=500,tolerance=1e-6):
    # Kaiser normalization, as in common SPSS classroom workflows.
    x=np.asarray(loadings,float)
    norms=np.sqrt((x*x).sum(axis=1)); norms=np.maximum(norms,1e-12)
    normalized=x/norms[:,None]; p,k=x.shape
    rotation=np.eye(k); old=0.
    for _ in range(iterations):
        a=normalized@rotation
        u,s,vh=np.linalg.svd(normalized.T@(a**3-gamma/p*a@np.diag((a*a).sum(axis=0))))
        rotation=u@vh; current=s.sum()
        if old and current<=old*(1+tolerance): break
        old=current
    return (normalized@rotation)*norms[:,None]
