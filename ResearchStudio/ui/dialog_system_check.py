from PyQt6.QtWidgets import *
from integrations.health_check import dependency_health
class SystemCheckDialog(QDialog):
 def __init__(self,p=None):
  super().__init__(p);self.setWindowTitle('System Check');self.resize(760,500);l=QVBoxLayout(self);t=QTableWidget(0,3);t.setHorizontalHeaderLabels(['Component','Status','Details']);t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);l.addWidget(t);r=dependency_health();t.setRowCount(len(r))
  for i,x in enumerate(r):
   for j,k in enumerate(('component','status','detail')):t.setItem(i,j,QTableWidgetItem(str(x[k])))
