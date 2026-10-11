"""Versioned model graph independent of the UI and analysis backends."""
from dataclasses import dataclass,field,asdict
import copy,hashlib,json,math,re,os,tempfile
from pathlib import Path
from .criteria import defaults,validate_rules

@dataclass
class Node:
    id:str
    name:str
    items:int=3
    reliable:bool=True
    alpha_min:float=.70
    alpha_max:float=.85
    r2_min:float=.25
    r2_max:float=.49
    x:float=200.
    y:float=200.
    r_metric:str='R'
    indicators:list=field(default_factory=list)
    @property
    def target_min(self):return math.sqrt(self.r2_min) if self.r_metric=='R' else self.r2_min
    @property
    def target_max(self):return math.sqrt(self.r2_max) if self.r_metric=='R' else self.r2_max
    def set_target(self,metric,low,high):
        if metric not in ('R','R²'):raise ValueError('Target metric must be R or R².')
        if not all(math.isfinite(v) for v in (low,high)) or not 0<low<high<1:raise ValueError('Use 0 < minimum < maximum < 1.')
        lo,hi=(low*low,high*high) if metric=='R' else (low,high)
        if hi>=.95:raise ValueError('Supported R² maximum is below .95 (R maximum below .97468).')
        if metric==self.r_metric and abs(low-self.target_min)<1e-10 and abs(high-self.target_max)<1e-10:return
        self.r_metric=metric;self.r2_min=lo;self.r2_max=hi
    @property
    def accepted(self):return self.reliable
    @property
    def columns(self):return [f'{self.name}_{i+1}' for i in range(self.items)]

@dataclass
class Edge:
    id:str
    source:str
    target:str
    kind:str='linear'
    moderator:str=''
    sign:int=1
    expected:str='significant'
    beta_min:float=.02
    beta_max:float=.90
    block:int=1

