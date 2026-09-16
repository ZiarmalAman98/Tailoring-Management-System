from __future__ import annotations

import shutil
import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from sqlalchemy import select

from .database import BACKUP_DIR, DATABASE_PATH, Customer, Expense, InventoryItem, Order, Payment, Session, audit, init_database, next_number, verify_password


WORKFLOW = ["نوی فرمایش", "د اندازه اخیستل شوې", "د پرې کولو په مرحله کې", "د ګنډلو په مرحله کې", "د فټینګ په مرحله کې", "بشپړ شوی", "تحویل شوی"]


def label(text: str) -> QLabel:
    widget = QLabel(text)
    widget.setWordWrap(True)
    return widget


class LoginDialog(QDialog):
    def __init__(self, factory, parent=None):
        super().__init__(parent)
        self.factory = factory
        self.username = ""
        self.setWindowTitle("د کارگاه ننوتل")
        self.setMinimumWidth(420)
        self.setLayoutDirection(Qt.RightToLeft)
        layout = QVBoxLayout(self)
        title = label("د کارگاه مدیریت سیستم")
        title.setObjectName("title")
        layout.addWidget(title)
        layout.addWidget(label("د خپل کارگاه د پرانیستلو لپاره ننوتل وکړئ."))
        form = QFormLayout()
        self.user = QLineEdit("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("admin123")
        form.addRow("کارن نوم", self.user)
        form.addRow("پټ نوم", self.password)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.password.returnPressed.connect(self.login)

    def login(self):
        with self.factory() as session:
            user = session.scalar(select(__import__("app.database", fromlist=["User"]).User).where(__import__("app.database", fromlist=["User"]).User.username == self.user.text().strip()))
            if user and verify_password(self.password.text(), user.password_hash):
                self.username = user.username
                self.accept()
                return
        QMessageBox.warning(self, "ننوتل", "کارن نوم یا پټ نوم ناسم دی.")


class DashboardPage(QWidget):
    def __init__(self, factory):
        super().__init__()
        self.factory = factory
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        heading = label("عمومي کتنه\nد کارگاه د نن ورځې مهم معلومات")
        heading.setObjectName("pageTitle")
        header.addWidget(heading)
        refresh = QPushButton("تازه کول")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        layout.addLayout(header)
        self.stats = QTableWidget(1, 5)
        self.stats.setHorizontalHeaderLabels(["ټول پېرودونکي", "روان سفارشونه", "د نن عاید", "پاتې حساب", "کمې ذخیرې"])
        self.stats.verticalHeader().setVisible(False)
        self.stats.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.stats)
        layout.addWidget(label("وروستي سفارشونه"))
        self.orders = QTableWidget(0, 6)
        self.orders.setHorizontalHeaderLabels(["شمېره", "پېرودونکی", "جامه", "سپارلو نېټه", "حالت", "پاتې"])
        self.orders.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.orders)
        self.refresh()

    def refresh(self):
        with self.factory() as session:
            customers = session.scalars(select(Customer)).all()
            orders = session.scalars(select(Order).order_by(Order.id.desc())).all()
            payments = session.scalars(select(Payment)).all()
            stock = session.scalars(select(InventoryItem)).all()
            active = [item for item in orders if item.status not in ("تحویل شوی", "لغوه شوی")]
            paid_today = sum(item.amount for item in payments if item.paid_at.date() == date.today())
            outstanding = sum(item.remaining for item in orders)
            low = sum(1 for item in stock if item.quantity <= item.minimum_quantity)
            values = [len(customers), len(active), f"AFN {paid_today:,.0f}", f"AFN {outstanding:,.0f}", low]
            for index, value in enumerate(values):
                self.stats.setItem(0, index, QTableWidgetItem(str(value)))
            self.orders.setRowCount(len(orders[:8]))
            for row, item in enumerate(orders[:8]):
                values = [item.order_number, item.customer.name, item.garment, item.delivery_date.isoformat(), item.status, f"AFN {item.remaining:,.0f}"]
                for col, value in enumerate(values):
                    self.orders.setItem(row, col, QTableWidgetItem(str(value)))
            self.orders.resizeColumnsToContents()


