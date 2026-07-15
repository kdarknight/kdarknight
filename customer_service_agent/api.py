"""FastAPI application exposing chat, knowledge-base, and health endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from .config import Settings, get_settings
from .database import BusinessDataStore
from .graph import build_customer_service_graph
from .llm import build_chat_model
from .memory import RedisConversationMemory
from .vector_store import PgVectorKnowledgeBase, build_knowledge_base


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    intent: str | None = None
    ticket_id: int | None = None
    tool_result: str | None = None


class IngestDocument(BaseModel):
    content: str = Field(min_length=1)
    source: str = "api"
    title: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: list[IngestDocument]


class IngestResponse(BaseModel):
    indexed: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    store = BusinessDataStore(settings.db_url)
    if settings.auto_init_db:
        store.create_schema()
        if settings.seed_demo_data:
            store.seed_demo_data()
    kb = build_knowledge_base(settings)
    if isinstance(kb, PgVectorKnowledgeBase):
        kb.create_schema()
    app.state.settings = settings
    app.state.store = store
    app.state.kb = kb
    app.state.llm = build_chat_model(settings)
    app.state.memory = RedisConversationMemory(settings)
    yield


app = FastAPI(title="Enterprise Intelligent Customer Service API", version="1.0.0", lifespan=lifespan)


def settings_dep() -> Settings:
    return get_settings()


@app.get("/health")
def health(settings: Settings = Depends(settings_dep)) -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    conversation_id = request.conversation_id or str(uuid4())
    messages = app.state.memory.load(conversation_id) if request.conversation_id else []
    for item in request.history[-get_settings().conversation_window :]:
        role = item.get("role", "user")
        content = item.get("content", "")
        messages.append(AIMessage(content=content) if role == "assistant" else HumanMessage(content=content))
    messages.append(HumanMessage(content=request.message))
    graph = build_customer_service_graph(llm=app.state.llm, kb=app.state.kb, store=app.state.store)
    result = graph.invoke({"messages": messages})
    app.state.memory.append_turn(conversation_id, request.message, result["answer"])
    return ChatResponse(
        conversation_id=conversation_id,
        answer=result["answer"],
        intent=result.get("intent"),
        ticket_id=result.get("ticket_id"),
        tool_result=result.get("tool_result"),
    )


@app.post("/knowledge/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    if not isinstance(app.state.kb, PgVectorKnowledgeBase):
        raise HTTPException(status_code=400, detail="Vector ingestion requires PostgreSQL + pgvector configuration")
    docs = [
        Document(page_content=doc.content, metadata={**doc.metadata, "source": doc.source, "title": doc.title})
        for doc in request.documents
    ]
    return IngestResponse(indexed=app.state.kb.add_documents(docs))
