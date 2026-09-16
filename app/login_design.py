from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from sqlalchemy import select

from .database import User, verify_password


LOGIN_STYLE = """
QDialog#modernLogin { background: #f3f6fb; }
QFrame#loginCard { background: white; border: 1px solid #e4e9f2; border-radius: 22px; }
QFrame#brandPanel { background: #0f2747; border-radius: 18px; }
QLabel#brandTitle { color: white; font-size: 23pt; font-weight: 800; }
QLabel#brandText { color: #cbd8ea; font-size: 10pt; }
QLabel#welcome { color: #10233f; font-size: 20pt; font-weight: 800; }
QLabel#subtitle { color: #718096; font-size: 10pt; }
QLabel#fieldLabel { color: #334155; font-size: 9pt; font-weight: 700; }
QLineEdit { background: #f8fafc; color: #172033; border: 1px solid #d8e0eb; border-radius: 10px; padding: 11px 13px; min-height: 22px; }
QLineEdit:focus { background: white; border: 2px solid #3b82f6; }
QPushButton#loginButton { background: #1769aa; color: white; border: none; border-radius: 10px; padding: 12px; font-size: 10pt; font-weight: 700; }
QPushButton#loginButton:hover { background: #12588e; }
QPushButton#loginButton:pressed { background: #0d4772; }
QPushButton#cancelButton { background: #eef2f7; color: #475569; border: none; border-radius: 10px; padding: 11px; font-weight: 600; }
QPushButton#cancelButton:hover { background: #e2e8f0; }
QLabel#footer { color: #94a3b8; font-size: 8pt; }
"""


class ModernLoginDialog(QDialog):
    def __init__(self, factory):
        super().__init__()
        self.factory = factory
        self.username = ""
        self.setObjectName("modernLogin")
        self.setWindowTitle("د کارگاه مدیریت سیستم")
        self.setFixedSize(780, 500)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(LOGIN_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 26, 26, 26)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("loginCard")
        outer.addWidget(card)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(18)

        brand = QFrame()
        brand.setObjectName("brandPanel")
        brand.setMinimumWidth(285)
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(28, 30, 28, 30)
        brand_layout.setSpacing(12)

        logo = QLabel("✂")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("color:white; font-size:42pt; font-weight:800; background:#1769aa; border-radius:18px; padding:12px;")
        brand_layout.addWidget(logo)
        brand_layout.addSpacing(8)
        brand_layout.addWidget(self._label("د خیاطۍ مدیریت", "brandTitle"))
        brand_layout.addWidget(self._label("Tailoring Management System", "brandText"))
        brand_layout.addSpacing(8)
        brand_layout.addWidget(self._label("د مشتریانو، اندازو، فرمایشونو، پیسو او تحویلي مدیریت په یوه مسلکي سیستم کې.", "brandText"))
        brand_layout.addStretch()
        brand_layout.addWidget(self._label("✓ خوندي معلومات\n✓ آفلاین کار\n✓ چټک او ساده مدیریت", "brandText"))
        layout.addWidget(brand, 1)

        form_frame = QFrame()
        form_layout = QVBoxLayout(form_frame)
        form_layout.setContentsMargins(24, 28, 28, 28)
        form_layout.setSpacing(10)

        form_layout.addWidget(self._label("ښه راغلاست 👋", "welcome"))
        form_layout.addWidget(self._label("خپل حساب ته ننوزئ تر څو سیستم وکاروئ.", "subtitle"))
        form_layout.addSpacing(18)

        form_layout.addWidget(self._label("کارن نوم", "fieldLabel"))
        self.user = QLineEdit("admin")
        self.user.setPlaceholderText("خپل کارن نوم ولیکئ")
        self.user.setClearButtonEnabled(True)
        form_layout.addWidget(self.user)

        form_layout.addSpacing(5)
        form_layout.addWidget(self._label("پټ نوم", "fieldLabel"))
        password_row = QHBoxLayout()
        password_row.setSpacing(6)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("خپل پټ نوم ولیکئ")
        password_row.addWidget(self.password)
        self.show_password = QPushButton("👁")
        self.show_password.setCheckable(True)
        self.show_password.setFixedWidth(46)
        self.show_password.setStyleSheet("QPushButton { background:#eef2f7; color:#475569; border:none; border-radius:10px; padding:9px; } QPushButton:checked { background:#dbeafe; color:#1769aa; }")
        self.show_password.toggled.connect(lambda checked: self.password.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password))
        password_row.addWidget(self.show_password)
        form_layout.addLayout(password_row)

        form_layout.addSpacing(16)
        self.login_button = QPushButton("ننوتل  ←")
        self.login_button.setObjectName("loginButton")
        self.login_button.setMinimumHeight(44)
        self.login_button.clicked.connect(self.login)
        form_layout.addWidget(self.login_button)

        cancel = QPushButton("لغوه")
        cancel.setObjectName("cancelButton")
        cancel.clicked.connect(self.reject)
        form_layout.addWidget(cancel)
        form_layout.addStretch()
        form_layout.addWidget(self._label("Tailoring Management System • Offline Desktop", "footer"))
        layout.addWidget(form_frame, 1)

        self.password.returnPressed.connect(self.login)
        self.user.returnPressed.connect(self.password.setFocus)
        self.password.setFocus()

    @staticmethod
    def _label(text: str, name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(name)
        label.setWordWrap(True)
        return label

    def login(self):
        username = self.user.text().strip()
        password = self.password.text()
        if not username or not password:
            QMessageBox.warning(self, "ننوتل", "مهرباني وکړئ کارن نوم او پټ نوم ولیکئ.")
            return
        with self.factory() as session:
            user = session.scalar(select(User).where(User.username == username))
            if user and verify_password(password, user.password_hash):
                self.username = user.username
                self.accept()
                return
        QMessageBox.warning(self, "ننوتل", "کارن نوم یا پټ نوم ناسم دی.")