class CustomersPage(QWidget):
    def __init__(self, factory, username):
        super().__init__()
        self.factory = factory
        self.username = username
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        title = label("پېرودونکي\nمعلومات، اړیکې او حسابونه")
        title.setObjectName("pageTitle")
        top.addWidget(title)
        top.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("د نوم یا موبایل له مخې لټون")
        self.search.textChanged.connect(self.refresh)
        top.addWidget(self.search)
        add = QPushButton("نوی پېرودونکی")
        add.clicked.connect(self.add_customer)
        top.addWidget(add)
        layout.addLayout(top)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["شمېره", "نوم", "د پلار نوم", "موبایل", "پته", "ثبت"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self):
        with self.factory() as session:
            query = select(Customer).order_by(Customer.id.desc())
            search = self.search.text().strip()
            rows = session.scalars(query).all()
            if search:
                rows = [row for row in rows if search.lower() in f"{row.name} {row.phone} {row.customer_number}".lower()]
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                values = [row.customer_number, row.name, row.father_name, row.phone, row.address, row.created_at.date().isoformat()]
                for c, value in enumerate(values):
                    self.table.setItem(r, c, QTableWidgetItem(str(value)))
            self.table.resizeColumnsToContents()

    def add_customer(self):
        dialog = CustomerDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        with self.factory.begin() as session:
            customer = Customer(customer_number=next_number(session, Customer, "CUS"), name=dialog.name.text(), father_name=dialog.father.text(), phone=dialog.phone.text(), address=dialog.address.text(), gender=dialog.gender.text())
            session.add(customer)
            audit(session, self.username, "created", "customers", f"Customer {customer.name} created")
        self.refresh()


class CustomerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("نوی پېرودونکی")
        form = QFormLayout(self)
        self.name, self.father, self.phone, self.address, self.gender = (QLineEdit() for _ in range(5))
        for field, title in ((self.name, "بشپړ نوم"), (self.father, "د پلار نوم"), (self.phone, "موبایل"), (self.address, "پته"), (self.gender, "جنسیت")):
            form.addRow(title, field)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class OrdersPage(QWidget):
    def __init__(self, factory, username):
        super().__init__()
        self.factory = factory
        self.username = username
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        heading = label("سفارشونه\nله ثبت څخه تر سپارلو پورې د کار بهیر")
        heading.setObjectName("pageTitle")
        top.addWidget(heading)
        top.addStretch()
        add = QPushButton("نوی سفارش")
        add.clicked.connect(self.add_order)
        top.addWidget(add)
        layout.addLayout(top)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["شمېره", "پېرودونکی", "جامه", "سپارلو نېټه", "حالت", "ټول", "پاتې"])
        self.table.cellDoubleClicked.connect(self.advance_status)
        layout.addWidget(label("په جدول کې پر سفارش دوه ځله کلیک وکړئ چې بل پړاو ته لاړ شي."))
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self):
        with self.factory() as session:
            rows = session.scalars(select(Order).order_by(Order.id.desc())).all()
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                values = [row.order_number, row.customer.name, row.garment, row.delivery_date.isoformat(), row.status, f"AFN {row.total:,.0f}", f"AFN {row.remaining:,.0f}"]
                for c, value in enumerate(values):
                    self.table.setItem(r, c, QTableWidgetItem(str(value)))
            self.table.resizeColumnsToContents()

    def add_order(self):
        with self.factory() as session:
            customers = session.scalars(select(Customer).order_by(Customer.name)).all()
        if not customers:
            QMessageBox.information(self, "سفارش", "لومړی پېرودونکی ثبت کړئ.")
            return
        dialog = OrderDialog(customers, self)
        if dialog.exec() != QDialog.Accepted:
            return
        with self.factory.begin() as session:
            order = Order(order_number=next_number(session, Order, "ORD"), customer_id=dialog.customer_id, garment=dialog.garment.text(), design=dialog.design.text(), delivery_date=dialog.delivery_date, total=dialog.total.value(), assigned_tailor=dialog.tailor.text(), notes=dialog.notes.text())
            session.add(order)
            audit(session, self.username, "created", "orders", f"Order {order.order_number} created")
        self.refresh()

    def advance_status(self, row: int, _column: int):
        number = self.table.item(row, 0).text()
        with self.factory.begin() as session:
            order = session.scalar(select(Order).where(Order.order_number == number))
            if not order:
                return
            position = WORKFLOW.index(order.status) if order.status in WORKFLOW else 0
            order.status = WORKFLOW[min(position + 1, len(WORKFLOW) - 1)]
            audit(session, self.username, "status_changed", "orders", f"{order.order_number} → {order.status}")
        self.refresh()


