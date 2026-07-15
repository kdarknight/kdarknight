import pytest

pytest.importorskip("sqlalchemy")

from customer_service_agent.database import BusinessDataStore


def test_seed_and_query_order(tmp_path):
    store = BusinessDataStore(f"sqlite:///{tmp_path / 'business.db'}")
    store.create_schema()
    store.seed_demo_data()

    snapshot = store.get_order("A1001")

    assert snapshot is not None
    assert snapshot.customer_name == "王女士"
    assert "上海分拨中心" in snapshot.logistics_status


def test_create_handoff_ticket(tmp_path):
    store = BusinessDataStore(f"sqlite:///{tmp_path / 'business.db'}")
    store.create_schema()

    ticket_id = store.create_handoff_ticket("用户要求转人工")

    assert ticket_id == 1
