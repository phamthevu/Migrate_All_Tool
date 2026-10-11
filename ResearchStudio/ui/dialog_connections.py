from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPushButton,QTabWidget,QWidget,QMessageBox,QLabel,QComboBox,QInputDialog,QScrollArea,QApplication)
from PyQt6.QtCore import QSettings
from integrations.config_store import load_profiles,save_profiles
from integrations.postgres_repository import PostgreSQLRepository
from integrations.sqlserver_repository import SQLServerRepository
from integrations.mysql_repository import MySQLRepository
from integrations.s3_repository import S3Repository
from integrations.drive_repository import GoogleDriveRepository
from integrations.adls_repository import ADLSRepository
from integrations.bigquery_repository import BigQueryRepository
from integrations.powerbi_connector import PowerBIConnector
from integrations.email_sender import SMTPSender
from integrations.local_folder_repository import LocalSyncFolderRepository
from integrations.extra_connectors import FTPConnector,SFTPConnector,MongoConnector,WebhookConnector
from ui.friendly_message import show_error

DB_NAMES={'postgres','sqlserver','mysql','mongodb'}
class ConnectionManagerDialog(QDialog):
 def __init__(self,parent=None,project_db=None):
  super().__init__(parent);self.project_db=project_db;self.setWindowTitle('Connection Manager');self._saving=False;self._settings=QSettings('ResearchStudio','ResearchStudio');self._apply_saved_size()
  root=QVBoxLayout(self);root.setContentsMargins(12,10,12,10);root.setSpacing(8)
  sizebar=QHBoxLayout();sizebar.addWidget(QLabel('UI width:'));
  for label,width in [('Compact',720),('Normal',860),('Wide',1040)]:
   b=QPushButton(label);b.setMaximumWidth(90);b.clicked.connect(lambda _,w=width:self._set_ui_width(w));sizebar.addWidget(b)
  sizebar.addStretch();root.addLayout(sizebar)
  note=QLabel('Connections are grouped by type. Local .mcdm remains the source of truth. Database Sync writes the current local project state to staging. OVERWRITE is the default; APPEND preserves historical snapshots. Credentials are stored outside the project.');note.setWordWrap(True);root.addWidget(note)
  self.categories=QTabWidget();root.addWidget(self.categories);self.sections={}
  self._category('Database',[('postgres','PostgreSQL',['host','port','database','schema','user','password','sslmode','timeout','sync_mode']),('sqlserver','SQL Server',['host','port','database','schema','auth_mode','user','password','driver','encrypt','trust_server_certificate','timeout','sync_mode']),('mysql','MySQL / MariaDB',['host','port','database','user','password','timeout','sync_mode']),('mongodb','MongoDB',['uri','database'])])
  self._category('Storage',[('s3','S3 / MinIO',['endpoint_url','region','bucket','access_key','secret_key','prefix']),('sync_folder','Cloud Sync Folder',['folder','project_subfolder']),('drive','Google Drive API (Legacy)',['service_account_json','folder_id']),('adls','Azure Blob / ADLS Gen2',['account_url','credential','container','prefix']),('ftp','FTP',['host','port','user','password','path']),('sftp','SFTP',['host','port','user','password','path'])])
  self._category('Email / Messaging',[('smtp','Email / SMTP',['host','port','user','password','from_email','starttls','ssl']),('webhook','REST / Webhook',['url','bearer_token'])])
  self._category('Analytics / BI',[('bigquery','BigQuery',['project_id','responses_table']),('powerbi','Power BI',['push_url','bearer_token'])])
  info=QLabel('Cloud Sync Folder works with Google Drive Desktop, OneDrive, Dropbox, NAS or any mounted/synced folder — no GCP required. Optional connectors such as MongoDB/SFTP require their Python packages.');info.setWordWrap(True);root.addWidget(info)
  row=QHBoxLayout();b=QPushButton('Save Connections');b.setProperty('success',True);b.setMinimumHeight(34);b.clicked.connect(self.save);row.addStretch();row.addWidget(b);root.addLayout(row);self.load()
 def _line(self,password=False):
  w=QLineEdit();
  if password:w.setEchoMode(QLineEdit.EchoMode.Password)
  return w
 def _category(self,title,items):
  outer=QTabWidget();self.categories.addTab(outer,title)
  for name,label,fields in items:
   content=QWidget();f=QFormLayout(content);f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow);d={}
   for k in fields:
    if k=='sync_mode':
     x=QComboBox();x.addItem('OVERWRITE current staging (Default)','overwrite');x.addItem('APPEND snapshots (History / more rows)','append');d[k]=x
    else:d[k]=self._line(k in ('password','credential','secret_key','bearer_token'))
    f.addRow(k.replace('_',' ').title()+':',d[k])
   if name=='smtp':
    x=QLabel('Test validates TCP + TLS/SSL + authentication. It does not rely on SMTP NOOP, avoiding the V5.3 false-fail issue.');x.setWordWrap(True);f.addRow(x)
   if name in DB_NAMES:
    x=QLabel('Sync mode: OVERWRITE (default) replaces staging rows only for the current project + source instance. APPEND creates a new full snapshot and can grow the DB quickly. Research Studio does not deduplicate or apply SCD2; metadata is retained for downstream processing.');x.setWordWrap(True);f.addRow(x)
   h=QHBoxLayout();test=QPushButton('Test Connection');test.clicked.connect(lambda _,n=name:self._test(n));h.addWidget(test)
   if name in {'postgres','sqlserver'}:
    ls=QPushButton('Load Schemas');ls.clicked.connect(lambda _,n=name:self._load_schemas(n));h.addWidget(ls)
   sync=QPushButton('Sync Current Project');sync.setProperty('primary',True);sync.clicked.connect(lambda _,n=name:self._sync(n));h.addWidget(sync);h.addStretch();f.addRow(h)
   scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.Shape.NoFrame);scroll.setWidget(content);outer.addTab(scroll,label);self.sections[name]=(content,d)
 def values(self):
  return {n:{k:(w.currentData() if isinstance(w,QComboBox) else w.text().strip()) for k,w in pair[1].items()} for n,pair in self.sections.items()}
 def load(self):
  p=load_profiles()
  for n,pair in self.sections.items():
   for k,w in pair[1].items():
    val=str(p.get(n,{}).get(k,''))
    if isinstance(w,QComboBox):
     idx=w.findData(val or 'overwrite');w.setCurrentIndex(max(0,idx))
    else:w.setText(val)
 def _apply_saved_size(self):
  screen=QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
  width=int(self._settings.value('connection_manager/width',860))
  width=max(680,min(width,(screen.width()-80) if screen else 1200))
  height=min(620,(screen.height()-100) if screen else 620)
  self.resize(width,max(460,height))
 def _set_ui_width(self,width):
  screen=QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
  width=max(680,min(int(width),(screen.width()-80) if screen else int(width)))
  self.resize(width,self.height());self._settings.setValue('connection_manager/width',width)
 def _persist(self):
  if self._saving:return
  self._saving=True
  try:
   save_profiles(self.values())
  finally:self._saving=False
 def save(self):
  try:self._persist();QMessageBox.information(self,'Connections Saved','Connection profiles and credentials were saved.')
  except Exception as e:show_error(self,'Save Failed','Could not save the connection profiles.',e,'Check Windows Credential Manager/keyring availability and try again.')
 def done(self,result):
  # Connection Manager is an editor: closing it persists the current values so other tabs can sync immediately.
  try:self._persist()
  except Exception as e:
   show_error(self,'Save Failed','The Connection Manager could not save your latest changes.',e,'Keep this dialog open, check credential storage, then save again.');return
  self._settings.setValue('connection_manager/width',self.width())
  super().done(result)
 def _connector(self,name):
  cls={'postgres':PostgreSQLRepository,'sqlserver':SQLServerRepository,'mysql':MySQLRepository,'mongodb':MongoConnector,'s3':S3Repository,'sync_folder':LocalSyncFolderRepository,'drive':GoogleDriveRepository,'adls':ADLSRepository,'ftp':FTPConnector,'sftp':SFTPConnector,'smtp':SMTPSender,'webhook':WebhookConnector,'bigquery':BigQueryRepository,'powerbi':PowerBIConnector}[name]
  return cls(self.values()[name])
 def _load_schemas(self,name):
  try:
   conn=self._connector(name); schemas=conn.list_schemas()
   if not schemas: raise ValueError('No schemas returned by server.')
   current=self.sections[name][1].get('schema').text().strip() if self.sections[name][1].get('schema') else ''
   idx=schemas.index(current) if current in schemas else 0
   choice,ok=QInputDialog.getItem(self,'Select Schema','Schema:',schemas,idx,False)
   if ok:self.sections[name][1]['schema'].setText(choice)
  except Exception as e:show_error(self,'Load Schemas Failed','Could not load database schemas.',e,'Check the server, database, credentials and network connection, then try again.')
 def _test(self,name):
  try:
   v=self.values()[name]
   if name in {'postgres','sqlserver','mysql'}:
    missing=[k for k in ('host','database') if not v.get(k)]
    if name!='sqlserver' or (v.get('auth_mode') or 'sql').lower()!='windows':
     missing += [k for k in ('user',) if not v.get(k)]
    if missing: raise ValueError('Missing required fields: '+', '.join(missing))
   if name=='smtp' and not all(v.get(k) for k in ('host','port','user','password','from_email')): raise ValueError('SMTP requires host, port, user, password/app-password and from_email.')
   result=self._connector(name).test();show_success(self,'Connection Test Successful',f'{name} connection test passed.',[('Connector',name),('Result',str(result))])
  except Exception as e:show_error(self,'Connection Failed',f'Could not connect to {name}.',e,'Check Host, Port, Database and credentials, then retry the connection test.')
 def _sync(self,name):
  if not self.project_db:QMessageBox.warning(self,'No Project','Open a project before syncing.');return
  try:
   save_profiles(self.values());conn=self._connector(name)
   if name in {'postgres','sqlserver','mysql'}:
    meta=self.project_db.get_meta() or {}; count=self.project_db.conn.execute('SELECT COUNT(*) FROM responses').fetchone()[0]
    mode=(self.values()[name].get('sync_mode') or 'overwrite').upper()
    warning='\n\nWARNING: APPEND keeps every full snapshot. Row count can grow quickly.' if mode=='APPEND' else '\n\nOVERWRITE only replaces rows for this project + this source instance.'
    msg=(f"Send the current local state of project '{meta.get('project_name','')}' to {name}?\n\n"
         f"Responses: {count}\nMode: {mode} → STAGING"
         f"{warning}\n\nMetadata: snapshot_id/time, source_instance_id/name/owner, local_response_id, respondent_id, source_updated_at, record_hash.\n\n"
         "Deduplication and SCD2 are downstream database/warehouse responsibilities. Continue?")
    if QMessageBox.question(self,'Confirm Database Snapshot',msg,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
   if name=='sync_folder':
    result=conn.upload_files([self.project_db.db_path],(self.project_db.get_meta() or {}).get('project_name') or 'Project');QMessageBox.information(self,'Sync Complete',str(result));return
   if not hasattr(conn,'sync'):
    QMessageBox.information(self,'Connector Saved',f'{name}: configuration is valid/saved. This connector is used for transfer/notification rather than project snapshot sync.');return
   result=conn.sync(self.project_db);QMessageBox.information(self,'Sync Complete',f'{name}: {result}')
  except Exception as e:show_error(self,'Sync Failed',f'Could not synchronize the current project to {name}.',e,'Refresh status and verify the connection. If this is a revision conflict, review the remote project before forcing a sync.')
