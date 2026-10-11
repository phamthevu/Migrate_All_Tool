from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QTabWidget,QLabel,QPushButton,QFileDialog,QMessageBox,QComboBox,QSplitter,QListWidget,QListWidgetItem,QTextBrowser,QTableWidget,QTableWidgetItem,QAbstractItemView,QGroupBox,QFormLayout,QDoubleSpinBox,QStatusBar,QPlainTextEdit,QFrame,QHeaderView,QInputDialog)
from core.excel_io import TEMPLATE,DEMATEL_TEMPLATE,DEMO,DEMATEL_DEMO,load_input,generate_template,method_input_preview,save_workbook_edits,write_results
from core.methods import (calculate_ahp,calculate_swara,calculate_entropy_weights,calculate_critic_weights,
                          calculate_merec_weights,calculate_std_weights,calculate_bwm_weights,
                          calculate_psi_weights,
                          calculate_fucom_weights,run_ranking,_run_dematel,_run_ism,_run_anp,get_audit_code)

METHOD_GROUPS={
 'Criterion Weights':['AHP','ANP','SWARA','BWM','FUCOM','Entropy weights','CRITIC','MEREC','Standard deviation','PSI weights'],
 'Alternative Ranking':['SAW','TOPSIS','MOORA','MULTIMOORA','COPRAS-G','ARAS','WASPAS','VIKOR','ELECTRE I','PROMETHEE II','CoCoSo','EDAS','MARCOS','CODAS','MAIRCA','MABAC','GRA','PIV'],
 'Causal / Structural Analysis':['DEMATEL','ISM']
}
METHOD_SHEETS={
 'AHP':['Criteria','AHP Pairwise'], 'ANP':['Criteria','ANP Weighted Supermatrix'],
 'SWARA':['Criteria','SWARA'], 'BWM':['Criteria'], 'FUCOM':['Criteria','FUCOM'],
 'Entropy weights':['Decision Matrix','Criteria'], 'CRITIC':['Decision Matrix','Criteria'], 'MEREC':['Decision Matrix','Criteria'],
 'Standard deviation':['Decision Matrix','Criteria'], 'PSI weights':['Decision Matrix','Criteria'],
 'DEMATEL':['DEMATEL Direct Relations'], 'ISM':['Criteria','ISM SSIM']
}
for _ranking_name in METHOD_GROUPS['Alternative Ranking']:
    METHOD_SHEETS[_ranking_name]=['Decision Matrix','Criteria']
BOOK_NOTES={
 'SAW':'The book’s §2.1 summary mixes in AHP consistency steps. In §2.2, the written cost formula and the hotel example’s cost column disagree: the table appears to reward larger cost values. This app uses min(x)/x for cost so a lower cost scores better; weights are calculated separately.',
 'COPRAS-G':'Chapter 13 presents COPRAS-G for interval data. This template contains scalar values, so each value is interpreted as a degenerate interval [x, x], preserving the book’s normalization and significance equations.',
 'SWARA':'Chapter 16 describes SWARA through a procedural figure rather than a full numbered equation list. The displayed coefficient/weight equations are the standard arithmetic that implements the book’s stated comparison, coefficient, recalculation, and normalization steps.',
 'WASPAS':'The app exposes λ (default 0.5) in the book’s Eq. 15.3. The book also presents variance-based λ optimization in Eqs. 15.4–15.6; it is not silently substituted for the user-selected λ.'
 ,'DEMATEL':'DEMATEL needs expert influence scores, not alternative performance values. Use the dedicated DEMATEL Direct Relations sheet (0–4; zero diagonal). This app calculates T=D(I−D)⁻¹, the conventional total-effects matrix; one typeset equation in the book omits the −I adjustment.'
 ,'ISM':'ISM needs expert judgments about pairwise contextual links. Use the upper triangle of the ISM SSIM sheet with V/A/X/O. The app computes transitive closure and level partitions; experts must validate the relation model.'
 ,'ANP':'ANP models dependence and feedback through a weighted, column-stochastic supermatrix. This implementation audits the later limit-priority calculation; cluster structure and local pairwise judgments must be prepared in the ANP Weighted Supermatrix sheet.'
 ,'ELECTRE I':'ELECTRE I creates a possibly incomplete outranking relation, not always a full ranking. This implementation uses mean off-diagonal concordance/discordance thresholds unless custom thresholds are passed to the calculation API.'
 ,'PROMETHEE II':'Uses the simplified linear preference function shown in the book’s worked procedure; the six generalized preference-function shapes are not enabled in this version.'
 ,'MULTIMOORA':'This combines ratio-system, reference-point and full multiplicative components. The displayed aggregate uses a transparent rank sum; classic MULTIMOORA applies dominance theory.'
 ,'BWM':'BWM uses one selected best and worst criterion plus two 1–9 comparison vectors. The app solves the linear minimax version and reports the optimal maximum deviation.'
 ,'CRITIC':'CRITIC derives objective weights from normalized standard deviation and inter-criterion correlation.'
 ,'MEREC':'MEREC derives objective weights from how much each criterion’s removal changes the aggregate logarithmic performance.'
 ,'Standard deviation':'An objective dispersion baseline: normalized standard deviations become weights. Compare it with CRITIC and MEREC.'
 ,'CoCoSo':'CoCoSo combines weighted sum and power measures into three compromise appraisals, then combines them into the final score.'
 ,'CODAS':'CODAS uses Euclidean distance from the negative ideal, with Taxicab distance as a secondary discriminator.'
 ,'MARCOS':'MARCOS compares alternatives against both ideal and anti-ideal reference alternatives.'
 ,'EDAS':'EDAS compares positive and negative distances from the average solution.'
 ,'MAIRCA':'MAIRCA compares theoretical ratings from equal alternative probabilities with performance-adjusted real ratings.'
 ,'MABAC':'MABAC ranks alternatives by their signed distance from the border approximation area.'
 ,'GRA':'Grey relational analysis compares each alternative with the ideal reference sequence using grey relational coefficients.'
 ,'PSI weights':'Preference Selection Index derives objective weights from criterion preference variation; no pairwise judgments are required.'
 ,'FUCOM':'FUCOM uses ranked criteria and adjacent priority judgments, then minimizes deviations from direct and transitive consistency.'
 ,'PIV':'PIV ranks alternatives by the weighted proximity from the ideal best; smaller total proximity is preferred.'
}
METHOD_LINKS={
 'AHP':('Thakkar (2021), ch. 3','https://doi.org/10.1007/978-981-33-4745-8'), 'ANP':('Thakkar (2021), ch. 4','https://doi.org/10.1007/978-981-33-4745-8'),
 'TOPSIS':('Thakkar (2021), ch. 5','https://doi.org/10.1007/978-981-33-4745-8'), 'DEMATEL':('Thakkar (2021), ch. 9','https://doi.org/10.1007/978-981-33-4745-8'), 'ISM':('Warfield (1974)','https://doi.org/10.1109/TSMC.1974.4309336'),
 'BWM':('Rezaei (2015)','https://doi.org/10.1016/j.omega.2014.11.009'), 'FUCOM':('Pamučar et al. (2018)','https://doi.org/10.3390/sym10090393'),
 'CRITIC':('Diakoulaki et al. (1995)','https://doi.org/10.1016/0305-0548(94)00059-H'), 'MEREC':('Keshavarz-Ghorabaee et al. (2021)','https://doi.org/10.3390/sym13040525'),
 'PSI weights':('Maniya & Bhatt (2010)','https://doi.org/10.1016/j.matdes.2009.11.020'), 'CoCoSo':('Yazdani et al. (2019)','https://doi.org/10.1108/MD-05-2017-0458'),
 'EDAS':('Keshavarz-Ghorabaee et al. (2015)','https://doi.org/10.15388/Informatica.2015.57'), 'MARCOS':('Stević et al. (2020)','https://doi.org/10.1016/j.cie.2019.106231'),
 'MABAC':('Pamučar & Ćirović (2015)','https://doi.org/10.1016/j.eswa.2014.11.057'), 'PIV':('Mufazzal & Muzakkir (2018)','https://doi.org/10.1016/j.cie.2018.03.045')
}

