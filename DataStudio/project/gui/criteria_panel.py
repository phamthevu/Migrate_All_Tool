"""Editable rules with fixed min/max directions and explicit required switches."""
import tkinter as tk
from tkinter import ttk
from core.criteria import defaults,validate_rules

class CriteriaPanel(ttk.LabelFrame):
    def __init__(self,parent,title='SEM acceptance criteria',rules=None):
        super().__init__(parent,text=title,padding=8)
        self.vars={}
        bar=ttk.Frame(self);bar.pack(fill='x')
        ttk.Label(bar,text='Required: checked criteria must pass before a dataset is accepted.').pack(side='left')
        ttk.Button(bar,text='Balanced',command=lambda:self.load(defaults())).pack(side='right',padx=3)
        ttk.Button(bar,text='Strict',command=lambda:self.load(defaults(True))).pack(side='right')
        area=ttk.Frame(self);area.pack(fill='x',pady=5)
        for i,(name,rule) in enumerate((rules or defaults()).items()):
            cell=ttk.Frame(area);cell.grid(row=i//4,column=i%4,padx=5,pady=3,sticky='ew');area.columnconfigure(i%4,weight=1)
            required=tk.BooleanVar(value=rule['required']);value=tk.StringVar(value=str(rule['value']))
            ttk.Checkbutton(cell,text=name,variable=required).pack(side='left')
            ttk.Label(cell,text='≥' if rule['direction']=='min' else '≤').pack(side='left')
            entry=ttk.Entry(cell,textvariable=value,width=6);entry.pack(side='right')
            if name=='Fornell-Larcker':entry.configure(state='readonly')
            self.vars[name]=(required,value,rule['direction'],cell)
        self.note=ttk.Label(self,text='Chi-square p is optional by default. GFI/AGFI follow semopy; compare AMOS results separately.',wraplength=1000)
        self.note.pack(anchor='w')
    def load(self,rules):
        for name,rule in rules.items():
            required,value,_,_=self.vars[name];required.set(rule['required']);value.set(str(rule['value']))
    def snapshot(self):
        return validate_rules({name:{'required':v[0].get(),'value':float(v[1].get()),'direction':v[2]} for name,v in self.vars.items()})
    def method(self,method):
        applicable={'Loading','Composite reliability','AVE','HTMT','Fornell-Larcker','Loading p','Path p'}
        visible=0
        for name,(_,_,_,cell) in self.vars.items():
            if method=='CB-SEM' or method=='PLS-SEM' and name in applicable or method=='REGRESSION' and name=='Path p':
                cell.grid(row=visible//4,column=visible%4);visible+=1
            else:cell.grid_remove()
        self.configure(text='Acceptance criteria • '+method)
        self.note.configure(text='Ordinary PLS Mode A / path weighting with full-refit bootstrap. CB-SEM fit criteria do not apply to PLS.' if method=='PLS-SEM' else 'Regression uses Path p. CFA / SEM fit criteria do not apply.' if method=='REGRESSION' else 'Chi-square p is optional by default. GFI/AGFI follow semopy; compare AMOS results separately.')