class OrderDialog(QDialog):
    def __init__(self, customers: list[Customer], parent=None):
        super().__init__(parent)
        self.setWindowTitle("نوی سفارش")
        form = QFormLayout(self)
        self.customer = QListWidget()
        for customer in customers:
            item = QListWidgetItem(f"{customer.name} — {customer.phone}")
            item.setData(Qt.UserRole, customer.id)
            self.customer.addItem(item)
        self.customer.setCurrentRow(0)
        self.garment, self.design, self.tailor, self.notes = (QLineEdit() for _ in range(4))
        self.delivery = QLineEdit(date.today().isoformat())
        self.delivery_date = date.today()
        self.delivery.editingFinished.connect(self.parse_date)
        self.total = QSpinBox()
        self.total.setRange(0, 10_000_000)
        self.total.setValue(2200)
        form.addRow("پېرودونکی", self.customer)
        form.addRow("جامه", self.garment)
        form.addRow("ډیزاین", self.design)
        form.addRow("سپارلو نېټه", self.delivery)
        form.addRow("ټوله بیه", self.total)
        form.addRow("ګنډونکی", self.tailor)
        form.addRow("یادښت", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @property
    def customer_id(self) -> int:
        return int(self.customer.currentItem().data(Qt.UserRole))

    def parse_date(self):
        try:
            self.delivery_date = date.fromisoformat(self.delivery.text().strip())
        except ValueError:
            self.delivery_date = date.today()


class SimpleDataPage(QWidget):
    def __init__(self, factory, title: str, model, columns: list[tuple[str, str]]):
        super().__init__()
        self.factory = factory
        self.model = model
        self.columns = columns
        layout = QVBoxLayout(self)
        heading = label(title)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels([heading for _, heading in columns])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self):
        with self.factory() as session:
            rows = session.scalars(select(self.model).order_by(self.model.id.desc())).all()
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, (attribute, _heading) in enumerate(self.columns):
                    value = getattr(row, attribute, "")
                    if isinstance(value, float):
                        value = f"{value:,.0f}"
                    self.table.setItem(r, c, QTableWidgetItem(str(value)))
            self.table.resizeColumnsToContents()


class MainWindow(QMainWindow):
    def __init__(self, factory, username):
        super().__init__()
        self.factory = factory
        self.username = username
        self.setWindowTitle("د کارگاه — Tailoring Management System")
        self.setMinimumSize(1180, 760)
        self.setLayoutDirection(Qt.RightToLeft)
        root = QWidget()
        root_layout = QHBoxLayout(root)
        self.setCentralWidget(root)
        self.nav = QListWidget()
        self.nav.setFixedWidth(240)
        self.pages = QStackedWidget()
        root_layout.addWidget(self.nav)
        root_layout.addWidget(self.pages, 1)
        page_defs = [
            ("عمومي کتنه", DashboardPage(factory)),
            ("پېرودونکي", CustomersPage(factory, username)),
            ("سفارشونه", OrdersPage(factory, username)),
            ("تادیات", SimpleDataPage(factory, "تادیات", Payment, [("receipt_number", "رسید"), ("amount", "مقدار"), ("method", "طریقه"), ("paid_at", "نېټه")])),
            ("ذخیره", SimpleDataPage(factory, "ذخیره", InventoryItem, [("name", "مواد"), ("category", "ډله"), ("quantity", "موجودي"), ("minimum_quantity", "لږ تر لږه"), ("supplier", "عرضه کوونکی")])),
            ("مصارف", SimpleDataPage(factory, "مصارف", Expense, [("category", "ډله"), ("amount", "مقدار"), ("expense_date", "نېټه"), ("description", "یادښت")])),
        ]
        for title, page in page_defs:
            self.nav.addItem(title)
            self.pages.addWidget(page)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)
        backup_action = QAction("بیک اپ", self)
        backup_action.triggered.connect(self.create_backup)
        self.menuBar().addAction(backup_action)

    def create_backup(self):
        target, _ = QFileDialog.getSaveFileName(self, "د بیک اپ ځای وټاکئ", str(BACKUP_DIR / "TailoringBackup.db"), "SQLite Database (*.db)")
        if target:
            shutil.copy2(DATABASE_PATH, target)
            QMessageBox.information(self, "بیک اپ", "بیک اپ په بریالیتوب جوړ شو.")


def apply_styles(app: QApplication) -> None:
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(
        """
        QWidget { background: #f7f4ef; color: #19343b; }
        QMainWindow, QDialog { background: #f7f4ef; }
        QLabel#title { font-size: 24px; font-weight: 700; color: #0d5c57; padding: 12px 0; }
        QLabel#pageTitle { font-size: 22px; font-weight: 700; padding: 6px 0 14px; }
        QListWidget { background: #123f47; color: #edf3ed; border: none; padding: 14px; }
        QListWidget::item { padding: 14px 12px; border-radius: 8px; margin: 3px 0; }
        QListWidget::item:selected { background: #d87158; color: white; }
        QLineEdit, QSpinBox, QListWidget, QTableWidget { border: 1px solid #d8d1c7; border-radius: 8px; padding: 8px; background: #fffdfa; }
        QTableWidget { gridline-color: #e8e0d6; }
        QHeaderView::section { background: #e9e2d8; color: #19343b; padding: 9px; border: none; font-weight: 700; }
        QPushButton { background: #0d6b60; color: white; border: none; border-radius: 8px; padding: 10px 16px; font-weight: 700; }
        QPushButton:hover { background: #d87158; }
        QMenuBar { background: #f7f4ef; padding: 5px; }
        """
    )


def main() -> None:
    factory = init_database()
    app = QApplication(sys.argv)
    app.setApplicationName("Tailoring Management System")
    app.setLayoutDirection(Qt.RightToLeft)
    apply_styles(app)
    login = LoginDialog(factory)
    if login.exec() != QDialog.Accepted:
        return
    window = MainWindow(factory, login.username)
    window.show()
    sys.exit(app.exec())