import json,copy,hashlib
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog
from core.csv_analysis import read_csv,prepare_data,analyze_csv

class CSVPanel(ttk.LabelFrame):
    def __init__(self,parent,advanced):
        super().__init__(parent,text='03   Import CSV & analyze your model',padding=12)
        self.a=advanced;self.app=advanced.app;self.frame=None;self.metadata={};self.path='';self.mapping={};self.result_signature=None;self.result=None;self.model_signature=None
        self.encoding=tk.StringVar(value='utf-8-sig');self.delimiter=tk.StringVar(value='auto');self.decimal=tk.StringVar(value='.');self.drop=tk.BooleanVar(value=False);self.info=tk.StringVar(value='No CSV loaded. Imported data is analyzed once; failed criteria remain visible and exportable.')
        top=ttk.Frame(self);top.pack(fill='x')
        for label,var,values in [('Encoding',self.encoding,['utf-8-sig','utf-8','cp1252','latin1']),('Delimiter',self.delimiter,['auto',',',';','TAB']),('Decimal',self.decimal,['.',','])]:
            ttk.Label(top,text=label).pack(side='left',padx=4);ttk.Combobox(top,textvariable=var,values=values,state='readonly',width=11).pack(side='left',padx=(0,8))
        buttons=ttk.Frame(self);buttons.pack(fill='x',pady=(6,0))
        for label,fn in [('Load CSV',self.load),('Map columns',self.map_dialog),('Analyze CSV',self.analyze),('Build model',lambda:self.app.tabs.select(self.app.tab_j)),('Options',self.options)]:self.app.action(buttons,label,fn,label=='Analyze CSV').pack(side='left',padx=3)
        self.a.store.listeners.append(self.sync_mapping)
        ttk.Checkbutton(self,text='Drop rows with missing mapped values (no imputation)',variable=self.drop).pack(anchor='w',pady=5)
        ttk.Label(self,textvariable=self.info,wraplength=1060).pack(anchor='w')
        self.method_info=tk.StringVar();ttk.Label(self,textvariable=self.method_info,style='Muted.TLabel').pack(anchor='w',pady=5);self.sync_mapping()
        reports=ttk.Frame(parent);self.reports=reports;reports.pack(side='bottom',fill='both',expand=True,pady=6)
        bar=ttk.Frame(reports);bar.pack(fill='x',padx=14)
        self.show_settings=tk.BooleanVar(value=True)
        ttk.Checkbutton(bar,text='Import settings',variable=self.show_settings,command=self.toggle_settings).pack(side='left',padx=5)
        self.report=tk.StringVar(value='Data');self.report_combo=ttk.Combobox(bar,textvariable=self.report,state='readonly',values=['Data'],width=28);self.report_combo.pack(side='right');self.report_combo.bind('<<ComboboxSelected>>',lambda e:self.view())
        self.app.action(bar,'Export analysis Excel',self.export).pack(side='left');self.app.action(bar,'Export AMOS bundle',self.export_amos).pack(side='left',padx=6)
        self.tree=self.app.table(reports,height=10)

    def toggle_settings(self):
        if self.show_settings.get():self.pack(side='top',fill='x',padx=14,pady=8,before=self.reports)
        else:self.pack_forget()

    def import_dialog(self):
        window=tk.Toplevel(self.app);window.title('Import CSV • choose model type');window.geometry('520x380');window.transient(self.app)
        ttk.Label(window,text='What model will you analyze?',font=(self.app.ui_font,15,'bold')).pack(anchor='w',padx=22,pady=18)
        choice=tk.StringVar(value='')
        for value,label in [('REGRESSION','Regression • observed variables or scale scores'),('CB-SEM','CB-SEM • reflective covariance model'),('PLS-SEM','PLS-SEM • reflective composite model')]:ttk.Radiobutton(window,text=label,variable=choice,value=value).pack(anchor='w',padx=22,pady=8)
        fresh=tk.BooleanVar(value=True);ttk.Checkbutton(window,text='Start with an empty diagram',variable=fresh).pack(anchor='w',padx=22,pady=16)
        def next_step():
            if not choice.get():self.app.error('Select Regression, CB-SEM or PLS-SEM before importing.');return
            method=choice.get();clear=fresh.get();window.destroy();self.load(method=method,fresh=clear)
        ttk.Button(window,text='Choose CSV file',command=next_step).pack(anchor='e',padx=22,pady=10)
    def sync_mapping(self):
        if hasattr(self,'method_info'):self.method_info.set('Selected model: '+self.a.store.model.method)
        required=[c for n in self.a.store.model.nodes for c in n.columns]
        previous=self.mapping;self.mapping={}
        for indicator in required:
            source=previous.get(indicator,'')
            if not source and self.frame is not None:
                candidates=[column for column in self.frame.columns if column.casefold()==indicator.casefold()]
                source=indicator if indicator in self.frame.columns else candidates[0] if len(candidates)==1 else ''
            self.mapping[indicator]=source
        for n in self.a.store.model.nodes:
            if n.indicators:
                for c,source in zip(n.columns,n.indicators):self.mapping[c]=source
    def view(self):
        if self.result is None:return
        name=self.report.get();df=self.result.data if name=='Data' else self.result.scores if name=='Construct Scores' else self.result.reports[name];self.app.show_table(self.tree,df)
    def checked(self):
        if self.result is None or self.a.snapshot().fingerprint()!=self.model_signature or self.source_signature()!=self.result_signature:raise ValueError('Model, source or mapping changed. Analyze CSV again before exporting.')
        return self.result
    def export(self):
        if self.app.busy:return
        try:
            from core.exporter import export_excel
            from core.delivery import quant_sheets
            result=self.checked();path=self.app.choose_save()
            if path:self.app.start(lambda:export_excel(path,quant_sheets(result),cancel=self.app.cancel_event),lambda _:self.app.saved(path))
        except Exception as e:self.app.error(e)
    def export_amos(self):
        if self.app.busy:return
        try:
            from core.delivery import export_amos_bundle
            result=self.checked()
            if not result.settings['CB SEM']:raise ValueError('AMOS export requires CB-SEM analysis.')
            path=self.app.choose_save('.zip')
            if path:self.app.start(lambda:export_amos_bundle(path,result,cancel=self.app.cancel_event),lambda _:self.app.saved(path))
        except Exception as e:self.app.error(e)
    def options(self):
        if self.app.busy:return
        from .criteria_panel import CriteriaPanel
        window=tk.Toplevel(self.app);window.title('Analysis options');window.geometry('1050x650');window.transient(self.app)
        model=self.a.store.model;variables={};fields=ttk.Frame(window);fields.pack(fill='x',padx=14,pady=12)
        for i,key in enumerate(['scale','seed','bootstrap','vif_max']):
            var=tk.StringVar(value='' if getattr(model,key) is None else str(min(model.bootstrap,100) if key=='bootstrap' else getattr(model,key)));variables[key]=var
            self.app.field(fields,{'scale':'Scale','seed':'Seed','bootstrap':'Bootstrap (50 or 100)','vif_max':'Maximum VIF'}[key],var,0,i,['CONTINUOUS','LIKERT5','LIKERT7'] if key=='scale' else ['50','100'] if key=='bootstrap' else None)
        rules=CriteriaPanel(window,rules=model.criteria);rules.pack(fill='x',padx=14,pady=10);rules.method(model.method)
        ttk.Label(window,text='These thresholds compare actual results. Imported data is never adjusted to pass them.',wraplength=1000).pack(anchor='w',padx=18)
        def apply():
            try:
                m=copy.deepcopy(model);m.scale=variables['scale'].get();m.seed=int(variables['seed'].get()) if variables['seed'].get() else None;m.bootstrap=int(variables['bootstrap'].get());m.vif_max=float(variables['vif_max'].get());m.criteria=rules.snapshot()
                if not 50<=m.bootstrap<=5000 or not 1<m.vif_max<=10:raise ValueError('Bootstrap: 50–5000; VIF: >1 and ≤10.')
                self.a.store.commit(m);window.destroy()
            except Exception as e:self.app.error(e)
        ttk.Button(window,text='Apply analysis options',command=apply).pack(anchor='e',padx=14,pady=16)
    def load(self,path=None,method=None,fresh=False):
        if self.app.busy:return
        if path is None and method is None:self.import_dialog();return
        path=path or filedialog.askopenfilename(filetypes=[('CSV / TSV','*.csv *.tsv'),('All files','*')])
        if not path:return
        try:
            frame,meta=read_csv(path,'\t' if self.delimiter.get()=='TAB' else self.delimiter.get(),self.encoding.get(),self.decimal.get())
            if method:
                model=copy.deepcopy(self.a.store.model);model.method=method
                if fresh:model.nodes=[];model.edges=[]
                self.a.store.commit(model)
            self.frame=frame;self.metadata=meta;self.path=str(Path(path).resolve())
            required=[c for n in self.a.store.model.nodes for c in n.columns];names={c.casefold():c for c in frame.columns if sum(x.casefold()==c.casefold() for x in frame.columns)==1}
            self.mapping={c:names.get(c.casefold(),'') for c in required}
            self.a.vars['rows'].set(str(len(frame)));self.sync_mapping();self.a.analysis_designer.attach_csv(self);
            if method:self.app.tabs.select(self.app.tab_j)
            self.info.set(f'{meta["File"]} • {len(frame)} rows / {len(frame.columns)} columns • review indicator mapping before analysis.')
        except Exception as e:self.app.error(e)
    def map_dialog(self):
        if self.app.busy:return
        if self.frame is None:self.app.error('Load a CSV first.');return
        window=tk.Toplevel(self.app);window.title('Map CSV columns to model indicators');window.geometry('640x600');window.transient(self.app)
        ttk.Label(window,text='One unique source column per indicator. Extra CSV columns are ignored.',wraplength=600).pack(padx=16,pady=12)
        canvas=tk.Canvas(window,highlightthickness=0);scroll=ttk.Scrollbar(window,command=canvas.yview);canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True,padx=12)
        body=ttk.Frame(canvas);canvas.create_window((0,0),window=body,anchor='nw');body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));self.app.register_scroll(canvas,body)
        variables={}
        for n in self.a.store.model.nodes:
            for c in n.columns:
                row=ttk.Frame(body);row.pack(fill='x',pady=4);ttk.Label(row,text=c,width=20).pack(side='left');v=tk.StringVar(value=self.mapping.get(c,''));variables[c]=v
                ttk.Combobox(row,textvariable=v,values=list(self.frame.columns),state='readonly',width=38).pack(side='left')
        def save():
            mapping={c:v.get() for c,v in variables.items()}
            try:prepare_data(self.frame,self.a.snapshot(),mapping,self.drop.get())
            except Exception as e:self.app.error(e);return
            model=copy.deepcopy(self.a.store.model)
            for node in model.nodes:node.indicators=[mapping[c] for c in node.columns]
            self.a.store.commit(model);self.mapping=mapping;self.info.set('Column mapping saved. Analyze CSV to calculate actual results.');window.destroy()
        ttk.Button(window,text='Apply mapping',command=save).pack(pady=12)
    def source_signature(self):
        if self.frame is None:raise ValueError('Load a CSV first.')
        return json.dumps({'SHA256':self.metadata['SHA256'],'Mapping':self.mapping,'Drop missing':self.drop.get()},sort_keys=True)
    def analyze(self):
        if self.app.busy:return
        try:
            if self.frame is None:raise ValueError('Load a CSV first.')
            m=self.a.snapshot();data,_=prepare_data(self.frame,m,self.mapping,self.drop.get())
            m.rows=len(data);m.validate(for_generation=False);source=self.source_signature();fingerprint=m.fingerprint();self.a.store.commit(m)
            frame=self.frame.copy();mapping=copy.deepcopy(self.mapping);meta=copy.deepcopy(self.metadata);drop=self.drop.get()
        except Exception as e:self.app.error(e);return
        self.result=None;self.model_signature=None
        def done(result):
            self.result=result;self.model_signature=fingerprint;self.result_signature=source
            self.report_combo.configure(values=['Data','Construct Scores']+list(result.reports));self.report.set('Acceptance');self.view()
            failed=int((result.reports['Acceptance'].Required & ~result.reports['Acceptance'].Pass).sum())
            self.info.set(f'CSV analysis complete • {m.method} • {len(result.data)} rows • {failed} required criteria failed. Actual results can be exported.')
            self.app.status.set('Imported CSV analysis complete. Source observations were not regenerated.')
        self.app.start(lambda:analyze_csv(frame,m,mapping,meta,drop,progress=self.app.progress,cancel=self.app.cancel_event),done)
