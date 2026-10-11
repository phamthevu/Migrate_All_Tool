import os, pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PyQt6')
from PyQt6.QtWidgets import QApplication,QScrollArea
import ui.dialog_connections as dc

def app(): return QApplication.instance() or QApplication([])

def test_close_autosaves_current_connection_values(monkeypatch):
    app(); saved=[]
    monkeypatch.setattr(dc,'load_profiles',lambda:{})
    monkeypatch.setattr(dc,'save_profiles',lambda data:saved.append(data))
    d=dc.ConnectionManagerDialog()
    d.sections['postgres'][1]['host'].setText('10.0.0.7')
    d.done(0)
    assert saved and saved[-1]['postgres']['host']=='10.0.0.7'

def test_connection_pages_scroll_and_width_controls_exist(monkeypatch):
    app(); monkeypatch.setattr(dc,'load_profiles',lambda:{})
    d=dc.ConnectionManagerDialog()
    assert d.findChildren(QScrollArea)
    d._set_ui_width(720); assert d.width()>=680