STYLE='''QMainWindow,QWidget{background:#f4f7fb;color:#1e293b;font-family:"Segoe UI";font-size:11pt} QGroupBox{background:white;border:1px solid #d9e2ee;border-radius:10px;margin-top:12px;padding:12px;font-weight:600} QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 5px;color:#174c69} QPushButton{background:#e8eef5;border:1px solid #d4deea;border-radius:7px;padding:9px 14px;font-weight:600} QPushButton:hover{background:#dce8f4} QPushButton[primary="true"]{background:#176b87;color:white;border-color:#176b87} QPushButton[primary="true"]:hover{background:#12566d} QComboBox,QDoubleSpinBox{background:white;border:1px solid #cad5e2;border-radius:6px;padding:7px} QListWidget,QTextBrowser,QTableWidget{background:white;border:1px solid #d9e2ee;border-radius:8px} QListWidget::item{padding:10px;border-radius:5px} QListWidget::item:selected{background:#dceef5;color:#134e63} QTabWidget::pane{border:1px solid #d9e2ee;border-radius:8px;background:white} QTabBar::tab{padding:10px 18px;background:#e8eef5;border-top-left-radius:6px;border-top-right-radius:6px;margin-right:4px} QTabBar::tab:selected{background:#176b87;color:white}'''

