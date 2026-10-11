from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox,QLabel,QTabWidget,QWidget,QGroupBox
from integrations.sync_manager import DataSyncManager
from integrations.config_store import load_profiles
from integrations.postgres_repository import PostgreSQLRepository
from integrations.s3_repository import S3Repository
from integrations.storage_identity import table_names
from ui.friendly_message import show_success,show_error

class DataSyncManagerDialog(QDialog):
 def __init__(self,parent=None,project_db=None):
  super().__init__(parent);self.project_db=project_db;self.setWindowTitle('V6 Data Sync Manager');self.resize(1050,680)
  root=QVBoxLayout(self);m=project_db.get_meta() or {};key=m.get('storage_key') or m.get('project_id');t=table_names(key)
  identity=QGroupBox('Project Storage Identity');il=QVBoxLayout(identity)
  il.addWidget(QLabel(f"Project: {m.get('project_name','')}    |    Project ID: {m.get('project_id','')}"))
  il.addWidget(QLabel(f"Storage Key / Table Prefix: {key}"))
  il.addWidget(QLabel(f"Tables: {t['runs']}   |   {t['responses']}   |   {t['values']}"));root.addWidget(identity)
  self.target=QLabel();self.target.setWordWrap(True);root.addWidget(self.target)
  self.tabs=QTabWidget();root.addWidget(self.tabs)
  self.status_table=QTableWidget(0,7);self.status_table.setHorizontalHeaderLabels(['Destination','Status','Last Sync','Last Attempt','Records','Retries','Last Error']);self.status_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
  sw=QWidget();sl=QVBoxLayout(sw);sl.addWidget(self.status_table);self.tabs.addTab(sw,'Status')
  self.hist_table=QTableWidget(0,7);self.hist_table.setHorizontalHeaderLabels(['ID','Destination','Started','Finished','Status','Records','Error']);self.hist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
  hw=QWidget();hl=QVBoxLayout(hw);hl.addWidget(self.hist_table);self.tabs.addTab(hw,'Sync History')
  row=QHBoxLayout()
  for label,fn in [('Refresh Status',self.refresh),('Sync PostgreSQL',lambda:self.sync_one('postgres')),('Sync S3',lambda:self.sync_one('s3')),('Push Power BI',lambda:self.sync_one('powerbi')),('Retry Failed',self.retry),('Sync All',self.sync_all),('Force Sync All',lambda:self.sync_all(True))]:
   b=QPushButton(label);b.clicked.connect(fn);row.addWidget(b)
  root.addLayout(row);self.refresh()
 def mgr(self):return DataSyncManager(self.project_db)
 def _target_status(self):
  p=load_profiles();parts=[]
  try:
   st=PostgreSQLRepository(p['postgres']).status(self.project_db);items='; '.join(f"{x['name']} = {'EXISTS' if x['exists'] else 'NOT CREATED'}" for x in st['tables'].values());reg=st.get('registry'); rev=(f" | Registry revision DB={reg['revision']} / Local={st.get('local_revision')}" if reg else ' | Registry: NOT REGISTERED'); parts.append(f"DATABASE → {p['postgres'].get('database')} / schema {st['schema']} | {items}{rev}")
  except Exception as e:parts.append(f'DATABASE → status unavailable: {e}')
  try:
   st=S3Repository(p['s3']).status(self.project_db);parts.append(f"S3 → s3://{st['bucket']}/{st['prefix']}/ = {'EXISTS' if st['exists'] else 'NOT CREATED'}")
  except Exception as e:parts.append(f'S3 → status unavailable: {e}')
  self.target.setText('\n'.join(parts))
 def refresh(self):
  try:
   self._target_status();m=self.mgr();rows=m.status();self.status_table.setRowCount(len(rows))
   for i,r in enumerate(rows):
    vals=[r['destination'],r['status'],r.get('last_sync_at') or '',r.get('last_attempt_at') or '',r.get('records',0),r.get('retry_count',0),r.get('last_error') or '']
    for j,v in enumerate(vals):self.status_table.setItem(i,j,QTableWidgetItem(str(v)))
   hist=m.history();self.hist_table.setRowCount(len(hist))
   for i,r in enumerate(hist):
    vals=[r['id'],r['destination'],r['started_at'],r.get('finished_at') or '',r['status'],r.get('records',0),r.get('error') or '']
    for j,v in enumerate(vals):self.hist_table.setItem(i,j,QTableWidgetItem(str(v)))
  except Exception as e:QMessageBox.critical(self,'Sync Manager',str(e))
 def sync_one(self,d):
  try:
   result=self.mgr().sync_one(d);show_success(self,'Sync Complete',f'{d} synchronization completed successfully.',[('Destination',d),('Status',result.get('status')),('Records',result.get('records'))],str(result))
  except Exception as e:show_error(self,'Sync Failed',f'Could not synchronize to {d}.',e,'Run System Check, verify the connection and retry.')
  self.refresh()
 def sync_all(self,force=False):
  try:
   result=self.mgr().sync_all(force=force);show_success(self,'Sync All Complete','Synchronization run finished successfully.',[('Destinations',len(result)),('Force mode','Yes' if force else 'No')],str(result))
  except Exception as e:show_error(self,'Sync Failed','Synchronization could not be completed.',e)
  self.refresh()
 def retry(self):
  try:
   result=self.mgr().retry_failed();show_success(self,'Retry Complete','Failed synchronization jobs were retried.',[('Jobs',len(result))],str(result))
  except Exception as e:show_error(self,'Retry Failed','Failed synchronization jobs could not be retried.',e)
  self.refresh()
