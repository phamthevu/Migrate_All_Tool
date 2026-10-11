from PyQt6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QCheckBox,QSpinBox,QComboBox,QPushButton,QHBoxLayout,QLabel,QMessageBox,QLineEdit
from integrations.config_store import load_profiles,save_profiles
from integrations.instance_identity import get_identity,save_identity
class AutoSnapshotDialog(QDialog):
 def __init__(self,parent=None):
  super().__init__(parent);self.setWindowTitle('V5.6 Snapshot & Instance Settings');self.resize(560,410);r=QVBoxLayout(self);f=QFormLayout();r.addLayout(f);i=get_identity()
  self.owner=QLineEdit(i.get('owner_name',''));self.name=QLineEdit(i.get('instance_name',''));iid=QLineEdit(i['instance_id']);iid.setReadOnly(True);f.addRow('Owner / Operator:',self.owner);f.addRow('Instance Name:',self.name);f.addRow('Instance ID:',iid)
  self.enabled=QCheckBox('Enable automatic snapshot');f.addRow(self.enabled);self.minutes=QSpinBox();self.minutes.setRange(10,43200);self.minutes.setSuffix(' minutes');f.addRow('Every:',self.minutes);self.dest=QComboBox();self.dest.addItems(['postgres','sqlserver','mysql']);f.addRow('Database destination:',self.dest)
  self.mode=QComboBox();self.mode.addItem('OVERWRITE current staging (Default)','overwrite');self.mode.addItem('APPEND snapshots (History / more rows)','append');f.addRow('Sync mode:',self.mode)
  n=QLabel('Range: 10 minutes to 30 days. OVERWRITE replaces staging rows only for the current project + this installation. APPEND keeps each full snapshot and may create many database rows. No deduplication or SCD2 is performed by Research Studio. Auto sync runs only while Research Studio is open.');n.setWordWrap(True);r.addWidget(n)
  p=load_profiles().get('auto_snapshot',{});self.enabled.setChecked(str(p.get('enabled','false')).lower()=='true');self.minutes.setValue(max(10,min(43200,int(p.get('interval_minutes') or 30))));self.dest.setCurrentText(p.get('destination') or 'postgres');idx=self.mode.findData(p.get('sync_mode') or 'overwrite');self.mode.setCurrentIndex(max(0,idx))
  h=QHBoxLayout();h.addStretch();b=QPushButton('Save');b.clicked.connect(self.save);h.addWidget(b);r.addLayout(h)
 def save(self):
  if self.mode.currentData()=='append':
   ans=QMessageBox.warning(self,'Append Mode Warning','APPEND keeps every full snapshot. With frequent auto sync, the database can grow quickly. Continue with APPEND?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
   if ans!=QMessageBox.StandardButton.Yes:return
  save_identity(self.name.text(),self.owner.text());save_profiles({'auto_snapshot':{'enabled':str(self.enabled.isChecked()).lower(),'interval_minutes':str(self.minutes.value()),'destination':self.dest.currentText(),'sync_mode':self.mode.currentData()}});QMessageBox.information(self,'Saved','Instance identity and auto sync settings saved. Restart Research Studio to apply a changed timer interval.');self.accept()
