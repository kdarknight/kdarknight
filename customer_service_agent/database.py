"""MySQL-backed business data access for the customer service agent.

The module keeps all SQL in one place so graph/tool code can work with business
objects instead of raw database rows.  A MySQL DSN can be supplied with
``CUSTOMER_SERVICE_DB_URL``; otherwise a local SQLite file is used for quick
experiments and tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DEFAULT_SQLITE_PATH = Path("customer_service.db")
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"


class Base(DeclarativeBase):
    """Base class for ORM models."""


class OrderStatus(str, Enum):
    pending = "pending"
    picking = "picking"
    shipped = "shipped"
    delivered = "delivered"
    refunding = "refunding"
    refunded = "refunded"


class Customer(Base):
    """Customer profile used by service representatives and automations."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    membership_level: Mapped[str] = mapped_column(String(32), default="普通会员")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    tickets: Mapped[list["ServiceTicket"]] = relationship(back_populates="customer")


class Order(Base):
    """Order business data that powers order-status conversations."""

    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    status: Mapped[OrderStatus] = mapped_column(SQLEnum(OrderStatus), default=OrderStatus.pending)
    item_name: Mapped[str] = mapped_column(String(160))
    logistics_status: Mapped[str] = mapped_column(Text)
    refund_status: Mapped[str | None] = mapped_column(String(160), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    customer: Mapped[Customer | None] = relationship(back_populates="orders")


class ServiceTicket(Base):
    """Human handoff ticket created when automation should escalate."""

    __tablename__ = "service_tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default="chat")
    status: Mapped[str] = mapped_column(String(32), default="open")
    subject: Mapped[str] = mapped_column(String(160))
    transcript: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    customer: Mapped[Customer | None] = relationship(back_populates="tickets")


@dataclass(frozen=True)
class OrderSnapshot:
    order_id: str
    status: OrderStatus
    item_name: str
    logistics_status: str
    refund_status: str | None
    customer_name: str | None = None
    membership_level: str | None = None

    def to_customer_message(self) -> str:
        customer_prefix = f"{self.customer_name}，" if self.customer_name else ""
        refund_part = f"；售后状态：{self.refund_status}" if self.refund_status else ""
        return (
            f"{customer_prefix}订单 {self.order_id}（{self.item_name}）当前状态为 {self.status.value}，"
            f"物流信息：{self.logistics_status}{refund_part}。"
        )


class BusinessDataStore:
    """Repository for customer-service business data."""

    def __init__(self, db_url: str | None = None, *, echo: bool = False):
        self.db_url = db_url or os.getenv("CUSTOMER_SERVICE_DB_URL", DEFAULT_DB_URL)
        self.engine = create_engine(self.db_url, echo=echo, pool_pre_ping=True)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def seed_demo_data(self) -> None:
        """Insert deterministic demo rows when the database is empty."""

        with self.session_factory() as session:
            if session.scalar(select(Customer.id).limit(1)) is not None:
                return
            customer = Customer(phone="13800000000", name="王女士", membership_level="金卡会员")
            session.add(customer)
            session.flush()
            session.add_all(
                [
                    Order(
                        order_id="A1001",
                        customer_id=customer.id,
                        status=OrderStatus.shipped,
                        item_name="降噪耳机",
                        logistics_status="已到达上海分拨中心，预计明天送达",
                    ),
                    Order(
                        order_id="A1002",
                        customer_id=customer.id,
                        status=OrderStatus.picking,
                        item_name="机械键盘",
                        logistics_status="仓库正在拣货，预计 24 小时内发出",
                    ),
                    Order(
                        order_id="R2001",
                        customer_id=customer.id,
                        status=OrderStatus.refunding,
                        item_name="智能手表",
                        logistics_status="退货包裹已签收",
                        refund_status="退款审核已通过，预计 1-3 个工作日原路返回",
                    ),
                ]
            )
            session.commit()

    def get_order(self, order_id: str) -> OrderSnapshot | None:
        with self.session_factory() as session:
            order = session.get(Order, order_id.strip().upper())
            if not order:
                return None
            return _to_snapshot(order)

    def create_handoff_ticket(self, transcript: str, subject: str = "智能客服转人工") -> int:
        with self.session_factory() as session:
            ticket = ServiceTicket(subject=subject, transcript=transcript)
            session.add(ticket)
            session.commit()
            return ticket.id


def build_engine(db_url: str | None = None) -> Engine:
    return create_engine(db_url or os.getenv("CUSTOMER_SERVICE_DB_URL", DEFAULT_DB_URL), pool_pre_ping=True)


def _to_snapshot(order: Order) -> OrderSnapshot:
    return OrderSnapshot(
        order_id=order.order_id,
        status=order.status,
        item_name=order.item_name,
        logistics_status=order.logistics_status,
        refund_status=order.refund_status,
        customer_name=order.customer.name if order.customer else None,
        membership_level=order.customer.membership_level if order.customer else None,
    )


def get_default_store() -> BusinessDataStore:
    store = BusinessDataStore()
    if os.getenv("CUSTOMER_SERVICE_AUTO_INIT_DB", "1") == "1":
        store.create_schema()
        if os.getenv("CUSTOMER_SERVICE_SEED_DEMO_DATA", "1") == "1":
            store.seed_demo_data()
    return store