def runtime_root():
    if getattr(sys,'frozen',False): return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def to_table(widget, df, editable=False):
    if not isinstance(df.index, pd.RangeIndex):
        label = df.index.name or 'Alternative / Criterion'
        df = df.rename_axis(label).reset_index()
    widget.clear(); widget.setRowCount(len(df)); widget.setColumnCount(len(df.columns)); widget.setHorizontalHeaderLabels([str(x) for x in df.columns])
    for i,row in enumerate(df.itertuples(index=False,name=None)):
        for j,val in enumerate(row):
            if pd.isna(val): text=''
            elif isinstance(val,(float,int,np.floating,np.integer)): text=f'{val:.6g}'
            else: text=str(val)
            item=QTableWidgetItem(text)
            if editable: item.setBackground(QColor('#fff2c6'))
            else: item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            widget.setItem(i,j,item)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); widget.horizontalHeader().setMinimumSectionSize(76); widget.verticalHeader().setDefaultSectionSize(30); widget.setAlternatingRowColors(True)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('MCDMStudio | Step-by-step decision methods'); self.resize(1600,1000); self.setMinimumSize(1280,800)
        self.data=None; self.steps=[]; self.weight_steps=[]; self.weights=None; self.weight_source='Manual / template'; self.export_path=None; self.input_saved=False; self.preview_frames={}; self.preview_sheet=''
        shell=QWidget(); shell_layout=QVBoxLayout(shell); shell_layout.setContentsMargins(0,0,0,0); shell_layout.setSpacing(0)
        self._build_header(shell_layout); self.tabs=QTabWidget(); shell_layout.addWidget(self.tabs,1); self.setCentralWidget(shell)
        self._build_import_tab(); self._build_practice_tab(); self._build_audit_tab(); self._build_export_tab(); self.setStatusBar(QStatusBar()); self.statusBar().showMessage('Import a workbook, review it, save, then continue to the MCDM tool.')
        self.setStyleSheet(STYLE)
        self.load_demo()

    def _build_header(self, layout):
        banner=QFrame(); banner.setObjectName('appBanner'); banner.setStyleSheet('#appBanner{background:#123f58;border:0}')
        row=QHBoxLayout(banner); row.setContentsMargins(24,10,24,10); row.setSpacing(12)
        mark=QLabel('MCDM TOOL'); mark.setStyleSheet('font-size:9pt;font-weight:800;letter-spacing:1px;background:#2e7991;border-radius:10px;padding:8px 12px;color:white')
        name=QLabel('MCDMStudio'); name.setStyleSheet('font-size:18pt;font-weight:750;color:white;background:transparent')
        tagline=QLabel('Step-by-step multi-criteria decision analysis'); tagline.setStyleSheet('color:#e6f1f6;font-size:10pt;background:transparent')
        row.addWidget(mark); row.addWidget(name); row.addWidget(tagline); row.addStretch(); layout.addWidget(banner)

    def _build_import_tab(self):
        page=QWidget(); root=QVBoxLayout(page); root.setContentsMargins(22,20,22,20); root.setSpacing(14)
        title=QLabel('Import, review and save data'); title.setStyleSheet('font-size:18pt;font-weight:700;color:#123f58'); root.addWidget(title)
        sub=QLabel('Choose the data layout that matches the method: DEMATEL has factors on both axes; TOPSIS-style input has alternatives in rows and factors in columns.'); sub.setWordWrap(True); sub.setStyleSheet('color:#526579'); root.addWidget(sub)
        actions=QHBoxLayout(); self.file_label=QLabel('No workbook selected'); self.file_label.setStyleSheet('font-weight:600;color:#174c69')
        actions.addWidget(QLabel('Input layout'))
        self.template_kind=QComboBox(); self.template_kind.addItem('TOPSIS: alternatives × factors','TOPSIS'); self.template_kind.addItem('DEMATEL: factors × factors','DEMATEL'); actions.addWidget(self.template_kind)
        b=QPushButton('Import Excel…'); b.setProperty('primary',True); b.clicked.connect(self.open_excel); actions.addWidget(b)
        b=QPushButton('Save blank template…'); b.clicked.connect(self.save_template); actions.addWidget(b)
        b=QPushButton('Load demo'); b.clicked.connect(self.load_demo); actions.addWidget(b); actions.addStretch(); actions.addWidget(self.file_label); root.addLayout(actions)
        method_row=QHBoxLayout(); method_row.addWidget(QLabel('Method group'))
        self.group_box=QComboBox(); self.group_box.addItems(METHOD_GROUPS); self.group_box.currentTextChanged.connect(self._group_changed); self.group_box.setMinimumWidth(245); method_row.addWidget(self.group_box)
        method_row.addWidget(QLabel('Method'))
        self.method_box=QComboBox(); self.method_box.currentTextChanged.connect(self._method_changed); self.method_box.setMinimumWidth(260); method_row.addWidget(self.method_box)
        self.param_label=QLabel('λ'); method_row.addWidget(self.param_label)
        self.param_spin=QDoubleSpinBox(); self.param_spin.setRange(0,1); self.param_spin.setSingleStep(.1); self.param_spin.setValue(.5); method_row.addWidget(self.param_spin)
        method_row.addStretch(); root.addLayout(method_row)
        self.validation=QLabel(''); self.validation.setWordWrap(True); root.addWidget(self.validation)
        self.method_help=QLabel('Choose a method to see which workbook sheets it uses.'); self.method_help.setWordWrap(True); self.method_help.setStyleSheet('color:#174c69;font-weight:600'); root.addWidget(self.method_help)
        group=QGroupBox('Workbook sheet preview and editor | select any sheet to inspect or edit its values'); gl=QVBoxLayout(group)
        sheet_row=QHBoxLayout(); sheet_row.addWidget(QLabel('Sheet')); self.sheet_box=QComboBox(); self.sheet_box.currentTextChanged.connect(self._show_selected_sheet); self.sheet_box.setMinimumWidth(280); sheet_row.addWidget(self.sheet_box); sheet_row.addStretch(); self.sheet_note=QLabel('Yellow cells can be edited; column headers stay fixed.'); self.sheet_note.setStyleSheet('color:#617488'); sheet_row.addWidget(self.sheet_note); gl.addLayout(sheet_row)
        self.input_table=QTableWidget(); self.input_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked|QAbstractItemView.EditTrigger.EditKeyPressed|QAbstractItemView.EditTrigger.AnyKeyPressed); gl.addWidget(self.input_table,1); root.addWidget(group,1)
        self.input_table.itemChanged.connect(self.mark_input_dirty)
        self.input_table.horizontalHeader().sectionDoubleClicked.connect(self.edit_sheet_header)
        actions2=QHBoxLayout(); note=QLabel('Edit any sheet, then save and calculate. The workbook is saved as a reviewed copy and processed immediately.'); note.setWordWrap(True); note.setStyleSheet('color:#617488'); actions2.addWidget(note,1)
        self.run_button=QPushButton('Save and calculate →'); self.run_button.setProperty('primary',True); self.run_button.clicked.connect(self.save_and_process); self.run_button.setEnabled(False); actions2.addWidget(self.run_button); root.addLayout(actions2); self._group_changed(self.group_box.currentText())
        self.tabs.addTab(page,'1. Import and preview')

    def _build_practice_tab(self):
        page=QWidget(); root=QVBoxLayout(page); root.setContentsMargins(20,18,20,18); root.setSpacing(12)
        title=QLabel('Calculation results'); title.setStyleSheet('font-size:19pt;font-weight:700;color:#123f58'); root.addWidget(title)
        self.result_status=QLabel('Choose a method on the Import and preview tab, then calculate to see the complete result here.'); self.result_status.setWordWrap(True); self.result_status.setStyleSheet('color:#526579'); root.addWidget(self.result_status)
        split=QSplitter(Qt.Orientation.Horizontal); root.addWidget(split,1)
        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,8,0); ll.addWidget(QLabel('Calculation steps'))
        self.step_list=QListWidget(); self.step_list.currentRowChanged.connect(self.show_step); self.step_list.setMinimumHeight(160); ll.addWidget(self.step_list,2)
        nav=QHBoxLayout(); self.prev=QPushButton('← Previous'); self.next=QPushButton('Next →'); self.prev.clicked.connect(lambda:self.step_list.setCurrentRow(max(0,self.step_list.currentRow()-1))); self.next.clicked.connect(lambda:self.step_list.setCurrentRow(min(self.step_list.count()-1,self.step_list.currentRow()+1))); nav.addWidget(self.prev); nav.addWidget(self.next); ll.addLayout(nav)
        self.left_details=QTabWidget(); self.theory=QTextBrowser(); self.theory.setOpenExternalLinks(True); self.left_details.addTab(self.theory,'Instructions and formula'); ll.addWidget(self.left_details,3); split.addWidget(left)
        right=QWidget(); rr=QVBoxLayout(right); rr.setContentsMargins(8,0,0,0); right_split=QSplitter(Qt.Orientation.Vertical); rr.addWidget(right_split,1)
        previous_box=QWidget(); previous_layout=QVBoxLayout(previous_box); previous_layout.setContentsMargins(0,0,0,4); previous_layout.addWidget(QLabel('Previous-step data | imported input for the first step'))
        self.previous_table=QTableWidget(); self.previous_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); previous_layout.addWidget(self.previous_table,1); right_split.addWidget(previous_box)
        result_box=QWidget(); result_layout=QVBoxLayout(result_box); result_layout.setContentsMargins(0,4,0,0); result_layout.addWidget(QLabel('Current-step result | click a cell to inspect its formula'))
        self.result_table=QTableWidget(); self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.result_table.cellClicked.connect(self.show_cell_formula); result_layout.addWidget(self.result_table,1); right_split.addWidget(result_box)
        right_split.setSizes([430,430]); right_split.setStretchFactor(0,1); right_split.setStretchFactor(1,1); split.addWidget(right)
        split.setSizes([470,1150]); split.setStretchFactor(0,0); split.setStretchFactor(1,1); self.tabs.addTab(page,'2. Results')

    def _build_audit_tab(self):
        page=QWidget(); root=QVBoxLayout(page); root.setContentsMargins(22,18,22,18); root.setSpacing(10)
        title=QLabel('Python audit source'); title.setStyleSheet('font-size:19pt;font-weight:700;color:#123f58'); root.addWidget(title)
        desc=QLabel('The source code for the selected method is shown here at full width. Copy it or export it as a .py or .txt file for review.')
        desc.setWordWrap(True); desc.setStyleSheet('color:#526579'); root.addWidget(desc)
        actions=QHBoxLayout(); actions.addWidget(QLabel('Calculation source for auditing')); actions.addStretch()
        self.copy_audit=QPushButton('Copy Python'); self.copy_audit.clicked.connect(self.copy_audit_code); self.save_audit=QPushButton('Export .py…'); self.save_audit.clicked.connect(self.save_audit_code); actions.addWidget(self.copy_audit); actions.addWidget(self.save_audit); root.addLayout(actions)
        self.audit_code=QPlainTextEdit(); self.audit_code.setReadOnly(True); self.audit_code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap); self.audit_code.setStyleSheet('font-family:Consolas,monospace;font-size:10pt;background:#10202d;color:#e2edf5'); root.addWidget(self.audit_code,1)
        self.tabs.addTab(page,'3. Python audit'); self.tabs.setTabEnabled(2,False)

    def _build_export_tab(self):
        page=QWidget(); root=QVBoxLayout(page); root.setContentsMargins(22,20,22,20); root.setSpacing(12)
        title=QLabel('Export the full calculation trail'); title.setStyleSheet('font-size:20pt;font-weight:700;color:#123f58'); root.addWidget(title)
        desc=QLabel('Export includes input matrix, active criterion weights, a separate worksheet for every method step, its displayed formula, and the book page reference.'); desc.setWordWrap(True); root.addWidget(desc)
        self.export_summary=QLabel('Run a weighting or ranking method first.'); self.export_summary.setWordWrap(True); root.addWidget(self.export_summary)
        b=QPushButton('Export all steps to Excel…'); b.setProperty('primary',True); b.clicked.connect(self.export_results); root.addWidget(b,0,Qt.AlignmentFlag.AlignLeft); root.addStretch(); self.tabs.addTab(page,'4. Export'); self.tabs.setTabEnabled(3,False)

    def _group_changed(self, group):
        if not hasattr(self,'method_box'): return
        methods=METHOD_GROUPS.get(group,[])
        if self.data and self.data.get('decision_mode')=='DEMATEL': methods=['DEMATEL'] if group=='Causal / Structural Analysis' else []
        self.method_box.blockSignals(True); self.method_box.clear(); self.method_box.addItems(methods); self.method_box.blockSignals(False); self._method_changed(self.method_box.currentText()); self.run_button.setEnabled(self.input_saved and bool(self.method_box.currentText()))
    def _method_changed(self, method):
        params={'WASPAS':('λ',.5),'VIKOR':('v',.5),'CoCoSo':('λ',.5),'CODAS':('τ',.02)}
        visible=method in params; label,default=params.get(method,('λ',.5)); self.param_label.setVisible(visible); self.param_label.setText(label); self.param_spin.setVisible(visible); self.param_spin.setDecimals(3); self.param_spin.setSingleStep(.01 if method=='CODAS' else .1); self.param_spin.setValue(default)
        if method and hasattr(self,'method_help'):
            sheets=METHOD_SHEETS.get(method,['Decision Matrix','Criteria'])
            template='DEMATEL template' if method=='DEMATEL' else 'TOPSIS-style template'
            shared=' The Decision Matrix is shared by every ranking method; each ranking method reads the same alternative-by-criterion layout.' if method in METHOD_GROUPS['Alternative Ranking'] else ''
            self.method_help.setText(f'{method} uses the {template}. Required sheets: {", ".join(sheets)}.{shared} Selecting a method opens its main input sheet below; use the sheet list to inspect or edit other sheets.')
            primary=sheets[-1] if method in ('AHP','ANP','SWARA','BWM','FUCOM','DEMATEL','ISM') else sheets[0]
            if self.data and primary in self.preview_frames and self.sheet_box.currentText()!=primary:
                self.sheet_box.setCurrentText(primary)
        if getattr(self,'calculated_method',None) and method!=self.calculated_method:
            self._clear_results('Method changed. Calculate again to replace the previous result.')
        if hasattr(self,'theory') and method and getattr(self,'calculated_method',None)==method:
            ref={'AHP':'Chapter 3, §§3.3–3.4','ANP':'Chapter 4, §4.3','SWARA':'Chapter 16, §16.2','Entropy weights':'Shannon entropy objective weighting','CRITIC':'Diakoulaki et al. (1995)','MEREC':'Keshavarz-Ghorabaee et al. (2021)','Standard deviation':'Objective weighting baseline','PSI weights':'Maniya & Bhatt (2010)','FUCOM':'Pamučar et al. (2018), DOI: 10.3390/sym10090393','BWM':'Rezaei (2015)','SAW':'Chapter 2, §§2.1–2.2','TOPSIS':'Chapter 5, §5.2','VIKOR':'Chapter 8, §8.2','MOORA':'Chapter 11, §11.2','MULTIMOORA':'Chapter 11, §11.2 and MULTIMOORA discussion','COPRAS-G':'Chapter 13, §13.2','ARAS':'Chapter 14, §14.2','WASPAS':'Chapter 15, §15.2','ELECTRE I':'Chapter 6, §6.2','PROMETHEE II':'Chapter 7, §7.2','CoCoSo':'Yazdani et al. (2019)','EDAS':'Keshavarz-Ghorabaee et al. (2015)','MARCOS':'Stević et al. (2020)','CODAS':'Ghorabaee et al. (2016)','MAIRCA':'Pamučar et al.','MABAC':'Pamučar & Ćirović (2015)','GRA':'Deng (1989), grey relational analysis','PIV':'Mufazzal & Muzakkir (2018), DOI: 10.1016/j.cie.2018.03.045','DEMATEL':'Chapter 9, §§9.2–9.3','ISM':'Chapter 18, §§18.2–18.3'}.get(method,'')
            note=BOOK_NOTES.get(method,'')
            citation,url=METHOD_LINKS.get(method,('Thakkar (2021), book reference', 'https://doi.org/10.1007/978-981-33-4745-8'))
            self.theory.setHtml(f'<h3>{method}</h3><p><b>Verified source:</b> <a href="{url}">{citation} · DOI/source</a> ({ref}).</p><p>Select a step, then click a cell in its result table to see the formula, value and source reference.</p>' + (f'<p style="color:#9a3412"><b>Method note:</b> {note}</p>' if note else ''))
            self.audit_code.setPlainText(get_audit_code(method))

    def _matrix_sheet_name(self):
        return 'DEMATEL Direct Relations' if self.data and self.data.get('decision_mode')=='DEMATEL' else 'Decision Matrix'

    def _table_frame(self):
        columns=[self.input_table.horizontalHeaderItem(c).text() if self.input_table.horizontalHeaderItem(c) else f'Column {c+1}' for c in range(self.input_table.columnCount())]
        rows=[]
        for r in range(self.input_table.rowCount()):
            rows.append([self.input_table.item(r,c).text() if self.input_table.item(r,c) else '' for c in range(self.input_table.columnCount())])
        return pd.DataFrame(rows,columns=columns)

    def _show_selected_sheet(self,sheet):
        if not sheet or sheet not in self.preview_frames:return
        self.preview_sheet=sheet
        self.input_table.blockSignals(True); to_table(self.input_table,self.preview_frames[sheet],editable=True); self.input_table.blockSignals(False)
        self.sheet_note.setText('Double-click a cell or a column heading to edit it. Select the sheet named in the method guide.')
        self.input_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked|QAbstractItemView.EditTrigger.EditKeyPressed|QAbstractItemView.EditTrigger.AnyKeyPressed)

    def edit_sheet_header(self,column):
        item=self.input_table.horizontalHeaderItem(column)
        if item is None:return
        value,ok=QInputDialog.getText(self,'Edit column name','Column heading:',text=item.text())
        if ok and value.strip():
            item.setText(value.strip())
            self.mark_input_dirty()

    def _clear_results(self,message='No results yet. Choose a method on the Import and preview tab, then calculate.'):
        self.calculated_method=None; self.steps=[]; self.weight_steps=[]
        if hasattr(self,'step_list'): self.step_list.clear()
        if hasattr(self,'result_table'): self.result_table.clear()
        if hasattr(self,'previous_table'): self.previous_table.clear()
        if hasattr(self,'theory'): self.theory.clear()
        if hasattr(self,'audit_code'): self.audit_code.clear()
        if hasattr(self,'export_summary'): self.export_summary.setText(message)
        if hasattr(self,'result_status'): self.result_status.setText(message)
        if hasattr(self,'tabs') and self.tabs.count()>3:
            self.tabs.setTabEnabled(2,False); self.tabs.setTabEnabled(3,False)

    def _set_input(self,data,saved=False):
        preferred_group=self.group_box.currentText() if hasattr(self,'group_box') else 'Criterion Weights'
        preferred_method=self.method_box.currentText() if hasattr(self,'method_box') else 'AHP'
        self.data=data; self.weights=None; self.weight_source='Manual / template'; self.input_saved=saved; self._clear_results()
        self.file_label.setText(Path(data['path']).name); self.preview_frames={name:frame.copy() for name,frame in data.get('sheet_previews',{}).items()};
        if not self.preview_frames:self.preview_frames={self._matrix_sheet_name():data['preview'].copy()}
        matrix_sheet=self._matrix_sheet_name()
        if matrix_sheet not in self.preview_frames:self.preview_frames[matrix_sheet]=data['preview'].copy()
        self.sheet_box.blockSignals(True); self.sheet_box.clear(); self.sheet_box.addItems(list(self.preview_frames)); self.sheet_box.setCurrentText(matrix_sheet); self.sheet_box.blockSignals(False); self._show_selected_sheet(matrix_sheet)
        mode=data.get('decision_mode','TOPSIS'); self.template_kind.setCurrentIndex(1 if mode=='DEMATEL' else 0)
        warning=[]
        vals=np.asarray(data.get('matrix'),dtype=float)
        if not np.isfinite(vals).all(): warning.append('Some numeric cells are blank. Fill the yellow cells and save before continuing.')
        if mode=='TOPSIS':
            if any(x not in ('Benefit','Cost') for x in data['directions']): warning.append('Set each factor direction to Benefit or Cost in the Criteria sheet.')
            if len(data['alternatives'])<2: warning.append('At least two alternatives are needed for ranking.')
            description=f'{len(data["alternatives"])} alternatives × {len(data["criteria"])} factors.'
        else:
            if np.isfinite(vals).all() and (np.diag(vals)!=0).any(): warning.append('DEMATEL diagonal values must remain zero.')
            if np.isfinite(vals).all() and ((vals<0).any() or (vals>4).any()): warning.append('DEMATEL influence scores must be between 0 and 4.')
            description=f'{len(data["criteria"])} factors × {len(data["criteria"])} factors.'
        self.validation.setText(('⚠ '+ ' '.join(warning)) if warning else f'Workbook loaded: {description} Review values and save to continue.')
        self.validation.setStyleSheet('color:#b45309;font-weight:600' if warning else 'color:#174c69;font-weight:600')
        target_group='Causal / Structural Analysis' if mode=='DEMATEL' else preferred_group
        if hasattr(self,'group_box'): self.group_box.setCurrentText(target_group); self._group_changed(target_group)
        if preferred_method in [self.method_box.itemText(i) for i in range(self.method_box.count())]: self.method_box.setCurrentText(preferred_method)
        self.tabs.setTabEnabled(1,saved); self.tabs.setTabEnabled(2,saved and bool(self.steps)); self.tabs.setTabEnabled(3,saved and bool(self.steps)); self.run_button.setEnabled(bool(self.method_box.currentText()))
        self.run_button.setText('Calculate selected method →' if saved else 'Save edits and calculate →')
        self.tabs.setCurrentIndex(0); self.statusBar().showMessage('Review the editable cells, then save the workbook to unlock the MCDM tool.')

    def mark_input_dirty(self,_item=None):
        if not self.data:return
        if self.preview_sheet: self.preview_frames[self.preview_sheet]=self._table_frame()
        self.input_saved=False; self.tabs.setTabEnabled(1,False); self.tabs.setTabEnabled(2,False); self.tabs.setTabEnabled(3,False)
        self.run_button.setEnabled(True); self.run_button.setText('Save edits and calculate →')
        self.statusBar().showMessage('Input changed. Save the workbook again before continuing.')

    def open_excel(self):
        path,_=QFileDialog.getOpenFileName(self,'Import MCDM Excel workbook','','Excel workbook (*.xlsx *.xlsm)')
        if not path:return
        try:self._set_input(load_input(path),saved=False)
        except Exception as e: QMessageBox.warning(self,'Workbook could not be loaded',str(e))
    def load_demo(self):
        try:
            is_dematel=self.template_kind.currentData()=='DEMATEL'
            p=(DEMATEL_DEMO if is_dematel else DEMO)
            if not p.exists(): p=runtime_root()/'Templates'/'Demo Data'/'MCDMStudio'/p.name
            self._set_input(load_input(p),saved=True)
        except Exception as e: self.validation.setText(f'Demo workbook is not installed yet: {e}')
    def save_template(self):
        kind=self.template_kind.currentData(); suggested='MCDM_DEMATEL_Input_Template.xlsx' if kind=='DEMATEL' else 'MCDM_TOPSIS_Input_Template.xlsx'
        p,_=QFileDialog.getSaveFileName(self,'Save blank MCDM template',suggested,'Excel workbook (*.xlsx)')
        if not p:return
        try:generate_template(p,False,kind); QMessageBox.information(self,'Template ready',f'Blank template saved to:\n{p}')
        except Exception as e: QMessageBox.critical(self,'Template error',str(e))

    def save_and_process(self):
        if not self.data:return
        if not self.method_box.currentText():
            QMessageBox.information(self,'Choose a method','Select the method before saving and calculating.')
            return
        if self.preview_sheet:self.preview_frames[self.preview_sheet]=self._table_frame()
        if self.input_saved:
            self.calculate()
            return
        try:
            suggested=Path(self.data['path']).with_name(Path(self.data['path']).stem+'_reviewed.xlsx')
            path,_=QFileDialog.getSaveFileName(self,'Save reviewed workbook and calculate',str(suggested),'Excel workbook (*.xlsx)')
            if not path:return
            save_workbook_edits(self.data['path'],path,self.preview_frames)
            self._set_input(load_input(path),saved=True)
            method=self.method_box.currentText()
            matrix=np.asarray(self.data.get('matrix'),dtype=float)
            if self.data.get('decision_mode')=='DEMATEL':
                if not np.isfinite(matrix).all():raise ValueError('Fill every required numeric input cell before calculating.')
                if matrix.shape[0]!=matrix.shape[1]:raise ValueError('The DEMATEL matrix must be square.')
                if not np.allclose(np.diag(matrix),0):raise ValueError('DEMATEL diagonal values must be zero.')
                if (matrix<0).any() or (matrix>4).any():raise ValueError('DEMATEL influence scores must be between 0 and 4.')
            elif method in METHOD_GROUPS['Alternative Ranking'] or method in ('Entropy weights','CRITIC','MEREC','Standard deviation','PSI weights'):
                if not np.isfinite(matrix).all():raise ValueError('Fill every required numeric input cell in Decision Matrix before calculating.')
                if matrix.shape[0]<2 or matrix.shape[1]<2:raise ValueError('This method needs at least two alternatives and two criteria.')
                if any(d not in ('Benefit','Cost') for d in self.data['directions']):raise ValueError('In Criteria, set each direction to Benefit or Cost.')
            self.calculate()
        except Exception as e:QMessageBox.warning(self,'Please correct the input',str(e))
    def calculate(self):
        if not self.data: QMessageBox.information(self,'Import data first','Import the MCDMStudio template or load demo data.'); return
        if not self.input_saved: QMessageBox.information(self,'Save the workbook first','Save the reviewed workbook before calculating.'); return
        method=self.method_box.currentText(); criteria=self.data['criteria']
        if not method: QMessageBox.information(self,'Choose a method','Select a method on the Import and preview tab first.'); return
        # Every run starts a fresh trail. Keep already-computed weights for a following
        # ranking method, but never carry the previous method's steps into this run.
        if method in METHOD_GROUPS['Criterion Weights'] or method in ('DEMATEL','ISM'):
            self.weights=None; self.weight_source='Manual / template'
        self._clear_results(f'Calculating {method}…')
        self.export_summary.setText('Run a method to create a new calculation trail.')
        self.tabs.setTabEnabled(1,True); self.tabs.setTabEnabled(2,False); self.tabs.setTabEnabled(3,False)
        try:
            if method=='AHP':
                if self.data.get('ahp') is None: raise ValueError('The AHP Pairwise sheet is missing or incomplete.')
                self.weights,self.weight_steps=calculate_ahp(criteria,self.data['ahp']); self.steps=self.weight_steps; self.weight_source='AHP'
            elif method=='SWARA':
                if set(self.data.get('swara',{}))!=set(criteria): raise ValueError('SWARA sheet needs an ordered row and relative-importance value for every criterion.')
                self.weights,self.weight_steps=calculate_swara(criteria,self.data['swara']); self.steps=self.weight_steps; self.weight_source='SWARA'
            elif method=='BWM':
                cfg=self.data.get('bwm')
                if cfg is None: raise ValueError('In the Criteria sheet, mark exactly one BWM best and one BWM worst criterion, then enter both comparison vectors.')
                self.weights,self.weight_steps=calculate_bwm_weights(criteria,cfg['best_idx'],cfg['worst_idx'],cfg['best_to_others'],cfg['others_to_worst']); self.steps=self.weight_steps; self.weight_source='BWM'
            elif method=='Entropy weights':
                self.weights,self.weight_steps=calculate_entropy_weights(criteria,self.data['matrix'],self.data['directions']); self.steps=self.weight_steps; self.weight_source='Entropy'
            elif method=='CRITIC':
                self.weights,self.weight_steps=calculate_critic_weights(criteria,self.data['matrix'],self.data['directions']); self.steps=self.weight_steps; self.weight_source='CRITIC'
            elif method=='MEREC':
                self.weights,self.weight_steps=calculate_merec_weights(criteria,self.data['matrix'],self.data['directions']); self.steps=self.weight_steps; self.weight_source='MEREC'
            elif method=='Standard deviation':
                self.weights,self.weight_steps=calculate_std_weights(criteria,self.data['matrix'],self.data['directions']); self.steps=self.weight_steps; self.weight_source='Standard deviation'
            elif method=='PSI weights':
                self.weights,self.weight_steps=calculate_psi_weights(criteria,self.data['matrix'],self.data['directions']); self.steps=self.weight_steps; self.weight_source='PSI weights'
            elif method=='ANP':
                if self.data.get('anp') is None: raise ValueError('Add a column-stochastic matrix to the ANP Weighted Supermatrix sheet.')
                self.weights,self.weight_steps=_run_anp(self.data['anp'],criteria); self.steps=self.weight_steps; self.weight_source='ANP limit priorities'
            elif method=='DEMATEL':
                if self.data.get('dematel') is None: raise ValueError('Add a numeric square matrix to the DEMATEL Direct Relations sheet.')
                self.steps=_run_dematel(self.data['dematel'],criteria); self.weights=np.array(self.data['weights'],dtype=float); self.weight_source='Manual / template'
            elif method=='ISM':
                if self.data.get('ism') is None: raise ValueError('Add V/A/X/O expert judgments to the ISM SSIM sheet.')
                self.steps=_run_ism(self.data['ism'],criteria); self.weights=np.array(self.data['weights'],dtype=float); self.weight_source='Manual / template'
            else:
                weights=np.array(self.weights if self.weights is not None else self.data['weights'],dtype=float)
                if method=='MOORA':
                    # Chapter 11 ratio/reference-point formulation does not include criterion weights.
                    self.steps=run_ranking(method,self.data['matrix'],self.data['alternatives'],criteria,self.data['directions'],weights)
                else:self.steps=run_ranking(method,self.data['matrix'],self.data['alternatives'],criteria,self.data['directions'],weights,**({'lambda':self.param_spin.value()} if method in ('WASPAS','CoCoSo') else {'v':self.param_spin.value()} if method=='VIKOR' else {'tau':self.param_spin.value()} if method=='CODAS' else {}))
                rank_steps=self.steps
                self.steps=rank_steps
                self.weight_source=self.weight_source if self.weights is not None else 'Manual / template'
                if self.weights is None:self.weights=weights
            self.step_list.clear()
            for i,step in enumerate(self.steps,1): self.step_list.addItem(f'{i:02d}  {step.title}')
            self.step_list.setCurrentRow(0); self.export_summary.setText(f'Method: {method}\nWeight source: {self.weight_source}\nSteps: {len(self.steps)}\nWeights: '+', '.join(f'{c}={w:.4f}' for c,w in zip(criteria,self.weights)))
            self.calculated_method=method; self.result_status.setText(f'{method} results · {len(self.steps)} steps · weights from {self.weight_source}. Select a step to inspect its input and output.')
            self.audit_code.setPlainText(get_audit_code(method)); self.tabs.setTabEnabled(1,True); self.tabs.setTabEnabled(2,True); self.tabs.setTabEnabled(3,True); self.tabs.setCurrentIndex(1); self.statusBar().showMessage(f'{method} complete: new result replaces the previous calculation.')
        except Exception as e:
            self._clear_results(f'{method} was not calculated. Correct the selected method inputs, then calculate again.')
            QMessageBox.warning(self,'Could not calculate',str(e))
    def show_step(self,row):
        if row<0 or row>=len(self.steps):return
        step=self.steps[row]
        previous=self.steps[row-1].table if row>0 else method_input_preview(self.data,self.calculated_method or self.method_box.currentText())
        to_table(self.previous_table,previous); to_table(self.result_table,step.table)
        self.theory.setHtml(f'<p><b>{step.title}</b> · {step.explanation}</p><p><b>General formula:</b> <code>{step.formula}</code></p><p><b>Source/ref:</b> {step.book_ref}</p><p>Click any result cell below to inspect its value and applicable formula.</p>')
        self.prev.setEnabled(row>0); self.next.setEnabled(row<len(self.steps)-1)

    def show_cell_formula(self,row,col):
        if not self.steps or self.step_list.currentRow()<0:return
        step=self.steps[self.step_list.currentRow()]
        header=self.result_table.horizontalHeaderItem(col).text() if self.result_table.horizontalHeaderItem(col) else f'Column {col+1}'
        row_header=self.result_table.verticalHeaderItem(row).text() if self.result_table.verticalHeaderItem(row) else str(row+1)
        selected=self.result_table.item(row,col).text() if self.result_table.item(row,col) else ''
        source,url=METHOD_LINKS.get(self.calculated_method or self.method_box.currentText(),('Source reference', 'https://doi.org/10.1007/978-981-33-4745-8'))
        self.theory.setHtml(f'<p><b>Selected result:</b> {row_header} · {header} = <b>{selected}</b></p><p><b>Applicable formula:</b><br><code>{step.formula}</code></p><p><b>Calculation step:</b> {step.title}<br>{step.explanation}</p><p><b>Method reference:</b> {step.book_ref}<br><a href="{url}">{source} · DOI/source</a></p>')
    def export_results(self):
        if not self.steps or not self.data: QMessageBox.information(self,'Nothing to export','Calculate a method first.'); return
        p,_=QFileDialog.getSaveFileName(self,'Export method steps','MCDM_Step_by_Step_Results.xlsx','Excel workbook (*.xlsx)')
        if not p:return
        try:
            write_results(p,self.method_box.currentText(),{**self.data,'weight_source':self.weight_source},self.weights,self.steps,{'parameter':self.param_spin.value() if self.param_spin.isVisible() else None})
            QMessageBox.information(self,'Export complete',f'All method steps were exported to:\n{p}')
        except Exception as e: QMessageBox.critical(self,'Export failed',str(e))
    def copy_audit_code(self):
        QApplication.clipboard().setText(self.audit_code.toPlainText()); self.statusBar().showMessage('Calculation source copied to clipboard.')
    def save_audit_code(self):
        method=self.method_box.currentText().replace(' ','_').replace('/','_'); p,_=QFileDialog.getSaveFileName(self,'Export Python audit source',f'MCDM_{method}_audit.py','Python source (*.py);;Text file (*.txt)')
        if not p:return
        try: Path(p).write_text(self.audit_code.toPlainText(),encoding='utf-8'); self.statusBar().showMessage(f'Python audit source saved: {p}')
        except Exception as e: QMessageBox.critical(self,'Could not save audit source',str(e))

def main():
    app=QApplication(sys.argv); app.setStyle('Fusion'); w=MainWindow(); w.showMaximized(); sys.exit(app.exec())
if __name__=='__main__': main()
