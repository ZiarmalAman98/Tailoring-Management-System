from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


APP_NAME = "TailoringManagementSystem"
DATA_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
DATA_DIR = DATA_ROOT / "data"
BACKUP_DIR = DATA_ROOT / "backups"
DOCUMENT_DIR = DATA_ROOT / "documents"
IMAGE_DIR = DATA_ROOT / "images"
LOG_DIR = DATA_ROOT / "logs"
DATABASE_PATH = DATA_DIR / "tailoring.db"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="Super Admin")
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=True)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    father_name: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(50), index=True)
    address: Mapped[str] = mapped_column(String(240), default="")
    gender: Mapped[str] = mapped_column(String(30), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    measurements: Mapped[list["MeasurementProfile"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class MeasurementProfile(Base):
    __tablename__ = "measurement_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    garment_type: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(20), default="cm")
    values_json: Mapped[str] = mapped_column(Text, default="{}")
    measured_at: Mapped[date] = mapped_column(Date, default=date.today)
    notes: Mapped[str] = mapped_column(Text, default="")
    customer: Mapped[Customer] = relationship(back_populates="measurements", lazy="joined")

    @property
    def values(self) -> dict[str, float]:
        return json.loads(self.values_json or "{}")


class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(50), default="")
    position: Mapped[str] = mapped_column(String(80), default="Tailor")
    specialization: Mapped[str] = mapped_column(String(160), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    garment: Mapped[str] = mapped_column(String(120))
    design: Mapped[str] = mapped_column(String(120), default="")
    delivery_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(80), default="نوی فرمایش", index=True)
    total: Mapped[float] = mapped_column(Float, default=0)
    paid: Mapped[float] = mapped_column(Float, default=0)
    assigned_tailor: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer: Mapped[Customer] = relationship(back_populates="orders", lazy="joined")

    @property
    def remaining(self) -> float:
        return max(0, self.total - self.paid)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_number: Mapped[str] = mapped_column(String(30), unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(40), default="نغدې")
    paid_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80), default="")
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(30), default="متر")
    minimum_quantity: Mapped[float] = mapped_column(Float, default=0)
    supplier: Mapped[str] = mapped_column(String(160), default="")


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(80))
    amount: Mapped[float] = mapped_column(Float)
    expense_date: Mapped[date] = mapped_column(Date, default=date.today)
    description: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(120))
    module: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        candidate = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return secrets.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def init_database() -> sessionmaker[Session]:
    for path in (DATA_DIR, BACKUP_DIR, DOCUMENT_DIR, IMAGE_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{DATABASE_PATH}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        if session.scalar(select(User).where(User.username == "admin")) is None:
            session.add(User(username="admin", password_hash=_password_hash("admin123"), role="Super Admin"))
        if session.scalar(select(AppSetting).where(AppSetting.key == "language")) is None:
            session.add_all(
                [
                    AppSetting(key="language", value="ps"),
                    AppSetting(key="currency", value="AFN"),
                    AppSetting(key="shop_name", value="د کارگاه"),
                ]
            )

        # Create a complete demo dataset only on a fresh database.
        if session.scalar(select(Customer).limit(1)) is None:
            demo_customers = [
                ("احمد خان", "محمد خان", "0700 100 001", "جلال آباد"),
                ("فرید احمد", "عبدالله", "0700 100 002", "جلال آباد"),
                ("رحیم الله", "حبیب الله", "0700 100 003", "بهسود"),
                ("حمیدالله", "نورمحمد", "0700 100 004", "کامې"),
                ("سعید احمد", "کریم", "0700 100 005", "سره رود"),
                ("نعمت الله", "عبدالودود", "0700 100 006", "جلال آباد"),
                ("محمود خان", "رحمت الله", "0700 100 007", "بټي کوټ"),
                ("جاوید احمد", "حیات الله", "0700 100 008", "رودات"),
                ("عبدالصبور", "عبدالکریم", "0700 100 009", "جلال آباد"),
                ("شمس الرحمن", "غلام نبي", "0700 100 010", "کامه"),
                ("مریم احمدي", "عبدالکریم", "0700 100 011", "جلال آباد"),
                ("زینب خان", "محمد یوسف", "0700 100 012", "جلال آباد"),
                ("سمیرا احمد", "نورالدین", "0700 100 013", "بهسود"),
                ("فرشته رحماني", "عبدالحمید", "0700 100 014", "جلال آباد"),
                ("لیلا محمدي", "عبدالحق", "0700 100 015", "سره رود"),
                ("شګوفه خان", "احمد شاه", "0700 100 016", "جلال آباد"),
                ("نازیه احمد", "عبدالودود", "0700 100 017", "کامه"),
                ("مریم جان", "رحیم الله", "0700 100 018", "جلال آباد"),
                ("رویا سعیدي", "حبیب الرحمن", "0700 100 019", "رودات"),
                ("عایشه محمدي", "محمد نعیم", "0700 100 020", "جلال آباد"),
            ]
            garments = [
                "شلوار کمیس", "سوټ", "کمیس", "پتلون", "کورتۍ",
                "ښځینه جامې", "کوټ", "واسکټ", "شلوار کمیس", "سوټ",
            ]
            statuses = [
                "نوی فرمایش", "د اندازه اخیستل شوې", "د پرې کولو په مرحله کې",
                "د ګنډلو په مرحله کې", "د فټینګ په مرحله کې", "QC", "بشپړ شوی", "تحویل شوی",
            ]
            tailors = ["احمد", "فرید", "رحیم", "حمید", "سعید"]
            for i, (name, father, phone, address) in enumerate(demo_customers, start=1):
                gender = "ښځینه" if i > 10 else "نارینه"
                customer = Customer(
                    customer_number=f"CUS-{i:06d}",
                    name=name,
                    father_name=father,
                    phone=phone,
                    address=address,
                    gender=gender,
                    notes="نمونه معلومات (Demo)",
                )
                session.add(customer)
                session.flush()

                garment = garments[(i - 1) % len(garments)]
                total = 1800 + ((i * 350) % 4200)
                paid = total if i % 4 == 0 else round(total * (0.45 if i % 3 == 0 else 0.60), 2)
                order = Order(
                    order_number=f"ORD-{i:06d}",
                    customer_id=customer.id,
                    garment=garment,
                    design=f"Demo Design {i}",
                    delivery_date=date.today() + timedelta(days=(i % 14) + 1),
                    status=statuses[(i - 1) % len(statuses)],
                    total=total,
                    paid=paid,
                    assigned_tailor=tailors[(i - 1) % len(tailors)],
                    notes="نمونه فرمایش د Demo لپاره",
                )
                session.add(order)
                session.flush()

                values = {
                    "اوږدوالی": float(70 + (i % 8)),
                    "سینه": float(90 + (i % 10)),
                    "ملا": float(78 + (i % 9)),
                    "اوږه": float(40 + (i % 5)),
                    "آستین": float(58 + (i % 7)),
                }
                session.add(
                    MeasurementProfile(
                        customer_id=customer.id,
                        garment_type=garment,
                        unit="cm",
                        values_json=json.dumps(values, ensure_ascii=False),
                        measured_at=date.today(),
                        notes="نمونه اندازه (Demo)",
                    )
                )
                session.add(
                    Payment(
                        receipt_number=f"REC-{i:06d}",
                        order_id=order.id,
                        amount=paid,
                        method="نغدې" if i % 2 else "بانکي",
                        paid_at=datetime.utcnow(),
                    )
                )

            session.add_all(
                [
                    InventoryItem(name="سپین لینن", category="ټوکر", quantity=28, unit="متر", minimum_quantity=10, supplier="کابل ټوکر"),
                    InventoryItem(name="تور سوټ ټوکر", category="ټوکر", quantity=18, unit="متر", minimum_quantity=8, supplier="جلال آباد ټوکر"),
                    InventoryItem(name="د ګنډلو تار", category="لوازم", quantity=6, unit="قرطاسیه", minimum_quantity=8, supplier="مېرویس سنټر"),
                ]
            )
    return factory


def next_number(session: Session, model: type[Any], prefix: str) -> str:
    total = session.scalar(select(func.count(model.id))) or 0
    return f"{prefix}-{int(total) + 1:06d}"


def audit(session: Session, username: str, action: str, module: str, description: str) -> None:
    session.add(AuditLog(username=username, action=action, module=module, description=description))
