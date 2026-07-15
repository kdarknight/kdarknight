import pytest

pytest.importorskip("langchain_core")
pytest.importorskip("langgraph")
pytest.importorskip("sqlalchemy")

from langchain_core.messages import HumanMessage

from customer_service_agent.database import BusinessDataStore
from customer_service_agent.graph import RuleBasedChatModel, build_customer_service_graph


def make_store(tmp_path):
    store = BusinessDataStore(f"sqlite:///{tmp_path / 'business.db'}")
    store.create_schema()
    store.seed_demo_data()
    return store


def invoke(question: str, tmp_path):
    graph = build_customer_service_graph(llm=RuleBasedChatModel(), store=make_store(tmp_path))
    return graph.invoke({"messages": [HumanMessage(content=question)]})


def test_order_status_uses_order_tool(tmp_path):
    result = invoke("我的订单 A1001 到哪了？", tmp_path)

    assert result["intent"] == "order_status"
    assert "上海分拨中心" in result["tool_result"]
    assert result["answer"]


def test_refund_question_retrieves_policy(tmp_path):
    result = invoke("我想申请退款，多久能到账？", tmp_path)

    assert result["intent"] == "refund"
    assert "退款" in result["context"]
    assert result["answer"]


def test_human_handoff_short_circuits_answer_generation(tmp_path):
    result = invoke("我要找人工客服投诉", tmp_path)

    assert result["intent"] == "human_handoff"
    assert "转接人工客服" in result["answer"]
    assert result["handoff_reason"]
    assert result["ticket_id"] == 1
