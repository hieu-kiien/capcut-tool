# app/theme.py
"""
Theme and styling definitions for Vortex Studio.
Contains color constants, font configurations, and standard QSS styles.
"""

from PySide6.QtGui import QColor

# Color Palette (Dark Obsidian, Surface & Cyan-Violet Accent)
DARK_BG = "#121214"
SURFACE_BG = "#1E1E22"
CYAN_VIOLET_GRADIENT = "linear-gradient(135deg, #00F2FE 0%, #7F00FF 100%)"

COLOR_TEAL = "#00F2FE"
COLOR_CYAN = "#00F2FE"
COLOR_VIOLET = "#7F00FF"
COLOR_DARK_ZINC = DARK_BG
COLOR_SIDEBAR_BG = DARK_BG
COLOR_CARD_BG = SURFACE_BG
COLOR_CARD_BORDER = "#2a2a30"
COLOR_TEXT_PRIMARY = "#f3f4f6"
COLOR_TEXT_SECONDARY = "#9ca3af"
COLOR_TEXT_MUTED = "#cbd5e1"
COLOR_ERROR = "#ef4444"
COLOR_SUCCESS = "#10b981"
COLOR_WARNING = "#fbbf24"
COLOR_SLATE = "#475569"
COLOR_TEXT_LIGHT = "#e2e8f0"
COLOR_TEXT_WHITE = "#ffffff"
COLOR_TEXT_BLACK = "#000000"
COLOR_BG_CONSOLE = "#0c0d0e"
COLOR_TEXT_CONSOLE = "#38bdf8"

GRADIENT_PRIMARY = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00F2FE, stop:1 #7F00FF)"

# QColor Objects for custom painters
QCOLOR_DARK_BG = QColor(DARK_BG)
QCOLOR_SURFACE_BG = QColor(SURFACE_BG)
QCOLOR_TEAL = QColor(COLOR_TEAL)
QCOLOR_DARK_ZINC = QColor(COLOR_DARK_ZINC)
QCOLOR_SIDEBAR_BG = QColor(COLOR_SIDEBAR_BG)
QCOLOR_CARD_BG = QColor(COLOR_CARD_BG)
QCOLOR_CARD_BORDER = QColor(COLOR_CARD_BORDER)
QCOLOR_TEXT_PRIMARY = QColor(COLOR_TEXT_PRIMARY)
QCOLOR_TEXT_SECONDARY = QColor(COLOR_TEXT_SECONDARY)
QCOLOR_TEXT_MUTED = QColor(COLOR_TEXT_MUTED)
QCOLOR_ERROR = QColor(COLOR_ERROR)
QCOLOR_SUCCESS = QColor(COLOR_SUCCESS)
QCOLOR_WARNING = QColor(COLOR_WARNING)
QCOLOR_SLATE = QColor(COLOR_SLATE)
QCOLOR_TEXT_LIGHT = QColor(COLOR_TEXT_LIGHT)
QCOLOR_TEXT_WHITE = QColor(COLOR_TEXT_WHITE)
QCOLOR_TEXT_BLACK = QColor(COLOR_TEXT_BLACK)
QCOLOR_BG_CONSOLE = QColor(COLOR_BG_CONSOLE)
QCOLOR_TEXT_CONSOLE = QColor(COLOR_TEXT_CONSOLE)

# Font Settings
FONT_FAMILY = "'Inter', 'Segoe UI', Arial, sans-serif"
FONT_CONSOLE = "'JetBrains Mono', 'Consolas', monospace"
FONT_SIZE_BASE = "13px"

# Standard QSS chunks to avoid duplication
QSS_CARD = f"""
    QFrame#configCard, QFrame#executionCard, QFrame#logCard, QFrame#projCard, QFrame#queueCard, QFrame#doctorCard, QFrame#backupCard {{
        background-color: {COLOR_CARD_BG};
        border: 1px solid {COLOR_CARD_BORDER};
        border-radius: 12px;
    }}
"""

QSS_BUTTON = f"""
    QPushButton {{
        background: {GRADIENT_PRIMARY};
        color: #000000;
        border: none;
        border-radius: 6px;
        padding: 10px 16px;
        font-size: 13px;
        font-weight: 800;
    }}
    QPushButton:hover {{
        opacity: 0.9;
    }}
    QPushButton:disabled {{
        background-color: {COLOR_CARD_BORDER};
        color: #9ca3af;
    }}
"""

QSS_LINEEDIT = f"""
    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
        background-color: {DARK_BG};
        border: 1px solid {COLOR_CARD_BORDER};
        border-radius: 6px;
        padding: 8px 10px;
        color: #f4f4f5;
    }}
    QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{
        border-color: {COLOR_TEAL};
    }}
"""

