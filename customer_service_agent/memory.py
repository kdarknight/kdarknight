"""Conversation memory backed by Redis for multi-turn customer-service chats."""

from __future__ import annotations

import json
from dataclasses import dataclass

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from redis import Redis

from .config import Settings, get_settings


@dataclass
class RedisConversationMemory:
    """Stores compact chat history per conversation id with TTL expiration."""

    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or get_settings()
        self.client = Redis.from_url(self.settings.redis_url, decode_responses=True)
        self.ttl_seconds = max(self.settings.cache_ttl_seconds * 24, 3600)

    def load(self, conversation_id: str) -> list[BaseMessage]:
        raw_items = self.client.lrange(self._key(conversation_id), -self.settings.conversation_window, -1)
        messages: list[BaseMessage] = []
        for raw in raw_items:
            item = json.loads(raw)
            content = item.get("content", "")
            messages.append(AIMessage(content=content) if item.get("role") == "assistant" else HumanMessage(content=content))
        return messages

    def append_turn(self, conversation_id: str, user_message: str, assistant_message: str) -> None:
        key = self._key(conversation_id)
        pipe = self.client.pipeline()
        pipe.rpush(key, json.dumps({"role": "user", "content": user_message}, ensure_ascii=False))
        pipe.rpush(key, json.dumps({"role": "assistant", "content": assistant_message}, ensure_ascii=False))
        pipe.ltrim(key, -self.settings.conversation_window, -1)
        pipe.expire(key, self.ttl_seconds)
        pipe.execute()

    @staticmethod
    def _key(conversation_id: str) -> str:
        return f"cs:conversation:{conversation_id}"
