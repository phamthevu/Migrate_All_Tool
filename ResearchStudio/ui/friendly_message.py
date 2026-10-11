import traceback
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QPlainTextEdit,QApplication,QFrame
from PyQt6.QtCore import Qt
class FriendlyMessageDialog(QDialog):
 def __init__(self,parent,title,summary,action='',details='',level='info',facts=None):
  super().__init__(parent);self.setWindowTitle(title);self.setMinimumWidth(590);self.resize(650,330);l=QVBoxLayout(self);l.setContentsMargins(24,22,24,20);l.setSpacing(12)
  icon={'success':'✓','error':'!','warning':'!','info':'i'}.get(level,'i');h=QLabel(f'{icon}  {summary}');h.setWordWrap(True);h.setStyleSheet('font-size:15pt;font-weight:700;color:#1f2937');l.addWidget(h)
  what=QLabel('<b>What happened</b>');what.setStyleSheet('font-size:10.5pt;color:#475467');l.addWidget(what)
  if facts:
   card=QFrame();card.setStyleSheet('QFrame{background:#f8fafc;border:1px solid #e2e8f0;border-radius:7px;}');cl=QVBoxLayout(card);cl.setContentsMargins(14,12,14,12)
   x=QLabel('<br><br>'.join(f'<b>{k}</b><br>{v}' for k,v in facts if v not in (None,'')));x.setWordWrap(True);x.setTextFormat(Qt.TextFormat.RichText);cl.addWidget(x);l.addWidget(card)
  else:
   x=QLabel(summary);x.setWordWrap(True);l.addWidget(x)
  if action:
   a=QLabel('<b>Recommended action / What you can do:</b><br>'+action);a.setWordWrap(True);a.setTextFormat(Qt.TextFormat.RichText);l.addWidget(a)
  self.d=QPlainTextEdit(details or 'No technical details.');self.d.setReadOnly(True);self.d.hide();self.d.setMaximumHeight(180);l.addWidget(self.d)
  r=QHBoxLayout();t=QPushButton('Technical details ▸');c=QPushButton('Copy Details');z=QPushButton('Close');z.setProperty('primary',True)
  def flip():self.d.setVisible(not self.d.isVisible());t.setText('Technical details ▾' if self.d.isVisible() else 'Technical details ▸')
  t.clicked.connect(flip);c.clicked.connect(lambda:QApplication.clipboard().setText(self.d.toPlainText()));z.clicked.connect(self.accept);r.addWidget(t);r.addWidget(c);r.addStretch();r.addWidget(z);l.addLayout(r)
def show_error(parent,title,summary,exc=None,action='Review the settings and try again.',facts=None):
 if isinstance(exc, BaseException):
  d=''.join(traceback.format_exception(type(exc),exc,exc.__traceback__))
 elif exc:
  d=str(exc)
 else:
  d=summary
 return FriendlyMessageDialog(parent,title,summary,action,d,'error',facts).exec()
def show_success(parent,title,summary,facts=None,details=''):
 return FriendlyMessageDialog(parent,title,summary,'No further action is required.',details,'success',facts).exec()
def show_warning(parent,title,summary,action='',facts=None,details=''):
 return FriendlyMessageDialog(parent,title,summary,action,details,'warning',facts).exec()
