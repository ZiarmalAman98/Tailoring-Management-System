from __future__ import annotations

import csv
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QFont
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QDoubleSpinBox,
    QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
    QWidget, QAbstractItemView
)
from sqlalchemy import select, func

from .database import (
    BACKUP_DIR, DATABASE_PATH, DOCUMENT_DIR, IMAGE_DIR, AuditLog, Customer,
    Employee, Expense, InventoryItem, MeasurementProfile, Order, Payment, Session,
    User, AppSetting, audit, init_database, next_number, verify_password
)

WORKFLOW = ["نوی فرمایش", "د اندازه اخیستل شوې", "د پرې کولو په مرحله کې", "د ګنډلو په مرحله کې", "د فټینګ په مرحله کې", "QC", "بشپړ شوی", "تحویل شوی"]
GARMENTS = ["شلوار کمیس", "ښځینه جامې", "کورتۍ", "کمیس", "پتلون", "سوټ", "کوټ", "واسکټ", "نور"]
UNITS = ["cm", "inch"]

STYLE = """
QWidget { font-family: 'Segoe UI', 'Noto Sans Arabic'; font-size: 10pt; }
QMainWindow { background: #f4f6f9; }
QFrame#sidebar { background: #10233f; border: none; }
QLabel#brand { color: white; font-size: 19pt; font-weight: 700; padding: 14px; }
QLabel#pageTitle { font-size: 18pt; font-weight: 700; color: #14213d; }
QLabel#muted { color: #718096; }
QPushButton { background: #1769aa; color: white; border: none; border-radius: 7px; padding: 9px 15px; }
QPushButton:hover { background: #12588e; }
QPushButton#danger { background: #c0392b; }
QPushButton#secondary { background: #64748b; }
QListWidget#nav { background: #10233f; color: #dbe7f5; border: none; padding: 8px; }
QListWidget#nav::item { padding: 13px 12px; border-radius: 7px; margin: 2px 0; }
QListWidget#nav::item:selected { background: #1769aa; color: white; }
QFrame#topbar, QFrame#card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; }
QLabel#cardValue { font-size: 18pt; font-weight: 700; color: #10233f; }
QLabel#cardTitle { color: #64748b; }
QLineEdit, QTextEdit, QComboBox, QDoubleSpinBox, QSpinBox { background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 7px; }
QTableWidget { background: white; border: 1px solid #e2e8f0; gridline-color: #edf2f7; alternate-background-color: #f8fafc; }
QHeaderView::section { background: #edf2f7; padding: 9px; border: none; font-weight: 600; }
QStatusBar { background: #10233f; color: white; }
"""


def money(value: float) -> str:
    return f"AFN {value:,.0f}"


def make_label(text: str, object_name: str = "") -> QLabel:
    w = QLabel(text)
    w.setWordWrap(True)
    if object_name:
        w.setObjectName(object_name)
    return w


def configure_table(table: QTableWidget):
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)


class LoginDialog(QDialog):
    def __init__(self, factory):
        super().__init__()
        self.factory = factory
        self.username = ""
        self.setWindowTitle("د کارگاه مدیریت سیستم")
        self.setMinimumSize(430, 330)
        self.setLayoutDirection(Qt.RightToLeft)
        box = QVBoxLayout(self)
        box.addWidget(make_label("د کارگاه مدیریت سیستم", "pageTitle"))
        box.addWidget(make_label("د خپل حساب له لارې سیستم ته ننوزئ.", "muted"))
        form = QFormLayout()
        self.user = QLineEdit("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("admin123")
        form.addRow("کارن نوم", self.user)
        form.addRow("پټ نوم", self.password)
        box.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.login)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)
        self.password.returnPressed.connect(self.login)

    def login(self):
        with self.factory() as session:
            user = session.scalar(select(User).where(User.username == self.user.text().strip()))
            if user and verify_password(self.password.text(), user.password_hash):
                self.username = user.username
                self.accept()
                return
        QMessageBox.warning(self, "ننوتل", "کارن نوم یا پټ نوم ناسم دی.")


class Card(QFrame):
    def __init__(self, title: str, value: str):
        super().__init__()
        self.setObjectName("card")
        box = QVBoxLayout(self)
        box.addWidget(make_label(title, "cardTitle"))
        self.value = make_label(value, "cardValue")
        box.addWidget(self.value)

    def set_value(self, value: str):
        self.value.setText(value)


