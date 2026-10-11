"""Explicit, configurable acceptance rules shared by quick and advanced SEM."""
import copy
import numpy as np
import pandas as pd

DEFAULTS = {
 'CFI':('min',.90,True),'TLI':('min',.90,True),'NFI':('min',.90,True),
 'GFI':('min',.90,False),'AGFI':('min',.90,False),
 'RMSEA':('max',.08,True),'SRMR':('max',.08,True),'CMIN/DF':('max',3.,True),
 'Chi-square p':('min',.05,False),'Loading':('min',.50,True),
 'Composite reliability':('min',.70,True),'AVE':('min',.50,True),
 'HTMT':('max',.85,True),'Fornell-Larcker':('min',1.,True),
 'Loading p':('max',.05,True),'Path p':('max',.05,True)
}

def defaults(strict=False):
    rules={k:{'direction':d,'value':v,'required':r} for k,(d,v,r) in DEFAULTS.items()}
    if strict:
        for key in ('CFI','TLI','NFI'):rules[key]['value']=.95
        rules['RMSEA']['value']=.06;rules['Loading']['value']=.70
    return rules

def validate_rules(rules):
    result=copy.deepcopy(rules if rules is not None else defaults())
    if set(result)!=set(DEFAULTS):raise ValueError('SEM criteria contain missing or extra metrics. Reset to the Balanced preset.')
    for name,rule in result.items():
        if set(rule)!={'direction','value','required'}:raise ValueError(f'Criterion {name} has an invalid schema.')
        if rule['direction']!=DEFAULTS[name][0] or not isinstance(rule['required'],bool):raise ValueError(f'Direction / requirement for {name} is invalid.')
        try:value=float(rule['value'])
        except (TypeError,ValueError):raise ValueError(f'{name} requires a numeric value.')
        if not np.isfinite(value) or value<=0 or (name!='CMIN/DF' and value>1):raise ValueError(f'Threshold {name} must be in (0,1]; Chi-square/df must be >0.')
        result[name]['value']=value
    return result

def loading_floor(rules):
    floor=0.
    for key,power in [('Loading',1),('AVE',.5)]:
        if rules[key]['required']:floor=max(floor,rules[key]['value']**power)
    return floor

class Checks:
    def __init__(self,rules):self.rules=validate_rules(rules);self.rows=[]
    def add(self,scope,name,value,required=None,threshold=None,direction=None):
        rule=self.rules.get(name,{'required':True,'value':1.,'direction':'min'})
        required=rule['required'] if required is None else required
        threshold=rule['value'] if threshold is None else threshold
        direction=rule['direction'] if direction is None else direction
        finite=bool(np.isfinite(value))
        passed=finite and (value>=threshold if direction=='min' else value<=threshold)
        self.rows.append({'Scope':scope,'Metric':name,'Actual':value,'Direction':direction,'Target':threshold,'Required':bool(required),'Pass':bool(passed),'Status':'PASS' if passed else 'NOT REQUIRED' if not required else 'FAIL'})
        return passed or not required
    def guard(self,scope,name,valid):return self.add(scope,name,float(bool(valid)),required=True,threshold=1.,direction='min')
    @property
    def passed(self):return all(r['Pass'] or not r['Required'] for r in self.rows)
    def frame(self):return pd.DataFrame(self.rows)
