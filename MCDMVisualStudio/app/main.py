import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Support both `python app/main.py` from any working directory and
# `python -m app.main` from the project root.
if __package__ in (None, ""):
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from app.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1400, 820)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
