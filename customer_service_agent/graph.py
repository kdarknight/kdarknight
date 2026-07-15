"""LangGraph orchestration for an intelligent customer service agent."""

from __future__ import annotations

import os
from typing import Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from .database import BusinessDataStore, get_default_store
from .knowledge_base import SimpleKnowledgeBase
from .tools import extract_order_id, lookup_order_in_store

Intent = Literal["order_status", "refund", "human_handoff", "general"]


class CustomerServiceState(TypedDict, total=False):
    """State shared by all LangGraph nodes."""

    messages: list[BaseMessage]
    intent: Intent
    context: str
    tool_result: str
    answer: str
    handoff_reason: str
    ticket_id: int


class RuleBasedChatModel:
    """Small offline fallback used for local demos and tests."""

    def invoke(self, messages: list[BaseMessage] | str) -> AIMessage:
        text = messages[-1].content if isinstance(messages, list) else messages
        return AIMessage(content=f"您好，我已收到：{text}\n我会根据当前客服流程为您处理。")


def get_chat_model() -> BaseChatModel | RuleBasedChatModel:
    """Create the configured chat model.

    Set CUSTOMER_SERVICE_FAKE_LLM=1 to avoid external API calls in local demos.
    """

    if os.getenv("CUSTOMER_SERVICE_FAKE_LLM") == "1":
        return RuleBasedChatModel()
    return ChatOpenAI(
        model=os.getenv("CUSTOMER_SERVICE_LLM_MODEL", os.getenv("CUSTOMER_SERVICE_MODEL", "qwen-plus")),
        api_key=os.getenv("CUSTOMER_SERVICE_LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("CUSTOMER_SERVICE_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        temperature=float(os.getenv("CUSTOMER_SERVICE_LLM_TEMPERATURE", "0.2")),
    )


def classify_intent(state: CustomerServiceState) -> CustomerServiceState:
    latest = _latest_user_message(state).lower()
    if any(keyword in latest for keyword in ["人工", "真人", "投诉", "主管"]):
        intent: Intent = "human_handoff"
    elif any(keyword in latest for keyword in ["订单", "物流", "快递", "到哪", "发货"]):
        intent = "order_status"
    elif any(keyword in latest for keyword in ["退款", "退货", "退换", "售后"]):
        intent = "refund"
    else:
        intent = "general"
    return {**state, "intent": intent}


def retrieve_policy(state: CustomerServiceState, kb: SimpleKnowledgeBase | None = None) -> CustomerServiceState:
    retriever = kb or SimpleKnowledgeBase()
    docs = retriever.retrieve(_latest_user_message(state))
    context = "\n".join(f"- {doc.page_content}" for doc in docs)
    return {**state, "context": context}


def query_order_tool(state: CustomerServiceState, store: BusinessDataStore | None = None) -> CustomerServiceState:
    latest = _latest_user_message(state)
    order_id = extract_order_id(latest)
    if not order_id:
        result = "用户询问订单状态，但尚未提供订单号。请礼貌地索要订单编号。"
    else:
        result = lookup_order_in_store(order_id, store=store)
    return {**state, "tool_result": result}


def prepare_handoff(state: CustomerServiceState, store: BusinessDataStore | None = None) -> CustomerServiceState:
    reason = "用户明确要求人工客服或存在投诉升级信号。"
    transcript = "\n".join(str(message.content) for message in state.get("messages", []))
    repository = store or get_default_store()
    ticket_id = repository.create_handoff_ticket(transcript=transcript, subject=reason)
    return {
        **state,
        "handoff_reason": reason,
        "ticket_id": ticket_id,
        "answer": f"已为您转接人工客服，请稍候。工单 #{ticket_id} 已创建，我会同步当前对话摘要。",
    }


def generate_answer(
    state: CustomerServiceState,
    llm: BaseChatModel | RuleBasedChatModel | None = None,
) -> CustomerServiceState:
    model = llm or get_chat_model()
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content=(
                    "你是电商平台的智能客服。回答要礼貌、简洁、可执行。"
                    "如果信息不足，先说明缺少什么；不要编造订单、政策或承诺。"
                )
            ),
            (
                "human",
                "用户问题：{question}\n意图：{intent}\n知识库上下文：{context}\n工具结果：{tool_result}\n请生成最终客服回复。",
            ),
        ]
    )
    chain = prompt | model
    response = chain.invoke(
        {
            "question": _latest_user_message(state),
            "intent": state.get("intent", "general"),
            "context": state.get("context", ""),
            "tool_result": state.get("tool_result", ""),
        }
    )
    answer = response.content if isinstance(response.content, str) else str(response.content)
    return {**state, "answer": answer}


def route_by_intent(state: CustomerServiceState) -> str:
    if state["intent"] == "human_handoff":
        return "handoff"
    if state["intent"] == "order_status":
        return "order_tool"
    return "retrieve"


def build_customer_service_graph(
    llm: BaseChatModel | RuleBasedChatModel | None = None,
    kb: SimpleKnowledgeBase | None = None,
    store: BusinessDataStore | None = None,
):
    """Build and compile the customer service workflow graph."""

    workflow = StateGraph(CustomerServiceState)
    workflow.add_node("classify", classify_intent)
    workflow.add_node("retrieve", lambda state: retrieve_policy(state, kb=kb))
    data_store = store or get_default_store()
    workflow.add_node("order_tool", lambda state: query_order_tool(state, store=data_store))
    workflow.add_node("handoff", lambda state: prepare_handoff(state, store=data_store))
    workflow.add_node("answer", lambda state: generate_answer(state, llm=llm))

    workflow.set_entry_point("classify")
    workflow.add_conditional_edges(
        "classify",
        route_by_intent,
        {"handoff": "handoff", "order_tool": "order_tool", "retrieve": "retrieve"},
    )
    workflow.add_edge("retrieve", "answer")
    workflow.add_edge("order_tool", "answer")
    workflow.add_edge("answer", END)
    workflow.add_edge("handoff", END)
    return workflow.compile()


def answer_customer(question: str, llm: BaseChatModel | RuleBasedChatModel | None = None) -> str:
    graph = build_customer_service_graph(llm=llm)
    result = graph.invoke({"messages": [HumanMessage(content=question)]})
    return result["answer"]


def _latest_user_message(state: CustomerServiceState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""
