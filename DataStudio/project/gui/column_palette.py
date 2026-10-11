"""Drag CSV columns onto constructs; assignment lives in the versioned model."""
import copy,re
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
from core.model_spec import Node
from .model_designer import new_id

class ColumnPalette(ttk.Frame):
    def __init__(self,parent,designer):
        super().__init__(parent,width=200);self.d=designer;self.csv=None;self.drag_columns=[]
        ttk.Label(self,text='CSV indicators',font=(designer.app.ui_font,12,'bold')).pack(anchor='w',padx=8,pady=8)
        ttk.Label(self,text='Ctrl/Shift: select multiple.\nDrag onto a construct or empty canvas.',wraplength=185).pack(anchor='w',padx=8)
        self.search=tk.StringVar();ttk.Entry(self,textvariable=self.search).pack(fill='x',padx=8,pady=6);self.search.trace_add('write',lambda *a:self.refresh())
        self.tree=ttk.Treeview(self,show='tree',selectmode='extended',height=12);self.tree.pack(fill='both',expand=True,padx=6)
        self.tree.bind('<Button-1>',self.press);self.tree.bind('<B1-Motion>',self.motion);self.tree.bind('<ButtonRelease-1>',self.release)
        ttk.Button(self,text='Assign selected to active node',command=self.assign_active).pack(side='bottom',fill='x',padx=6,pady=6,before=self.tree)
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        if self.csv is None or self.csv.frame is None:return
        used={c for n in self.d.store.model.nodes for c in n.indicators};query=self.search.get().casefold()
        for index,col in enumerate(self.csv.frame.columns):
            if query in col.casefold():self.tree.insert('','end',iid=str(index),text=('✓ ' if col in used else '')+col,values=[col])
    def press(self,event):
        if self.d.app.busy:return 'break'
        item=self.tree.identify_row(event.y)
        if not item:return 'break'
        selected=list(self.tree.selection())
        if event.state & 4:
            if item in selected:selected.remove(item)
            else:selected.append(item)
            self.tree.selection_set(selected);self.drag_columns=[];return 'break'
        if event.state & 1 and selected:
            allrows=list(self.tree.get_children());a,b=sorted((allrows.index(selected[0]),allrows.index(item)));self.tree.selection_set(allrows[a:b+1])
        elif item not in selected:self.tree.selection_set(item)
        self.drag_columns=[self.tree.item(i,'values')[0] for i in self.tree.selection()];return 'break'
    def motion(self,event):
        if self.drag_columns:self.d.hint.set(f'Dragging {len(self.drag_columns)} column(s). Drop onto a construct or empty canvas.')
        return 'break'
    def release(self,event):
        columns=self.drag_columns;self.drag_columns=[]
        x=event.x_root-self.d.canvas.winfo_rootx();y=event.y_root-self.d.canvas.winfo_rooty()
        if columns and 0<=x<=self.d.canvas.winfo_width() and 0<=y<=self.d.canvas.winfo_height():
            hit=self.d.hit(SimpleNamespace(x=x,y=y));self.assign(columns,hit[1] if hit and hit[0]=='node' else None,x,y)
        return 'break'
    def assign_active(self):
        cols=[self.tree.item(i,'values')[0] for i in self.tree.selection()]
        if not self.d.selected or self.d.selected[0]!='node':self.d.app.error('Select a construct on the canvas first.');return
        self.assign(cols,self.d.selected[1])
    def assign(self,columns,node_id=None,x=200,y=200):
        if self.d.app.busy or not columns:return
        try:
            m=copy.deepcopy(self.d.store.model);used={c for n in m.nodes if n.id!=node_id for c in n.indicators}
            if any(c in used for c in columns):raise ValueError('A CSV column can belong to only one construct. Remove it from its current construct first.')
            if node_id is None:
                if len(m.nodes)>=12:raise ValueError('Up to 12 constructs are supported.')
                base=re.sub(r'[_ -]\d+$','',columns[0]);base=re.sub(r'[^A-Za-z0-9]','',base)
                if not base or not base[0].isalpha():base='X'
                name=base;i=2
                while name in {n.name for n in m.nodes}:name=base+str(i);i+=1
                node=Node(new_id('n'),name,items=len(columns),x=(x-self.d.offset[0])/self.d.zoom,y=(y-self.d.offset[1])/self.d.zoom,indicators=list(columns));m.nodes.append(node)
            else:
                node=m.by_id[node_id];node.indicators=list(dict.fromkeys(node.indicators+columns));node.items=len(node.indicators)
            if not 1<=node.items<=10:raise ValueError('Each construct supports up to 10 mapped columns.')
            self.d.selected=('node',node.id);self.d.store.commit(m)
            self.d.hint.set('CSV indicators assigned. CB/PLS needs ≥3 per construct; imported regression supports one observed column.')
        except Exception as e:self.d.app.error(e)
