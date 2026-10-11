"""Pre-generation diagnostics; statistical feasibility warnings are not proofs."""
import numpy as np
import pandas as pd
from .criteria import loading_floor

def preflight(spec):
    rows=[]
    def put(level,scope,issue,action):rows.append({'Level':level,'Scope':scope,'Issue':issue,'Suggestion':action})
    try:spec.validate()
    except (ValueError,TypeError) as e:put('ERROR','Model',str(e),'Resolve model / target validation errors before generation.')
    floor=loading_floor(spec.criteria) if spec.method!='REGRESSION' else 0
    for n in spec.nodes:
        if n.reliable and floor:
            bound=n.items*floor**2/(1+(n.items-1)*floor**2)
            if n.alpha_max-bound<.03:put('WARNING',n.name,'Alpha max is close to the implied loading / AVE boundary.','Raise alpha max, reduce indicators or relax the enabled loading / AVE threshold.')
        if spec.incoming(n.id):
            if n.r2_max-n.r2_min<.025:put('WARNING',n.name,'Narrow R / R² range may require many candidates.','Widen the range or increase rows / attempts.')
            if spec.method!='CB-SEM' and n.r2_min>n.alpha_max:put('WARNING',n.name,'R² exceeds alpha max; the equal-loading synthesis may face substantial attenuation.','Review reliability and range targets. This is a heuristic, not a universal upper bound.')
        if spec.method=='CB-SEM' and not n.reliable:put('WARNING',n.name,'An unreliable scale remains in the advanced CB model.','Use reliable measurement or remove it from the model; near-independent items can cause inadmissible fits.')
    if spec.method=='REGRESSION' and spec.polynomial_basis=='CENTERED' and any(e.kind=='cubic' for e in spec.edges):put('WARNING','Regression','Centered cubic terms can be highly correlated with linear terms.','Use ORTHOGONAL basis or review the VIF target; coefficients have a different interpretation.')
    if spec.method!='REGRESSION' and spec.bootstrap<500:put('INFO','Bootstrap','Fewer than 500 resamples: useful for a quick demo, less stable intervals.','Increase bootstrap for the final teaching example if runtime allows.')
    if not rows:put('INFO','Model','No obvious conflicts found.','Only actual generation and validation determine whether all targets can pass.')
    return pd.DataFrame(rows)
