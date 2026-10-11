from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QTabWidget,QLabel,QPushButton,QFileDialog,QMessageBox,QComboBox,QSplitter,QListWidget,QListWidgetItem,QTextBrowser,QTableWidget,QTableWidgetItem,QAbstractItemView,QGroupBox,QFormLayout,QDoubleSpinBox,QStatusBar,QPlainTextEdit)
from core.excel_io import TEMPLATE,DEMO,load_input,generate_template,write_results
from core.methods import (calculate_ahp,calculate_swara,calculate_entropy_weights,calculate_critic_weights,
                          calculate_merec_weights,calculate_std_weights,calculate_bwm_weights,
                          calculate_psi_weights,
                          run_ranking,_run_dematel,_run_ism,_run_anp,get_audit_code)

METHOD_GROUPS={
 'Criterion Weights':['AHP','ANP','SWARA','BWM','Entropy weights','CRITIC','MEREC','Standard deviation','PSI weights'],
 'Alternative Ranking':['SAW','TOPSIS','MOORA','MULTIMOORA','COPRAS-G','ARAS','WASPAS','VIKOR','ELECTRE I','PROMETHEE II','CoCoSo','EDAS','MARCOS','CODAS','MAIRCA','MABAC','GRA'],
 'Causal / Structural Analysis':['DEMATEL','ISM']
}
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
}

STYLE='''QMainWindow,QWidget{background:#f4f7fb;color:#1e293b;font-family:"Segoe UI";font-size:10pt} QGroupBox{background:white;border:1px solid #d9e2ee;border-radius:10px;margin-top:12px;padding:12px;font-weight:600} QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 5px;color:#174c69} QPushButton{background:#e8eef5;border:1px solid #d4deea;border-radius:7px;padding:8px 12px;font-weight:600} QPushButton:hover{background:#dce8f4} QPushButton[primary="true"]{background:#176b87;color:white;border-color:#176b87} QPushButton[primary="true"]:hover{background:#12566d} QComboBox,QDoubleSpinBox{background:white;border:1px solid #cad5e2;border-radius:6px;padding:6px} QListWidget,QTextBrowser,QTableWidget{background:white;border:1px solid #d9e2ee;border-radius:8px} QListWidget::item{padding:8px;border-radius:5px} QListWidget::item:selected{background:#dceef5;color:#134e63} QTabWidget::pane{border:1px solid #d9e2ee;border-radius:8px;background:white} QTabBar::tab{padding:9px 16px;background:#e8eef5;border-top-left-radius:6px;border-top-right-radius:6px;margin-right:4px} QTabBar::tab:selected{background:#176b87;color:white}'''

