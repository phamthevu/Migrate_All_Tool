from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from app.ui.data_tab import DataTab
from app.ui.visual_tab import VisualTab
from app.core.model import AppState

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MCDMVisualStudio")
        self.setMinimumSize(1100, 700)

        self.state = AppState()

        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        banner = QFrame()
        banner.setObjectName("studioBanner")
        banner.setFixedHeight(68)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(18, 7, 18, 7)
        banner_layout.setSpacing(10)

        mark = QLabel("MVS")
        mark.setObjectName("studioMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(40, 40)
        mark.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        banner_layout.addWidget(mark)

        brand = QVBoxLayout()
        brand.setSpacing(1)
        title = QLabel("MCDMVisualStudio")
        title.setObjectName("studioTitle")
        title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        subtitle = QLabel("DEMATEL · TOPSIS · AHP · Result visualization")
        subtitle.setObjectName("studioSubtitle")
        subtitle.setFont(QFont("Segoe UI", 9))
        brand.addWidget(title)
        brand.addWidget(subtitle)
        banner_layout.addLayout(brand)
        banner_layout.addStretch(1)

        badge = QLabel("ANALYSIS STUDIO")
        badge.setObjectName("studioBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        banner_layout.addWidget(badge)
        shell_layout.addWidget(banner)

        self.tabs = QTabWidget()
        self.data_tab = DataTab(self.state)
        self.visual_tab = VisualTab(self.state)

        self.tabs.addTab(self.data_tab, "Data")
        self.tabs.addTab(self.visual_tab, "Visual")
        self.tabs.setObjectName("workspaceTabs")
        shell_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(shell)

        self.setStyleSheet("""
            QMainWindow { background: #F3F5FA; }
            QFrame#studioBanner { background: #0F172A; border: none; }
            QLabel#studioMark {
                background: #4F46E5; color: white; border-radius: 12px;
            }
            QLabel#studioTitle { color: white; }
            QLabel#studioSubtitle { color: #A5B4FC; }
            QLabel#studioBadge {
                color: #C7D2FE; background: #1E293B;
                border-radius: 7px; padding: 5px 9px;
            }
            QTabWidget#workspaceTabs::pane {
                border: none; background: #F3F5FA; top: -1px;
            }
            QTabWidget#workspaceTabs > QTabBar::tab {
                color: #334155; background: #E7ECF4;
                border: none; padding: 8px 16px; margin-right: 4px;
                border-top-left-radius: 7px; border-top-right-radius: 7px;
            }
            QTabWidget#workspaceTabs > QTabBar::tab:selected {
                color: white; background: #4F46E5;
            }
        """)

        self.state.changed.connect(self.visual_tab.refresh_from_state)
