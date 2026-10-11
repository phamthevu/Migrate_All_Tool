from pathlib import Path
import sys

def shared_templates_root() -> Path:
    """Locate the shared workbook library beside the suite or app executable."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent / 'Templates'
    return Path(__file__).resolve().parents[2] / 'Templates'

def research_template_path(name='Config_Template.xlsx') -> Path:
    return shared_templates_root() / 'Template' / 'ResearchStudio' / name
