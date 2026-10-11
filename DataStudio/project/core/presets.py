from .model_spec import example,Edge
PRESETS=['Direct effects','Mediation','Moderation (regression)','Nonlinear regression','Null effect','Unreliable predictor (regression)']
def preset(name,method='CB-SEM'):
    if name not in PRESETS:raise ValueError('Unknown teaching preset.')
    model=example('MEDIATION' if name=='Mediation' else 'POLYNOMIAL' if name=='Nonlinear regression' else 'DIRECT')
    model.title=name
    if name=='Nonlinear regression':return model
    model.method=method
    if name=='Moderation (regression)':
        model.method='REGRESSION';model.edges.append(Edge('e3','n1','n3',kind='interaction',moderator='n2',block=2,beta_min=.04));model.nodes[-1].set_target('R',.50,.65)
    if name in ('Null effect','Unreliable predictor (regression)'):
        model.edges[1].expected='null';model.nodes[-1].set_target('R',.35,.55)
    if name=='Unreliable predictor (regression)':model.method='REGRESSION';model.nodes[1].reliable=False
    return model