def get_application_stylesheet() -> str:
    """
    Returns the comprehensive application-wide stylesheet.
    """
    return f"""
        QMainWindow {{
            background-color: {COLOR_DARK_ZINC};
        }}
        QWidget {{
            color: {COLOR_TEXT_PRIMARY};
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_BASE};
        }}
        
        /* 1. Left Sidebar Styling */
        QFrame#sidebar {{
            background-color: {COLOR_SIDEBAR_BG};
            border-right: 1px solid {COLOR_CARD_BORDER};
            min-width: 220px;
            max-width: 220px;
        }}
        QPushButton#navButton {{
            background-color: transparent;
            border: none;
            border-left: 3px solid transparent;
            border-radius: 8px;
            color: {COLOR_TEXT_SECONDARY};
            text-align: left;
            padding: 12px 15px;
            font-weight: 500;
            font-size: 13px;
            margin: 2px 4px;
        }}
        QPushButton#navButton:hover {{
            color: #ffffff;
            background-color: rgba(255, 255, 255, 0.03);
        }}
        QPushButton#navButton[active="true"] {{
            color: {COLOR_TEAL};
            background-color: rgba(0, 242, 254, 0.10);
            font-weight: 600;
            border-left: 3px solid {COLOR_TEAL};
            border-top-left-radius: 0px;
            border-bottom-left-radius: 0px;
            padding-left: 12px;
        }}
        QFrame#logoIcon {{
            background-color: {COLOR_TEAL};
            border-radius: 10px;
        }}
        
        /* 2. Scroll Area */
        QScrollArea {{
            background-color: {COLOR_DARK_ZINC};
            border: none;
        }}
        QScrollArea > QWidget {{
            background-color: {COLOR_DARK_ZINC};
        }}
        QScrollArea > QWidget > QWidget {{
            background-color: {COLOR_DARK_ZINC};
        }}
        
        /* 3. Header Styling */
        QFrame#header {{
            border-bottom: 1px solid {COLOR_CARD_BORDER};
            background-color: {COLOR_DARK_ZINC};
        }}
        QLabel#appTitle {{
            font-size: 14px;
            font-weight: bold;
            color: #ffffff;
        }}
        QLabel#appSubtitle {{
            font-size: 12px;
            color: {COLOR_TEXT_SECONDARY};
        }}
        QLabel#badge {{
            background-color: rgba(0, 242, 254, 0.15);
            border: 1px solid rgba(0, 242, 254, 0.3);
            color: {COLOR_TEAL};
            padding: 2px 6px;
            font-size: 10px;
            font-weight: bold;
            border-radius: 4px;
        }}
        
        /* 4. Cards & Container Styling */
        QFrame#configCard, QFrame#executionCard, QFrame#logCard, QFrame#projCard, QFrame#queueCard, QFrame#doctorCard, QFrame#backupCard {{
            background-color: {COLOR_CARD_BG};
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 12px;
        }}
        QFrame#kpiCard {{
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 8px;
        }}
        QFrame#kpiCard:hover {{
            background-color: rgba(255, 255, 255, 0.04);
            border-color: rgba(255, 255, 255, 0.12);
        }}
        QLabel#cardTitle {{
            font-size: 12px;
            font-weight: 800;
            color: {COLOR_TEXT_SECONDARY};
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }}
        QLabel#fieldLabel {{
            font-size: 11px;
            color: {COLOR_TEXT_MUTED};
            font-weight: 500;
            text-transform: uppercase;
        }}
        
        /* 5. Inputs & Buttons */
        QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
            background-color: {COLOR_SIDEBAR_BG};
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 6px;
            padding: 8px 10px;
            color: #f4f4f5;
        }}
        QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{
            border-color: {COLOR_TEAL};
        }}
        QComboBox QAbstractItemView {{
            background-color: {COLOR_CARD_BG};
            color: {COLOR_TEXT_PRIMARY};
            selection-background-color: {COLOR_TEAL};
            selection-color: #000000;
            border: 1px solid {COLOR_CARD_BORDER};
        }}
        QPushButton#btnBrowse {{
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 6px;
            padding: 8px 14px;
            color: {COLOR_TEXT_PRIMARY};
            font-weight: bold;
        }}
        QPushButton#btnBrowse:hover {{
            background-color: rgba(255, 255, 255, 0.1);
        }}
        QPushButton#btnStyle {{
            background-color: rgba(255, 255, 255, 0.03);
            color: {COLOR_TEXT_MUTED};
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 11px;
            font-weight: 800;
        }}
        QPushButton#btnStyle:hover {{
            background-color: rgba(255, 255, 255, 0.08);
            color: #f4f4f5;
        }}
        QPushButton#btnStyle:checked {{
            background-color: rgba(0, 242, 254, 0.15);
            color: {COLOR_TEAL};
            border: 1px solid rgba(0, 242, 254, 0.35);
        }}
        QPushButton#settingsToggle {{
            background: transparent;
            border: none;
            color: {COLOR_TEAL};
            font-weight: bold;
            text-align: left;
            padding: 5px 0;
        }}
        QFrame#settingsFrame {{
            background-color: transparent;
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 8px;
        }}
        QRadioButton, QCheckBox {{
            color: {COLOR_TEXT_MUTED};
        }}
        QRadioButton::indicator, QCheckBox::indicator {{
            width: 16px;
            height: 16px;
        }}
        
        /* 6. Stepper Rows & States */
        QFrame#stepRow {{
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px solid transparent;
            border-radius: 8px;
        }}
        QLabel#stepName {{
            font-size: 13px;
            font-weight: bold;
            color: #94a3b8;
        }}
        QLabel#stepStatus {{
            font-size: 11px;
            color: #94a3b8;
        }}
        QLabel#stepCircle {{
            border-radius: 11px;
            font-size: 11px;
            font-weight: bold;
        }}
        
        QFrame#stepRow[state="pending"] {{
            border-color: transparent;
        }}
        QFrame#stepRow[state="pending"] QLabel#stepCircle {{
            border: 2px solid #64748b;
            color: #cbd5e1;
        }}
        
        QFrame#stepRow[state="running"] {{
            border-color: rgba(245, 158, 11, 0.2);
            background-color: rgba(245, 158, 11, 0.03);
        }}
        QFrame#stepRow[state="running"] QLabel#stepCircle {{
            border: 2px solid #f59e0b;
            color: #f59e0b;
        }}
        QFrame#stepRow[state="running"] QLabel#stepName {{
            color: #ffffff;
        }}
        QFrame#stepRow[state="running"] QLabel#stepStatus {{
            color: #f59e0b;
        }}
        
        QFrame#stepRow[state="done"] {{
            border-color: rgba(0, 242, 254, 0.2);
            background-color: rgba(0, 242, 254, 0.05);
        }}
        QFrame#stepRow[state="done"] QLabel#stepCircle {{
            border: 2px solid {COLOR_TEAL};
            background-color: {COLOR_TEAL};
            color: #000000;
        }}
        QFrame#stepRow[state="done"] QLabel#stepName {{
            color: #ffffff;
        }}
        QFrame#stepRow[state="done"] QLabel#stepStatus {{
            color: {COLOR_TEAL};
        }}
        
        QFrame#stepRow[state="error"] {{
            border-color: rgba(239, 68, 68, 0.2);
            background-color: rgba(239, 68, 68, 0.03);
        }}
        QFrame#stepRow[state="error"] QLabel#stepCircle {{
            border: 2px solid #ef4444;
            background-color: #ef4444;
            color: #ffffff;
        }}
        QFrame#stepRow[state="error"] QLabel#stepName {{
            color: #ffffff;
        }}
        QFrame#stepRow[state="error"] QLabel#stepStatus {{
            color: #ef4444;
        }}
        
        /* 7. Progress Bar */
        QProgressBar {{
            background-color: {COLOR_SIDEBAR_BG};
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 4px;
        }}
        QProgressBar::chunk {{
            background-color: {COLOR_TEAL};
            border-radius: 3px;
        }}
        
        /* 8. Table, List & Dialog Widgets */
        QTableWidget, QListWidget, QListView, QTreeView {{
            background-color: {DARK_BG};
            alternate-background-color: {SURFACE_BG};
            color: #f8fafc;
            gridline-color: {COLOR_CARD_BORDER};
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 6px;
            selection-background-color: rgba(0, 242, 254, 0.18);
            selection-color: {COLOR_TEAL};
        }}
        QTableWidget::item, QListWidget::item, QListView::item {{
            padding: 6px 10px;
            color: #f8fafc;
        }}
        QTableWidget::item:alternate, QListWidget::item:alternate {{
            background-color: {SURFACE_BG};
            color: #f8fafc;
        }}
        QTableWidget::item:selected, QListWidget::item:selected, QListView::item:selected {{
            background-color: rgba(0, 242, 254, 0.18);
            color: {COLOR_TEAL};
        }}
        QDialog, QMessageBox {{
            background-color: {DARK_BG};
            color: #f8fafc;
        }}
        QHeaderView::section {{
            background-color: {COLOR_CARD_BG};
            color: {COLOR_TEXT_SECONDARY};
            padding: 6px;
            border: none;
            border-bottom: 1px solid {COLOR_CARD_BORDER};
            border-right: 1px solid {COLOR_CARD_BORDER};
            font-weight: bold;
            text-transform: uppercase;
            font-size: 11px;
        }}
        
        /* 9. Queue Buttons */
        QPushButton#btnStartQueue, QPushButton#btnPauseQueue, QPushButton#btnSkipJob, QPushButton#btnClearQueue {{
            background-color: transparent;
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 6px;
            padding: 6px 12px;
            color: {COLOR_TEXT_MUTED};
            font-weight: 500;
        }}
        QPushButton#btnStartQueue:hover, QPushButton#btnPauseQueue:hover, QPushButton#btnSkipJob:hover, QPushButton#btnClearQueue:hover {{
            background-color: rgba(255, 255, 255, 0.05);
            color: #ffffff;
        }}
        
        /* 10. Control Buttons */
        QPushButton#btnRun, QPushButton#btnBuildNow, QPushButton#btnAddQueue {{
            background: {GRADIENT_PRIMARY};
            color: #000000;
            border: none;
            border-radius: 6px;
            padding: 10px 16px;
            font-size: 13px;
            font-weight: 800;
        }}
        QPushButton#btnRun:hover, QPushButton#btnBuildNow:hover, QPushButton#btnAddQueue:hover {{
            opacity: 0.9;
        }}
        QPushButton#btnRun:disabled, QPushButton#btnBuildNow:disabled, QPushButton#btnAddQueue:disabled {{
            background: {COLOR_CARD_BORDER};
            color: {COLOR_TEXT_SECONDARY};
        }}
        QPushButton#btnCancel {{
            background-color: transparent;
            color: #ef4444;
            border: 1px solid #ef4444;
            border-radius: 6px;
            padding: 10px 16px;
            font-weight: 800;
        }}
        QPushButton#btnCancel:hover {{
            background-color: rgba(239, 68, 68, 0.1);
        }}
        QPushButton#btnCancel:disabled {{
            border-color: {COLOR_CARD_BORDER};
            color: {COLOR_TEXT_SECONDARY};
        }}
        
        /* 11. Log Terminal & Card */
        QLabel#logTitle {{
            font-size: 12px;
            font-weight: 800;
            color: {COLOR_TEXT_SECONDARY};
            text-transform: uppercase;
        }}
        QPushButton#btnClearLog {{
            background: transparent;
            border: none;
            color: {COLOR_TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 500;
        }}
        QPushButton#btnClearLog:hover {{
            color: #ffffff;
        }}
        QPlainTextEdit#logTerminal {{
            background-color: {COLOR_SIDEBAR_BG};
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 8px;
            font-family: {FONT_CONSOLE};
            font-size: 12px;
            padding: 10px;
            color: {COLOR_TEXT_MUTED};
            line-height: 1.6;
        }}
        
        /* 12. Custom Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 6px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(255, 255, 255, 0.25);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}
        
        /* 13. QMessageBox */
        QMessageBox {{
            background-color: {DARK_BG};
            color: #e2e8f0;
        }}
        QMessageBox QLabel {{
            color: #e2e8f0;
        }}
        QMessageBox QPushButton {{
            background-color: {SURFACE_BG};
            border: 1px solid {COLOR_CARD_BORDER};
            border-radius: 6px;
            padding: 6px 14px;
            color: #ffffff;
            font-weight: bold;
            min-width: 70px;
        }}
        QMessageBox QPushButton:hover {{
            background-color: rgba(255, 255, 255, 0.08);
            border-color: {COLOR_TEAL};
        }}
        
        /* 14. Page Headers styling */
        QLabel#pageTitle {{
            font-size: 20px;
            font-weight: 800;
            color: #ffffff;
        }}
        QLabel#pageSubtitle {{
            font-size: 13px;
            color: {COLOR_TEXT_SECONDARY};
        }}

        /* 15. QSplitter Studio Layout Styling */
        QSplitter::handle:horizontal {{
            background-color: {COLOR_CARD_BORDER};
            width: 3px;
        }}
        QSplitter::handle:horizontal:hover {{
            background-color: {COLOR_TEAL};
        }}
        QSplitter::handle:vertical {{
            background-color: {COLOR_CARD_BORDER};
            height: 3px;
        }}
        QSplitter::handle:vertical:hover {{
            background-color: {COLOR_TEAL};
        }}
    """