class DashboardPage(QWidget):
    def __init__(self, factory):
        super().__init__()
        self.factory = factory
        root = QVBoxLayout(self)
        head = QHBoxLayout()
        head.addWidget(make_label("عمومي کتنه", "pageTitle"))
        head.addStretch()
        refresh = QPushButton("↻ تازه کول")
        refresh.clicked.connect(self.refresh)
        head.addWidget(refresh)
        root.addLayout(head)
        self.cards = {}
        grid = QGridLayout()
        names = [("customers", "ټول پېرودونکي"), ("active", "روان سفارشونه"), ("today", "د نن عاید"), ("outstanding", "پاتې حساب"), ("expenses", "د نن مصارف"), ("profit", "د نن خالصه"), ("low", "کمې ذخیرې"), ("delivery", "د نن تحویلي")]
        for i, (key, title) in enumerate(names):
            self.cards[key] = Card(title, "0")
            grid.addWidget(self.cards[key], i // 4, i % 4)
        root.addLayout(grid)
        root.addWidget(make_label("وروستي سفارشونه", "pageTitle"))
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["شمېره", "پېرودونکی", "جامه", "سپارلو نېټه", "حالت", "ټول", "پاتې"])
        configure_table(self.table)
        root.addWidget(self.table)
        self.refresh()

    def refresh(self):
        with self.factory() as s:
            customers = s.scalar(select(func.count(Customer.id))) or 0
            orders = s.scalars(select(Order).order_by(Order.id.desc())).all()
            payments = s.scalars(select(Payment)).all()
            expenses = s.scalars(select(Expense)).all()
            stock = s.scalars(select(InventoryItem)).all()
            active = [o for o in orders if o.status not in ("تحویل شوی", "لغوه شوی")]
            today = date.today()
            revenue = sum(p.amount for p in payments if p.paid_at.date() == today)
            exp = sum(e.amount for e in expenses if e.expense_date == today)
            outstanding = sum(o.remaining for o in orders)
            low = sum(1 for x in stock if x.quantity <= x.minimum_quantity)
            deliveries = sum(1 for o in orders if o.delivery_date == today and o.status != "تحویل شوی")
            for k, v in {"customers": customers, "active": len(active), "today": money(revenue), "outstanding": money(outstanding), "expenses": money(exp), "profit": money(revenue-exp), "low": low, "delivery": deliveries}.items():
                self.cards[k].set_value(str(v))
            rows = orders[:10]
            self.table.setRowCount(len(rows))
            for r, o in enumerate(rows):
                vals = [o.order_number, o.customer.name, o.garment, o.delivery_date.isoformat(), o.status, money(o.total), money(o.remaining)]
                for c, v in enumerate(vals): self.table.setItem(r, c, QTableWidgetItem(str(v)))


class CustomerDialog(QDialog):
    def __init__(self, customer=None, parent=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("د پېرودونکي معلومات")
        self.setMinimumWidth(520)
        self.setLayoutDirection(Qt.RightToLeft)
        form = QFormLayout(self)
        self.name = QLineEdit(getattr(customer, "name", ""))
        self.father = QLineEdit(getattr(customer, "father_name", ""))
        self.phone = QLineEdit(getattr(customer, "phone", ""))
        self.address = QLineEdit(getattr(customer, "address", ""))
        self.gender = QComboBox(); self.gender.addItems(["", "نارینه", "ښځینه"]); self.gender.setCurrentText(getattr(customer, "gender", ""))
        self.notes = QTextEdit(getattr(customer, "notes", "")); self.notes.setMaximumHeight(80)
        for w, t in [(self.name, "بشپړ نوم"), (self.father, "د پلار نوم"), (self.phone, "موبایل"), (self.address, "پته"), (self.gender, "جنسیت"), (self.notes, "یادښت")]: form.addRow(t, w)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)


