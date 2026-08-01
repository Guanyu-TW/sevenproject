"""Demand-understanding layer.

The rest of the app only ever talks to :class:`AIProvider`, so swapping the
mock for a real LLM later is a one-line change in ``settings.AI_PROVIDER`` plus
one new subclass. Nothing above this module knows which provider is in play.

The interface is intentionally synchronous: the API layer uses a synchronous
SQLAlchemy session, and FastAPI already runs sync endpoints in a worker thread,
so a blocking HTTP call to an LLM here will not stall the event loop.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Callable, ClassVar

from app.core.config import settings
from app.schemas.ai import DemandAnalysis, MissingField

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Contract every demand-understanding backend must satisfy."""

    #: Short identifier recorded on the task so results stay traceable.
    name: ClassVar[str]

    @abstractmethod
    def analyze_demand(self, prompt: str) -> DemandAnalysis:
        """Turn free-form resident input into a structured demand."""
        raise NotImplementedError


class MockAIProvider(AIProvider):
    """Deterministic stand-in used until a real LLM is wired up.

    It ignores the semantics of ``prompt`` on purpose and always returns the
    same fixture, which keeps the frontend and the persistence path testable
    without an API key or network access. The original prompt is still echoed
    back so the UI can show what was submitted.
    """

    name: ClassVar[str] = "mock"

    def analyze_demand(self, prompt: str) -> DemandAnalysis:
        if settings.MOCK_AI_LATENCY_MS > 0:
            # Makes the frontend loading state observable during a demo.
            time.sleep(settings.MOCK_AI_LATENCY_MS / 1000)

        logger.info("MockAIProvider handling prompt (%d chars)", len(prompt))

        return DemandAnalysis(
            title="廚房水龍頭漏水",
            summary="廚房水龍頭底座持續滴水，疑似墊片老化，需要師傅到場檢修並更換零件。",
            category_code="plumbing",
            confidence=0.82,
            parsed_data={
                "service_type": "faucet_leak_repair",
                "budget": {
                    "amount": 2000,
                    "currency": "TWD",
                    "note": "住戶提到預算約兩千元",
                },
                "location": {
                    "city": "嘉義市",
                    "district": None,
                    "address": None,
                },
                "urgency": "normal",
                "preferred_time": None,
                "contact": {"name": None, "phone": None},
                "attachments": [],
                "keywords": ["水龍頭", "漏水", "廚房"],
            },
            missing_fields=[
                MissingField(
                    field="address",
                    label="地址",
                    reason="只知道嘉義市，需要完整地址才能派工。",
                    required=True,
                ),
                MissingField(
                    field="photos",
                    label="照片",
                    reason="漏水處的照片可以讓師傅先判斷零件與報價。",
                    required=True,
                ),
            ],
        )


# Registry of available providers. Add real ones here as they land.
_PROVIDERS: dict[str, Callable[[], AIProvider]] = {
    MockAIProvider.name: MockAIProvider,
}


def get_ai_provider(name: str | None = None) -> AIProvider:
    """Resolve the configured provider.

    Raises:
        ValueError: if the configured name is not registered.
    """
    key = (name or settings.AI_PROVIDER).strip().lower()
    factory = _PROVIDERS.get(key)
    if factory is None:
        available = ", ".join(sorted(_PROVIDERS)) or "(none)"
        raise ValueError(f"Unknown AI provider {key!r}. Registered: {available}")
    return factory()


def register_provider(name: str, factory: Callable[[], AIProvider]) -> None:
    """Hook for future providers (OpenAI, Bedrock, Gemini, ...)."""
    _PROVIDERS[name.strip().lower()] = factory


def available_providers() -> list[str]:
    return sorted(_PROVIDERS)


__all__ = [
    "AIProvider",
    "MockAIProvider",
    "available_providers",
    "get_ai_provider",
    "register_provider",
]
