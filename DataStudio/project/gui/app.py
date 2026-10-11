import json,queue,threading,re
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from tkinter import font as tkfont
import numpy as np
import pandas as pd
from core.config_loader import load_config_excel,validate_scale
from core.generator import parse_advance
from core.batch import generate_batch
from core.quantitative import Construct,generate_quantitative,validate
from core.exporter import export_excel
from core.converter import convert_df
from core.delivery import batch_sheets,mcdm_data_sheets,mcdm_report_sheets,quant_sheets,export_amos_bundle
from core.config_writer import save_config
from .criteria_panel import CriteriaPanel
from .advanced import AdvancedPanel
from .session_manager import SessionManager
from .workspace import WorkspaceNotebook

BG='#F3F5FA';WHITE='#FFFFFF';INK='#0F172A';MUTED='#64748B';ACCENT='#4F46E5'

class AnsGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__();self.title('DataStudio');self.geometry(f'1360x{min(960,self.winfo_screenheight()-70)}');self.minsize(1100,700);self.configure(bg=BG)
        self.scroll_pages=[];self.bind_all('<MouseWheel>',self.scroll_wheel);self.bind_all('<Button-4>',self.scroll_wheel);self.bind_all('<Button-5>',self.scroll_wheel)
        self.style_ui();self.config_data=None;self.batch_result=None;self.quant_result=None;self.convert_sheets=None
        self.batch_signature=None;self.quant_signature=None;self.busy=False;self.events=queue.Queue();self.cancel_event=threading.Event();self.actions=[]
        strings={'mode':'DEMATEL','output':'LING','count':'10','prefix':'CODE','seed':'42','consensus':'0.78','pearson':'0.65','pearson_max':'0.90','spearman':'0.60','spearman_max':'0.95','noise':'0.15','cr':'0.10','order_min':'0.80','qrows':'400','qseed':'42','qscale':'LIKERT7','rmetric':'R','rmin':'0.67','rmax':'0.78','amin':'0.70','amax':'0.80','vif':'2.00','qattempts':'100','extraction':'PCA','outcome':'Y','conversion':'LING_TO_FUZZY','ans_selection':'Ans 1','report_selection':'Data','status':'Ready • synthetic data for learning and demonstration'}
        for name,value in strings.items():setattr(self,name,tk.StringVar(value=value))
        self.discrete=tk.BooleanVar(value=True);self.use_order=tk.BooleanVar(value=True);self.qsem=tk.BooleanVar(value=False)
        self.groups=[];self.weight_vars={};self.prob_vars=[]
        h=tk.Frame(self,bg='#0F172A');h.pack(fill='x')
        brand=tk.Label(h,text='DS',bg='#4F46E5',fg='white',font=(self.ui_font,15,'bold'),padx=11,pady=6);brand.pack(side='left',padx=(18,11),pady=8)
        titles=tk.Frame(h,bg='#0F172A');titles.pack(side='left',pady=7)
        tk.Label(titles,text='DataStudio',bg='#0F172A',fg='white',font=(self.ui_font,19,'bold')).pack(anchor='w')
        tk.Label(titles,text='MCDM · Quanti · DEA · Bootstrap',bg='#0F172A',fg='#A5B4FC',font=(self.ui_font,9)).pack(anchor='w',pady=(1,0))
        tk.Label(h,text='GENERATE & ANALYZE',bg='#1E293B',fg='#C7D2FE',font=(self.ui_font,9,'bold'),padx=10,pady=5).pack(side='right',padx=18)
        self.tabs=WorkspaceNotebook(self);self.tabs.pack(fill='both',expand=True,padx=16,pady=3)
        definitions=[('mcdm','MCDM',[('m','Generate & Validate'),('w','Factor Setup'),('c','Converter'),('help','Help')]),
                     ('quanti','Quanti',[('q','Traditional Generator'),('a','Advanced Generator'),('d','Model Designer'),('i','CSV & Results'),('j','Model Builder')])]
        for key,label,leaves in definitions:
            group,notebook=self.tabs.group(key,label)
            for name,title in leaves:setattr(self,'tab_'+name,self.tabs.leaf(name,title,group,notebook))
        group,notebook=self.tabs.group('dea','DEA')
        self.dea_pages={}
        for name,title in [('input','Input & Preview'),('model','Model & Formula'),('results','Results Preview'),('generate','Generate Data')]:
            page=self.tabs.leaf('dea_'+name,title,group,notebook);self.dea_pages[name]=page
        group,notebook=self.tabs.group('bootstrap','Bootstrap')
        self.bootstrap_pages={}
        for name,title in [('input','Import & Preview Data'),('fuzzy','Fuzzy Scale & Defuzz'),('settings','Bootstrap Config'),('results','Results & Export')]:
            page=self.tabs.leaf('bootstrap_'+name,title,group,notebook);self.bootstrap_pages[name]=page
        self.build_mcdm();self.build_weights();self.build_quant();self.build_convert();self.build_help();self.advanced=AdvancedPanel(self.tab_a,self.tab_d,self,self.tab_i,self.tab_j)
        from integrations.panels import build_dea_panels, build_bootstrap_panels
        build_dea_panels(self,self.dea_pages)
        build_bootstrap_panels(self,self.bootstrap_pages)
        self.previous_tab=self.tabs.select();self.tabs.bind('<<NotebookTabChanged>>',self.tab_changed)
        for notebook in self.tabs.groups.values():notebook.bind('<<NotebookTabChanged>>',self.tab_changed)
        for name in ['X1','X2','X3','Y']:self.add_group(name,3)
        f=ttk.Frame(self);f.pack(side='bottom',fill='x',padx=18,pady=(3,7),before=self.tabs)
        self.progressbar=ttk.Progressbar(f,mode='indeterminate',length=140);self.progressbar.pack(side='left',padx=(0,12))
        ttk.Label(f,textvariable=self.status,style='Muted.TLabel').pack(side='left',fill='x',expand=True)
        self.cancel_button=ttk.Button(f,text='Cancel task',command=self.cancel_event.set,state='disabled');self.cancel_button.pack(side='right')
        self.session=SessionManager(self)
        self.after(100,self.poll);self.protocol('WM_DELETE_WINDOW',self.close)

    def style_ui(self):
        families=set(tkfont.families(self))
        family='Segoe UI' if 'Segoe UI' in families else 'DejaVu Sans' if 'DejaVu Sans' in families else 'Arial'
        self.ui_font=family
        s=ttk.Style(self);s.theme_use('clam');s.configure('.',font=(family,10),background=BG,foreground=INK)
        s.configure('TFrame',background=BG);s.configure('Card.TFrame',background=WHITE);s.configure('TLabel',background=BG);s.configure('Card.TLabel',background=WHITE)
        s.configure('Muted.TLabel',foreground=MUTED);s.configure('Title.TLabel',font=(self.ui_font,23,'bold'))
        s.configure('Validation.Error.TLabel',background='#FEE2E2',foreground='#991B1B',padding=10,font=(self.ui_font,10,'bold'))
        s.configure('Validation.Warning.TLabel',background='#FEF3C7',foreground='#92400E',padding=10,font=(self.ui_font,10,'bold'))
        s.configure('Validation.Ok.TLabel',background='#DCFCE7',foreground='#166534',padding=8,font=(self.ui_font,10,'bold'))
        s.configure('TLabelframe',background=WHITE,bordercolor='#DEE5EE',relief='solid',borderwidth=1)
        s.configure('TLabelframe.Label',background=WHITE,foreground='#334155',font=(self.ui_font,11,'bold'))
        s.configure('TButton',padding=(12,8),background=WHITE,borderwidth=0);s.map('TButton',background=[('active','#EEF2FF')])
        s.configure('Accent.TButton',background=ACCENT,foreground=WHITE,font=(self.ui_font,10,'bold'));s.map('Accent.TButton',background=[('active','#4338CA'),('disabled','#C7D2FE')])
        s.configure('TEntry',padding=7,fieldbackground=WHITE);s.configure('TCombobox',padding=7,fieldbackground=WHITE)
        s.configure('TNotebook',background=BG,borderwidth=0);s.configure('TNotebook.Tab',padding=(14,12),background=BG)
        s.map('TNotebook.Tab',background=[('selected','#E0E7FF')],foreground=[('selected',ACCENT)])
        s.configure('Treeview',rowheight=28,background=WHITE,fieldbackground=WHITE,borderwidth=0)
        s.configure('Treeview.Heading',font=(self.ui_font,10,'bold'),foreground='#475569',background='#EEF2F6',padding=9)
        s.map('Treeview',background=[('selected','#D7E8FF')],foreground=[('selected',INK)])
        s.configure('Horizontal.TProgressbar',background=ACCENT,troughcolor='#E2E8F1',borderwidth=0)

    def tab_changed(self,event):
        current=self.tabs.select()
        if self.previous_tab==str(self.tab_a) and current!=str(self.tab_a) and not self.busy:
            try:self.advanced.flush_settings()
            except Exception as e:
                self.error(e);self.tabs.select(self.tab_a);return
        self.previous_tab=current
    def register_scroll(self,canvas,container):self.scroll_pages.append((canvas,container))
    def scroll_wheel(self,event):
        try:
            widget=self.winfo_containing(event.x_root,event.y_root)
            if widget is None or widget.winfo_class() in ('Treeview','Text','TCombobox'):return
            ancestors=[];current=widget
            while current is not None:ancestors.append(current);current=getattr(current,'master',None)
            for canvas,container in self.scroll_pages:
                if container in ancestors or canvas in ancestors:
                    direction=-1 if getattr(event,'num',None)==4 else 1 if getattr(event,'num',None)==5 else -1 if event.delta>0 else 1
                    canvas.yview_scroll(direction*3,'units');return 'break'
        except tk.TclError:return
    def card(self,parent,title):
        f=ttk.LabelFrame(parent,text=title,padding=14);f.pack(fill='x',padx=14,pady=8);return f
    def field(self,parent,label,var,row,col,values=None):
        parent.columnconfigure(col,weight=1)
        f=ttk.Frame(parent,style='Card.TFrame');f.grid(row=row,column=col,sticky='ew',padx=6,pady=3)
        ttk.Label(f,text=label,style='Card.TLabel').pack(anchor='w',pady=(0,3))
        w=ttk.Combobox(f,textvariable=var,values=values,state='readonly',width=18) if values else ttk.Entry(f,textvariable=var,width=18)
        w.pack(fill='x');return w
    def action(self,parent,text,callback,primary=False):
        b=ttk.Button(parent,text=text,command=callback,style='Accent.TButton' if primary else 'TButton');self.actions.append(b);return b
    def table(self,parent,height=8):
        f=ttk.Frame(parent);f.pack(fill='both',expand=True,padx=14,pady=8);t=ttk.Treeview(f,show='headings',height=height)
        x=ttk.Scrollbar(f,orient='horizontal',command=t.xview);y=ttk.Scrollbar(f,orient='vertical',command=t.yview);t.configure(xscrollcommand=x.set,yscrollcommand=y.set)
        t.grid(row=0,column=0,sticky='nsew');y.grid(row=0,column=1,sticky='ns');x.grid(row=1,column=0,sticky='ew');f.rowconfigure(0,weight=1);f.columnconfigure(0,weight=1)
        t.tag_configure('alternate',background='#F7F9FC');return t
    def show_table(self,t,df):
        t.delete(*t.get_children());keys=[f'c{i}' for i in range(len(df.columns)+1)];t['columns']=keys
        for key,label in zip(keys,['Row']+list(df.columns)):t.heading(key,text=str(label));t.column(key,width=150,minwidth=90,stretch=False,anchor='center')
        for i,(idx,row) in enumerate(df.head(250).iterrows()):
            vals=[idx]+[json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict,tuple)) else '—' if pd.isna(v) else f'{v:.5g}' if isinstance(v,(float,np.floating)) else str(v) for v in row]
            t.insert('','end',values=vals,tags=('alternate',) if i%2 else ())
    def hint(self,parent,text):ttk.Label(parent,text=text,style='Muted.TLabel',wraplength=1120).pack(anchor='w',padx=18,pady=4)

    def build_mcdm(self):
        top=ttk.Frame(self.tab_m);top.pack(fill='x',padx=14,pady=6)
        self.action(top,'Open configuration',self.load_config,True).pack(side='left')
        self.config_label=ttk.Label(top,text='No configuration loaded');self.config_label.pack(side='left',padx=12)
        self.m_config_visible=tk.BooleanVar(value=True)
        ttk.Checkbutton(top,text='Show settings',variable=self.m_config_visible,command=self.toggle_m_config).pack(side='right')
        self.m_panes=ttk.Panedwindow(self.tab_m,orient='horizontal');self.m_panes.pack(fill='both',expand=True,padx=6,pady=6)
        self.m_config=ttk.Frame(self.m_panes);preview=ttk.Frame(self.m_panes)
        self.m_panes.add(self.m_config,weight=1);self.m_panes.add(preview,weight=3)
        canvas=tk.Canvas(self.m_config,bg=BG,highlightthickness=0,height=235)
        scroll=ttk.Scrollbar(self.m_config,orient='vertical',command=canvas.yview);canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        parent=ttk.Frame(canvas);window=canvas.create_window((0,0),window=parent,anchor='nw')
        parent.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width));self.register_scroll(canvas,parent)
        p=self.card(parent,'Method & agreement');self.m_ahp_controls=[]
        fields=[('Method',self.mode,['NORMAL','DELPHI','TOPSIS','DEMATEL','AHP']),('Output format',self.output,['LING','FUZZY','CRISP']),('Answers',self.count,None),('Seed (blank = random)',self.seed,None),('Sheet prefix',self.prefix,None),('Initial consensus (0–1)',self.consensus,None),('Pearson min',self.pearson,None),('Pearson max',self.pearson_max,None),('Spearman rank min',self.spearman,None),('Spearman rank max',self.spearman_max,None),('AHP noise (0–1)',self.noise,None),('Maximum AHP CR',self.cr,None)]
        for i,(label,var,values) in enumerate(fields):
            widget=self.field(p,label,var,i//2,i%2,values)
            if label in ('AHP noise (0–1)','Maximum AHP CR'):self.m_ahp_controls.append(widget.master)
        saaty=ttk.Checkbutton(p,text='Round to Saaty scale',variable=self.discrete);saaty.grid(row=6,column=0,sticky='w',padx=6);self.m_ahp_controls.append(saaty)
        self.m_order_check=ttk.Checkbutton(p,text='Use Order sheet ranks',variable=self.use_order);self.m_order_check.grid(row=6,column=1,sticky='w')
        self.m_order_field=self.field(p,'Spearman vs. Order ≥',self.order_min,7,0).master
        self.dematel_vars={}
        self.action(top,'Factor setup →',lambda:self.tabs.select(self.tab_w)).pack(side='left',padx=8)
        self.mode.trace_add('write',lambda *args:self.update_m_controls());self.update_m_controls()
        self.hint(parent,'All answer pairs must meet Pearson and rank Spearman min/max. Max below 1 prevents identical answers. AHP also reports CI and CR. Settings stay in the left pane; drag the divider or hide them to widen the preview.')
        bar=ttk.Frame(preview);bar.pack(fill='x',padx=14,pady=5)
        self.action(bar,'Generate & Validate',self.generate_mcdm,True).pack(side='left')
        self.action(bar,'Export Excel',self.export_mcdm).pack(side='left',padx=6)
        self.action(bar,'Export validation report',lambda:self.export_mcdm(report=True)).pack(side='left')
        self.ans_combo=ttk.Combobox(bar,textvariable=self.ans_selection,values=['Ans 1'],width=22,state='readonly');self.ans_combo.pack(side='right');self.ans_combo.bind('<<ComboboxSelected>>',lambda e:self.view_batch())
        self.m_info=tk.StringVar(value='Data export contains CODE sheets only. Validation has a separate export.')
        ttk.Label(preview,textvariable=self.m_info,style='Muted.TLabel',wraplength=960).pack(anchor='w',padx=18,pady=4)
        self.mtree=self.table(preview,height=8)
        self.m_panes.bind('<Configure>',lambda e:self.after_idle(self.keep_m_preview))
        self.after(200,self.keep_m_preview)

    def toggle_m_config(self):
        if self.m_config_visible.get():self.m_panes.insert(0,self.m_config,weight=1);self.keep_m_preview()
        else:self.m_panes.forget(self.m_config)

    def keep_m_preview(self):
        if not self.m_config_visible.get() or not self.m_panes.winfo_exists():return
        width=self.m_panes.winfo_width()
        if width>600:
            target=max(320,min(470,int(width*0.36)))
            self.m_panes.sashpos(0,target)

    def update_m_controls(self):
        for widget in self.m_ahp_controls:
            if self.mode.get()=='AHP':widget.grid()
            else:widget.grid_remove()
        if hasattr(self,'dematel_panel') and self.dematel_panel.winfo_exists():
            if self.mode.get()=='DEMATEL':self.dematel_panel.grid()
            else:self.dematel_panel.grid_remove()
        has_order=self.config_data is not None and self.config_data.order_df is not None
        for widget in (self.m_order_check,self.m_order_field):
            if has_order and self.mode.get()!='DEMATEL':widget.grid()
            else:widget.grid_remove()

    def build_weights(self):
        self.hint(self.tab_w,'DEMATEL: choose cause / effect independently. Prominence: HIGH = strong, LOW = weak; RANK derives strength from rank (1 = strongest). AUTO uses Weight.\nExcel: Weights(Criterion, Weight); Order(Criterion, Rank), with 1 = highest. Enable Order to derive weights from ranks.\nProbability controls label sampling; agreement filtering can change the observed distribution.')
        f=ttk.Frame(self.tab_w);f.pack(fill='both',expand=True,padx=14,pady=8)
        canvas=tk.Canvas(f,bg=WHITE,highlightthickness=0);sb=ttk.Scrollbar(f,orient='vertical',command=canvas.yview);canvas.configure(yscrollcommand=sb.set);sb.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        self.edit_frame=ttk.Frame(canvas,style='Card.TFrame');canvas.create_window((0,0),window=self.edit_frame,anchor='nw');self.edit_frame.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        self.action(self.tab_w,'Save configuration',self.save_config).pack(anchor='e',padx=18,pady=10)

    def build_quant(self):
        outer=ttk.Frame(self.tab_q);outer.pack(fill='both',expand=True)
        page=tk.Canvas(outer,bg=BG,highlightthickness=0)
        scroll=ttk.Scrollbar(outer,orient='vertical',command=page.yview)
        page.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');page.pack(side='left',fill='both',expand=True)
        parent=ttk.Frame(page);window=page.create_window((0,0),window=parent,anchor='nw')
        parent.bind('<Configure>',lambda e:page.configure(scrollregion=page.bbox('all')))
        page.bind('<Configure>',lambda e:page.itemconfigure(window,width=e.width))
        self.register_scroll(page,parent)
        p=self.card(parent,'01   Data & target range')
        fields=[('Rows',self.qrows,None),('Response scale',self.qscale,['LIKERT5','LIKERT7','CONTINUOUS']),('Seed',self.qseed,None),('Maximum attempts',self.qattempts,None),('EFA extraction',self.extraction,['PCA','ML']),('Target metric',self.rmetric,['R²','R','Adjusted R²']),('Target minimum',self.rmin,None),('Target maximum',self.rmax,None),('Cronbach min',self.amin,None),('Cronbach max',self.amax,None)]
        for i,(label,var,values) in enumerate(fields):self.field(p,label,var,i//5,i%5,values)
        self.field(p,'VIF must be below',self.vif,2,0)
        ttk.Checkbutton(p,text='CB-SEM / AMOS • validate CFA, model fit and structural paths',variable=self.qsem).grid(row=2,column=1,columnspan=4,sticky='w',padx=6)
        self.qcriteria=CriteriaPanel(parent,'CB-SEM • Fit, measurement & path criteria')
        self.qcriteria.pack(fill='x',padx=14,pady=6);self.qcriteria.pack_forget()
        c=self.card(parent,'02   Constructs & indicators');h=ttk.Frame(c,style='Card.TFrame');h.pack(fill='x')
        for label in ['Construct code','Indicators','Reliable scale','Outcome Y']:ttk.Label(h,text=label,width=18,style='Card.TLabel',font=(self.ui_font,10,'bold')).pack(side='left',padx=4)
        area=ttk.Frame(c,style='Card.TFrame');area.pack(fill='x',pady=3);canvas=tk.Canvas(area,height=165,bg=WHITE,highlightthickness=0);sb=ttk.Scrollbar(area,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set);canvas.pack(side='left',fill='both',expand=True);sb.pack(side='right',fill='y');self.gframe=ttk.Frame(canvas,style='Card.TFrame');canvas.create_window((0,0),window=self.gframe,anchor='nw');self.gframe.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        self.action(c,'+ Add construct',self.add_group).pack(anchor='w',pady=4)
        self.hint(parent,'Uncheck Reliable: low alpha and OLS p ≥0.05; excluded from retained EFA/CFA/SEM. Y must be reliable.\nCB-SEM needs ≥200 rows. For 4+ indicators, review alpha max against AVE ≥0.50.')
        self.qsem.trace_add('write',lambda *args:self.qcriteria.pack(fill='x',padx=14,pady=6,before=c) if self.qsem.get() else self.qcriteria.pack_forget())
        bar=ttk.Frame(parent);bar.pack(fill='x',padx=14,pady=4)
        self.action(bar,'Generate & Validate',self.generate_quant,True).pack(side='left');self.action(bar,'Export Excel',self.export_quant).pack(side='left',padx=8);self.action(bar,'Export AMOS bundle',self.export_amos).pack(side='left')
        self.report_combo=ttk.Combobox(bar,textvariable=self.report_selection,values=['Data'],state='readonly',width=25);self.report_combo.pack(side='right');self.report_combo.bind('<<ComboboxSelected>>',lambda e:self.view_quant())
        self.q_info=tk.StringVar(value='Validation is calculated on the generated dataset.');ttk.Label(parent,textvariable=self.q_info,style='Muted.TLabel',wraplength=1120).pack(anchor='w',padx=18,pady=3);self.qtree=self.table(parent,height=5)

    def add_group(self,name=None,items=3):
        if self.busy:return
        if len(self.groups)>=10:self.error('Up to 10 constructs are supported.');return
        if name is None:name=f'X{len(self.groups)+1}'
        f=ttk.Frame(self.gframe,style='Card.TFrame');f.pack(fill='x',pady=3);g={'frame':f,'name':tk.StringVar(value=name),'items':tk.StringVar(value=str(items)),'accepted':tk.BooleanVar(value=True)}
        ttk.Entry(f,textvariable=g['name'],width=18).pack(side='left',padx=4);ttk.Spinbox(f,textvariable=g['items'],from_=3,to=10,width=16).pack(side='left',padx=4)
        ttk.Checkbutton(f,text='Reliable',variable=g['accepted'],width=16).pack(side='left',padx=4);radio=ttk.Radiobutton(f,text='Y',variable=self.outcome,value=name,width=16);radio.pack(side='left',padx=4)
        previous=[name]
        def renamed(*args):
            new=g['name'].get().strip();radio.configure(value=new)
            if self.outcome.get()==previous[0]:self.outcome.set(new)
            previous[0]=new
        g['name'].trace_add('write',renamed)
        self.action(f,'Delete',lambda:self.remove_group(g)).pack(side='left',padx=6);self.groups.append(g)
    def remove_group(self,g):
        if not self.busy:g['frame'].destroy();self.groups.remove(g)

    def build_convert(self):
        f=self.card(self.tab_c,'Workbook linguistic ↔ fuzzy')
        ttk.Label(f,text='Convert all sheets using the configured Fuzzy mapping; the first column is the row index.\nUnmapped values are preserved. AHP has a separate scale mapping.',style='Card.TLabel').pack(anchor='w',pady=8)
        self.action(f,'Open workbook',self.load_convert,True).pack(anchor='w',pady=6);self.convert_label=ttk.Label(f,text='No workbook loaded',style='Card.TLabel');self.convert_label.pack(anchor='w',pady=4)
        for value,label in [('LING_TO_FUZZY','Linguistic → Fuzzy'),('FUZZY_TO_LING','Fuzzy → Linguistic')]:ttk.Radiobutton(f,text=label,variable=self.conversion,value=value).pack(anchor='w',pady=6)
        self.action(f,'Convert & Export',self.run_convert).pack(anchor='w',pady=10)
    def build_help(self):
        self.hint(self.tab_help,'DataStudio • synthetic data for learning and analysis. See the included user guide for MCDM and Quanti workflows.')
        text=(
            'MCDM\nOpen an Excel configuration, review weights and ranks, then generate and validate all answers. AHP reports CI and CR.\n\n'
            'QUANTITATIVE\nDefine constructs, indicator counts, reliable scales and outcome Y. Choose R, R² or Adjusted R² with a minimum and maximum. Enable CB-SEM to configure required fit and measurement criteria.\n\n'
            'ADVANCED\nChoose CB-SEM, PLS-SEM or regression. Outcome targets are visible directly in Advanced: select R or R² and set a range for each endogenous construct. R = √R² is the model multiple correlation; pairwise Pearson r is separate. Apply settings before editing the diagram.\n\n'
            'MODEL DESIGNER\nAdd constructs, select and drag to move, or use Connect and click source then target. Select any construct or path to edit its properties. Apply properties to save edits. For regression, choose linear, quadratic, cubic or interaction before connecting. Interactions require a moderator. Use Undo/Redo, Auto layout, Fit view, wheel zoom and middle-button pan. Save/Open JSON and export PNG/SVG.\n\n'
            'CSV ANALYSIS\nQuantitative Analysis → Load CSV: select Regression, CB-SEM or PLS-SEM first. Drag source columns into Model Builder, draw arrows, then Analyze CSV. Missing mapped values are rejected unless Drop incomplete rows is enabled. Imported observations are never regenerated; failed criteria stay visible and exportable.\n\n'
            'SESSIONS & PRESETS\nSettings autosave every 15 seconds. Restore autosave, or Save/Open a session. Sessions contain source references, not raw CSV data or completed results; re-run after recovery. Teaching presets include mediation, null effects and regression moderation. Check feasibility lists generation conflicts and heuristic warnings.\n\n'
            'VALIDATION & EXPORT\nCheck model, then Generate & Validate. Required acceptance criteria must pass before export. Changing analytical settings requires regeneration; moving a construct does not. Export Excel or an AMOS data bundle for CB-SEM.\n\n'
            'SCOPE\nCB/PLS: reflective linear DAGs. Regression: polynomial, interaction and hierarchical blocks. Ordinary PLS uses Mode A/path weighting and full-refit bootstrap; it is not PLSc. CB uses semopy MLW; compare proprietary software separately. No formative, higher-order latent, multigroup or cyclic models.\n\n'
            'SYNTHETIC DEMO\nGenerated data is for learning and demonstration. Selected p-values and fit statistics are not evidence from a real survey.')
        area=tk.Text(self.tab_help,wrap='word',font=(self.ui_font,11),bg=WHITE,fg=INK,relief='flat',padx=18,pady=16)
        area.pack(fill='both',expand=True,padx=14,pady=10);area.insert('1.0',text);area.configure(state='disabled')

    def error(self,e):messagebox.showerror('Please check your settings',str(e))
    def choose_save(self,ext='.xlsx'):return filedialog.asksaveasfilename(defaultextension=ext,filetypes=[('Excel' if ext=='.xlsx' else 'ZIP','*'+ext)])
    def seed_value(self,v):
        seed=int(v.get()) if v.get().strip() else None
        if seed is not None and seed<0:raise ValueError('Seed must be a nonnegative integer.')
        return seed
    def adjusted_scale(self):
        if self.config_data is None:raise ValueError('Open the Excel configuration first.')
        s=self.config_data.fuzzy_df.copy();s['Probability']=[float(v.get()) for v in self.prob_vars];return validate_scale(s)

    def load_config(self,path=None):
        if self.busy:return
        path=path or filedialog.askopenfilename(filetypes=[('Excel config','*.xlsx')])
        if not path:return
        try:
            c=load_config_excel(path);self.loaded_config_path=str(Path(path).resolve());parse_advance(c.adv_df,c.rows,c.cols);self.config_data=c;self.update_m_controls();self.batch_result=None;self.batch_signature=None
            self.m_info.set('Configuration loaded. Open Factor Setup to edit cause / effect and strong / weak weights, then generate a new dataset.');self.show_table(self.mtree,pd.DataFrame())
            self.config_label.configure(text=f'{Path(path).name} • {c.m} × {c.n} • '+('Order available' if c.order_df is not None else 'No Order'))
            for w in self.edit_frame.winfo_children():w.destroy()
            self.weight_vars={};self.prob_vars=[];weights=dict(zip(c.weights_df.Criterion,c.weights_df.Weight)) if c.weights_df is not None else {};order=dict(zip(c.order_df.Criterion,c.order_df.Rank)) if c.order_df is not None else {}
            base=len(c.rows)+5
            for j,label in enumerate(['Criterion','Weight','Order Rank','Label / Level','Probability']):ttk.Label(self.edit_frame,text=label,style='Card.TLabel',font=(self.ui_font,10,'bold')).grid(row=base,column=j,padx=18,pady=12)
            for i,r in enumerate(c.rows,1):
                v=tk.StringVar(value=str(weights.get(r,1)));self.weight_vars[r]=v;ttk.Label(self.edit_frame,text=r,style='Card.TLabel').grid(row=base+i,column=0,padx=18,sticky='w');ttk.Entry(self.edit_frame,textvariable=v,width=15).grid(row=base+i,column=1,padx=18,pady=4);ttk.Label(self.edit_frame,text=str(order.get(r,'—')),style='Card.TLabel').grid(row=base+i,column=2,padx=18)
            self.dematel_panel=ttk.LabelFrame(self.edit_frame,text='DEMATEL • independent factor targets',padding=12)
            self.dematel_panel.grid(row=0,column=0,columnspan=5,sticky='ew',padx=12,pady=10)
            self.dematel_vars={}
            profiles=c.dematel_df.set_index('Criterion').to_dict('index') if c.dematel_df is not None else {}
            for j,label in enumerate(['Factor','Weight strength','Cause / effect','Role strength (0–1)','Rank (1 = high)']):ttk.Label(self.dematel_panel,text=label).grid(row=0,column=j,padx=12,pady=5)
            for i,r in enumerate(c.rows,1):
                d=profiles.get(r,{})
                variables=[tk.StringVar(value=str(d.get(k,v))) for k,v in [('Prominence','AUTO'),('Role','AUTO'),('Strength',.65),('Rank',order.get(r,i))]]
                self.dematel_vars[r]=variables;ttk.Label(self.dematel_panel,text=r).grid(row=i,column=0,padx=12,sticky='w')
                for j,choices in [(1,['AUTO','HIGH','MEDIUM','LOW','RANK']),(2,['AUTO','CAUSE','EFFECT','BALANCED'])]:ttk.Combobox(self.dematel_panel,textvariable=variables[j-1],values=choices,state='readonly',width=14).grid(row=i,column=j,padx=12,pady=3)
                ttk.Entry(self.dematel_panel,textvariable=variables[2],width=14).grid(row=i,column=3,padx=12)
                ttk.Entry(self.dematel_panel,textvariable=variables[3],width=14).grid(row=i,column=4,padx=12)
            for i,(_,r) in enumerate(c.fuzzy_df.iterrows(),1):
                v=tk.StringVar(value=str(r.Probability));self.prob_vars.append(v);ttk.Label(self.edit_frame,text=f'{r.Lingustic} / {r.Level}',style='Card.TLabel').grid(row=base+i,column=3,padx=18,sticky='w');ttk.Entry(self.edit_frame,textvariable=v,width=15).grid(row=base+i,column=4,padx=18,pady=4)
            self.update_m_controls()
        except Exception as e:self.error(e)
    def save_config(self):
        if self.busy:return
        try:
            scale=self.adjusted_scale();c=self.config_data;weights=pd.DataFrame({'Criterion':c.rows,'Weight':[float(self.weight_vars[r].get()) for r in c.rows]})
            if not np.isfinite(weights.Weight).all() or (weights.Weight<=0).any():raise ValueError('Weight must be positive and finite.')
            path=self.choose_save()
            if path:save_config(path,c,scale,weights,pd.DataFrame.from_dict(self.dematel_profile(),orient='index').reset_index(names='Criterion'));self.saved(path)
        except Exception as e:self.error(e)

    def dematel_profile(self):
        return {r:dict(Prominence=v[0].get(),Role=v[1].get(),Strength=float(v[2].get()),Rank=float(v[3].get())) for r,v in self.dematel_vars.items()}

    def m_snapshot(self):
        if self.config_data is None:raise ValueError('Open an Excel configuration before generating MCDM data.')
        c=self.config_data;scale=self.adjusted_scale();n=int(self.count.get());prefix=self.prefix.get().strip()
        import re
        if not prefix or len(f'{prefix} {n}')>31 or re.search(r'[\\/*?:\[\]]',prefix) or prefix.startswith("'") or prefix.casefold()=='numeric':raise ValueError('Invalid sheet prefix; Numeric is reserved.')
        opts=dict(count=n,seed=self.seed_value(self.seed),weights=[float(self.weight_vars[r].get()) for r in c.rows],noise=float(self.noise.get()) if self.mode.get()=='AHP' else .15,max_cr=float(self.cr.get()) if self.mode.get()=='AHP' else .1,discrete=self.discrete.get() if self.mode.get()=='AHP' else True,consensus=float(self.consensus.get()),min_pearson=float(self.pearson.get()),min_spearman=float(self.spearman.get()),max_pearson=float(self.pearson_max.get()),max_spearman=float(self.spearman_max.get()))
        if self.mode.get()=='DEMATEL':opts['dematel_profiles']=self.dematel_profile()
        if self.mode.get()!='DEMATEL' and self.use_order.get() and c.order_df is not None:
            mapping=dict(zip(c.order_df.Criterion,c.order_df.Rank));ranks=np.array([mapping[r] for r in c.rows]);opts['weights']=(1+4*(len(ranks)-ranks)/max(1,len(ranks)-1)).tolist();opts['order_ranks']=ranks.tolist();opts['min_order']=float(self.order_min.get())
        args=(c.rows[:],c.cols[:],scale,c.adv_df,self.mode.get(),self.output.get());sig=json.dumps({'axes':args[:2],'modes':args[4:],'scale':scale.to_json(),'advance':c.adv_df.to_json() if c.adv_df is not None else None,'opts':opts,'prefix':prefix},sort_keys=True);return args,opts,prefix,sig
    def q_snapshot(self):
        groups=[Construct(g['name'].get().strip(),int(g['items'].get()),g['accepted'].get(),g['name'].get().strip()==self.outcome.get()) for g in self.groups]
        lo,hi=float(self.rmin.get()),float(self.rmax.get());n=int(self.qrows.get());metric=self.rmetric.get()
        if not np.isfinite([lo,hi]).all() or not 0<lo<hi<1:raise ValueError('Use 0 < min < max < 1.')
        if metric=='R':lo,hi=lo**2,hi**2
        if metric=='Adjusted R²':k=len(groups)-1;lo,hi=1-(1-lo)*(n-k-1)/(n-1),1-(1-hi)*(n-k-1)/(n-1)
        opts=dict(n=n,r2_min=lo,r2_max=hi,scale=self.qscale.get(),sem=self.qsem.get(),seed=self.seed_value(self.qseed),max_attempts=int(self.qattempts.get()),alpha_min=float(self.amin.get()),alpha_max=float(self.amax.get()),vif_max=float(self.vif.get()),extraction=self.extraction.get(),sem_criteria=self.qcriteria.snapshot() if self.qsem.get() else None)
        validate(groups,n,lo,hi,opts['scale'],opts['sem'],opts['max_attempts'],opts['alpha_min'],opts['alpha_max'],opts['vif_max'],opts['sem_criteria'])
        sig=json.dumps({'groups':[vars(g) for g in groups],'opts':opts,'metric':metric,'range':[self.rmin.get(),self.rmax.get()]},sort_keys=True);return groups,opts,sig

    def start(self,work,callback):
        if self.busy:return
        self.busy=True;self.cancel_event.clear();self.progressbar.configure(mode='indeterminate',value=0);self.progressbar.start(10);self.cancel_button.configure(state='normal')
        for b in self.actions:
            if b.winfo_exists():b.configure(state='disabled')
        self.status.set('Working…')
        def run():
            try:self.events.put(('done',(callback,work())))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=run,daemon=True).start()
    def progress(self,text):self.events.put(('progress',text))
    def poll(self):
        try:
            while True:
                kind,payload=self.events.get_nowait()
                if kind=='progress':
                    self.status.set(payload)
                    stages=re.findall(r'(?:attempt|candidate|bootstrap)\s+(\d+)/(\d+)',payload,re.I)
                    if stages:
                        current,total=map(int,stages[-1]);self.progressbar.stop()
                        self.progressbar.configure(mode='determinate',maximum=total,value=current)
                    continue
                self.busy=False;self.progressbar.stop();self.cancel_button.configure(state='disabled')
                for b in self.actions:
                    if b.winfo_exists():b.configure(state='normal')
                if kind=='error':self.status.set('Task stopped; no new result.');self.error(payload)
                else:
                    callback,value=payload
                    try:callback(value)
                    except Exception as e:self.error(e)
        except queue.Empty:pass
        self.after(100,self.poll)

    def generate_mcdm(self):
        if self.busy:return
        try:args,opts,prefix,sig=self.m_snapshot()
        except Exception as e:self.error(e);return
        self.batch_result=None;self.batch_signature=None
        def done(r):
            self.batch_result=r;self.batch_signature=sig;self.ans_combo.configure(values=[f'Ans {i+1}' for i in range(len(r.answers))]+['Agreement Summary','Factor Scores','Cell Pearson','Factor Pearson','Factor Spearman']+(['DEMATEL Results'] if r.settings.get('DEMATEL aggregate results') else []));self.ans_selection.set('Ans 1' if r.settings.get('Required criteria passed',False) else 'Agreement Summary');self.view_batch()
            mask=~np.eye(len(r.pearson),dtype=bool);p=r.pearson.to_numpy()[mask];s=r.spearman.to_numpy()[mask]
            text=('All criteria passed • ' if r.settings.get('Required criteria passed',False) else 'BEST EFFORT — review Agreement Summary • ')+f'{len(r.answers)} answers • '+(f'Pearson={np.nanmin(p):.3f}–{np.nanmax(p):.3f} • Spearman={np.nanmin(s):.3f}–{np.nanmax(s):.3f}' if len(p) and np.isfinite(p).any() else 'Correlation not applicable / undefined')
            if r.settings['Mode']=='AHP':text+=' • CI/CR in Agreement Summary'
            if r.settings['Mode']=='DEMATEL':text+=f" • aggregate target failures: {r.settings.get('DEMATEL aggregate target failures','undefined')}"
            self.m_info.set(text);self.status.set('MCDM results are ready to export.')
        self.start(lambda:generate_batch(*args,**opts,progress=self.progress,cancel=self.cancel_event),done)
    def view_batch(self):
        if self.batch_result is None:return
        r=self.batch_result;name=self.ans_selection.get();mapping={'Agreement Summary':r.summary,'Factor Scores':r.factor_scores,'Cell Pearson':r.cell_pearson,'Factor Pearson':r.pearson,'Factor Spearman':r.spearman,'DEMATEL Results':pd.DataFrame(r.settings.get('DEMATEL aggregate results',[]))};df=r.answers[int(name.split()[1])-1] if name.startswith('Ans ') else mapping[name];self.show_table(self.mtree,df)
    def export_mcdm(self,report=False):
        if self.busy:return
        try:
            args,opts,prefix,sig=self.m_snapshot()
            if self.batch_result is None or sig!=self.batch_signature:raise ValueError('Settings changed or no dataset exists. Generate & Validate before exporting.')
            path=self.choose_save()
            if not path:return
            sheets=mcdm_report_sheets(self.batch_result,args[2],args[3],pd.DataFrame({'Criterion':args[0],'Weight':opts['weights']}),self.config_data.order_df) if report else mcdm_data_sheets(self.batch_result,prefix)
            self.start(lambda:export_excel(path,sheets,cancel=self.cancel_event),lambda _:self.saved(path))
        except Exception as e:self.error(e)

    def generate_quant(self):
        if self.busy:return
        try:groups,opts,sig=self.q_snapshot()
        except Exception as e:self.error(e);return
        self.quant_result=None;self.quant_signature=None
        def work():
            r=generate_quantitative(groups,**opts,progress=self.progress,cancel=self.cancel_event);r.settings['Construct design']=json.dumps([vars(g) for g in groups]);return r
        def done(r):
            self.quant_result=r;self.quant_signature=sig;self.report_combo.configure(values=['Data','Construct Scores']+list(r.reports));self.report_selection.set('Data' if r.settings.get('Required criteria passed',False) else 'Acceptance');self.view_quant();row=r.reports['Regression Summary'].iloc[0]
            self.q_info.set(f"{len(r.data)} rows • R={row['R']:.3f} • R²={row['R2']:.3f} • Adjusted R²={row['Adjusted R2']:.3f} • Attempt {r.settings['Attempt accepted']} • "+('All required criteria passed' if r.settings.get('Required criteria passed',False) else 'BEST EFFORT — review Acceptance for failed criteria'));self.status.set('Ready to export. Preview shows up to 250 rows.')
        self.start(work,done)
    def view_quant(self):
        if self.quant_result is None:return
        r=self.quant_result;name=self.report_selection.get();self.show_table(self.qtree,r.data if name=='Data' else r.scores if name=='Construct Scores' else r.reports[name])
    def checked_quant(self):
        _,_,sig=self.q_snapshot()
        if self.quant_result is None or sig!=self.quant_signature:raise ValueError('Settings changed or no dataset exists. Generate & Validate before exporting.')
        return self.quant_result
    def export_quant(self):
        if self.busy:return
        try:
            r=self.checked_quant();path=self.choose_save()
            if path:self.start(lambda:export_excel(path,quant_sheets(r),cancel=self.cancel_event),lambda _:self.saved(path))
        except Exception as e:self.error(e)
    def export_amos(self):
        if self.busy:return
        try:
            r=self.checked_quant()
            if not r.settings['CB SEM']:raise ValueError('Enable CB-SEM and regenerate before exporting an AMOS bundle.')
            path=self.choose_save('.zip')
            if path:self.start(lambda:export_amos_bundle(path,r,cancel=self.cancel_event),lambda _:self.saved(path))
        except Exception as e:self.error(e)
    def saved(self,path):self.status.set('Saved '+Path(path).name);messagebox.showinfo('Export complete',f'Saved {Path(path).name}')
    def load_convert(self):
        if self.busy:return
        path=filedialog.askopenfilename(filetypes=[('Excel','*.xlsx')])
        if not path:return
        try:self.convert_sheets=pd.read_excel(path,sheet_name=None,index_col=0);self.convert_label.configure(text=f'{Path(path).name} • {len(self.convert_sheets)} sheets')
        except Exception as e:self.error(e)
    def run_convert(self):
        if self.busy:return
        try:
            scale=self.adjusted_scale()
            if self.convert_sheets is None:raise ValueError('Open a workbook to convert first.')
            mode=self.conversion.get();source=self.convert_sheets.copy();path=self.choose_save()
            if path:self.start(lambda:export_excel(path,{name:convert_df(df,mode,scale) for name,df in source.items()}),lambda _:self.saved(path))
        except Exception as e:self.error(e)
    def close(self):
        if self.busy and not messagebox.askyesno('Task in progress','Close the application and cancel this task?'):return
        if hasattr(self,'session') and self.session.enabled.get():self.session.autosave()
        self.cancel_event.set();self.destroy()