class CustomersPage(QWidget):
    def __init__(self, factory, username):
        super().__init__(); self.factory=factory; self.username=username
        root=QVBoxLayout(self); head=QHBoxLayout(); head.addWidget(make_label("پېرودونکي", "pageTitle")); head.addStretch()
        self.search=QLineEdit(); self.search.setPlaceholderText("لټون: نوم، موبایل، شمېره"); self.search.textChanged.connect(self.refresh); head.addWidget(self.search)
        for text, slot, obj in [("＋ نوی پېرودونکی", self.add, ""), ("✎ سمول", self.edit, "secondary"), ("🗑 حذف", self.delete, "danger")]:
            b=QPushButton(text); b.setObjectName(obj); b.clicked.connect(slot); head.addWidget(b)
        root.addLayout(head)
        self.table=QTableWidget(0,7); self.table.setHorizontalHeaderLabels(["شمېره","نوم","د پلار نوم","موبایل","جنسیت","پته","ثبت"]); configure_table(self.table); root.addWidget(self.table); self.refresh()

    def rows(self):
        with self.factory() as s: rows=s.scalars(select(Customer).order_by(Customer.id.desc())).all()
        q=self.search.text().strip().lower()
        return [x for x in rows if not q or q in f"{x.customer_number} {x.name} {x.phone}".lower()]
    def refresh(self):
        rows=self.rows(); self.table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            vals=[x.customer_number,x.name,x.father_name,x.phone,x.gender,x.address,x.created_at.date().isoformat()]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def selected_number(self):
        row=self.table.currentRow(); return self.table.item(row,0).text() if row>=0 else None
    def add(self):
        d=CustomerDialog(self)
        if d.exec()!=QDialog.Accepted or not d.name.text().strip(): return
        with self.factory.begin() as s:
            x=Customer(customer_number=next_number(s,Customer,"CUS"),name=d.name.text().strip(),father_name=d.father.text().strip(),phone=d.phone.text().strip(),address=d.address.text().strip(),gender=d.gender.currentText(),notes=d.notes.toPlainText()); s.add(x); audit(s,self.username,"created","customers",x.name)
        self.refresh()
    def edit(self):
        n=self.selected_number()
        if not n: return
        with self.factory() as s: x=s.scalar(select(Customer).where(Customer.customer_number==n))
        if not x: return
        d=CustomerDialog(x,self)
        if d.exec()!=QDialog.Accepted:return
        with self.factory.begin() as s:
            x=s.scalar(select(Customer).where(Customer.customer_number==n)); x.name=d.name.text().strip(); x.father_name=d.father.text().strip(); x.phone=d.phone.text().strip(); x.address=d.address.text().strip(); x.gender=d.gender.currentText(); x.notes=d.notes.toPlainText(); audit(s,self.username,"updated","customers",n)
        self.refresh()
    def delete(self):
        n=self.selected_number()
        if not n or QMessageBox.question(self,"حذف","دا پېرودونکی حذف شي؟")!=QMessageBox.Yes:return
        with self.factory.begin() as s:
            x=s.scalar(select(Customer).where(Customer.customer_number==n));
            if x: s.delete(x); audit(s,self.username,"deleted","customers",n)
        self.refresh()


class MeasurementDialog(QDialog):
    FIELDS=["سینه","کمر","اوږدوالی","اوږه","آستین","غاړه","شلوار اوږدوالی","پتلون کمر","پتلون اوږدوالی"]
    def __init__(self, customers, parent=None):
        super().__init__(parent); self.setWindowTitle("نوې اندازه"); self.setMinimumWidth(600); form=QFormLayout(self)
        self.customer=QComboBox(); self.customer.addItems([f"{c.name} — {c.customer_number}" for c in customers]); self.customer_ids=[c.id for c in customers]
        self.garment=QComboBox(); self.garment.addItems(GARMENTS); self.unit=QComboBox(); self.unit.addItems(UNITS); self.notes=QLineEdit()
        self.fields={k:QLineEdit() for k in self.FIELDS}
        form.addRow("پېرودونکی",self.customer); form.addRow("د جامې ډول",self.garment); form.addRow("واحد",self.unit)
        grid=QGridLayout();
        for i,(k,w) in enumerate(self.fields.items()): grid.addWidget(QLabel(k),i//3*2,i%3*2); grid.addWidget(w,i//3*2,i%3*2+1)
        form.addRow(grid); form.addRow("یادښت",self.notes)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); form.addRow(b)
    def values(self): return {k: float(v.text() or 0) for k,v in self.fields.items()}


