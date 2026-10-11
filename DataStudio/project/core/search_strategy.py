"""Observed-result selection and finite-sample calibration for synthetic demos."""
import numpy as np
import pandas as pd

def calibrated_noise(rng, n, basis=None, columns=1):
    noise=rng.normal(size=(n,columns));noise-=noise.mean(axis=0)
    if basis is not None:
        x=np.asarray(basis,float).reshape(n,-1);x=x-x.mean(axis=0)
        noise-=x@np.linalg.lstsq(x,noise,rcond=None)[0]
    q,_=np.linalg.qr(noise,mode='reduced')
    return q[:,:columns]*np.sqrt(n)

def quality(reports):
    table=reports.get('Acceptance',pd.DataFrame())
    required=table['Required'].astype(bool) if 'Required' in table else pd.Series(True,index=table.index)
    fails=int((required & ~table['Pass'].astype(bool)).sum()) if 'Pass' in table else 1
    structural=reports.get('Structural R2',reports.get('Regression Summary',pd.DataFrame()))
    r2=structural['R2'].to_numpy(float) if 'R2' in structural else np.array([])
    # Weakest equation first prevents one strong outcome hiding a weak one.
    r=float(np.sqrt(np.clip(np.min(r2),0,1))) if len(r2) and np.isfinite(r2).all() else -1.
    return (r,-fails)

def mark_result(result,passed,attempt,tried,history):
    result.settings.update({'Required criteria passed':bool(passed),'Best effort':not bool(passed),
        'Attempt accepted':attempt,'Attempts evaluated':tried,'Selection policy':'Highest minimum equation R, then fewest required failed checks',
        'Generation strategy':'Calibrated latent signal, orthogonal indicator noise, observed-result feedback'})
    result.reports['Generation Search']=pd.DataFrame(history)
    return result


def stopped_result(result,attempt,tried,history):
    if 'Inference Status' in result.reports:
        result.reports['Acceptance']=pd.concat([result.reports['Acceptance'],pd.DataFrame([{
            'Scope':'Inference','Metric':'Bootstrap completed','Required':True,'Pass':False,'Status':'FAIL',
            'Actual':0.,'Direction':'min','Target':1.}])],ignore_index=True)
        result.reports['Inference Status']=pd.DataFrame([{'Status':'INCOMPLETE','Reason':'Stopped by user; point estimates retained, bootstrap incomplete'}])
    result.settings['Stopped by user']=True
    return mark_result(result,False,attempt,tried,history)
