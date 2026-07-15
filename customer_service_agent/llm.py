"""LLM and embedding factories for OpenAI-compatible Qwen/DeepSeek endpoints."""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .config import Settings, get_settings
from .graph import RuleBasedChatModel


def build_chat_model(settings: Settings | None = None):
    cfg = settings or get_settings()
    if cfg.fake_llm or os.getenv("CUSTOMER_SERVICE_FAKE_LLM") == "1":
        return RuleBasedChatModel()
    api_key = cfg.llm_api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    return ChatOpenAI(
        model=cfg.llm_model,
        api_key=api_key,
        base_url=cfg.llm_base_url,
        temperature=cfg.llm_temperature,
    )


def build_embeddings(settings: Settings | None = None) -> OpenAIEmbeddings:
    cfg = settings or get_settings()
    api_key = cfg.embedding_api_key or cfg.llm_api_key or os.getenv("DASHSCOPE_API_KEY")
    return OpenAIEmbeddings(model=cfg.embedding_model, api_key=api_key, base_url=cfg.embedding_base_url)