class MeasurementsPage(QWidget):
    def __init__(self,factory,username):
        super().__init__(); self.factory=factory; self.username=username; root=QVBoxLayout(self); h=QHBoxLayout(); h.addWidget(make_label("اندازې", "pageTitle")); h.addStretch(); b=QPushButton("＋ نوې اندازه"); b.clicked.connect(self.add); h.addWidget(b); root.addLayout(h)
        self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(["پېرودونکی","جامه","واحد","اندازه","نېټه","یادښت"]); configure_table(self.table); root.addWidget(self.table); self.refresh()
    def refresh(self):
        with self.factory() as s: rows=s.scalars(select(MeasurementProfile).order_by(MeasurementProfile.id.desc())).all()
        self.table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            vals=[x.customer.name,x.garment_type,x.unit,"، ".join(f"{k}: {v:g}" for k,v in x.values.items()),x.measured_at.isoformat(),x.notes]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def add(self):
        with self.factory() as s: customers=s.scalars(select(Customer).order_by(Customer.name)).all()
        if not customers: QMessageBox.information(self,"اندازې","لومړی پېرودونکی ثبت کړئ."); return
        d=MeasurementDialog(customers,self)
        if d.exec()!=QDialog.Accepted:return
        with self.factory.begin() as s:
            s.add(MeasurementProfile(customer_id=d.customer_ids[d.customer.currentIndex()],garment_type=d.garment.currentText(),unit=d.unit.currentText(),values_json=json.dumps(d.values(),ensure_ascii=False),notes=d.notes.text())); audit(s,self.username,"created","measurements","measurement")
        self.refresh()


class OrderDialog(QDialog):
    def __init__(self, customers, employees, parent=None):
        super().__init__(parent); self.setWindowTitle("نوی سفارش"); self.setMinimumWidth(600); form=QFormLayout(self)
        self.customer=QComboBox(); self.customer.addItems([f"{x.name} — {x.customer_number}" for x in customers]); self.customer_ids=[x.id for x in customers]
        self.garment=QComboBox(); self.garment.addItems(GARMENTS); self.design=QLineEdit(); self.delivery=QLineEdit(date.today().isoformat()); self.total=QDoubleSpinBox(); self.total.setRange(0,1e9); self.total.setDecimals(0)
        self.advance=QDoubleSpinBox(); self.advance.setRange(0,1e9); self.advance.setDecimals(0); self.tailor=QComboBox(); self.tailor.addItem("—"); self.tailor.addItems([x.name for x in employees]); self.notes=QTextEdit(); self.notes.setMaximumHeight(70)
        for w,t in [(self.customer,"پېرودونکی"),(self.garment,"جامه"),(self.design,"ډیزاین"),(self.delivery,"د سپارلو نېټه YYYY-MM-DD"),(self.total,"ټوله بیه"),(self.advance,"مخکینۍ پیسې"),(self.tailor,"ګنډونکی"),(self.notes,"یادښت")]: form.addRow(t,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); form.addRow(b)
    def parsed_date(self):
        try:return date.fromisoformat(self.delivery.text().strip())
        except:return date.today()


