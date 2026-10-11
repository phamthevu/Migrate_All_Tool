import json
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent/'i18n'; _current='en'; _maps={}

def language(): return _current

def _load(code):
    if code not in _maps:
        try:_maps[code]=json.loads((BASE/f'{code}.json').read_text(encoding='utf-8'))
        except Exception:_maps[code]={}
    return _maps[code]

def set_language(code):
    global _current
    _current=code if code in ('en','vi') else 'en'; _load(_current)

def tr(text):
    if _current=='en': return text
    mp=_load(_current)
    for k,v in sorted(mp.items(),key=lambda x:-len(x[0])):
        if text==k:return v
        if text.startswith(k+':'):return v+text[len(k):]
    return mp.get(text,text)

def _source(obj, prop, current):
    key='_i18n_'+prop
    saved=obj.property(key)
    if saved is None:
        obj.setProperty(key,current); return current
    return str(saved)

def translate_tree(root):
    """Always translate from the original English source, never from rendered text."""
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import QWidget,QLabel,QPushButton,QGroupBox,QTabWidget,QMenu
    for obj in [root]+root.findChildren(QWidget):
        if isinstance(obj,(QLabel,QPushButton,QGroupBox)) and obj.text():
            src=_source(obj,'text',obj.text()); obj.setText(tr(src) if _current!='en' else src)
        if obj.windowTitle():
            src=_source(obj,'title',obj.windowTitle()); obj.setWindowTitle(tr(src) if _current!='en' else src)
        if isinstance(obj,QTabWidget):
            for i in range(obj.count()):
                child=obj.widget(i); key='_i18n_tab_text'
                src=child.property(key)
                if src is None: src=obj.tabText(i); child.setProperty(key,src)
                obj.setTabText(i,tr(str(src)) if _current!='en' else str(src))
    for a in root.findChildren(QAction):
        src=_source(a,'text',a.text()); a.setText(tr(src) if _current!='en' else src)
    for m in root.findChildren(QMenu):
        src=_source(m,'menu_title',m.title()); m.setTitle(tr(src) if _current!='en' else src)
