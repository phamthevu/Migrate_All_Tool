import copy,json
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from core.model_spec import ModelStore
from core.advanced_generate import generate_advanced
from core.delivery import quant_sheets,export_amos_bundle
from core.exporter import export_excel
from .criteria_panel import CriteriaPanel
from .model_designer import ModelDesigner
from .csv_panel import CSVPanel
from core.preflight import preflight
from core.presets import PRESETS,preset

class AdvancedPanel(ttk.Frame):
    def __init__(self,parent,designer_parent,app,analysis_parent,analysis_designer_parent):
        super().__init__(parent);self.pack(fill='both',expand=True);self.app=app;self.store=ModelStore();self.result=None;self.signature=None;self.vars={};self.widgets={};self.range_vars={};self.range_widgets={};self.diagnostics=None
        self.designer=ModelDesigner(designer_parent,app,self.store)
        self.analysis_designer=ModelDesigner(analysis_designer_parent,app,self.store)
        actions=ttk.Frame(self);actions.pack(side='bottom',fill='x',padx=14,pady=10)
        outer=ttk.Frame(self);outer.pack(fill='both',expand=True);canvas=tk.Canvas(outer,bg='#F2F5FA',highlightthickness=0);scroll=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview);canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        page=ttk.Frame(canvas);window=canvas.create_window((0,0),window=page,anchor='nw');app.register_scroll(canvas,page);page.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        presets=ttk.Frame(page);presets.pack(fill='x',padx=14,pady=7)
        ttk.Label(presets,text='Teaching preset').pack(side='left',padx=6)
        self.preset_name=tk.StringVar(value=PRESETS[0]);ttk.Combobox(presets,textvariable=self.preset_name,values=PRESETS,state='readonly',width=33).pack(side='left',padx=6)
        app.action(presets,'Load preset',self.load_preset).pack(side='left',padx=4)
        app.action(presets,'Check feasibility',self.show_preflight).pack(side='left',padx=4)
        top=app.card(page,'01   Advanced settings')
        fields=[('method','Method',['CB-SEM','PLS-SEM','REGRESSION']),('rows','Rows',None),('scale','Response scale',['CONTINUOUS','LIKERT5','LIKERT7']),('seed','Seed (blank = random)',None),('attempts','Attempts',None),('vif_max','Maximum VIF',None),('bootstrap','Bootstrap (50 or 100)',['50','100']),('polynomial_basis','Polynomial basis',['CENTERED','ORTHOGONAL'])]
        for i,(name,label,values) in enumerate(fields):
            var=tk.StringVar();self.vars[name]=var;widget=app.field(top,label,var,i//4,i%4,values);self.widgets[name]=widget
            if name=='method':widget.bind('<<ComboboxSelected>>',lambda e:self.method_changed())
        self.indirect=tk.BooleanVar();self.indirect_widget=ttk.Checkbutton(top,text='CB-SEM: bootstrap indirect-effect confidence intervals',variable=self.indirect);self.indirect_widget.grid(row=2,column=0,columnspan=3,sticky='w',padx=6)
        app.action(top,'Apply settings',self.apply_settings).grid(row=2,column=3,pady=6)
        app.hint(page,'Set an R or R² range for each outcome below. Use Model Designer to edit constructs and paths.\nApply settings before editing the diagram. CB/PLS: reflective linear DAGs. Regression: powers, interactions and blocks.')
        self.range_card=app.card(page,'02   Outcome targets • R / R²')
        self.range_area=ttk.Frame(self.range_card,style='Card.TFrame');self.range_area.pack(fill='x')
        ttk.Label(self.range_card,text='R is the model multiple correlation: R = √R². Pairwise Pearson r is reported separately.',style='Card.TLabel',wraplength=1000).pack(anchor='w',padx=8,pady=6)
        self.csv=CSVPanel(analysis_parent,self);self.csv.pack(side='top',fill='x',padx=14,pady=8,before=self.csv.reports)
        self.criteria=CriteriaPanel(page);self.criteria.pack(fill='x',padx=14,pady=6)
        bar=actions
        for label,fn,primary in [('Edit diagram',self.open_designer,False),('Check model',self.check,False),('Generate & Validate',self.generate,True),('Export Excel',self.export,False),('AMOS bundle',self.export_amos,False)]:app.action(bar,label,fn,primary).pack(side='left',padx=3)
        self.info=tk.StringVar(value='Example: X1, X2 → Y. R, R², beta and VIF are computed after generation.')
        ttk.Label(page,textvariable=self.info,wraplength=1100).pack(anchor='w',padx=18,pady=6)
        self.choice=tk.StringVar(value='Model Nodes');self.combo=ttk.Combobox(page,textvariable=self.choice,state='readonly',width=32,values=['Model Nodes','Model Edges']);self.combo.pack(anchor='e',padx=18);self.combo.bind('<<ComboboxSelected>>',lambda e:self.view())
        self.tree=app.table(page,height=9);self.tree.bind('<Double-1>',self.edit_selected)
        self.store.listeners.append(self.changed);self.changed()
    def load_preset(self):
        if self.app.busy:return
        try:
            model=preset(self.preset_name.get(),self.vars['method'].get());self.store.commit(model);self.designer.fit()
            self.info.set('Preset loaded. Review targets and CSV mapping before running.')
        except Exception as e:self.app.error(e)
    def show_preflight(self):
        if self.app.busy:return
        try:
            self.diagnostics=preflight(self.snapshot());self.combo.configure(values=list(self.combo.cget('values'))+['Preflight']);self.choice.set('Preflight');self.view()
            self.info.set('Generation feasibility checks: warnings are heuristics, not a guarantee. Imported CSV is analyzed regardless of target failures.')
        except Exception as e:self.app.error(e)
    def changed(self):
        m=self.store.model
        for key,v in self.vars.items():v.set('' if getattr(m,key) is None else str(min(m.bootstrap,100) if key=='bootstrap' else getattr(m,key)))
        self.indirect.set(m.bootstrap_indirect);self.criteria.load(m.criteria);self.method_changed()
        if self.result is not None:
            try:stale=m.fingerprint()!=self.signature
            except (ValueError,TypeError):stale=True
            if stale:self.info.set('Model changed. Regenerate before exporting; previous results are for reference.')
        self.render_ranges();self.view()
    def render_ranges(self):
        for w in self.range_area.winfo_children():w.destroy()
        self.range_vars={};self.range_widgets={}
        for i,n in enumerate(self.store.model.nodes):
            if not self.store.model.incoming(n.id):continue
            row=ttk.Frame(self.range_area,style="Card.TFrame");row.pack(fill="x",padx=8,pady=5)
            ttk.Label(row,text=n.name,width=14,style="Card.TLabel",font=(self.app.ui_font,11,"bold")).pack(side="left")
            metric=tk.StringVar(value=n.r_metric);lo=tk.StringVar(value=format(n.target_min,".12g"));hi=tk.StringVar(value=format(n.target_max,".12g"));hint=tk.StringVar()
            combo=ttk.Combobox(row,textvariable=metric,values=["R","R²"],state="readonly",width=7);self.range_widgets[n.id]=combo;combo.pack(side="left",padx=6)
            ttk.Label(row,text="Min",style="Card.TLabel").pack(side="left",padx=6);ttk.Entry(row,textvariable=lo,width=16).pack(side="left")
            ttk.Label(row,text="Max",style="Card.TLabel").pack(side="left",padx=6);ttk.Entry(row,textvariable=hi,width=16).pack(side="left")
            ttk.Label(row,textvariable=hint,style="Card.TLabel").pack(side="left",padx=16)
            self.range_vars[n.id]=(metric,lo,hi)
            def update_hint(*args,metric=metric,lo=lo,hi=hi,hint=hint):
                try:
                    l,h=float(lo.get()),float(hi.get());hint.set(f"R² = {l*l:.3f} – {h*h:.3f}" if metric.get()=="R" else f"R = {max(0,l)**.5:.3f} – {max(0,h)**.5:.3f}")
                except ValueError:hint.set("Enter a numeric range")
            for var in (metric,lo,hi):var.trace_add("write",update_hint)
            previous=[n.r_metric]
            def switch_metric(event,metric=metric,lo=lo,hi=hi,previous=previous):
                try:
                    if metric.get()!=previous[0]:
                        values=[float(lo.get()),float(hi.get())]
                        values=[x*x for x in values] if previous[0]=='R' else [max(0,x)**.5 for x in values]
                        lo.set(format(values[0],'.12g'));hi.set(format(values[1],'.12g'));previous[0]=metric.get()
                except ValueError:previous[0]=metric.get()
            combo.bind('<<ComboboxSelected>>',switch_metric)
            update_hint()
    def method_changed(self):
        method=self.vars['method'].get();self.criteria.method(method)
        self.widgets['polynomial_basis'].configure(state='readonly' if method=='REGRESSION' else 'disabled')
        self.widgets['bootstrap'].configure(state='disabled' if method=='REGRESSION' else 'normal')
        self.indirect_widget.configure(state='normal' if method=='CB-SEM' else 'disabled')
    def snapshot(self):
        m=copy.deepcopy(self.store.model)
        for key,v in self.vars.items():
            raw=v.get().strip()
            value=int(raw) if key in ('rows','attempts','bootstrap') else None if key=='seed' and not raw else int(raw) if key=='seed' else float(raw) if key=='vif_max' else raw
            setattr(m,key,value)
        for id,(metric,low,high) in self.range_vars.items():
            node=m.by_id[id];lo,hi=float(low.get()),float(high.get())
            if metric.get()!=node.r_metric or abs(lo-node.target_min)>1e-10 or abs(hi-node.target_max)>1e-10:node.set_target(metric.get(),lo,hi)
        m.bootstrap_indirect=self.indirect.get();m.criteria=self.criteria.snapshot();return m
    def flush_settings(self):
        m=self.snapshot()
        if m.to_dict()!=self.store.model.to_dict():self.store.commit(m)
    def open_designer(self):
        if self.app.busy:return
        try:self.flush_settings();self.app.tabs.select(self.app.tab_d)
        except Exception as e:self.app.error(e)
    def apply_settings(self):
        if self.app.busy:return
        try:
            m=self.snapshot()
            # Incomplete diagrams can still receive settings; full validation is a separate action.
            if m.to_dict()!=self.store.model.to_dict():self.store.commit(m)
        except Exception as e:self.app.error(e)
    def check(self):
        if self.app.busy:return
        try:
            m=self.snapshot();m.validate()
            if m.to_dict()!=self.store.model.to_dict():self.store.commit(m)
            self.info.set('Model structure is valid. Statistical targets will be checked on the generated dataset.')
            messagebox.showinfo('Valid model',f'{m.method}: {len(m.nodes)} constructs / {len(m.edges)} paths. Valid DAG structure.')
        except Exception as e:self.app.error(e)
    def generate(self):
        if self.app.busy:return
        try:
            m=self.snapshot();self.diagnostics=preflight(m);m.validate();signature=m.fingerprint()
            if m.to_dict()!=self.store.model.to_dict():self.store.commit(m)
        except Exception as e:self.app.error(e);return
        self.result=None;self.signature=None
        def done(r):
            r.reports['Generation Preflight']=self.diagnostics.copy();self.result=r;self.signature=signature;self.combo.configure(values=['Data','Construct Scores','Model Nodes','Model Edges']+[k for k in r.reports if k not in ('Model Nodes','Model Edges')]);self.choice.set('Acceptance');self.view()
            r2=r.reports['Structural R2'];summary=' / '.join(f'{row.Target}: R={row.R:.3f} · R²={row.R2:.3f}' for row in r2.itertuples())
            outcome='All required criteria passed' if r.settings.get('Required criteria passed',False) else 'BEST EFFORT — failed criteria remain; review Acceptance'
            self.info.set(f'{m.method} • {len(r.data)} rows • {outcome} • {summary} • candidate {r.settings["Attempt accepted"]}')
            self.app.status.set('Finished • Export Excel is enabled • '+('All criteria passed' if r.settings.get('Required criteria passed',False) else 'BEST EFFORT — failed/incomplete checks retained'))
        self.app.start(lambda:generate_advanced(m,progress=self.app.progress,cancel=self.app.cancel_event),done)
    def view(self):
        import pandas as pd
        name=self.choice.get();m=self.store.model
        if name=='Preflight':df=self.diagnostics
        elif name=='Model Nodes':df=pd.DataFrame([vars(n) for n in m.nodes])
        elif name=='Model Edges':df=pd.DataFrame([vars(e) for e in m.edges])
        elif self.result is None:return
        else:df=self.result.data if name=='Data' else self.result.scores if name=='Construct Scores' else self.result.reports.get(name,pd.DataFrame())
        self.app.show_table(self.tree,df)
    def edit_selected(self,event):
        if self.choice.get() not in ('Model Nodes','Model Edges') or self.app.busy:return
        row=self.tree.identify_row(event.y)
        if not row:return
        values=self.tree.item(row,'values')
        if len(values)<2:return
        self.apply_settings();self.designer.selected=('node' if self.choice.get()=='Model Nodes' else 'edge',values[1]);self.designer.show_properties();self.designer.redraw();self.app.tabs.select(self.app.tab_d)
    def checked(self):
        if self.result is None or self.snapshot().fingerprint()!=self.signature:raise ValueError('Model or settings changed, or no dataset exists. Generate & Validate before exporting.')
        return self.result
    def export(self):
        if self.app.busy:return
        try:
            r=self.checked();path=self.app.choose_save()
            if path:self.app.start(lambda:export_excel(path,quant_sheets(r),cancel=self.app.cancel_event),lambda _:self.app.saved(path))
        except Exception as e:self.app.error(e)
    def export_amos(self):
        if self.app.busy:return
        try:
            r=self.checked()
            if not r.settings['CB SEM']:raise ValueError('AMOS bundles require CB-SEM results.')
            path=self.app.choose_save('.zip')
            if path:self.app.start(lambda:export_amos_bundle(path,r,cancel=self.app.cancel_event),lambda _:self.app.saved(path))
        except Exception as e:self.app.error(e)
