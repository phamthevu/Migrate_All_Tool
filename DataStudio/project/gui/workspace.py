from tkinter import ttk
class WorkspaceNotebook(ttk.Notebook):
    """Three top-level workspaces with leaf-tab routing for shared model tools."""
    def __init__(self,parent):super().__init__(parent);self.routes={};self.groups={}
    def group(self,key,title):
        frame=ttk.Frame(self);super().add(frame,text='  '+title+'  ')
        tabs=ttk.Notebook(frame);tabs.pack(fill='both',expand=True,pady=(8,0));self.groups[str(frame)]=tabs
        return frame,tabs
    def leaf(self,name,title,group,tabs):
        frame=ttk.Frame(tabs);tabs.add(frame,text='  '+title+'  ');self.routes[str(frame)]=(group,tabs);return frame
    def select(self,tab_id=None):
        if tab_id is None:
            group=super().select();tabs=self.groups.get(group)
            return tabs.select() if tabs is not None else group
        route=self.routes.get(str(tab_id))
        if route:
            group,tabs=route;super().select(group);tabs.select(tab_id)
        else:super().select(tab_id)