class OrdersPage(QWidget):
    def __init__(self,factory,username):
        super().__init__(); self.factory=factory; self.username=username; root=QVBoxLayout(self); h=QHBoxLayout(); h.addWidget(make_label("سفارشونه او تولید", "pageTitle")); h.addStretch(); self.search=QLineEdit(); self.search.setPlaceholderText("لټون"); self.search.textChanged.connect(self.refresh); h.addWidget(self.search)
        b=QPushButton("＋ نوی سفارش"); b.clicked.connect(self.add); h.addWidget(b); root.addLayout(h); root.addWidget(make_label("په سفارش دوه ځله کلیک وکړئ چې بل workflow پړاو ته لاړ شي.","muted")); self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(["شمېره","پېرودونکی","جامه","سپارلو نېټه","حالت","ګنډونکی","ټول","پاتې"]); configure_table(self.table); self.table.cellDoubleClicked.connect(self.advance); root.addWidget(self.table); self.refresh()
    def refresh(self):
        with self.factory() as s: rows=s.scalars(select(Order).order_by(Order.id.desc())).all()
        q=self.search.text().strip().lower(); rows=[x for x in rows if not q or q in f"{x.order_number} {x.customer.name} {x.garment} {x.status}".lower()]
        self.table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            vals=[x.order_number,x.customer.name,x.garment,x.delivery_date.isoformat(),x.status,x.assigned_tailor,money(x.total),money(x.remaining)]
            for c,v in enumerate(vals):self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def add(self):
        with self.factory() as s: customers=s.scalars(select(Customer).order_by(Customer.name)).all(); employees=s.scalars(select(Employee).where(Employee.active==True).order_by(Employee.name)).all()
        if not customers: QMessageBox.information(self,"سفارش","لومړی پېرودونکی ثبت کړئ."); return
        d=OrderDialog(customers,employees,self)
        if d.exec()!=QDialog.Accepted:return
        with self.factory.begin() as s:
            total=d.total.value(); advance=min(d.advance.value(),total); o=Order(order_number=next_number(s,Order,"ORD"),customer_id=d.customer_ids[d.customer.currentIndex()],garment=d.garment.currentText(),design=d.design.text(),delivery_date=d.parsed_date(),total=total,paid=advance,assigned_tailor=d.tailor.currentText().replace("—","").strip(),notes=d.notes.toPlainText()); s.add(o); s.flush()
            if advance>0:s.add(Payment(receipt_number=next_number(s,Payment,"PAY"),order_id=o.id,amount=advance,method="نغدې"))
            audit(s,self.username,"created","orders",o.order_number)
        self.refresh()
    def advance(self,row,_):
        number=self.table.item(row,0).text()
        with self.factory.begin() as s:
            o=s.scalar(select(Order).where(Order.order_number==number)); pos=WORKFLOW.index(o.status) if o.status in WORKFLOW else 0; o.status=WORKFLOW[min(pos+1,len(WORKFLOW)-1)]; audit(s,self.username,"status_changed","orders",f"{number} -> {o.status}")
        self.refresh()


class EmployeesPage(QWidget):
    def __init__(self,factory,username):
        super().__init__(); self.factory=factory; self.username=username; root=QVBoxLayout(self); h=QHBoxLayout(); h.addWidget(make_label("ګنډونکي او کارکوونکي", "pageTitle")); h.addStretch(); b=QPushButton("＋ نوی کارکوونکی"); b.clicked.connect(self.add); h.addWidget(b); root.addLayout(h); self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(["نوم","موبایل","دنده","تخصص","فعال"]); configure_table(self.table); root.addWidget(self.table); self.refresh()
    def refresh(self):
        with self.factory() as s: rows=s.scalars(select(Employee).order_by(Employee.id.desc())).all()
        self.table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            for c,v in enumerate([x.name,x.phone,x.position,x.specialization,"هو" if x.active else "نه"]): self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def add(self):
        d=QDialog(self); f=QFormLayout(d); name=QLineEdit(); phone=QLineEdit(); pos=QComboBox(); pos.addItems(["Tailor","Manager","Receptionist","Accountant","Other"]); spec=QLineEdit(); f.addRow("نوم",name);f.addRow("موبایل",phone);f.addRow("دنده",pos);f.addRow("تخصص",spec); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(d.accept);b.rejected.connect(d.reject);f.addRow(b)
        if d.exec()!=QDialog.Accepted or not name.text().strip():return
        with self.factory.begin() as s:s.add(Employee(name=name.text().strip(),phone=phone.text(),position=pos.currentText(),specialization=spec.text()));audit(s,self.username,"created","employees",name.text())
        self.refresh()


