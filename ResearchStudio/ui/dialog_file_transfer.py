from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPlainTextEdit,QPushButton,QListWidget,QFileDialog,QMessageBox,QLabel,QGroupBox)
from integrations.config_store import load_profiles
from integrations.email_sender import SMTPSender
from integrations.drive_repository import GoogleDriveRepository
from integrations.snapshot_package import create_snapshot_package
from ui.friendly_message import show_success,show_error

class _FileMixin:
    def _add_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Select files to send/upload')
        for p in paths:
            if p and not any(self.files.item(i).text()==p for i in range(self.files.count())): self.files.addItem(p)
    def _add_project(self):
        p=getattr(self.project_db,'db_path',None) if self.project_db else None
        if not p: QMessageBox.warning(self,'No Project','Open a project first.'); return
        if not any(self.files.item(i).text()==p for i in range(self.files.count())): self.files.addItem(p)
    def _remove(self):
        for i in sorted([x.row() for x in self.files.selectedIndexes()],reverse=True): self.files.takeItem(i)
    def _paths(self): return [self.files.item(i).text() for i in range(self.files.count())]
    def _file_box(self):
        box=QGroupBox('Files'); v=QVBoxLayout(box); self.files=QListWidget(); v.addWidget(self.files)
        h=QHBoxLayout();
        for label,fn in [('Add Files...',self._add_files),('Add Current .mcdm',self._add_project),('Remove',self._remove)]:
            b=QPushButton(label); b.clicked.connect(fn); h.addWidget(b)
        h.addStretch(); v.addLayout(h); return box

class SendFilesEmailDialog(QDialog,_FileMixin):
    def __init__(self,parent=None,project_db=None):
        super().__init__(parent); self.project_db=project_db; self.setWindowTitle('Send Files by Email'); self.resize(760,620)
        root=QVBoxLayout(self); note=QLabel('Uses the SMTP profile from Integrations → Connection Manager. If a project is open, Send Email attaches the correct current snapshot package for that project type: MCDM = JSON + 2 Excel files; Quantitative = JSON + 1 Excel file; Qualitative = JSON + 1 Excel file. You may add extra files below.'); note.setWordWrap(True); root.addWidget(note)
        f=QFormLayout(); self.to=QLineEdit(); self.cc=QLineEdit(); self.bcc=QLineEdit(); self.subject=QLineEdit('Research Studio files'); self.body=QPlainTextEdit('Please find the attached Research Studio files.')
        f.addRow('To *:',self.to); f.addRow('Cc:',self.cc); f.addRow('Bcc:',self.bcc); f.addRow('Subject:',self.subject); f.addRow('Message:',self.body); root.addLayout(f); root.addWidget(self._file_box())
        h=QHBoxLayout(); test=QPushButton('Test SMTP'); send=QPushButton('Send Email'); send.setProperty('primary',True); test.clicked.connect(self._test); send.clicked.connect(self._send); h.addStretch(); h.addWidget(test); h.addWidget(send); root.addLayout(h)
    def _sender(self): return SMTPSender(load_profiles().get('smtp',{}))
    def _test(self):
        try:
            r=self._sender().test();cfg=load_profiles().get('smtp',{});show_success(self,'SMTP Connection Successful','SMTP connection and authentication succeeded.',[('Server',f"{cfg.get('host')}:{cfg.get('port')}"),('User',cfg.get('user')),('From',cfg.get('from_email'))],str(r))
        except Exception as e: show_error(self,'SMTP Failed','Could not connect or authenticate to the SMTP server.',e,'Verify the SMTP settings and credentials.')
    def _send(self):
        try:
            paths=self._paths()
            if self.project_db:
                package=create_snapshot_package(self.project_db)
                paths=package['files']+paths
            if not paths: raise RuntimeError('Open a project or add at least one file.')
            # de-duplicate while preserving order
            paths=list(dict.fromkeys(paths))
            r=self._sender().send(self.to.text(),self.subject.text(),self.body.toPlainText(),attachments=paths,cc=self.cc.text(),bcc=self.bcc.text())
            show_success(self,'Email Sent','Email was sent successfully.',[('To',self.to.text()),('Cc',self.cc.text()),('Bcc',self.bcc.text()),('Subject',self.subject.text()),('Recipients',r.get('sent')),('Attachments',len(r.get('attachments',[]))),('Files','\n'.join(Path(x).name for x in paths))])
        except Exception as e: show_error(self,'Send Failed','The email could not be sent.',e,'Verify SMTP settings, recipients and attachments.')

class UploadDriveDialog(QDialog,_FileMixin):
    def __init__(self,parent=None,project_db=None):
        super().__init__(parent); self.project_db=project_db; self.setWindowTitle('Upload Files to Google Drive'); self.resize(760,500)
        root=QVBoxLayout(self); note=QLabel('Uses Service Account JSON + Folder ID from Connection Manager. IMPORTANT: share the target Google Drive folder with the service-account email.'); note.setWordWrap(True); root.addWidget(note); root.addWidget(self._file_box())
        h=QHBoxLayout(); test=QPushButton('Test Drive'); upload=QPushButton('Upload Files'); upload.setProperty('primary',True); test.clicked.connect(self._test); upload.clicked.connect(self._upload); h.addStretch(); h.addWidget(test); h.addWidget(upload); root.addLayout(h)
    def _repo(self): return GoogleDriveRepository(load_profiles().get('drive',{}))
    def _test(self):
        try: show_success(self,'Google Drive Connection Successful','Google Drive connection test passed.',[('Result',str(self._repo().test()))])
        except Exception as e: show_error(self,'Drive Failed','Google Drive connection test failed.',e)
    def _upload(self):
        try:
            paths=self._paths(); repo=self._repo(); results=[]
            if self.project_db:
                r=repo.sync(self.project_db); results.extend(r['files'])
            if paths: results.extend(repo.upload_files(paths))
            if not results: raise RuntimeError('Open a project or add at least one file.')
            lines=[f"{x.get('name')} → {x.get('id')}" for x in results]
            show_success(self,'Upload Complete','Files were uploaded successfully.',[('Files',len(results)),('Destination','Google Drive')],'\n'.join(lines))
        except Exception as e: show_error(self,'Upload Failed','Files could not be uploaded.',e)
