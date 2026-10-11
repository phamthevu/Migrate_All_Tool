from pathlib import Path
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QFileDialog,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox,QGroupBox,QCheckBox
from core.legacy_data_import import generate_import_template,validate_import_file,import_file
from ui.friendly_message import show_success,show_error
from integrations.backup_manager import backup_project

class TabLegacyImport(QWidget):
    def __init__(self):
        super().__init__(); self.db=None; self.current_file=None; self.current_files=[]; self.check=None
        root=QVBoxLayout(self); title=QLabel('Legacy Data Import'); title.setObjectName('pageTitle'); root.addWidget(title)
        sub=QLabel('Convert historical Excel data into the currently open .mcdm project, then use the existing Sync destinations. The project research configuration is never changed.'); sub.setWordWrap(True); sub.setObjectName('muted'); root.addWidget(sub)
        g=QGroupBox('1. Template'); a=QHBoxLayout(g); self.gen=QPushButton('Download Import Template...'); self.gen.setProperty('primary',True); self.gen.clicked.connect(self.generate); a.addWidget(self.gen); a.addStretch(); root.addWidget(g)
        g2=QGroupBox('2. Select & Validate Data File'); b=QHBoxLayout(g2); self.browse=QPushButton('Browse Excel File(s)...'); self.browse.setProperty('accent',True); self.browse.clicked.connect(self.browse_file); self.folder=QPushButton('Scan Folder...'); self.folder.clicked.connect(self.browse_folder); self.autodetect=QCheckBox('Auto-detect schema from Schema sheet / compatible headers'); self.autodetect.setToolTip('Off: strict project-config schema. On: use the workbook Schema sheet and safe header aliases where possible.'); self.validate=QPushButton('Validate & Preview'); self.validate.clicked.connect(self.validate_file); b.addWidget(self.browse); b.addWidget(self.folder); b.addWidget(self.autodetect); b.addWidget(self.validate); b.addStretch(); root.addWidget(g2)
        self.state=QLabel('No file selected.'); root.addWidget(self.state)
        self.preview=QTableWidget(); self.preview.setAlternatingRowColors(True); root.addWidget(self.preview,1)
        self.details=QPlainTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(110); root.addWidget(self.details)
        row=QHBoxLayout(); row.addStretch(); self.imp=QPushButton('IMPORT INTO PROJECT'); self.imp.setProperty('success',True); self.imp.setEnabled(False); self.imp.clicked.connect(self.do_import); row.addWidget(self.imp); root.addLayout(row)
    def load_project(self,db): self.db=db; self.current_file=None; self.current_files=[]; self.check=None; self.imp.setEnabled(False); self.state.setText('Ready. Download the template for this project before preparing historical data.'); self.preview.clear(); self.preview.setRowCount(0); self.preview.setColumnCount(0); self.details.clear()
    def clear_project(self): self.db=None; self.imp.setEnabled(False)
    def generate(self):
        if not self.db:return
        meta=self.db.get_meta() or {}; key=meta.get('storage_key','project'); path,_=QFileDialog.getSaveFileName(self,'Save Import Template',str(Path.home()/f'{key}_LEGACY_IMPORT_TEMPLATE.xlsx'),'Excel (*.xlsx)')
        if not path:return
        try: generate_import_template(self.db,path); show_success(self,'Template Created','Legacy data import template was created successfully.',[('Project',meta.get('project_name','')),('File',path),('Next step','Fill the Data sheet without renaming headers, then return here to validate it.')])
        except Exception as e: show_error(self,'Template Failed','Could not create the import template.',str(e))
    def browse_file(self):
        ps,_=QFileDialog.getOpenFileNames(self,'Select Historical Data File(s)',str(Path.home()),'Excel (*.xlsx)')
        if ps:self.current_files=ps; self.current_file=ps[0]; self.state.setText(f'Selected: {len(ps)} file(s)'); self.imp.setEnabled(False); self.check=None

    def browse_folder(self):
        d=QFileDialog.getExistingDirectory(self,'Select Folder Containing Historical Excel Files',str(Path.home()))
        if d:
            self.current_files=[str(x) for x in sorted(Path(d).rglob('*.xlsx')) if not x.name.startswith('~$')]
            self.current_file=self.current_files[0] if self.current_files else None
            self.state.setText(f'Found: {len(self.current_files)} Excel file(s)')
            self.imp.setEnabled(False); self.check=None
            if not self.current_files: QMessageBox.warning(self,'No Excel Files','No .xlsx files were found in the selected folder or its subfolders.')

    def validate_file(self):
        files=self.current_files or ([self.current_file] if self.current_file else [])
        if not self.db or not files: QMessageBox.warning(self,'File Required','Select one or more Excel files first.'); return
        try:
            checks=[(p,validate_import_file(self.db,p,autodetect=self.autodetect.isChecked())) for p in files]; bad=[(p,c) for p,c in checks if not c['valid']]
            c=checks[0][1]; self.check={'valid':not bad,'files':checks,'rows':sum(len(x['rows']) for _,x in checks)}; self.preview.clear(); h=c['headers']; rows=c['preview']; self.preview.setColumnCount(len(h)); self.preview.setHorizontalHeaderLabels(h); self.preview.setRowCount(len(rows))
            for i,r in enumerate(rows):
                for j,k in enumerate(h): self.preview.setItem(i,j,QTableWidgetItem('' if r.get(k) is None else str(r.get(k))))
            self.preview.resizeColumnsToContents(); msgs=[]
            for p,x in checks:
                if x['errors']: msgs += [f'ERROR [{Path(p).name}]: '+e for e in x['errors']]
            if not bad: msgs.append(f"VALID: {len(checks)} file(s), {self.check['rows']} source row(s) ready for import. Preview shows the first file.")
            self.details.setPlainText('\n'.join(msgs)); self.imp.setEnabled(not bad and bool(c.get('preview'))); self.state.setText(('VALID' if not bad else 'INVALID')+f' — {len(checks)} file(s)')
        except Exception as e: self.imp.setEnabled(False); self.details.setPlainText('ERROR: '+str(e)); show_error(self,'Validation Failed','The selected file does not match the import template.',str(e))
    def do_import(self):
        if not self.check or not self.check.get('valid'):return
        ans=QMessageBox.question(self,'Confirm Legacy Import',f"Import {self.check['rows']} source row(s) from {len(self.check['files'])} file(s)?\n\nExisting respondents with the same Respondent_ID may have their response updated. A safety backup will be created first.")
        if ans!=QMessageBox.StandardButton.Yes:return
        try:
            backup_project(self.db,'legacy_import')
            total_r=total_rows=0
            for p,_ in self.check['files']:
                res=import_file(self.db,p,autodetect=self.autodetect.isChecked()); total_r+=res['responses']; total_rows+=res['rows']
            self.imp.setEnabled(False); show_success(self,'Import Completed','Historical data was converted into project responses successfully.',[('Files',str(len(self.check['files']))),('Responses processed',str(total_r)),('Source rows',str(total_rows)),('Next step','Review Data Manager, then use Data Sync Manager to send the project to configured destinations.')])
            self.state.setText(f"IMPORTED — {len(self.check['files'])} file(s), {total_r} response(s) processed")
        except Exception as e: show_error(self,'Import Failed','No further import steps were completed.',str(e))
