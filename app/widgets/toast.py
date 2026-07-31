# app/widgets/toast.py
"""
Non-Blocking Floating Toast Notification System for Vortex Studio.
Displays non-modal, auto-dismissing notification banners in the top-right corner
of the application window so users are NEVER blocked from continuing their work.
"""

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsDropShadowEffect,
    QFrame
)
from app.theme import SURFACE_BG
from app.icons import get_svg_icon

class ToastNotification(QFrame):
    """
    A single floating toast banner with auto-dismiss and fade animation.
    """
    def __init__(self, title: str, message: str, level: str = "info", duration_ms: int = 3500, parent=None):
        super().__init__(parent)
        self.duration_ms = duration_ms
        self.setObjectName("toastFrame")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        
        # Color theme based on level
        themes = {
            "info": ("#00F2FE", "rgba(0, 242, 254, 0.15)", "info"),
            "success": ("#10b981", "rgba(16, 185, 129, 0.15)", "check"),
            "warning": ("#fbbf24", "rgba(251, 191, 36, 0.15)", "alert"),
            "error": ("#ef4444", "rgba(239, 68, 68, 0.15)", "alert"),
        }
        accent_color, bg_tint, icon_name = themes.get(level.lower(), themes["info"])

        self.setStyleSheet(f"""
            QFrame#toastFrame {{
                background-color: {SURFACE_BG};
                border: 1px solid {accent_color};
                border-radius: 8px;
            }}
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_icon(icon_name, color=accent_color, size=20).pixmap(20, 20))
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(icon_lbl)

        # Text Layout
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: #ffffff; border: none; background: transparent;")
        text_layout.addWidget(lbl_title)

        if message:
            lbl_msg = QLabel(message)
            lbl_msg.setWordWrap(True)
            lbl_msg.setStyleSheet(f"font-size: 11px; color: #e2e8f0; border: none; background: transparent;")
            text_layout.addWidget(lbl_msg)

        layout.addLayout(text_layout, 1)

        # Close button
        btn_close = QPushButton("×")
        btn_close.setFixedSize(18, 18)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ffffff;
            }
        """)
        btn_close.clicked.connect(self.close_toast)
        layout.addWidget(btn_close)

        # Auto dismiss timer
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close_toast)
        self.timer.start(self.duration_ms)

    def close_toast(self):
        self.timer.stop()
        self.hide()
        self.deleteLater()


class ToastManager:
    """
    Manages layout and stacking of floating non-blocking toast notifications.
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ToastManager()
        return cls._instance

    def __init__(self):
        self.active_toasts = []

    def show(self, parent_widget: QWidget, title: str, message: str, level: str = "info", duration_ms: int = 3500):
        if not parent_widget:
            return

        toast = ToastNotification(title, message, level=level, duration_ms=duration_ms, parent=parent_widget)
        toast.setFixedWidth(360)
        toast.adjustSize()

        # Calculate position at top-right of parent
        parent_rect = parent_widget.rect()
        margin_right = 24
        margin_top = 60

        y_offset = margin_top
        for existing in list(self.active_toasts):
            if existing.isVisible():
                y_offset += existing.height() + 10

        x = parent_rect.width() - toast.width() - margin_right
        y = y_offset

        toast.move(x, y)
        toast.show()
        toast.raise_()

        self.active_toasts.append(toast)

        # Clean up list when toast closes
        toast.destroyed.connect(lambda: self._remove_toast(toast))

    def _remove_toast(self, toast):
        if toast in self.active_toasts:
            self.active_toasts.remove(toast)