@dataclass
class ModelSpec:
    version:int=4
    title:str='Demo model'
    method:str='CB-SEM'
    rows:int=500
    scale:str='CONTINUOUS'
    seed:int|None=42
    attempts:int=80
    bootstrap:int=100
    bootstrap_indirect:bool=True
    vif_max:float=5.
    polynomial_basis:str='CENTERED'
    criteria:dict=field(default_factory=defaults)
    nodes:list=field(default_factory=list)
    edges:list=field(default_factory=list)
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,data):
        if not isinstance(data,dict) or data.get('version')!=4:raise ValueError('Only model JSON version 4 is supported.')
        if set(data)!=set(cls().__dict__):raise ValueError('Model JSON has missing or extra fields.')
        obj=copy.deepcopy(data)
        try:
            if not isinstance(obj['nodes'],list) or not isinstance(obj['edges'],list) or len(obj['nodes'])>12 or len(obj['edges'])>100:
                raise ValueError('Model JSON exceeds 12 constructs / 100 paths.')
            template=cls()
            for key,default in vars(template).items():
                value=obj[key]
                if key in ('nodes','edges','criteria'):continue
                if key=='seed':
                    if value is not None and (type(value) is not int or value<0):raise ValueError('Invalid seed.')
                elif isinstance(default,bool):
                    if type(value) is not bool:raise ValueError(f'{key}: requires a boolean.')
                elif isinstance(default,int):
                    if type(value) is not int:raise ValueError(f'{key}: requires an integer.')
                elif isinstance(default,float):
                    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError(f'{key}: requires a finite number.')
                elif not isinstance(value,str):raise ValueError(f'{key}: requires a string.')
            for listkey,kind in [('nodes',Node),('edges',Edge)]:
                converted=[]
                for fields in obj[listkey]:
                    if not isinstance(fields,dict):raise ValueError('Constructs / paths must be JSON objects.')
                    item=kind(**fields)
                    sample=Node('','') if kind is Node else Edge('','','')
                    for key,value in vars(item).items():
                        default=getattr(sample,key)
                        if isinstance(default,list):valid=isinstance(value,list) and len(value)<=10 and all(isinstance(c,str) and c for c in value) and len(set(value))==len(value)
                        elif isinstance(default,bool):valid=type(value) is bool
                        elif isinstance(default,int):valid=type(value) is int
                        elif isinstance(default,float):valid=type(value) in (int,float) and math.isfinite(value)
                        else:valid=isinstance(value,str)
                        if not valid:raise ValueError(f'{listkey}.{key}: invalid data type.')
                    if not item.id or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',item.id):raise ValueError('IDs must use letters, numbers or underscores and start with a letter.')
                    converted.append(item)
                obj[listkey]=converted
            obj['criteria']=validate_rules(obj['criteria'])
            return cls(**obj)
        except (TypeError,KeyError) as e:raise ValueError(f'Invalid model JSON: {e}')
    @property
    def by_id(self):return {n.id:n for n in self.nodes}
    def incoming(self,node_id):return [e for e in self.edges if e.target==node_id]
    def parents(self,node_id):
        return sorted({p for e in self.incoming(node_id) for p in (e.source,e.moderator) if p})
    def topological(self):
        ids=[n.id for n in self.nodes];done=[]
        while len(done)<len(ids):
            ready=[i for i in ids if i not in done and set(self.parents(i))<=set(done)]
            if not ready:raise ValueError('The model contains a cycle. Only DAGs are supported.')
            done.extend(ready)
        return done
    def validate(self,for_generation=True):
        errors=[]
        if self.method not in ('CB-SEM','PLS-SEM','REGRESSION'):errors.append('Method must be CB-SEM, PLS-SEM or REGRESSION.')
        if not isinstance(self.rows,int) or isinstance(self.rows,bool) or not 100<=self.rows<=10000:errors.append('Rows must be 100–10,000.')
        if self.method=='CB-SEM' and self.rows<200:errors.append('CB-SEM requires ≥200 rows.')
        if self.scale not in ('CONTINUOUS','LIKERT5','LIKERT7'):errors.append('Invalid response scale.')
        if self.seed is not None and (not isinstance(self.seed,int) or self.seed<0):errors.append('Seed must be a nonnegative integer or blank.')
        if not isinstance(self.attempts,int) or not 1<=self.attempts<=500:errors.append('Attempts: 1–500.')
        if not isinstance(self.bootstrap,int) or not 50<=self.bootstrap<=5000:errors.append('Bootstrap resamples must be 50–5,000; generation uses 50–100 (default 100).')
        if not math.isfinite(self.vif_max) or not 1<self.vif_max<=10:errors.append('Maximum VIF must be in (1,10].')
        if self.polynomial_basis not in ('CENTERED','ORTHOGONAL'):errors.append('Invalid polynomial basis.')
        try:validate_rules(self.criteria)
        except ValueError as e:errors.append(str(e))
        if not 2<=len(self.nodes)<=12:errors.append('Use 2–12 constructs.')
        if len({n.id for n in self.nodes})!=len(self.nodes) or len({n.name for n in self.nodes})!=len(self.nodes):errors.append('IDs and construct codes must be unique.')
        if sum(n.items for n in self.nodes)>80:errors.append('Up to 80 indicators are supported.')
        ids=set(self.by_id)
        for n in self.nodes:
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*',n.name) or n.name in ('Intercept','const'):errors.append(f'Construct code {n.name}: Latin letters/numbers, starting with a letter; const/Intercept is reserved.')
            minimum=1 if self.method=='REGRESSION' and not for_generation else 3
            if not isinstance(n.items,int) or not minimum<=n.items<=10:errors.append(f'{n.name}: requires {minimum}–10 indicators ({self.method}).')
            if n.indicators and (len(n.indicators)!=n.items or len(set(n.indicators))!=len(n.indicators)):errors.append(f'{n.name}: mapped indicator count must match items and be unique.')
            if not all(math.isfinite(v) for v in (n.alpha_min,n.alpha_max,n.r2_min,n.r2_max,n.x,n.y)):errors.append(f'{n.name}: values must be finite.')
            if not .5<=n.alpha_min<n.alpha_max<.99:errors.append(f'{n.name}: 0.5 ≤ Alpha min < max <0.99.')
            if n.r_metric not in ('R','R²'):errors.append(f'{n.name}: target metric must be R or R².')
            if not 0<n.r2_min<n.r2_max<.95:errors.append(f'{n.name}: 0 < R² min < max <0.95.')
            if abs(n.x)>100000 or abs(n.y)>100000:errors.append(f'{n.name}: coordinates are too large.')
        if len({e.id for e in self.edges})!=len(self.edges):errors.append('Duplicate path ID.')
        seen=set()
        for e in self.edges:
            if e.source not in ids or e.target not in ids or (e.moderator and e.moderator not in ids):errors.append(f'{e.id}: source / target construct is missing.');continue
            if e.target in (e.source,e.moderator):errors.append(f'{e.id}: self-loops are not allowed.')
            if e.kind not in ('linear','quadratic','cubic','interaction'):errors.append(f'{e.id}: invalid term type.')
            if self.method!='REGRESSION' and e.kind!='linear':errors.append('Interactions / powers require REGRESSION. CB / PLS uses linear paths.')
            if e.kind=='interaction' and (not e.moderator or e.source==e.moderator):errors.append('An interaction requires two different source constructs.')
            if e.kind!='interaction' and e.moderator:errors.append(f'{e.id}: moderator is only valid for interactions.')
            key=(tuple(sorted((e.source,e.moderator))),e.target,e.kind) if e.kind=='interaction' else (e.source,e.target,e.kind,e.moderator)
            if key in seen:errors.append(f'{e.id}: duplicate path.')
            seen.add(key)
            if e.sign not in (-1,1) or e.expected not in ('significant','null','free'):errors.append(f'{e.id}: invalid path target.')
            if not all(math.isfinite(v) for v in (e.beta_min,e.beta_max)) or not 0<=e.beta_min<e.beta_max<=1.5:errors.append(f'{e.id}: use 0 ≤ |beta| min < max ≤1.5.')
            if not isinstance(e.block,int) or not 1<=e.block<=10:errors.append('Regression blocks must be 1–10.')
        if not self.edges:errors.append('At least one path is required.')
        for n in self.nodes:
            if not any(n.id in (e.source,e.target,e.moderator) for e in self.edges):errors.append(f'{n.name} is isolated; connect or remove it.')
        for e in self.edges:
            if e.kind!='linear' and e.source in ids and e.target in ids and (not e.moderator or e.moderator in ids):
                required=[e.source]+([e.moderator] if e.kind=='interaction' else [])
                for src in required:
                    if not any(x.source==src and x.target==e.target and x.kind=='linear' for x in self.edges):errors.append(f'{e.id}: add main effect {self.by_id[src].name} → {self.by_id[e.target].name} first.')
                main_edges=[x for x in self.edges if x.target==e.target and x.source in required and x.kind=='linear']
                if any(x.block>e.block for x in main_edges):errors.append(f'{e.id}: main effects must enter no later than higher-order terms.')
                if e.kind=='cubic' and not any(x.source==e.source and x.target==e.target and x.kind=='quadratic' for x in self.edges):errors.append(f'{e.id}: cubic terms require quadratic terms.')
        try:self.topological()
        except ValueError as e:errors.append(str(e))
        for n in self.nodes:
            incoming=self.incoming(n.id)
            # Conflicting statistical goals are reported as failed checks, not input errors.
        if errors:raise ValueError('\n'.join(dict.fromkeys(errors)))
        return self.topological()
    def fingerprint(self):
        data=self.to_dict();data.pop('title')
        for n in data['nodes']:n.pop('x');n.pop('y')
        return hashlib.sha256(json.dumps(data,sort_keys=True,allow_nan=False).encode()).hexdigest()

