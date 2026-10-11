from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QComboBox,QCheckBox,QPushButton,QLabel,
    QFileDialog,QTableWidget,QTableWidgetItem,QPlainTextEdit,QLineEdit,QGroupBox,QMessageBox,
    QTabWidget,QWidget,QRadioButton,QButtonGroup,QHeaderView,QAbstractItemView,QSplitter,
    QScrollArea,QApplication
)
from PyQt6.QtCore import pyqtSignal,Qt,QTimer
from core.standalone_import import inspect_workbook,create_project_from_workbook
from core.import_builder import validate_definition,summary_definition,infer_from_sample,generate_data_template
from ui.friendly_message import show_success,show_error

QUESTION_TYPES=['SHORT_TEXT','LONG_TEXT','INTEGER','DECIMAL','SINGLE_CHOICE','MULTI_CHOICE','LIKERT','MATRIX_LIKERT']

class ImportProjectDialog(QDialog):
    project_created=pyqtSignal(str)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Import Excel as New Project — V8.5')
        self.setMinimumSize(760,520)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint,True)
        self.setSizeGripEnabled(True)
        self.path='';self.check=None;self.definition=None
        self.matrix_by_parent={};self.current_matrix_parent='';self._building_ui=True
        root=QVBoxLayout(self)
        title=QLabel('Excel → New .mcdm Project');title.setObjectName('pageTitle');root.addWidget(title)
        sub=QLabel('V8.5: configure a friendly schema on UI or infer it from a sample Excel, validate it, generate the data-entry workbook, then preview the completed workbook before creating a project.')
        sub.setWordWrap(True);root.addWidget(sub)
        self.tabs=QTabWidget();root.addWidget(self.tabs,1)
        self._build_config_tab();self._build_preview_tab();self._building_ui=False
        QTimer.singleShot(0,self._fit_to_screen)

    def _fit_to_screen(self):
        screen=self.screen() or QApplication.primaryScreen()
        if not screen:return
        a=screen.availableGeometry()
        w=min(1100,max(820,int(a.width()*0.78)));h=min(760,max(580,int(a.height()*0.78)))
        self.resize(w,h)
        self.move(a.center().x()-w//2,a.center().y()-h//2)

    def _button_row(self,add_slot,remove_slot,add_text='+ Add',remove_text='− Remove selected'):
        w=QWidget();l=QHBoxLayout(w);l.setContentsMargins(0,0,0,0)
        a=QPushButton(add_text);a.clicked.connect(add_slot);r=QPushButton(remove_text);r.clicked.connect(remove_slot)
        l.addWidget(a);l.addWidget(r);l.addStretch();return w

    def _table(self,headers,rows):
        t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers);t.setAlternatingRowColors(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        t.horizontalHeader().setStretchLastSection(True)
        t.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for row in rows:self._append_plain_row(t,row)
        return t

    def _append_plain_row(self,t,row):
        r=t.rowCount();t.insertRow(r)
        for c,v in enumerate(row):
            t.setItem(r,c,QTableWidgetItem(str(v)))
        return r

    def _set_combo(self,t,r,c,choices,value):
        cb=QComboBox();cb.addItems(choices);cb.setCurrentText(value if value in choices else choices[0])
        cb.currentTextChanged.connect(lambda _v,rr=r,cc=c,tt=t:self._combo_changed(tt,rr,cc))
        t.setCellWidget(r,c,cb)

    def _cell_text(self,t,r,c):
        w=t.cellWidget(r,c)
        if isinstance(w,QComboBox):return w.currentText().strip()
        return t.item(r,c).text().strip() if t.item(r,c) else ''

    def _rows(self,t):
        out=[]
        for r in range(t.rowCount()):
            vals=[self._cell_text(t,r,c) for c in range(t.columnCount())]
            if any(vals):out.append(vals)
        return out

    def _remove_selected(self,t,after=None):
        rows=sorted({i.row() for i in t.selectionModel().selectedRows()},reverse=True)
        if not rows and t.currentRow()>=0:rows=[t.currentRow()]
        for r in rows:t.removeRow(r)
        if after:after()

    def _next_code(self,t,prefix,width=3,col=0):
        used={self._cell_text(t,r,col) for r in range(t.rowCount())}
        n=1
        while f'{prefix}{n:0{width}d}' in used:n+=1
        return f'{prefix}{n:0{width}d}'

    def _add_mcdm_row(self,t,prefix,kind):
        code=self._next_code(t,prefix,2 if kind=='scale' else 3)
        if kind=='scale':row=[f'New level {t.rowCount()+1}',code,'']
        else:row=[code,'']
        r=self._append_plain_row(t,row);t.setCurrentCell(r,1 if t.columnCount()>1 else 0);t.editItem(t.item(r,1))

    def _add_question(self):
        qid=self._next_code(self.questions,'Q',3)
        r=self._append_plain_row(self.questions,[qid,'New question','','',''])
        self.questions.item(r,0).setFlags(self.questions.item(r,0).flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._set_combo(self.questions,r,2,QUESTION_TYPES,'SHORT_TEXT');self._set_combo(self.questions,r,3,['No','Yes'],'No')
        self.questions.setCurrentCell(r,1);self.questions.editItem(self.questions.item(r,1))
        if not self._building_ui:self._question_selected(r,1)

    def _remove_question(self):
        r=self.questions.currentRow()
        if r<0:return
        qid=self._cell_text(self.questions,r,0);self.matrix_by_parent.pop(qid,None)
        self.questions.removeRow(r);self.current_matrix_parent='';self._load_matrix('')

    def _add_qual(self):
        qid=self._next_code(self.qualq,'Q',3)
        r=self._append_plain_row(self.qualq,[qid,'New interview question',''])
        self.qualq.item(r,0).setFlags(self.qualq.item(r,0).flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._set_combo(self.qualq,r,2,['No','Yes'],'No');self.qualq.setCurrentCell(r,1);self.qualq.editItem(self.qualq.item(r,1))

    def _add_matrix_item(self):
        parent=self.current_matrix_parent
        if not parent:return
        existing=self._rows(self.matrix);n=len(existing)+1
        used={x[0] for x in existing}
        item=f'{parent}_{n:02d}'
        while item in used:n+=1;item=f'{parent}_{n:02d}'
        r=self._append_plain_row(self.matrix,[item,'New component'])
        self.matrix.item(r,0).setFlags(self.matrix.item(r,0).flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.matrix.setCurrentCell(r,1);self.matrix.editItem(self.matrix.item(r,1))

    def _remove_matrix_item(self):
        self._remove_selected(self.matrix);self._save_matrix_for_current()

    def _build_config_tab(self):
        outer=QWidget();ol=QVBoxLayout(outer)
        scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();lay=QVBoxLayout(body);scroll.setWidget(body);ol.addWidget(scroll,1)
        top=QHBoxLayout();top.addWidget(QLabel('Project type:'));self.pt=QComboBox()
        self.pt.addItem('MCDM','MCDM');self.pt.addItem('Quantitative Survey','QUANTITATIVE_SURVEY');self.pt.addItem('Qualitative Interview','QUALITATIVE_INTERVIEW')
        self.pt.currentIndexChanged.connect(self._type_changed);top.addWidget(self.pt);top.addSpacing(18)
        self.ui_mode=QRadioButton('Configure on UI');self.sample_mode=QRadioButton('Detect schema from sample Excel');self.ui_mode.setChecked(True)
        self.mode_group=QButtonGroup(self);self.mode_group.addButton(self.ui_mode);self.mode_group.addButton(self.sample_mode);self.ui_mode.toggled.connect(self._mode_changed)
        top.addWidget(self.ui_mode);top.addWidget(self.sample_mode);top.addStretch();lay.addLayout(top)
        h=QLabel('Choose one method. In UI mode, IDs/codes are generated automatically. Use + Add to create as many questions, factors, solutions or components as needed.');h.setWordWrap(True);lay.addWidget(h)

        self.manual_box=QGroupBox('A. Configure schema on UI');ml=QVBoxLayout(self.manual_box)
        self.mcdm_opts=QWidget();mf=QFormLayout(self.mcdm_opts);self.model=QComboBox();self.model.addItems(['DEMATEL','TOPSIS','AHP','DELPHI']);self.z=QCheckBox('Enable Z-number')
        mf.addRow('MCDM model',self.model);mf.addRow('',self.z);ml.addWidget(self.mcdm_opts)

        self.editor_tabs=QTabWidget();self.editor_tabs.setMinimumHeight(360);ml.addWidget(self.editor_tabs,1)
        self.scale=self._table(['Code (auto)','Linguistic Term','Value'],[])
        self.factors=self._table(['Code (auto)','Factor Name'],[])
        self.alts=self._table(['Code (auto)','Solution / Alternative'],[])
        self.zscale=self._table(['Code (auto)','Reliability Term','Value'],[])
        for term,val in [('Low','0,0.25,0.5'),('Medium','0.25,0.5,0.75'),('High','0.5,0.75,1')]:
            r=self._append_plain_row(self.scale,[self._next_code(self.scale,'S',2),term,val]);self.scale.item(r,0).setFlags(self.scale.item(r,0).flags() & ~Qt.ItemFlag.ItemIsEditable)
        for name in ['Criterion 1','Criterion 2']:
            r=self._append_plain_row(self.factors,[self._next_code(self.factors,'C',3),name]);self.factors.item(r,0).setFlags(self.factors.item(r,0).flags() & ~Qt.ItemFlag.ItemIsEditable)
        for name in ['Alternative 1','Alternative 2']:
            r=self._append_plain_row(self.alts,[self._next_code(self.alts,'A',3),name]);self.alts.item(r,0).setFlags(self.alts.item(r,0).flags() & ~Qt.ItemFlag.ItemIsEditable)
        for term,val in [('Low certainty','0,0.25,0.5'),('Medium certainty','0.25,0.5,0.75'),('High certainty','0.5,0.75,1')]:
            r=self._append_plain_row(self.zscale,[self._next_code(self.zscale,'Z',2),term,val]);self.zscale.item(r,0).setFlags(self.zscale.item(r,0).flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.questions=self._table(['Question_ID (auto)','Question / Column','Type','Required','Options / Choices'],[])
        for text,typ,opt in [('Question 1','SHORT_TEXT',''),('Question 2','LIKERT','1|2|3|4|5')]:
            self._add_question();r=self.questions.rowCount()-1;self.questions.item(r,1).setText(text);self.questions.cellWidget(r,2).setCurrentText(typ);self.questions.item(r,4).setText(opt)
        self.questions.currentCellChanged.connect(self._question_selected);self.questions.cellClicked.connect(lambda r,c:self._question_selected(r,c))
        self.matrix=self._table(['Item_ID (auto)','Matrix component / statement'],[])
        self.qualq=self._table(['Question_ID (auto)','Interview Question','Required'],[])
        for text,req in [('Describe your experience.','Yes'),('What challenges did you encounter?','No')]:
            self._add_qual();r=self.qualq.rowCount()-1;self.qualq.item(r,1).setText(text);self.qualq.cellWidget(r,2).setCurrentText(req)
        self.qualq.currentCellChanged.connect(self._qual_selected)

        self.guide=QLabel('Click a configuration row or field to see what should be entered.');self.guide.setWordWrap(True)
        self.guide.setStyleSheet('padding:9px;border:1px solid #b8c2cc;background:#f7f9fb;')
        for table in (self.scale,self.factors,self.alts,self.zscale):table.currentCellChanged.connect(self._mcdm_selected)
        ml.addWidget(self.guide);lay.addWidget(self.manual_box,1)

        self.sample_box=QGroupBox('B. Detect schema from sample Excel');sl=QVBoxLayout(self.sample_box);sr=QHBoxLayout()
        self.sample_path=QLineEdit();self.sample_path.setReadOnly(True);sb=QPushButton('Select Sample Excel...');sb.clicked.connect(self._sample)
        sr.addWidget(self.sample_path,1);sr.addWidget(sb);sl.addLayout(sr)
        self.sample_info=QPlainTextEdit();self.sample_info.setReadOnly(True);self.sample_info.setMaximumHeight(95)
        self.sample_info.setPlaceholderText('MCDM: at least one ANS sheet. Quantitative: header + at least one data row. Qualitative: answer table with Answer column.')
        sl.addWidget(self.sample_info);lay.addWidget(self.sample_box)

        actions=QHBoxLayout();self.validate_schema=QPushButton('SCAN / VALIDATE SCHEMA');self.validate_schema.setProperty('accent',True);self.validate_schema.clicked.connect(self._validate_schema)
        self.gen=QPushButton('GENERATE DATA-ENTRY EXCEL...');self.gen.setProperty('success',True);self.gen.setEnabled(False);self.gen.clicked.connect(self._generate)
        actions.addWidget(self.validate_schema);actions.addWidget(self.gen);actions.addStretch();lay.addLayout(actions)
        self.schema_summary=QLabel('NOT VALIDATED — Configure the schema or select a sample workbook, then Scan / Validate.')
        self.schema_summary.setWordWrap(True);self.schema_summary.setStyleSheet('padding:8px;border:1px solid #999;font-weight:600;');lay.addWidget(self.schema_summary)
        self.tabs.addTab(outer,'1. Configure / Detect Schema');self._type_changed();self._mode_changed()

    def _mcdm_panel(self,t,prefix,kind):
        w=QWidget();l=QVBoxLayout(w);l.addWidget(t,1)
        l.addWidget(self._button_row(lambda:self._add_mcdm_row(t,prefix,kind),lambda:self._remove_selected(t)))
        return w

    def _clear_editor_tabs(self):
        while self.editor_tabs.count():self.editor_tabs.removeTab(0)

    def _type_changed(self):
        if not hasattr(self,'editor_tabs'):return
        self._clear_editor_tabs();pt=self.pt.currentData();self.mcdm_opts.setVisible(pt=='MCDM')
        if pt=='MCDM':
            self.editor_tabs.addTab(self._mcdm_panel(self.scale,'S','scale'),'Scale')
            self.editor_tabs.addTab(self._mcdm_panel(self.factors,'C','item'),'Factors')
            self.editor_tabs.addTab(self._mcdm_panel(self.alts,'A','item'),'Solutions')
            self.editor_tabs.addTab(self._mcdm_panel(self.zscale,'Z','scale'),'Z Reliability')
        elif pt=='QUANTITATIVE_SURVEY':
            panel=QWidget();pl=QVBoxLayout(panel);split=QSplitter(Qt.Orientation.Horizontal)
            left=QWidget();ll=QVBoxLayout(left);ll.addWidget(QLabel('Questions / data columns'));ll.addWidget(self.questions,1);ll.addWidget(self._button_row(self._add_question,self._remove_question,'+ Add question','− Remove question'))
            right=QGroupBox('Matrix components — selected MATRIX_LIKERT question');rl=QVBoxLayout(right)
            self.matrix_hint=QLabel('Select a MATRIX_LIKERT question. Each component becomes a separate column, and each answer is ONE choice from the parent question Options (for example 1|2|3|4|5).')
            self.matrix_hint.setWordWrap(True);rl.addWidget(self.matrix_hint);rl.addWidget(self.matrix,1);rl.addWidget(self._button_row(self._add_matrix_item,self._remove_matrix_item,'+ Add component','− Remove component'))
            split.addWidget(left);split.addWidget(right);split.setSizes([650,450]);pl.addWidget(split,1);self.quant_matrix_box=right;self.editor_tabs.addTab(panel,'Questions / Columns')
            if self.questions.rowCount():self.questions.setCurrentCell(0,1);self._question_selected(0,1)
        else:
            panel=QWidget();pl=QVBoxLayout(panel);pl.addWidget(self.qualq,1);pl.addWidget(self._button_row(self._add_qual,lambda:self._remove_selected(self.qualq),'+ Add interview question','− Remove question'))
            self.editor_tabs.addTab(panel,'Interview Questions')
        self.definition=None
        if hasattr(self,'gen'):self.gen.setEnabled(False)

    def _combo_changed(self,t,r,c):
        if self._building_ui:return
        if t is self.questions:self._question_selected(r,c)
        elif t is self.qualq:self._qual_selected(r,c)

    def _question_selected(self,r,c,pr=-1,pc=-1):
        if r<0 or r>=self.questions.rowCount():return
        if self.current_matrix_parent:self._save_matrix_for_current()
        qid=self._cell_text(self.questions,r,0);qtype=self._cell_text(self.questions,r,2)
        self.current_matrix_parent=qid if qtype=='MATRIX_LIKERT' else ''
        guides={
            0:'Question_ID is generated automatically and is read-only. It remains stable in Excel, .mcdm, export and sync.',
            1:'Enter the user-facing question/column label.',
            2:'Choose the data type. SINGLE_CHOICE, MULTI_CHOICE and LIKERT need Options. MATRIX_LIKERT needs Options plus one or more components on the right.',
            3:'Required = Yes means blank answers are rejected; No permits blanks.',
            4:'Choices are separated by |. Example: Yes|No or 1|2|3|4|5. For MATRIX_LIKERT, every component uses this same single-choice scale.'
        }
        self.guide.setText(guides.get(c,'Configure the selected question.'))
        enabled=(qtype=='MATRIX_LIKERT')
        self.quant_matrix_box.setEnabled(enabled)
        if enabled:
            self.matrix_hint.setText(f'{qid}: add each matrix statement/component below. Every component is answered with ONE choice from Options of {qid}. Item_ID is generated automatically.')
            self._load_matrix(qid)
        else:
            self._load_matrix('')

    def _save_matrix_for_current(self):
        if self.current_matrix_parent:self.matrix_by_parent[self.current_matrix_parent]=self._rows(self.matrix)

    def _load_matrix(self,parent):
        self.matrix.clearContents();self.matrix.setRowCount(0)
        for row in self.matrix_by_parent.get(parent,[]) if parent else []:
            r=self._append_plain_row(self.matrix,row)
            self.matrix.item(r,0).setFlags(self.matrix.item(r,0).flags() & ~Qt.ItemFlag.ItemIsEditable)

    def _qual_selected(self,r,c,pr=-1,pc=-1):
        self.guide.setText({
            0:'Question_ID is generated automatically and is read-only.',
            1:'Enter the interview question exactly as respondents should see it.',
            2:'Required = Yes requires an answer; No permits a blank answer.'
        }.get(c,'Configure the selected interview question.'))

    def _mcdm_selected(self,r,c,pr=-1,pc=-1):
        t=self.sender()
        if t in (self.scale,self.zscale):
            msg={0:'Code is generated automatically and read-only.',1:'Enter a readable linguistic/reliability label.',2:'Enter the fuzzy numeric tuple used by the selected scale.'}.get(c,'Configure the scale row.')
        else:
            msg='Code is generated automatically and read-only.' if c==0 else 'Enter the user-facing factor/solution name.'
        self.guide.setText(msg)

    def _mode_changed(self):
        if hasattr(self,'manual_box'):
            self.manual_box.setEnabled(self.ui_mode.isChecked());self.sample_box.setEnabled(self.sample_mode.isChecked());self.definition=None;self.gen.setEnabled(False)

    def _manual_definition(self):
        pt=self.pt.currentData();d={'project_type':pt,'source_mode':'UI','access_mode':'Free'}
        if pt=='MCDM':
            # UI columns are Code, Label, Value; builder expects term/code/value
            d.update(model=self.model.currentText(),use_z=self.z.isChecked(),
                scale=[{'code':r[0],'term':r[1],'value':r[2]} for r in self._rows(self.scale)],
                factors=[{'code':r[0],'name':r[1]} for r in self._rows(self.factors)],
                alternatives=[{'code':r[0],'name':r[1]} for r in self._rows(self.alts)],
                z_scale=[{'code':r[0],'term':r[1],'value':r[2]} for r in self._rows(self.zscale)])
        elif pt=='QUANTITATIVE_SURVEY':
            d['questions']=[{'question_id':r[0],'question_text':r[1],'question_type':r[2] or 'SHORT_TEXT','required':r[3].lower()=='yes','options':r[4]} for r in self._rows(self.questions)]
            self._save_matrix_for_current();d['matrix_items']=[]
            for parent,items in self.matrix_by_parent.items():
                d['matrix_items'].extend([{'parent_id':parent,'item_id':r[0],'item_text':r[1]} for r in items if any(r)])
        else:
            d['questions']=[{'question_id':r[0],'question_text':r[1],'required':r[2].lower()=='yes'} for r in self._rows(self.qualq)]
        return d

    def _sample(self):
        p,_=QFileDialog.getOpenFileName(self,'Select sample data workbook',str(Path.home()),'Excel (*.xlsx)')
        if p:self.sample_path.setText(p);self.definition=None;self.gen.setEnabled(False)

    def _validate_schema(self):
        try:
            d=self._manual_definition() if self.ui_mode.isChecked() else infer_from_sample(self.sample_path.text(),self.pt.currentData(),self.model.currentText(),self.z.isChecked()) if self.sample_path.text() else (_ for _ in ()).throw(ValueError('Select a sample Excel workbook first.'))
            errs=validate_definition(d)
            if errs:raise ValueError('\n'.join(errs))
            self.definition=d;self.gen.setEnabled(True);s=summary_definition(d);self.schema_summary.setText(s);self.sample_info.setPlainText(s+(f"\nSample: {d.get('sample_file')}" if d.get('sample_file') else ''))
        except Exception as e:
            self.definition=None;self.gen.setEnabled(False);self.schema_summary.setText('INVALID — '+str(e).replace('\n',' | '))
            show_error(self,'Schema Validation Failed','Configuration/sample schema is not ready.',e)

    def _generate(self):
        if not self.definition:return
        p,_=QFileDialog.getSaveFileName(self,'Generate Data-entry Excel',str(Path.home()/f"{self.pt.currentData()}_V85_DATA_TEMPLATE.xlsx"),'Excel (*.xlsx)')
        if not p:return
        try:
            generate_data_template(p,self.definition)
            show_success(self,'Data Template Created','Configuration is embedded. Paste historical data into BLUE tabs only, then use Preview & Create Project.',[('File',p),('Schema',summary_definition(self.definition))]);self.tabs.setCurrentIndex(1)
        except Exception as e:show_error(self,'Template Failed','Could not generate the data-entry workbook.',e)

    def _build_preview_tab(self):
        w=QWidget();root=QVBoxLayout(w);note=QLabel('Select the completed V8.5 Excel workbook. Validation and preview happen before any .mcdm project is created.');note.setWordWrap(True);root.addWidget(note)
        row=QHBoxLayout();self.scan=QPushButton('Scan / Detect Workbook...');self.scan.clicked.connect(self.scan_file);self.browse=QPushButton('Select Workbook...');self.browse.clicked.connect(self.select);self.validate=QPushButton('Validate & Preview');self.validate.setProperty('accent',True);self.validate.clicked.connect(self.preview)
        row.addWidget(self.scan);row.addWidget(self.browse);row.addWidget(self.validate);row.addStretch();root.addLayout(row)
        self.state=QLabel('No workbook selected.');root.addWidget(self.state);self.table=QTableWidget();self.table.setAlternatingRowColors(True);self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel);root.addWidget(self.table,1)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(120);root.addWidget(self.details)
        b=QHBoxLayout();b.addWidget(QLabel('New project name:'));self.name=QLineEdit();b.addWidget(self.name,1);self.create=QPushButton('CREATE NEW .MCDM PROJECT');self.create.setProperty('success',True);self.create.setEnabled(False);self.create.clicked.connect(self.do_create);b.addWidget(self.create);root.addLayout(b)
        self.tabs.addTab(w,'2. Preview & Create Project')

    def _set_path(self,p):self.path=p;self.check=None;self.create.setEnabled(False);self.state.setText(Path(p).name);self.name.setText(Path(p).stem)
    def select(self):
        p,_=QFileDialog.getOpenFileName(self,'Select V8.5 data workbook',str(Path.home()),'Excel (*.xlsx)')
        if p:self._set_path(p)
    def scan_file(self):
        p,_=QFileDialog.getOpenFileName(self,'Scan Excel Workbook',str(Path.home()),'Excel (*.xlsx)')
        if p:self._set_path(p);self.preview()
    def preview(self):
        if not self.path:QMessageBox.warning(self,'Workbook Required','Select a workbook first.');return
        try:
            c=inspect_workbook(self.path);self.check=c;h=c.get('headers',[]);rows=c.get('preview',[])
            self.table.clear();self.table.setColumnCount(len(h));self.table.setHorizontalHeaderLabels(h);self.table.setRowCount(len(rows))
            for i,r in enumerate(rows):
                for j,k in enumerate(h):self.table.setItem(i,j,QTableWidgetItem(str(r.get(k,'') or '')))
            self.table.resizeColumnsToContents()
            msg=['Sheets: '+', '.join(c.get('sheets',[]))]+(['ERROR: '+x for x in c['errors']] if c.get('errors') else [f"VALID — {len(rows)} preview rows shown. Review them before creating the project."])
            self.details.setPlainText('\n'.join(msg));self.create.setEnabled(c['valid']);self.state.setText(('VALID' if c['valid'] else 'INVALID')+f" — {c.get('project_type') or 'UNKNOWN'} — Preview: {c.get('sheet') or 'n/a'}")
        except Exception as e:self.create.setEnabled(False);show_error(self,'Validation Failed','Workbook could not be validated.',e)
    def do_create(self):
        if not self.check or not self.check.get('valid'):return
        p,_=QFileDialog.getSaveFileName(self,'Create New Project',str(Path.home()/(self.name.text().strip() or 'Imported_Project')),'Research Project (*.mcdm)')
        if not p:return
        if not p.lower().endswith('.mcdm'):p+='.mcdm'
        try:
            res=create_project_from_workbook(self.path,p,self.name.text().strip() or None)
            show_success(self,'New Project Created','Excel data was converted into a new Research Studio project.',[('Project ID',res['project_id']),('Storage Key',res['storage_key']),('Responses',str(res['responses'])),('File',p)])
            self.project_created.emit(p);self.accept()
        except Exception as e:show_error(self,'Import Failed','No project was kept because validation/import did not complete successfully.',e)