class PaymentsPage(QWidget):
    def __init__(self,factory,username):
        super().__init__(); self.factory=factory; self.username=username; root=QVBoxLayout(self); h=QHBoxLayout();h.addWidget(make_label("تادیات او رسیدونه", "pageTitle"));h.addStretch();b=QPushButton("＋ نوې تادیه");b.clicked.connect(self.add);h.addWidget(b);root.addLayout(h);self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(["رسید","سفارش","مقدار","طریقه","نېټه","پېرودونکی"]);configure_table(self.table);root.addWidget(self.table);self.refresh()
    def refresh(self):
        with self.factory() as s: rows=s.scalars(select(Payment).order_by(Payment.id.desc())).all(); orders={o.id:o for o in s.scalars(select(Order)).all()}
        self.table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            o=orders.get(x.order_id); vals=[x.receipt_number,o.order_number if o else "",money(x.amount),x.method,x.paid_at.strftime("%Y-%m-%d %H:%M"),o.customer.name if o else ""]
            for c,v in enumerate(vals):self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def add(self):
        with self.factory() as s: orders=s.scalars(select(Order).where(Order.status!="تحویل شوی").order_by(Order.id.desc())).all()
        if not orders:return
        d=QDialog(self);f=QFormLayout(d);order=QComboBox();order.addItems([f"{o.order_number} — {o.customer.name} — پاتې {money(o.remaining)}" for o in orders]);amount=QDoubleSpinBox();amount.setRange(1,1e9);amount.setDecimals(0);method=QComboBox();method.addItems(["نغدې","بانک","حواله"]);f.addRow("سفارش",order);f.addRow("مقدار",amount);f.addRow("طریقه",method);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(d.accept);b.rejected.connect(d.reject);f.addRow(b)
        if d.exec()!=QDialog.Accepted:return
        with self.factory.begin() as s:
            o=s.scalar(select(Order).where(Order.id==orders[order.currentIndex()].id)); amount_value=min(amount.value(),o.remaining); o.paid+=amount_value; p=Payment(receipt_number=next_number(s,Payment,"PAY"),order_id=o.id,amount=amount_value,method=method.currentText());s.add(p);audit(s,self.username,"created","payments",p.receipt_number)
        self.refresh()