class ModelStore:
    def __init__(self,model=None):self.model=model or example('DIRECT');self.undo_stack=[];self.redo_stack=[];self.listeners=[]
    def notify(self):
        for f in self.listeners[:]:f()
    def commit(self,model):
        self.undo_stack.append(self.model.to_dict());self.undo_stack=self.undo_stack[-100:]
        self.redo_stack=[];self.model=model;self.notify()
    def undo(self):
        if self.undo_stack:self.redo_stack.append(self.model.to_dict());self.model=ModelSpec.from_dict(self.undo_stack.pop());self.notify()
    def redo(self):
        if self.redo_stack:self.undo_stack.append(self.model.to_dict());self.model=ModelSpec.from_dict(self.redo_stack.pop());self.notify()

def example(kind='DIRECT'):
    nodes=[Node('n1','X1',x=180,y=160),Node('n2','X2',x=180,y=360),Node('n3','Y',x=560,y=250)]
    edges=[Edge('e1','n1','n3'),Edge('e2','n2','n3')]
    if kind=='MEDIATION':
        nodes.insert(2,Node('n4','M',r2_min=.15,r2_max=.30,x=410,y=160))
        nodes[-1].x=730;nodes[-1].r2_min=.25;nodes[-1].r2_max=.45
        edges=[Edge('e1','n1','n4'),Edge('e2','n4','n3'),Edge('e3','n2','n3'),Edge('e4','n1','n3',beta_min=.01)]
    if kind=='MEDIATION':
        next(n for n in nodes if n.name=='M').set_target('R',.35,.50)
        next(n for n in nodes if n.name=='Y').set_target('R',.50,.65)
    model=ModelSpec(nodes=nodes,edges=edges)
    if kind=='POLYNOMIAL':
        model.method='REGRESSION';model.polynomial_basis='ORTHOGONAL'
        model.edges += [Edge('e3','n1','n3',kind='quadratic',block=2),Edge('e4','n1','n3',kind='cubic',block=3),Edge('e5','n1','n3',kind='interaction',moderator='n2',block=2)]
    return model

def save_model(path,model):
    # Editing incomplete diagrams is allowed; analysis performs full validation.
    dest=Path(path);fd,tmp=tempfile.mkstemp(dir=dest.parent,suffix='.json');os.close(fd)
    try:
        Path(tmp).write_text(json.dumps(model.to_dict(),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
