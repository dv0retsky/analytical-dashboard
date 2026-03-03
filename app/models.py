from __future__ import annotations

import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    Date,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class HREventType(str, enum.Enum):
    hire = "Найм"
    fire = "Увольнение"
    vacation = "Отпуск"
    sick_leave = "Больничный"


class DocumentStatus(str, enum.Enum):
    uploaded = "Загружен"
    signed = "Подписан"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    sales: Mapped[list["Sale"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)

    store: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    employee_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    product: Mapped["Product"] = relationship(back_populates="sales")

    __table_args__ = (
        Index("ix_sales_date_store", "sale_date", "store"),
    )


class HREvent(Base):
    __tablename__ = "hr_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    event_type: Mapped[HREventType] = mapped_column(Enum(HREventType), nullable=False, index=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_hr_events_start_type", "start_date", "event_type"),
    )


class HRDocument(Base):
    __tablename__ = "hr_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)

    doc_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), nullable=False, index=True)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)