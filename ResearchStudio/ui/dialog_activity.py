from PyQt6.QtWidgets import *
from integrations.activity_store import recent
class ActivityDialog(QDialog):
 def __init__(self,p=None):
  super().__init__(p);self.setWindowTitle('Activity Center');self.resize(900,500);l=QVBoxLayout(self);t=QTableWidget(0,4);t.setHorizontalHeaderLabels(['Time','Type','Summary','Details']);t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);l.addWidget(t);r=recent();t.setRowCount(len(r))
  for i,x in enumerate(r):
   for j,k in enumerate(('at','kind','summary','detail')):t.setItem(i,j,QTableWidgetItem(str(x[k] or '')))