def runtime_root():
    if getattr(sys,'frozen',False): return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def to_table(widget, df):
    if not isinstance(df.index, pd.RangeIndex):
        label = df.index.name or 'Alternative / Criterion'
        df = df.rename_axis(label).reset_index()
    widget.clear(); widget.setRowCount(len(df)); widget.setColumnCount(len(df.columns)); widget.setHorizontalHeaderLabels([str(x) for x in df.columns])
    for i,row in enumerate(df.itertuples(index=False,name=None)):
        for j,val in enumerate(row):
            if pd.isna(val): val=''
            item=QTableWidgetItem(f'{val:.6g}' if isinstance(val,(float,int)) else str(val)); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable); widget.setItem(i,j,item)
    widget.resizeColumnsToContents(); widget.horizontalHeader().setStretchLastSection(True); widget.setAlternatingRowColors(True)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('MCDMStudio | Step-by-step decision methods'); self.resize(1440,900); self.setMinimumSize(1120,720)
        self.data=None; self.steps=[]; self.weight_steps=[]; self.weights=None; self.weight_source='Manual / template'; self.export_path=None
        self.tabs=QTabWidget(); self.setCentralWidget(self.tabs); self._build_import_tab(); self._build_practice_tab(); self._build_export_tab(); self.setStatusBar(QStatusBar()); self.statusBar().showMessage('Load an Excel template or demo data to begin.')
        self.setStyleSheet(STYLE)
        self.load_demo()

    def _build_import_tab(self):
        page=QWidget(); root=QVBoxLayout(page); root.setContentsMargins(22,20,22,20); root.setSpacing(14)
        title=QLabel('Import numerical decision data'); title.setStyleSheet('font-size:20pt;font-weight:700;color:#123f58'); root.addWidget(title)
        sub=QLabel('Use one workbook: alternatives × numeric criteria, benefit/cost directions, criterion weights, and optional AHP/SWARA inputs.'); sub.setWordWrap(True); sub.setStyleSheet('color:#526579'); root.addWidget(sub)
        actions=QHBoxLayout(); self.file_label=QLabel('No workbook selected'); self.file_label.setStyleSheet('font-weight:600;color:#174c69')
        b=QPushButton('Import Excel…'); b.setProperty('primary',True); b.clicked.connect(self.open_excel); actions.addWidget(b)
        b=QPushButton('Download blank template…'); b.clicked.connect(self.save_template); actions.addWidget(b)
        b=QPushButton('Load demo workbook'); b.clicked.connect(self.load_demo); actions.addWidget(b); actions.addStretch(); actions.addWidget(self.file_label); root.addLayout(actions)
        self.validation=QLabel(''); self.validation.setWordWrap(True); root.addWidget(self.validation)
        group=QGroupBox('Decision Matrix preview'); gl=QVBoxLayout(group); self.input_table=QTableWidget(); self.input_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); gl.addWidget(self.input_table); root.addWidget(group,1)
        note=QLabel('Input template includes Instructions, Decision Matrix, Criteria, AHP Pairwise, and SWARA sheets. Yellow cells are input areas.'); note.setWordWrap(True); note.setStyleSheet('color:#617488'); root.addWidget(note)
        self.tabs.addTab(page,'1  Import & Preview')

    def _build_practice_tab(self):
        page=QWidget(); root=QVBoxLayout(page); root.setContentsMargins(16,14,16,14); root.setSpacing(10)
        title=QLabel('Guided calculation'); title.setStyleSheet('font-size:19pt;font-weight:700;color:#123f58'); root.addWidget(title)
        ctl=QHBoxLayout(); ctl.addWidget(QLabel('Method group'))
        self.group_box=QComboBox(); self.group_box.addItems(METHOD_GROUPS); self.group_box.currentTextChanged.connect(self._group_changed); ctl.addWidget(self.group_box)
        ctl.addWidget(QLabel('Method'))
        self.method_box=QComboBox(); ctl.addWidget(self.method_box)
        self.param_label=QLabel('λ'); ctl.addWidget(self.param_label)
        self.param_spin=QDoubleSpinBox(); self.param_spin.setRange(0,1); self.param_spin.setSingleStep(.1); self.param_spin.setValue(.5); ctl.addWidget(self.param_spin)
        self.run_button=QPushButton('Calculate method'); self.run_button.setProperty('primary',True); self.run_button.clicked.connect(self.calculate); ctl.addWidget(self.run_button); ctl.addStretch(); root.addLayout(ctl)
        self.method_box.currentTextChanged.connect(self._method_changed); self._group_changed(self.group_box.currentText())
        split=QSplitter(Qt.Orientation.Horizontal); root.addWidget(split,1)
        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,4,0); ll.addWidget(QLabel('Steps'))
        self.step_list=QListWidget(); self.step_list.currentRowChanged.connect(self.show_step); ll.addWidget(self.step_list,1)
        nav=QHBoxLayout(); self.prev=QPushButton('← Previous'); self.next=QPushButton('Next →'); self.prev.clicked.connect(lambda:self.step_list.setCurrentRow(max(0,self.step_list.currentRow()-1))); self.next.clicked.connect(lambda:self.step_list.setCurrentRow(min(self.step_list.count()-1,self.step_list.currentRow()+1))); nav.addWidget(self.prev); nav.addWidget(self.next); ll.addLayout(nav); split.addWidget(left)
        self.detail_tabs=QTabWidget()
        theory=QWidget(); tl=QVBoxLayout(theory); self.theory=QTextBrowser(); self.theory.setOpenExternalLinks(False); tl.addWidget(self.theory); self.detail_tabs.addTab(theory,'Formula & explanation')
        audit=QWidget(); al=QVBoxLayout(audit); audit_actions=QHBoxLayout(); self.copy_audit=QPushButton('Copy Python'); self.copy_audit.clicked.connect(self.copy_audit_code); self.save_audit=QPushButton('Export .py…'); self.save_audit.clicked.connect(self.save_audit_code); audit_actions.addWidget(QLabel('Exact calculation logic from MCDMStudio/core/methods.py')); audit_actions.addStretch(); audit_actions.addWidget(self.copy_audit); audit_actions.addWidget(self.save_audit); al.addLayout(audit_actions); self.audit_code=QPlainTextEdit(); self.audit_code.setReadOnly(True); self.audit_code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap); self.audit_code.setStyleSheet('font-family:Consolas,monospace;font-size:9pt;background:#10202d;color:#e2edf5'); al.addWidget(self.audit_code,1); self.detail_tabs.addTab(audit,'Python audit')
        split.addWidget(self.detail_tabs)
        demo=QGroupBox('Practice | calculated values'); dl=QVBoxLayout(demo); self.result_table=QTableWidget(); self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); dl.addWidget(self.result_table); split.addWidget(demo)
        split.setSizes([205,390,740]); self.tabs.addTab(page,'2  Weight, Rank & Structure')

    def _build_export_tab(self):
        page=QWidget(); root=QVBoxLayout(page); root.setContentsMargins(22,20,22,20); root.setSpacing(12)
        title=QLabel('Export the full calculation trail'); title.setStyleSheet('font-size:20pt;font-weight:700;color:#123f58'); root.addWidget(title)
        desc=QLabel('Export includes input matrix, active criterion weights, a separate worksheet for every method step, its displayed formula, and the book page reference.'); desc.setWordWrap(True); root.addWidget(desc)
        self.export_summary=QLabel('Run a weighting or ranking method first.'); self.export_summary.setWordWrap(True); root.addWidget(self.export_summary)
        b=QPushButton('Export all steps to Excel…'); b.setProperty('primary',True); b.clicked.connect(self.export_results); root.addWidget(b,0,Qt.AlignmentFlag.AlignLeft); root.addStretch(); self.tabs.addTab(page,'3  Export')

    def _group_changed(self, group):
        if not hasattr(self,'method_box'): return
        self.method_box.blockSignals(True); self.method_box.clear(); self.method_box.addItems(METHOD_GROUPS.get(group,[])); self.method_box.blockSignals(False); self._method_changed(self.method_box.currentText())
    def _method_changed(self, method):
        params={'WASPAS':('λ',.5),'VIKOR':('v',.5),'CoCoSo':('λ',.5),'CODAS':('τ',.02)}
        visible=method in params; label,default=params.get(method,('λ',.5)); self.param_label.setVisible(visible); self.param_label.setText(label); self.param_spin.setVisible(visible); self.param_spin.setDecimals(3); self.param_spin.setSingleStep(.01 if method=='CODAS' else .1); self.param_spin.setValue(default)
        if hasattr(self,'theory'):
            ref={'AHP':'Chapter 3, §§3.3–3.4','ANP':'Chapter 4, §4.3','SWARA':'Chapter 16, §16.2','Entropy weights':'Shannon entropy objective weighting','CRITIC':'Diakoulaki et al. (1995)','MEREC':'Keshavarz-Ghorabaee et al. (2021)','Standard deviation':'Objective weighting baseline','PSI weights':'Maniya & Bhatt (2010)','BWM':'Rezaei (2015)','SAW':'Chapter 2, §§2.1–2.2','TOPSIS':'Chapter 5, §5.2','VIKOR':'Chapter 8, §8.2','MOORA':'Chapter 11, §11.2','MULTIMOORA':'Chapter 11, §11.2 and MULTIMOORA discussion','COPRAS-G':'Chapter 13, §13.2','ARAS':'Chapter 14, §14.2','WASPAS':'Chapter 15, §15.2','ELECTRE I':'Chapter 6, §6.2','PROMETHEE II':'Chapter 7, §7.2','CoCoSo':'Yazdani et al. (2019)','EDAS':'Keshavarz-Ghorabaee et al. (2015)','MARCOS':'Stević et al. (2020)','CODAS':'Ghorabaee et al. (2016)','MAIRCA':'Pamučar et al.','MABAC':'Pamučar & Ćirović (2015)','GRA':'Deng (1989), grey relational analysis','DEMATEL':'Chapter 9, §9.2','ISM':'Chapter 18, §§18.2–18.3'}.get(method,'')
            note=BOOK_NOTES.get(method,'')
            self.theory.setHtml(f'<h2>{method}</h2><p><b>Source:</b> J. J. Thakkar, <i>Multi-Criteria Decision Making</i>, 2021, {ref}.</p><p>Select <b>Calculate method</b> to inspect formulas and intermediate matrices one step at a time.</p>' + (f'<p style="color:#9a3412"><b>Reading note:</b> {note}</p>' if note else ''))
            self.audit_code.setPlainText(get_audit_code(method))

    def _set_input(self,data):
        self.data=data; self.weights=None; self.steps=[]; self.weight_steps=[]; self.weight_source='Manual / template';
        self.file_label.setText(Path(data['path']).name)
        to_table(self.input_table,data['preview'])
        warning=[]
        if any(x not in ('Benefit','Cost') for x in data['directions']): warning.append('Direction values must be Benefit or Cost.')
        if len(data['alternatives'])<2: warning.append('At least two alternatives are needed for ranking.')
        self.validation.setText(('⚠ '+ ' '.join(warning)) if warning else f'Workbook validated: {len(data["alternatives"])} alternatives, {len(data["criteria"])} criteria. Criteria directions: '+', '.join(f'{c}={d}' for c,d in zip(data['criteria'],data['directions'])))
        self.validation.setStyleSheet('color:#b45309;font-weight:600' if warning else 'color:#16734a;font-weight:600')
        self.tabs.setCurrentIndex(0); self.statusBar().showMessage('Input loaded and previewed.')

    def open_excel(self):
        path,_=QFileDialog.getOpenFileName(self,'Import MCDM Excel workbook','','Excel workbook (*.xlsx *.xlsm)')
        if not path:return
        try:self._set_input(load_input(path))
        except Exception as e: QMessageBox.warning(self,'Workbook could not be loaded',str(e))
    def load_demo(self):
        try:
            p=DEMO if DEMO.exists() else runtime_root()/'Templates'/'Demo Data'/'MCDMStudio'/'MCDM_Demo_Data.xlsx'
            self._set_input(load_input(p))
        except Exception as e: self.validation.setText(f'Demo workbook is not installed yet: {e}')
    def save_template(self):
        p,_=QFileDialog.getSaveFileName(self,'Save blank MCDM template','MCDM_Input_Template.xlsx','Excel workbook (*.xlsx)')
        if not p:return
        try:generate_template(p,False); QMessageBox.information(self,'Template ready',f'Blank template saved to:\n{p}')
        except Exception as e: QMessageBox.critical(self,'Template error',str(e))
    def calculate(self):
        if not self.data: QMessageBox.information(self,'Import data first','Import the MCDMStudio template or load demo data.'); return
        method=self.method_box.currentText(); criteria=self.data['criteria']
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
                self.steps=[*self.weight_steps,*rank_steps] if self.weight_steps else rank_steps
                self.weight_source=self.weight_source if self.weights is not None else 'Manual / template'
                if self.weights is None:self.weights=weights
            self.step_list.clear()
            for i,step in enumerate(self.steps,1): self.step_list.addItem(f'{i:02d}  {step.title}')
            self.step_list.setCurrentRow(0); self.export_summary.setText(f'Method: {method}\nWeight source: {self.weight_source}\nSteps: {len(self.steps)}\nWeights: '+', '.join(f'{c}={w:.4f}' for c,w in zip(criteria,self.weights)))
            self.tabs.setCurrentIndex(1); self.statusBar().showMessage(f'{method} complete: {len(self.steps)} intermediate steps ready.')
        except Exception as e: QMessageBox.warning(self,'Could not calculate',str(e))
    def show_step(self,row):
        if row<0 or row>=len(self.steps):return
        step=self.steps[row]; note=BOOK_NOTES.get(self.method_box.currentText(),'')
        self.theory.setHtml(f'<h2>{step.title}</h2><p><b>Formula</b></p><div style="background:#eff6fb;padding:12px;border-left:4px solid #176b87;font-family:Consolas;font-size:12pt">{step.formula}</div><p>{step.explanation}</p><p><b>Book location:</b> {step.book_ref}</p>'+(f'<p style="color:#9a3412"><b>Reading note:</b> {note}</p>' if note else ''))
        to_table(self.result_table,step.table)
        self.prev.setEnabled(row>0); self.next.setEnabled(row<len(self.steps)-1)
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
    app=QApplication(sys.argv); app.setStyle('Fusion'); w=MainWindow(); w.show(); sys.exit(app.exec())
if __name__=='__main__': main()
