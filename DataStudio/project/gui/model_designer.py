"""Shared model canvas and properties editor; no statistical logic in this module."""
import copy,json,math,uuid
import tkinter as tk
from tkinter import ttk,filedialog
from pathlib import Path
from xml.sax.saxutils import escape
from core.model_spec import Node,Edge,ModelSpec,save_model,example

BLUE='#4F46E5';INK='#0F172A'
def new_id(prefix):return prefix+uuid.uuid4().hex[:10]

class ModelDesigner(ttk.Frame):
    def __init__(self,parent,app,store):
        super().__init__(parent);self.app=app;self.store=store;self.selected=None;self.source=None;self.drag=None;self.pan=None;self.zoom=1.;self.offset=[40.,40.];self.mode=tk.StringVar(value='select');self.link_kind=tk.StringVar(value='linear');self.link_moderator=tk.StringVar();self.props={}
        self.pack(fill='both',expand=True)
        top=ttk.Frame(self);top.pack(fill='x',padx=12,pady=6)
        for label,mode in [('Select / Move','select'),('Connect','connect')]:ttk.Radiobutton(top,text=label,variable=self.mode,value=mode,command=self.reset_link).pack(side='left',padx=4)
        for label,fn in [('+ Construct',self.add_node),('Delete',self.delete),('Undo',store.undo),('Redo',store.redo),('Auto layout',self.layout),('Fit view',self.fit)]:app.action(top,label,fn).pack(side='left',padx=2)
        files=ttk.Frame(self);files.pack(fill='x',padx=12,pady=(0,6))
        for label,fn in [('Open JSON',self.open),('Save JSON',self.save),('PNG',lambda:self.export('png')),('SVG',lambda:self.export('svg'))]:app.action(files,label,fn).pack(side='left',padx=2)
        self.template=tk.StringVar(value='DIRECT');ttk.Combobox(files,textvariable=self.template,values=['DIRECT','MEDIATION','POLYNOMIAL'],state='readonly',width=16).pack(side='left',padx=8)
        app.action(files,'Load example',self.use_template).pack(side='left')
        links=ttk.Frame(self);links.pack(fill='x',padx=12,pady=(0,4))
        ttk.Label(links,text='New path:').pack(side='left',padx=4)
        self.kind_combo=ttk.Combobox(links,textvariable=self.link_kind,values=['linear'],state='readonly',width=16);self.kind_combo.pack(side='left',padx=4)
        ttk.Label(links,text='Moderator:').pack(side='left',padx=4)
        self.moderator_combo=ttk.Combobox(links,textvariable=self.link_moderator,values=[],state='readonly',width=16);self.moderator_combo.pack(side='left',padx=4)
        ttk.Label(links,text='Powers and interactions require REGRESSION.').pack(side='left',padx=8)
        self.hint=tk.StringVar(value='Select a construct or path to edit. Connect: click source then target. Wheel: zoom. Middle drag: pan.')
        ttk.Label(self,textvariable=self.hint,wraplength=1080).pack(anchor='w',padx=16,pady=4)
        body=ttk.Panedwindow(self,orient='horizontal');self.body=body;body.pack(fill='both',expand=True,padx=12,pady=6)
        self.canvas=tk.Canvas(body,bg='#FAFBFE',highlightthickness=1,highlightbackground='#DCE5F0');body.add(self.canvas,weight=4)
        side=ttk.Frame(body,width=300);body.add(side,weight=1)
        self.property_title=ttk.Label(side,text='Properties',font=(app.ui_font,13,'bold'));self.property_title.pack(anchor='w',padx=10,pady=8)
        property_outer=ttk.Frame(side);property_outer.pack(fill='both',expand=True,padx=8)
        property_canvas=tk.Canvas(property_outer,bg='#F3F5FA',highlightthickness=0,width=280)
        property_scroll=ttk.Scrollbar(property_outer,orient='vertical',command=property_canvas.yview)
        property_canvas.configure(yscrollcommand=property_scroll.set);property_scroll.pack(side='right',fill='y');property_canvas.pack(fill='both',expand=True)
        self.property_area=ttk.Frame(property_canvas);property_window=property_canvas.create_window((0,0),window=self.property_area,anchor='nw')
        app.register_scroll(property_canvas,self.property_area)
        self.property_area.bind('<Configure>',lambda e:property_canvas.configure(scrollregion=property_canvas.bbox('all')))
        property_canvas.bind('<Configure>',lambda e:property_canvas.itemconfigure(property_window,width=e.width))
        app.action(side,'Apply properties',self.apply,True).pack(side='bottom',fill='x',padx=8,pady=8,before=property_outer)
        ttk.Label(side,text='R / R² applies to endogenous constructs.\nMeasurement quality and path significance are separate.\nCB/PLS: reflective, linear.\nPowers / interactions: regression.',wraplength=280).pack(anchor='w',padx=8,pady=8)
        self.canvas.bind('<Configure>',lambda e:self.redraw())
        self.canvas.bind('<Button-1>',self.press);self.canvas.bind('<B1-Motion>',self.motion);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<MouseWheel>',lambda e:self.change_zoom(1.1 if e.delta>0 else 1/1.1,e.x,e.y))
        self.canvas.bind('<Button-4>',lambda e:self.change_zoom(1.1,e.x,e.y));self.canvas.bind('<Button-5>',lambda e:self.change_zoom(1/1.1,e.x,e.y))
        self.canvas.bind('<Button-2>',lambda e:setattr(self,'pan',(e.x,e.y,*self.offset)))
        self.canvas.bind('<B2-Motion>',self.pan_move);self.canvas.bind('<ButtonRelease-2>',lambda e:setattr(self,'pan',None))
        self.canvas.bind('<Delete>',lambda e:self.delete());self.canvas.bind('<Control-z>',lambda e:store.undo() if not app.busy else None);self.canvas.bind('<Control-y>',lambda e:store.redo() if not app.busy else None)
        store.listeners.append(self.changed);self.changed()
    def attach_csv(self,csv_panel):
        from .column_palette import ColumnPalette
        if not hasattr(self,'palette'):
            self.palette=ColumnPalette(self.body,self);self.body.insert(0,self.palette,weight=1)
        self.palette.csv=csv_panel;self.palette.refresh();self.after_idle(self.fit)
    def reset_link(self):self.source=None;self.redraw()
    def xy(self,node):return (node.x*self.zoom+self.offset[0],node.y*self.zoom+self.offset[1])
    def changed(self):
        if self.selected and self.selected[1] not in ({n.id for n in self.store.model.nodes}|{e.id for e in self.store.model.edges}):self.selected=None
        kinds=['linear','quadratic','cubic','interaction'] if self.store.model.method=='REGRESSION' else ['linear']
        self.kind_combo.configure(values=kinds)
        if self.link_kind.get() not in kinds:self.link_kind.set('linear')
        names=[n.name for n in self.store.model.nodes];self.moderator_combo.configure(values=['']+names)
        if self.link_moderator.get() not in names:self.link_moderator.set('')
        if hasattr(self,'palette'):self.palette.refresh()
        self.redraw();self.show_properties()
    def redraw(self):
        c=self.canvas;c.delete('all');m=self.store.model;by=m.by_id
        for x in range(int(self.offset[0]%40),max(1,c.winfo_width()),40):c.create_line(x,0,x,c.winfo_height(),fill='#EDF1F7')
        for e in m.edges:
            if e.source not in by or e.target not in by:continue
            a,b=self.xy(by[e.source]),self.xy(by[e.target]);dx=b[0]-a[0];dy=b[1]-a[1];norm=max(math.hypot(dx,dy),1);ux,uy=dx/norm,dy/norm
            a=(a[0]+55*self.zoom*ux,a[1]+30*self.zoom*uy);b=(b[0]-57*self.zoom*ux,b[1]-32*self.zoom*uy)
            # Separate nonlinear terms visually; all refer to the same shared edge IDs.
            offset={'linear':0,'quadratic':-32,'cubic':32,'interaction':64}.get(e.kind,0)*self.zoom
            mid=((a[0]+b[0])/2-uy*offset,(a[1]+b[1])/2+ux*offset)
            color=BLUE if self.selected==('edge',e.id) else '#61748B'
            tags=('edge',e.id)
            c.create_line(*a,*mid,*b,arrow='last',smooth=True,width=3 if color==BLUE else 2,fill=color,dash=(5,3) if e.expected=='null' else (),tags=tags)
            text=(by[e.source].name+'×'+by[e.moderator].name if e.kind=='interaction' and e.moderator in by else 'x²' if e.kind=='quadratic' else 'x³' if e.kind=='cubic' else '−' if e.sign<0 else '+')
            c.create_text(mid[0],mid[1]-12*self.zoom,text=text+' · '+e.expected,fill=color,font=(self.app.ui_font,max(8,int(9*self.zoom))),tags=tags)
        for n in m.nodes:
            x,y=self.xy(n);selected=self.selected==('node',n.id);color=BLUE if selected or self.source==n.id else '#8EA6BF'
            tags=('node',n.id);c.create_oval(x-62*self.zoom,y-35*self.zoom,x+62*self.zoom,y+35*self.zoom,fill='#EEF2FF' if selected else 'white',outline=color,width=2,tags=tags)
            c.create_text(x,y-9*self.zoom,text=n.name,fill=INK,font=(self.app.ui_font,max(9,int(12*self.zoom)),'bold'),tags=tags)
            c.create_text(x,y+13*self.zoom,text=f'{n.items} items · '+('pass' if n.reliable else 'fail'),fill='#61748B',font=(self.app.ui_font,max(8,int(9*self.zoom))),tags=tags)
            if m.incoming(n.id):c.create_text(x,y+49*self.zoom,text=f'{n.r_metric} target  {n.target_min:.3f} – {n.target_max:.3f}',fill=BLUE,font=(self.app.ui_font,max(8,int(9*self.zoom))),tags=tags)
        c.create_text(12,12,anchor='nw',text=f'{m.method}  •  {len(m.nodes)} constructs  /  {len(m.edges)} paths  •  {self.zoom:.0%}',fill='#61748B')
    def hit(self,event):
        for item in reversed(self.canvas.find_overlapping(event.x-4,event.y-4,event.x+4,event.y+4)):
            tags=self.canvas.gettags(item)
            if tags and tags[0] in ('node','edge'):return tags[0],tags[1]
        return None
    def press(self,event):
        if self.app.busy:return
        self.canvas.focus_set();hit=self.hit(event)
        if self.mode.get()=='connect':
            if hit and hit[0]=='node':
                if self.source is None:self.source=hit[1];self.hint.set('Source selected. Click the target construct.');self.redraw()
                else:
                    if self.source!=hit[1]:
                        m=copy.deepcopy(self.store.model);kind=self.link_kind.get()
                        moderator=next((n.id for n in m.nodes if n.name==self.link_moderator.get()),'') if kind=='interaction' else ''
                        if kind=='interaction' and (not moderator or moderator in (self.source,hit[1])):
                            self.app.error('Select a moderator different from the source and target.');self.source=None;self.redraw();return
                        edge=Edge(new_id('e'),self.source,hit[1],kind=kind,moderator=moderator,block=3 if kind=='cubic' else 2 if kind!='linear' else 1)
                        duplicate=any(e.source==edge.source and e.target==edge.target and e.kind==kind and e.moderator==moderator for e in m.edges)
                        if duplicate:self.hint.set('This path already exists. Select it to edit properties.')
                        else:
                            m.edges.append(edge);self.selected=('edge',edge.id);self.store.commit(m)
                            self.hint.set('Connected '+kind+'. Check the model in Advanced before generating.')
                    self.source=None;self.redraw()
            return
        self.selected=hit;self.show_properties();self.redraw()
        if hit and hit[0]=='node':
            n=self.store.model.by_id[hit[1]];self.drag=(event.x,event.y,n.x,n.y,copy.deepcopy(self.store.model))
    def motion(self,event):
        if not self.drag or self.app.busy:return
        sx,sy,x,y,_=self.drag;n=self.store.model.by_id[self.selected[1]];n.x=x+(event.x-sx)/self.zoom;n.y=y+(event.y-sy)/self.zoom;self.redraw()
    def release(self,event):
        if self.drag:
            before=self.drag[4];after=copy.deepcopy(self.store.model);self.drag=None
            if before.to_dict()!=after.to_dict():self.store.model=before;self.store.commit(after)
    def pan_move(self,event):
        if self.pan:self.offset=[self.pan[2]+event.x-self.pan[0],self.pan[3]+event.y-self.pan[1]];self.redraw()
    def change_zoom(self,factor,x,y):
        new=max(.35,min(2.5,self.zoom*factor));f=new/self.zoom;self.offset=[x-(x-self.offset[0])*f,y-(y-self.offset[1])*f];self.zoom=new;self.redraw()
    def add_node(self):
        if self.app.busy:return
        m=copy.deepcopy(self.store.model)
        if len(m.nodes)>=12:self.app.error('Up to 12 constructs are supported.');return
        i=1
        while f'X{i}' in {n.name for n in m.nodes}:i+=1
        m.nodes.append(Node(new_id('n'),f'X{i}',x=250+20*i,y=200+20*i));self.selected=('node',m.nodes[-1].id);self.store.commit(m)
    def delete(self):
        if not self.selected or self.app.busy:return
        m=copy.deepcopy(self.store.model);kind,id=self.selected
        if kind=='node':m.nodes=[n for n in m.nodes if n.id!=id];m.edges=[e for e in m.edges if id not in (e.source,e.target,e.moderator)]
        else:m.edges=[e for e in m.edges if e.id!=id]
        self.selected=None;self.store.commit(m)
    def show_properties(self):
        for w in self.property_area.winfo_children():w.destroy()
        self.props={}
        if not self.selected:
            self.property_title.configure(text='Properties')
            ttk.Label(self.property_area,text='Select a construct or path',font=(self.app.ui_font,12,'bold'),wraplength=280).pack(anchor='w',pady=(24,8))
            ttk.Label(self.property_area,text='Constructs: indicators, reliability and R / R² range.\n\nPaths: direction, effect target, beta and regression block.',wraplength=280).pack(anchor='w')
            return
        kind,id=self.selected;m=self.store.model
        obj=m.by_id[id] if kind=='node' else next(e for e in m.edges if e.id==id)
        fields=[('name','Construct code',None),('items','Indicator count',None),('reliable','Reliable measurement',True),('alpha_min','Cronbach min',None),('alpha_max','Cronbach max',None),('r_metric','Target metric',['R','R²']),('target_min','Target minimum',None),('target_max','Target maximum',None)] if kind=='node' else [('kind','Term type',['linear','quadratic','cubic','interaction']),('moderator','Moderator',['']+[n.name for n in m.nodes]),('sign','Direction',['1','-1']),('expected','Expected effect',['significant','null','free']),('beta_min','|beta| min',None),('beta_max','|beta| max',None),('block','Regression block',None)]
        self.property_title.configure(text=obj.name if kind=='node' else f'{m.by_id[obj.source].name} → {m.by_id[obj.target].name}')
        for key,label,choices in fields:
            f=ttk.Frame(self.property_area);f.pack(fill='x',pady=3);ttk.Label(f,text=label).pack(anchor='w')
            v=tk.BooleanVar(value=getattr(obj,key)) if choices is True else tk.StringVar(value=str(getattr(obj,key)))
            if key=='moderator':v.set(m.by_id[obj.moderator].name if obj.moderator else '')
            self.props[key]=v
            if choices is True:ttk.Checkbutton(f,text='Require reliable measurement',variable=v).pack(anchor='w')
            elif choices:
                combo=ttk.Combobox(f,textvariable=v,values=choices,state='readonly');combo.pack(fill='x')
                if key=='r_metric':combo.bind('<<ComboboxSelected>>',self.switch_target_metric)
            else:ttk.Entry(f,textvariable=v).pack(fill='x')
        if kind=='node':
            self.previous_metric=obj.r_metric
            if obj.indicators:
                ttk.Label(self.property_area,text='Assigned CSV columns',font=(self.app.ui_font,10,'bold')).pack(anchor='w',pady=(10,4))
                listing=tk.Listbox(self.property_area,height=min(6,len(obj.indicators)),selectmode='extended',exportselection=False)
                for col in obj.indicators:listing.insert('end',col)
                listing.pack(fill='x')
                def remove():
                    if self.app.busy:return
                    model=copy.deepcopy(self.store.model);node=model.by_id[id];removed={listing.get(i) for i in listing.curselection()};node.indicators=[c for c in node.indicators if c not in removed];node.items=max(1,len(node.indicators));self.store.commit(model)
                ttk.Button(self.property_area,text='Remove selected indicators',command=remove).pack(fill='x',pady=5)
        if kind=='edge':ttk.Label(self.property_area,text='Select the moderator by name.\nnull: p ≥ threshold; CI includes 0.\nfree: reported without beta/p gates.',wraplength=280).pack(anchor='w',pady=5)
    def switch_target_metric(self,event):
        try:
            metric=self.props['r_metric'].get()
            if metric!=self.previous_metric:
                values=[float(self.props[k].get()) for k in ('target_min','target_max')]
                values=[x*x for x in values] if self.previous_metric=='R' else [max(0,x)**.5 for x in values]
                for key,val in zip(('target_min','target_max'),values):self.props[key].set(format(val,'.12g'))
            self.previous_metric=metric
        except ValueError:self.previous_metric=self.props['r_metric'].get()
    def apply(self):
        if not self.selected or self.app.busy:return
        try:
            m=copy.deepcopy(self.store.model);kind,id=self.selected;obj=m.by_id[id] if kind=='node' else next(e for e in m.edges if e.id==id)
            for key,v in self.props.items():
                if key in ('r_metric','target_min','target_max'):continue
                old=getattr(obj,key);raw=v.get()
                if key=='moderator':raw=next((n.id for n in m.nodes if n.name==raw),'')
                value=int(raw) if isinstance(old,int) and not isinstance(old,bool) else float(raw) if isinstance(old,float) else raw
                setattr(obj,key,value)
            if kind=='node':
                obj.set_target(self.props['r_metric'].get(),float(self.props['target_min'].get()),float(self.props['target_max'].get()))
                import re
                if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*',obj.name) or sum(n.name==obj.name for n in m.nodes)!=1:raise ValueError('Construct codes must be unique Latin letters/numbers, starting with a letter.')
                minimum=1 if m.method=='REGRESSION' or obj.indicators else 3
                if obj.indicators and obj.items!=len(obj.indicators):raise ValueError('Add/remove CSV indicators using the palette / assigned-columns list.')
                if not minimum<=obj.items<=10 or not .5<=obj.alpha_min<obj.alpha_max<.99 or not 0<obj.r2_min<obj.r2_max<.95:raise ValueError(f'Indicators: {minimum}–10; alpha: .5–.99; R²: 0–.95; min < max.')
            else:
                if not 0<=obj.beta_min<obj.beta_max<=1.5 or not 1<=obj.block<=10:raise ValueError('Beta: 0–1.5, min < max; block: 1–10.')
            self.store.commit(m);self.hint.set('Properties applied. Check the model in Advanced before generating.')
        except Exception as e:self.app.error(e)
    def layout(self):
        if self.app.busy:return
        m=copy.deepcopy(self.store.model)
        try:
            order=m.topological();levels={}
            for id in order:levels[id]=max([levels[p]+1 for p in m.parents(id)]+[0])
            counts={}
            for n in m.nodes:
                level=levels[n.id];row=counts.get(level,0);n.x=150+270*level;n.y=120+150*row;counts[level]=row+1
            self.store.commit(m);self.fit()
        except Exception as e:self.app.error(e)
    def fit(self):
        nodes=self.store.model.nodes
        if not nodes:return
        xmin=min(n.x for n in nodes)-85;xmax=max(n.x for n in nodes)+85;ymin=min(n.y for n in nodes)-60;ymax=max(n.y for n in nodes)+60
        self.zoom=max(.35,min(1.5,(max(200,self.canvas.winfo_width())-40)/(xmax-xmin),(max(200,self.canvas.winfo_height())-50)/(ymax-ymin)))
        self.offset=[20-xmin*self.zoom,35-ymin*self.zoom];self.redraw()
    def use_template(self):
        if self.app.busy:return
        self.selected=None;self.store.commit(example(self.template.get()));self.fit()
    def save(self):
        if self.app.busy:return
        try:
            path=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('Model JSON','*.json')])
            if path:save_model(path,self.store.model);self.app.saved(path)
        except Exception as e:self.app.error(e)
    def open(self):
        if self.app.busy:return
        try:
            path=filedialog.askopenfilename(filetypes=[('Model JSON','*.json')])
            if path:
                if Path(path).stat().st_size>2_000_000:raise ValueError('Model JSON is too large.')
                m=ModelSpec.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))
                # Incomplete diagrams are editable, but malformed IDs/coordinates cannot enter the canvas.
                if len(m.nodes)>12 or len(m.edges)>100 or len(m.by_id)!=len(m.nodes):raise ValueError('Model exceeds limits or contains duplicate IDs.')
                for n in m.nodes:
                    if not isinstance(n.name,str) or not all(isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<100000 for v in (n.x,n.y)):raise ValueError('Invalid construct name or coordinates.')
                if any(e.source not in m.by_id or e.target not in m.by_id or e.moderator and e.moderator not in m.by_id for e in m.edges):raise ValueError('A path references a missing construct.')
                self.selected=None;self.store.commit(m);self.fit()
        except Exception as e:self.app.error(e)
    def export(self,kind):
        if self.app.busy:return
        try:
            path=filedialog.asksaveasfilename(defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
            if path:export_diagram(path,self.store.model,kind);self.app.saved(path)
        except Exception as e:self.app.error(e)

def export_diagram(path,model,kind):
    """Draw from model coordinates, independent of canvas zoom; atomic writes."""
    import os,tempfile
    if not model.nodes:raise ValueError('Add a construct before exporting.')
    xmin=min(n.x for n in model.nodes)-100;ymin=min(n.y for n in model.nodes)-75
    width=int(max(n.x for n in model.nodes)-xmin+100);height=int(max(n.y for n in model.nodes)-ymin+100)
    if width>10000 or height>10000 or width*height>6_000_000:raise ValueError('Diagram is too large. Use Auto layout before exporting.')
    pos={n.id:(n.x-xmin,n.y-ymin) for n in model.nodes}
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/><defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#61748B"/></marker></defs>']
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new('RGB',(width*2,height*2),'white');draw=ImageDraw.Draw(image)
    try:font=ImageFont.truetype('DejaVuSans.ttf',22)
    except OSError:font=ImageFont.load_default()
    for e in model.edges:
        if e.source not in pos or e.target not in pos:continue
        a,b=pos[e.source],pos[e.target];dx=b[0]-a[0];dy=b[1]-a[1];norm=max(math.hypot(dx,dy),1);ux,uy=dx/norm,dy/norm
        a=(a[0]+62*ux,a[1]+35*uy);b=(b[0]-62*ux,b[1]-35*uy);offset={'linear':0,'quadratic':-32,'cubic':32,'interaction':64}.get(e.kind,0)
        mid=((a[0]+b[0])/2-uy*offset,(a[1]+b[1])/2+ux*offset)
        term=model.by_id[e.source].name+'×'+model.by_id[e.moderator].name if e.kind=='interaction' and e.moderator in model.by_id else model.by_id[e.source].name+('²' if e.kind=='quadratic' else '³' if e.kind=='cubic' else '')
        label=term+' · '+e.kind+' · '+e.expected
        svg.append(f'<path d="M {a[0]} {a[1]} Q {2*mid[0]-(a[0]+b[0])/2} {2*mid[1]-(a[1]+b[1])/2} {b[0]} {b[1]}" fill="none" stroke="#61748B" stroke-width="2" marker-end="url(#arrow)"/><text x="{mid[0]}" y="{mid[1]-8}" text-anchor="middle" font-family="sans-serif" font-size="11">{escape(label)}</text>')
        points=[]
        control=(2*mid[0]-(a[0]+b[0])/2,2*mid[1]-(a[1]+b[1])/2)
        for i in range(41):t=i/40;points.append(tuple(2*((1-t)**2*a[j]+2*(1-t)*t*control[j]+t*t*b[j]) for j in range(2)))
        draw.line(points,fill='#61748B',width=3);last=points[-1];prev=points[-2];theta=math.atan2(last[1]-prev[1],last[0]-prev[0]);draw.polygon([last,(last[0]-16*math.cos(theta-.4),last[1]-16*math.sin(theta-.4)),(last[0]-16*math.cos(theta+.4),last[1]-16*math.sin(theta+.4))],fill='#61748B')
        draw.text((mid[0]*2,(mid[1]-12)*2),label,font=font,fill=INK,anchor='mm')
    for n in model.nodes:
        x,y=pos[n.id];svg.append(f'<ellipse cx="{x}" cy="{y}" rx="62" ry="35" fill="#EEF2FF" stroke="#4F46E5" stroke-width="2"/><text x="{x}" y="{y-5}" text-anchor="middle" font-family="sans-serif" font-size="15">{escape(n.name)}</text><text x="{x}" y="{y+16}" text-anchor="middle" font-family="sans-serif" font-size="11">{n.items} items · {"pass" if n.reliable else "fail"}</text>')
        draw.ellipse(((x-62)*2,(y-35)*2,(x+62)*2,(y+35)*2),fill='#EEF2FF',outline=BLUE,width=3);draw.text((x*2,(y-7)*2),n.name,font=font,fill=INK,anchor='mm');draw.text((x*2,(y+16)*2),f'{n.items} items',font=font,fill=INK,anchor='mm')
        if model.incoming(n.id):
            target=f'{n.r_metric} target {n.target_min:.3f} – {n.target_max:.3f}'
            svg.append(f'<text x="{x}" y="{y+52}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#4F46E5">{escape(target)}</text>')
            draw.text((x*2,(y+52)*2),target,font=font,fill=BLUE,anchor='mm')
    svg.append('</svg>');dest=Path(path);fd,tmp=tempfile.mkstemp(dir=dest.parent,suffix='.'+kind);os.close(fd)
    try:
        if kind=='svg':Path(tmp).write_text(''.join(svg),encoding='utf-8')
        else:image.save(tmp,format='PNG')
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
