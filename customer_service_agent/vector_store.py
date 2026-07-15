"""PostgreSQL + pgvector knowledge-base indexing and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document
from sqlalchemy import JSON, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import UserDefinedType

from .config import Settings, get_settings
from .knowledge_base import SimpleKnowledgeBase
from .llm import build_embeddings


class Vector(UserDefinedType):
    """SQLAlchemy type wrapper for pgvector columns."""

    cache_ok = True

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dimensions})"


class VectorBase(DeclarativeBase):
    pass


class KnowledgeChunk(VectorBase):
    """A chunk of approved enterprise knowledge with an embedding."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(256), index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    content: Mapped[str] = mapped_column(Text)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(get_settings().embedding_dimension))


@dataclass
class PgVectorKnowledgeBase:
    """Production retriever backed by PostgreSQL pgvector."""

    db_url: str | None = None
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or get_settings()
        self.engine = create_engine(self.db_url or self.settings.db_url, pool_pre_ping=True)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        self.embeddings = build_embeddings(self.settings)

    def create_schema(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        VectorBase.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"))

    def add_documents(self, documents: list[Document], *, source: str = "manual") -> int:
        texts = [doc.page_content for doc in documents]
        vectors = self.embeddings.embed_documents(texts)
        with self.session_factory() as session:
            for doc, vector in zip(documents, vectors, strict=True):
                session.add(
                    KnowledgeChunk(
                        source=str(doc.metadata.get("source", source)),
                        title=str(doc.metadata.get("title", doc.metadata.get("topic", ""))),
                        content=doc.page_content,
                        chunk_metadata=dict(doc.metadata),
                        embedding=vector,
                    )
                )
            session.commit()
        return len(documents)

    def retrieve(self, query: str, limit: int = 4) -> list[Document]:
        vector = self.embeddings.embed_query(query)
        vector_literal = "[" + ",".join(str(x) for x in vector) + "]"
        sql = text(
            "SELECT content, chunk_metadata FROM knowledge_chunks "
            "ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit"
        )
        with Session(self.engine) as session:
            rows = session.execute(sql, {"embedding": vector_literal, "limit": limit}).mappings().all()
        return [Document(page_content=row["content"], metadata=row["chunk_metadata"] or {}) for row in rows]


def build_knowledge_base(settings: Settings | None = None):
    cfg = settings or get_settings()
    if cfg.db_url.startswith("sqlite") or cfg.fake_llm:
        return SimpleKnowledgeBase()
    return PgVectorKnowledgeBase(settings=cfg)