class InventoryPage(QWidget):
    def __init__(self,factory,username):
        super().__init__();self.factory=factory;self.username=username;root=QVBoxLayout(self);h=QHBoxLayout();h.addWidget(make_label("ذخیره او مواد", "pageTitle"));h.addStretch();b=QPushButton("＋ نوی توکي");b.clicked.connect(self.add);h.addWidget(b);root.addLayout(h);self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(["توکي","کټګوري","مقدار","واحد","حد اقل","عرضه کوونکی"]);configure_table(self.table);root.addWidget(self.table);self.refresh()
    def refresh(self):
        with self.factory() as s:rows=s.scalars(select(InventoryItem).order_by(InventoryItem.id.desc())).all()
        self.table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            vals=[x.name,x.category,f"{x.quantity:g}",x.unit,f"{x.minimum_quantity:g}",x.supplier]
            for c,v in enumerate(vals):self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def add(self):
        d=QDialog(self);f=QFormLayout(d);name=QLineEdit();cat=QLineEdit();qty=QDoubleSpinBox();qty.setRange(0,1e9);unit=QLineEdit("متر");minimum=QDoubleSpinBox();minimum.setRange(0,1e9);supplier=QLineEdit();
        for w,t in [(name,"نوم"),(cat,"کټګوري"),(qty,"مقدار"),(unit,"واحد"),(minimum,"حد اقل"),(supplier,"عرضه کوونکی")]:f.addRow(t,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(d.accept);b.rejected.connect(d.reject);f.addRow(b)
        if d.exec()!=QDialog.Accepted:return
        with self.factory.begin() as s:s.add(InventoryItem(name=name.text(),category=cat.text(),quantity=qty.value(),unit=unit.text(),minimum_quantity=minimum.value(),supplier=supplier.text()));audit(s,self.username,"created","inventory",name.text())
        self.refresh()


class ExpensesPage(QWidget):
    def __init__(self,factory,username):
        super().__init__();self.factory=factory;self.username=username;root=QVBoxLayout(self);h=QHBoxLayout();h.addWidget(make_label("مصارف", "pageTitle"));h.addStretch();b=QPushButton("＋ نوی مصرف");b.clicked.connect(self.add);h.addWidget(b);root.addLayout(h);self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(["کټګوري","مقدار","نېټه","تشریح"]);configure_table(self.table);root.addWidget(self.table);self.refresh()
    def refresh(self):
        with self.factory() as s:rows=s.scalars(select(Expense).order_by(Expense.id.desc())).all()
        self.table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            for c,v in enumerate([x.category,money(x.amount),x.expense_date.isoformat(),x.description]):self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def add(self):
        d=QDialog(self);f=QFormLayout(d);cat=QLineEdit();amount=QDoubleSpinBox();amount.setRange(0,1e9);amount.setDecimals(0);desc=QLineEdit();f.addRow("کټګوري",cat);f.addRow("مقدار",amount);f.addRow("تشریح",desc);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(d.accept);b.rejected.connect(d.reject);f.addRow(b)
        if d.exec()!=QDialog.Accepted:return
        with self.factory.begin() as s:s.add(Expense(category=cat.text(),amount=amount.value(),description=desc.text()));audit(s,self.username,"created","expenses",cat.text())
        self.refresh()


class ReportsPage(QWidget):
    def __init__(self,factory):
        super().__init__();self.factory=factory;root=QVBoxLayout(self);root.addWidget(make_label("راپورونه", "pageTitle"));root.addWidget(make_label("د معلوماتو CSV، Excel او PDF راپورونه جوړ کړئ.","muted"));
        grid=QGridLayout();
        for i,(title,kind) in enumerate([("پېرودونکي CSV","customers"),("سفارشونه CSV","orders"),("تادیات CSV","payments"),("ذخیره CSV","inventory"),("مصارف CSV","expenses")]):
            b=QPushButton(title);b.clicked.connect(lambda _,k=kind:self.export_csv(k));grid.addWidget(b,i//2,i%2)
        pdf=QPushButton("د عمومي راپور PDF / چاپ مخکتنه");pdf.clicked.connect(self.preview_pdf);grid.addWidget(pdf,3,0,1,2);root.addLayout(grid);root.addStretch()
    def export_csv(self,kind):
        path,_=QFileDialog.getSaveFileName(self,"CSV راپور",f"{kind}_{date.today()}.csv","CSV (*.csv)");
        if not path:return
        with self.factory() as s:
            mapping={"customers":(Customer,["customer_number","name","phone","address"]),"orders":(Order,["order_number","garment","status","total","paid"]),"payments":(Payment,["receipt_number","amount","method","paid_at"]),"inventory":(InventoryItem,["name","category","quantity","unit","minimum_quantity"]),"expenses":(Expense,["category","amount","expense_date","description"])};model,fields=mapping[kind];rows=s.scalars(select(model)).all()
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f);w.writerow(fields)
            for x in rows:w.writerow([getattr(x,k) for k in fields])
        QMessageBox.information(self,"راپور","راپور جوړ شو.")
    def preview_pdf(self):
        doc=QTextDocument();doc.setHtml(self.report_html());printer=QPrinter(QPrinter.HighResolution);preview=QPrintPreviewDialog(printer,self);preview.paintRequested.connect(doc.print);preview.exec()
    def report_html(self):
        with self.factory() as s:
            customers=s.scalar(select(func.count(Customer.id))) or 0; orders=s.scalar(select(func.count(Order.id))) or 0; revenue=s.scalar(select(func.coalesce(func.sum(Payment.amount),0))) or 0; exp=s.scalar(select(func.coalesce(func.sum(Expense.amount),0))) or 0; outstanding=s.scalar(select(func.coalesce(func.sum(Order.total-Order.paid),0))) or 0
        return f"<html><body dir='rtl'><h1>د کارگاه عمومي راپور</h1><p>نېټه: {date.today()}</p><hr><p>ټول پېرودونکي: {customers}</p><p>ټول سفارشونه: {orders}</p><p>ټول عاید: {money(revenue)}</p><p>ټول مصارف: {money(exp)}</p><p>خالص: {money(revenue-exp)}</p><p>پاتې حساب: {money(outstanding)}</p></body></html>"


class SettingsPage(QWidget):
    def __init__(self,factory,username,window):
        super().__init__();self.factory=factory;self.username=username;self.window=window;root=QVBoxLayout(self);root.addWidget(make_label("تنظیمات او بیک اپ", "pageTitle"));form=QFormLayout();self.shop=QLineEdit();self.currency=QLineEdit();form.addRow("د کارگاه نوم",self.shop);form.addRow("اسعار",self.currency);root.addLayout(form);save=QPushButton("ذخیره تنظیمات");save.clicked.connect(self.save);root.addWidget(save);backup=QPushButton("بیک اپ جوړول");backup.clicked.connect(self.backup);root.addWidget(backup);restore=QPushButton("بیک اپ Restore");restore.clicked.connect(self.restore);root.addWidget(restore);root.addStretch();self.load()
    def load(self):
        with self.factory() as s:self.shop.setText(s.scalar(select(AppSetting.value).where(AppSetting.key=="shop_name")) or "د کارگاه");self.currency.setText(s.scalar(select(AppSetting.value).where(AppSetting.key=="currency")) or "AFN")
    def save(self):
        with self.factory.begin() as s:
            for k,v in [("shop_name",self.shop.text()),("currency",self.currency.text())]:
                x=s.get(AppSetting,k);x.value=v if x else v
                if not x:s.add(AppSetting(key=k,value=v))
            audit(s,self.username,"updated","settings","settings")
        QMessageBox.information(self,"تنظیمات","ذخیره شول.")
    def backup(self):
        BACKUP_DIR.mkdir(parents=True,exist_ok=True);target=BACKUP_DIR/f"TailoringBackup_{datetime.now():%Y-%m-%d_%H-%M}.db";shutil.copy2(DATABASE_PATH,target);QMessageBox.information(self,"بیک اپ",f"بیک اپ جوړ شو:\n{target}")
    def restore(self):
        path,_=QFileDialog.getOpenFileName(self,"بیک اپ انتخاب کړئ",str(BACKUP_DIR),"Database (*.db)")
        if not path or QMessageBox.question(self,"Restore","د اوسني معلوماتو پر ځای دا بیک اپ واچول شي؟")!=QMessageBox.Yes:return
        shutil.copy2(path,DATABASE_PATH);QMessageBox.information(self,"Restore","Restore بشپړ شو. سیستم به بیا خلاص شي.");self.window.close()


class MainWindow(QMainWindow):
    def __init__(self,factory,username):
        super().__init__();self.factory=factory;self.username=username;self.setWindowTitle("د کارگاه | Tailoring Management System");self.setMinimumSize(1280,800);self.setLayoutDirection(Qt.RightToLeft)
        central=QWidget();self.setCentralWidget(central);root=QHBoxLayout(central);root.setContentsMargins(0,0,0,0);root.setSpacing(0)
        sidebar=QFrame();sidebar.setObjectName("sidebar");side=QVBoxLayout(sidebar);side.addWidget(make_label("🧵 د کارگاه", "brand"));side.addWidget(make_label(f"کارن: {username}","muted"))
        self.nav=QListWidget();self.nav.setObjectName("nav");self.nav.setIconSize(QSize(22,22));side.addWidget(self.nav,1);logout=QPushButton("وتل");logout.clicked.connect(self.close);side.addWidget(logout);root.addWidget(sidebar)
        body=QWidget();bv=QVBoxLayout(body);bv.setContentsMargins(18,18,18,12)
        top=QFrame();top.setObjectName("topbar");th=QHBoxLayout(top);th.addWidget(make_label("Tailoring Management System", "pageTitle"));th.addStretch();th.addWidget(make_label(datetime.now().strftime("%Y-%m-%d"),"muted"));bv.addWidget(top)
        self.pages=QStackedWidget();bv.addWidget(self.pages,1);root.addWidget(body,1)
        defs=[("🏠 عمومي کتنه",DashboardPage(factory)),("👥 پېرودونکي",CustomersPage(factory,username)),("📏 اندازې",MeasurementsPage(factory,username)),("🧵 سفارشونه",OrdersPage(factory,username)),("👨‍🔧 ګنډونکي",EmployeesPage(factory,username)),("💰 تادیات",PaymentsPage(factory,username)),("📦 ذخیره",InventoryPage(factory,username)),("💸 مصارف",ExpensesPage(factory,username)),("📊 راپورونه",ReportsPage(factory)),("⚙ تنظیمات",SettingsPage(factory,username,self))]
        for title,page in defs:self.nav.addItem(QListWidgetItem(title));self.pages.addWidget(page)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex);self.nav.setCurrentRow(0);self.statusBar().showMessage("سیستم چمتو دی")


def main():
    app=QApplication(sys.argv);app.setApplicationName("TailoringManagementSystem");app.setStyle("Fusion");app.setStyleSheet(STYLE);app.setFont(QFont("Segoe UI",10));factory=init_database();login=LoginDialog(factory)
    if login.exec()!=QDialog.Accepted:return 0
    win=MainWindow(factory,login.username);win.show();return app.exec()


if __name__=="__main__":sys.exit(main())
