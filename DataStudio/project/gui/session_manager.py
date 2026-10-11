import tkinter as tk
from tkinter import ttk,filedialog
from core.session import state_path,write_session,read_session
from core.model_spec import ModelSpec

class SessionManager:
    def __init__(self,app):
        self.app=app;self.path=state_path();self.last=None;self.enabled=tk.BooleanVar(value=True)
        bar=ttk.Frame(app);bar.pack(fill='x',padx=24,pady=(5,0),before=app.tabs)
        ttk.Checkbutton(bar,text='Autosave settings every 15 s',variable=self.enabled).pack(side='left')
        self.info=tk.StringVar(value='Recovery available' if self.path.exists() else 'No recovery file yet');ttk.Label(bar,textvariable=self.info,style='Muted.TLabel').pack(side='left',padx=14)
        for label,fn in [('Restore autosave',lambda:self.restore(self.path)),('Open session',self.open),('Save session',self.save)]:app.action(bar,label,fn).pack(side='right',padx=3)
        app.after(15000,self.tick)
    def capture(self):
        app=self.app;a=app.advanced
        settings={name:v.get() for name,v in vars(app).items() if isinstance(v,(tk.StringVar,tk.BooleanVar)) and name not in ('status','m_info','q_info','m_config_visible')}
        groups=[{'name':g['name'].get(),'items':g['items'].get(),'accepted':g['accepted'].get()} for g in app.groups]
        return {'session_version':1,'model':a.store.model.to_dict(),'settings':settings,'groups':groups,
                'advanced':{k:v.get() for k,v in a.vars.items()},'ranges':{k:[v.get() for v in values] for k,values in a.range_vars.items()},'indirect':a.indirect.get(),
                'criteria':{k:[v[0].get(),v[1].get()] for k,v in a.criteria.vars.items()},'quick_criteria':{k:[v[0].get(),v[1].get()] for k,v in app.qcriteria.vars.items()},
                'config_path':getattr(app,'loaded_config_path',''),'weights':{k:v.get() for k,v in app.weight_vars.items()},'probabilities':[v.get() for v in app.prob_vars],'dematel_profiles':app.dematel_profile(),
                'csv':{'path':a.csv.path,'encoding':a.csv.encoding.get(),'delimiter':a.csv.delimiter.get(),'decimal':a.csv.decimal.get(),'mapping':a.csv.mapping,'drop_missing':a.csv.drop.get(),'checksum':a.csv.metadata.get('SHA256')},
                'note':'Settings and source references only. Completed results must be exported; re-run analysis after recovery.'}
    def tick(self):
        if self.enabled.get() and not self.app.busy:self.autosave()
        if self.app.winfo_exists():self.app.after(15000,self.tick)
    def autosave(self):
        try:
            payload=self.capture()
            if payload!=self.last:write_session(self.path,payload);self.last=payload
            self.info.set('Settings saved locally')
        except Exception as e:self.info.set('Autosave failed: '+str(e))
    def save(self):
        if self.app.busy:return
        path=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('Session JSON','*.json')])
        if path:
            try:write_session(path,self.capture());self.app.saved(path)
            except Exception as e:self.app.error(e)
    def open(self):
        path=filedialog.askopenfilename(filetypes=[('Session JSON','*.json')])
        if path:self.restore(path)
    def restore(self,path):
        if self.app.busy:return
        try:
            payload=read_session(path);model=ModelSpec.from_dict(payload['model']);app=self.app;a=app.advanced
            a.store.commit(model)
            for g in app.groups[:]:g['frame'].destroy()
            app.groups=[]
            for g in payload['groups']:
                app.add_group(g['name'],3);app.groups[-1]['items'].set(str(g['items']));app.groups[-1]['accepted'].set(bool(g['accepted']))
            app.config_data=None;app.loaded_config_path='';app.config_label.configure(text='No configuration loaded');app.weight_vars={};app.prob_vars=[]
            for widget in app.edit_frame.winfo_children():widget.destroy()
            app.update_m_controls()
            if payload.get('config_path'):
                try:app.load_config(payload['config_path'])
                except Exception as e:self.info.set(str(e))
            a.csv.frame=None;a.csv.metadata={};a.csv.path='';a.csv.mapping={};a.csv.info.set('No CSV loaded. Reopen the source to analyze.')
            csv=payload.get('csv',{})
            if csv.get('path'):
                for key in ('encoding','delimiter','decimal'):getattr(a.csv,key).set(csv.get(key,getattr(a.csv,key).get()))
                a.csv.load(csv['path'],method=model.method);a.csv.mapping=csv.get('mapping',{});a.csv.drop.set(csv.get('drop_missing',False))
                if a.csv.metadata.get('SHA256')!=csv.get('checksum'):a.csv.info.set('Source file differs from the saved session. Review mapping and re-analyze.')
            for key,value in payload['settings'].items():
                var=getattr(app,key,None)
                if isinstance(var,(tk.StringVar,tk.BooleanVar)):var.set(value)
            for key,value in payload['advanced'].items():
                if key in a.vars:a.vars[key].set(value)
            for key,values in payload.get('ranges',{}).items():
                if key in a.range_vars:
                    for var,value in zip(a.range_vars[key],values):var.set(value)
            a.indirect.set(payload.get('indirect',True))
            for panel,key in [(a.criteria,'criteria'),(app.qcriteria,'quick_criteria')]:
                for name,values in payload.get(key,{}).items():
                    if name in panel.vars:panel.vars[name][0].set(values[0]);panel.vars[name][1].set(values[1])
            for key,value in payload.get('weights',{}).items():
                if key in app.weight_vars:app.weight_vars[key].set(value)
            for key,values in payload.get('dematel_profiles',{}).items():
                if key in app.dematel_vars:
                    for var,name in zip(app.dematel_vars[key],('Prominence','Role','Strength','Rank')):
                        if name in values:var.set(str(values[name]))
            for var,value in zip(app.prob_vars,payload.get('probabilities',[])):var.set(value)
            a.method_changed();a.result=None;a.signature=None;a.csv.result=None;a.csv.model_signature=None;app.quant_result=None;app.batch_result=None
            a.info.set('Session restored. Generate or analyze again before exporting results.');self.info.set('Session restored')
        except Exception as e:self.app.error(e)
