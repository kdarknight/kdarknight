"""Tools used by the customer service graph."""

from __future__ import annotations

import re
from typing import Annotated

from langchain_core.tools import tool

from .database import BusinessDataStore, get_default_store


def lookup_order_in_store(order_id: str, store: BusinessDataStore | None = None) -> str:
    """Query the business database for an order and format it for customers."""

    normalized = order_id.strip().upper()
    repository = store or get_default_store()
    snapshot = repository.get_order(normalized)
    if snapshot is None:
        return f"未查询到订单 {normalized}，请确认订单号是否正确。"
    return snapshot.to_customer_message()


@tool
def lookup_order(order_id: Annotated[str, "订单编号，例如 A1001"]) -> str:
    """查询 MySQL 业务数据库中的订单或退款单状态。"""

    return lookup_order_in_store(order_id)


def extract_order_id(text: str) -> str | None:
    match = re.search(r"\b[A-Z]\d{4}\b", text.upper())
    return match.group(0) if match else None
