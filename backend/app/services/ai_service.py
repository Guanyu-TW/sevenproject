"""Demand-understanding layer.

The rest of the app only ever talks to :class:`AIProvider`, so swapping the
mock for a real LLM is a one-line change in ``settings.AI_PROVIDER``. Nothing
above this module knows which provider is in play.

The interface is intentionally synchronous: the API layer uses a synchronous
SQLAlchemy session, and FastAPI already runs sync endpoints in a worker thread,
so a blocking HTTP call to Bedrock here will not stall the event loop.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Callable, ClassVar

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.ai import (
    BedrockDemandPayload,
    CategoryHint,
    DemandAnalysis,
    MissingField,
)
from app.schemas.matching import (
    BedrockVendorRanking,
    DemandContext,
    VendorContext,
)
from app.services.missing_fields import (
    ALLOWED_FIELD_KEYS,
    catalog_field,
    normalize_missing_fields,
)

logger = logging.getLogger(__name__)

try:  # boto3 is only needed for the Bedrock provider.
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError

    BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in trimmed installs
    boto3 = None  # type: ignore[assignment]
    BotoConfig = None  # type: ignore[assignment]
    BOTO3_AVAILABLE = False

    class BotoCoreError(Exception):  # type: ignore[no-redef]
        """Placeholder so except clauses stay valid without boto3."""

    class ClientError(Exception):  # type: ignore[no-redef]
        """Placeholder so except clauses stay valid without boto3."""


class AIProviderError(RuntimeError):
    """The provider could not produce a usable analysis.

    Carries a short ``code`` and a ``retryable`` flag so the API layer can pick
    an HTTP status without re-inspecting boto3 exceptions.
    """

    def __init__(self, message: str, *, code: str = "ProviderError", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class AIProvider(ABC):
    """Contract every demand-understanding backend must satisfy."""

    #: Short identifier recorded on the task so results stay traceable.
    name: ClassVar[str]

    @abstractmethod
    def analyze_demand(
        self,
        prompt: str,
        *,
        categories: Sequence[CategoryHint] | None = None,
    ) -> DemandAnalysis:
        """Turn free-form resident input into a structured demand.

        ``categories`` comes from the database so the allowed classification
        set stays in sync with ``service_categories`` without editing prompts.
        """
        raise NotImplementedError

    @abstractmethod
    def recommend_vendors(
        self,
        *,
        demand: DemandContext,
        vendors: Sequence[VendorContext],
        limit: int = 3,
    ) -> BedrockVendorRanking:
        """Score and justify each candidate vendor for this demand.

        ``vendors`` has already passed the hard filter, so the job here is
        purely ranking plus writing a reason a resident can act on.
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Mock
# --------------------------------------------------------------------------- #


class MockAIProvider(AIProvider):
    """Deterministic stand-in that needs no credentials or network.

    It ignores the semantics of ``prompt`` on purpose and always returns the
    same fixture, which keeps the frontend and the persistence path testable
    offline. The original prompt is still echoed back by the API layer.
    """

    name: ClassVar[str] = "mock"

    def analyze_demand(
        self,
        prompt: str,
        *,
        categories: Sequence[CategoryHint] | None = None,
    ) -> DemandAnalysis:
        if settings.MOCK_AI_LATENCY_MS > 0:
            # Makes the frontend loading state observable during a demo.
            time.sleep(settings.MOCK_AI_LATENCY_MS / 1000)

        logger.info("MockAIProvider handling prompt (%d chars)", len(prompt))

        return DemandAnalysis(
            title="廚房水龍頭漏水",
            summary="廚房水龍頭底座持續滴水，疑似墊片老化，需要師傅到場檢修並更換零件。",
            intent="service_request",
            category_code="plumbing",
            confidence=0.82,
            model="mock-fixture",
            parsed_data={
                "intent": "service_request",
                "service_type": "faucet_leak_repair",
                "service_label": "水龍頭漏水維修",
                "budget": {
                    "amount": 2000,
                    "currency": "TWD",
                    "note": "住戶提到預算約兩千元",
                },
                "location": {"city": "嘉義市", "district": None, "address": None},
                "urgency": "normal",
                "preferred_time": None,
                "contact": {"name": None, "phone": None},
                "attachments": [],
                "keywords": ["水龍頭", "漏水", "廚房"],
            },
            missing_fields=[
                catalog_field("address"),
                catalog_field("photos"),
            ],
        )

    def recommend_vendors(
        self,
        *,
        demand: DemandContext,
        vendors: Sequence[VendorContext],
        limit: int = 3,
    ) -> BedrockVendorRanking:
        if settings.MOCK_AI_LATENCY_MS > 0:
            time.sleep(settings.MOCK_AI_LATENCY_MS / 1000)

        ranked = sorted(vendors, key=lambda v: v.rating, reverse=True)[:limit]
        return BedrockVendorRanking(
            recommendations=[
                {
                    "vendorId": v.id,
                    "estimatedPrice": _midpoint_price(v, demand.budget_amount),
                    "matchScore": round(min(v.rating / 5.0, 1.0), 2),
                    "recommendationReason": (
                        f"評分 {v.rating} 且服務範圍涵蓋{v.service_city or '該地區'}，"
                        f"報價區間 {v.price_min}-{v.price_max} 元符合你的需求。"
                        "（此為 mock provider 產生的樣板理由）"
                    ),
                }
                for v in ranked
            ]
        )


# --------------------------------------------------------------------------- #
# Amazon Bedrock
# --------------------------------------------------------------------------- #

def _midpoint_price(vendor: VendorContext, budget: float | None) -> int | None:
    """Cheap price estimate used by the mock and by the rule-based fallback."""
    low, high = vendor.price_min, vendor.price_max
    if low is None and high is None:
        return int(budget) if budget else None
    if low is None:
        return high
    if high is None:
        return low
    if budget is not None and low <= budget <= high:
        return int(budget)
    return int((low + high) / 2)


DEMAND_TOOL_NAME = "record_life_demand"
RANK_TOOL_NAME = "rank_vendors"

_SYSTEM_PROMPT_TEMPLATE = """\
你是「AI 智慧管家」，服務台灣智慧社區的住戶。你的工作是把住戶用口語說出的生活需求，
整理成結構化資料，交給後續的廠商媒合系統。

規則：
1. 你必須呼叫 `{tool_name}` 工具回報結果，不要用純文字回答。
2. `categoryCode` 只能從下列清單挑一個最接近的；如果都不像，填 null：
{category_lines}
3. 絕對不要編造住戶沒有說的資訊。住戶沒提到的欄位一律填 null，
   並把它列進 `missingFields`。寧可標記為缺少，也不要猜測。
4. `missingFields[].field` 只能使用下列鍵值：
   {allowed_fields}
   只列出「這次服務真正需要、但住戶還沒提供」的欄位，不要把全部欄位都列上。
5. `budget.amount` 只填數字（例如「兩千」要轉成 2000），幣別預設 TWD。
6. `title` 用不超過 20 個字的繁體中文短句描述問題本身。
6-1. `serviceLabel` 用 4 到 10 個字的繁體中文寫出「服務細項」，要比 `categoryCode`
     更具體，例如分類是水電維修時可寫「馬桶阻塞疏通」、「熱水器維修」、「插座配線檢修」。
     這是廠商用來判斷自己能不能接的關鍵欄位，不要只重複分類名稱。
7. `urgency` 只能是 "low"、"normal"、"high"、"emergency" 之一。
8. `intent` 只能是 "service_request"（要找服務）、"question"（只是詢問）、
   "other"（其他）之一。
9. `confidence` 用 0 到 1 的小數，表示你對這次解析的信心。
10. 所有給住戶看的文字（title、summary、label、reason）都用繁體中文。
11. `title` 與 `summary` 之後會顯示給廠商，所以不要寫入完整門牌、路名、
    電話或姓名。地點只寫到縣市與行政區即可，精確地址請放進 `location.address`。
"""


def _build_tool_spec() -> dict[str, Any]:
    """Hand-written JSON Schema for the forced tool call.

    Written out flat rather than generated from Pydantic so the model sees
    descriptions tuned for prompting, with no ``$ref`` indirection.
    """
    return {
        "name": DEMAND_TOOL_NAME,
        "description": "記錄一筆住戶的生活服務需求，並標記還缺少哪些資料。",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": ["service_request", "question", "other"],
                        "description": "住戶這句話的意圖。",
                    },
                    "serviceType": {
                        "type": "string",
                        "description": "更細的服務項目代號，英文小寫加底線，例如 faucet_leak_repair。",
                    },
                    "serviceLabel": {
                        "type": "string",
                        "description": (
                            "serviceType 的繁體中文說法，4 到 10 個字，會直接顯示給廠商，"
                            "例如「馬桶阻塞疏通」。必須比服務分類更具體。"
                        ),
                    },
                    "categoryCode": {
                        "type": ["string", "null"],
                        "description": "服務分類代號，必須來自系統提供的清單，無法判斷填 null。",
                    },
                    "title": {
                        "type": "string",
                        "description": "20 字以內的繁體中文短標題。",
                    },
                    "summary": {
                        "type": ["string", "null"],
                        "description": "兩三句繁體中文摘要，只能根據住戶說過的內容。",
                    },
                    "location": {
                        "type": "object",
                        "properties": {
                            "city": {"type": ["string", "null"], "description": "縣市。"},
                            "district": {"type": ["string", "null"], "description": "行政區。"},
                            "address": {
                                "type": ["string", "null"],
                                "description": "完整門牌地址，住戶沒說就填 null。",
                            },
                        },
                        "required": ["city", "district", "address"],
                    },
                    "budget": {
                        "type": "object",
                        "properties": {
                            "amount": {
                                "type": ["number", "null"],
                                "description": "純數字金額，沒提到填 null。",
                            },
                            "currency": {"type": ["string", "null"], "description": "幣別，預設 TWD。"},
                            "note": {"type": ["string", "null"], "description": "預算相關補充。"},
                        },
                        "required": ["amount", "currency", "note"],
                    },
                    "urgency": {
                        "type": ["string", "null"],
                        "enum": ["low", "normal", "high", "emergency", None],
                        "description": "急迫程度。",
                    },
                    "preferredTime": {
                        "type": ["string", "null"],
                        "description": "住戶希望的時間，保留原話即可，沒提到填 null。",
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "3 到 5 個繁體中文關鍵詞。",
                    },
                    "missingFields": {
                        "type": "array",
                        "description": "這次服務需要但住戶還沒提供的資料。",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {
                                    "type": "string",
                                    "enum": ALLOWED_FIELD_KEYS,
                                    "description": "欄位鍵值。",
                                },
                                "label": {
                                    "type": "string",
                                    "description": "給住戶看的繁體中文欄位名稱。",
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "一句繁體中文說明為什麼需要這項資料。",
                                },
                            },
                            "required": ["field", "label", "reason"],
                        },
                    },
                    "confidence": {
                        "type": "number",
                        "description": "0 到 1 的解析信心。",
                    },
                },
                "required": [
                    "intent",
                    "serviceType",
                    "categoryCode",
                    "title",
                    "summary",
                    "location",
                    "budget",
                    "missingFields",
                    "confidence",
                ],
            }
        },
    }


def build_system_prompt(categories: Sequence[CategoryHint]) -> str:
    if categories:
        category_lines = "\n".join(f"   - {c.code}：{c.name}" for c in categories)
    else:
        category_lines = "   （目前沒有可用分類，請填 null）"
    return _SYSTEM_PROMPT_TEMPLATE.format(
        tool_name=DEMAND_TOOL_NAME,
        category_lines=category_lines,
        allowed_fields=", ".join(ALLOWED_FIELD_KEYS),
    )


_RANK_SYSTEM_PROMPT = """\
你是「AI 智慧管家」的媒合顧問。系統已經用硬性條件（服務類型、地區）篩選出候選廠商，
你的工作是替住戶挑出最適合的幾家，並寫出住戶看得懂的推薦理由。

規則：
1. 你必須呼叫 `{tool_name}` 工具回報結果，不要用純文字回答。
2. `vendorId` 只能使用候選清單裡出現過的 id，絕對不要發明新的 id。
3. 最多推薦 {limit} 家，依適合程度由高到低排列。若候選少於 {limit} 家就全部列出。
4. `recommendationReason` 用繁體中文，60 到 100 字，必須具體對應這次需求。
   要提到至少兩個實際依據，例如評分、價格區間與預算的關係、服務範圍、
   急迫程度是否能配合、廠商專長是否對得上問題。
   不要寫「這家很好」這種空話，也不要編造候選資料裡沒有的資訊。
5. `estimatedPrice` 必須落在該廠商的 price_min 與 price_max 之間。
   若住戶有預算，盡量靠近但不超過預算；若超出區間下限就給區間下限。
6. `matchScore` 用 0 到 1 的小數表示適合程度。
7. 如果住戶預算低於某家廠商的最低價，仍可推薦，但理由要誠實說明可能超出預算。
"""


def _build_rank_tool_spec() -> dict[str, Any]:
    return {
        "name": RANK_TOOL_NAME,
        "description": "回報排序後的推薦廠商與推薦理由。",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "recommendations": {
                        "type": "array",
                        "description": "依適合程度由高到低排序的推薦名單。",
                        "items": {
                            "type": "object",
                            "properties": {
                                "vendorId": {
                                    "type": "integer",
                                    "description": "候選清單中的廠商 id。",
                                },
                                "estimatedPrice": {
                                    "type": ["number", "null"],
                                    "description": "落在該廠商價格區間內的預估金額。",
                                },
                                "matchScore": {
                                    "type": "number",
                                    "description": "0 到 1 的適合程度。",
                                },
                                "recommendationReason": {
                                    "type": "string",
                                    "description": "60-100 字的繁體中文推薦理由。",
                                },
                            },
                            "required": [
                                "vendorId",
                                "estimatedPrice",
                                "matchScore",
                                "recommendationReason",
                            ],
                        },
                    }
                },
                "required": ["recommendations"],
            }
        },
    }


def _format_demand(demand: DemandContext) -> str:
    def line(label: str, value: Any) -> str | None:
        return f"- {label}：{value}" if value not in (None, "", []) else None

    parts = [
        line("需求標題", demand.title),
        line("需求說明", demand.summary),
        line("服務分類", demand.category_name),
        # Prefer the Chinese label; the snake_case code is only a fallback for
        # rows analysed before serviceLabel existed.
        line("服務細項", demand.service_label or demand.service_type),
        line(
            "預算",
            f"{int(demand.budget_amount)} {demand.currency or 'TWD'}"
            if demand.budget_amount
            else None,
        ),
        line(
            "地點",
            " ".join(p for p in [demand.city, demand.district, demand.address] if p),
        ),
        line("急迫程度", demand.urgency),
        line("希望時間", demand.preferred_time or demand.preferred_date),
        line("補充說明", demand.description),
        line("住戶原話", demand.raw_input),
    ]
    return "\n".join(p for p in parts if p)


def _format_vendors(vendors: Sequence[VendorContext]) -> str:
    rows = []
    for v in vendors:
        districts = "、".join(v.service_districts) if v.service_districts else "全市"
        rows.append(
            f"- id={v.id} | {v.name} | 評分 {v.rating} | "
            f"價格 {v.price_min}-{v.price_max} 元 | "
            f"服務範圍 {v.service_city or '未指定'}（{districts}）| "
            f"可承接 {'、'.join(v.categories) or '未指定'} | "
            f"簡介：{v.description or '無'}"
        )
    return "\n".join(rows)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort recovery when a model answers with text instead of a tool call."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
        cleaned = cleaned.removeprefix("json").strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        candidate = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return candidate if isinstance(candidate, dict) else None


class RealAIProvider(AIProvider):
    """Amazon Bedrock provider using the Converse API with forced tool use.

    Forcing a tool call (``toolChoice``) is what makes the JSON reliable: the
    model fills in a schema instead of writing prose we then have to parse.
    A text-parsing fallback is still in place for models that ignore it.
    """

    name: ClassVar[str] = "bedrock"

    def __init__(self, client: Any | None = None):
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client

        if not BOTO3_AVAILABLE:
            raise AIProviderError(
                "boto3 is not installed. Run: pip install -r requirements.txt",
                code="Boto3Missing",
            )

        self._client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_DEFAULT_REGION,
            config=BotoConfig(
                retries={"max_attempts": settings.BEDROCK_MAX_ATTEMPTS, "mode": "standard"},
                connect_timeout=10,
                read_timeout=settings.BEDROCK_READ_TIMEOUT_SECONDS,
            ),
        )
        return self._client

    def analyze_demand(
        self,
        prompt: str,
        *,
        categories: Sequence[CategoryHint] | None = None,
    ) -> DemandAnalysis:
        category_list = list(categories or [])
        model_id = settings.BEDROCK_MODEL_ID

        logger.info(
            "Bedrock converse model=%s region=%s prompt_chars=%d",
            model_id,
            settings.AWS_DEFAULT_REGION,
            len(prompt),
        )

        try:
            response = self.client.converse(
                modelId=model_id,
                system=[{"text": build_system_prompt(category_list)}],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={
                    "maxTokens": settings.BEDROCK_MAX_TOKENS,
                    "temperature": settings.BEDROCK_TEMPERATURE,
                },
                toolConfig={
                    "tools": [{"toolSpec": _build_tool_spec()}],
                    "toolChoice": {"tool": {"name": DEMAND_TOOL_NAME}},
                },
            )
        except ClientError as exc:
            raise _translate_client_error(exc) from exc
        except BotoCoreError as exc:
            raise AIProviderError(
                f"無法連線到 Bedrock（{type(exc).__name__}）。請確認 AWS 憑證與網路設定。",
                code=type(exc).__name__,
                retryable=True,
            ) from exc

        raw_payload = self._extract_tool_input(response)

        try:
            payload = BedrockDemandPayload.model_validate(raw_payload)
        except ValidationError as exc:
            logger.warning("Bedrock payload failed validation: %s", exc)
            raise AIProviderError(
                f"Bedrock 回傳的 JSON 不符合規格（{exc.error_count()} 個欄位錯誤）。",
                code="SchemaValidation",
                retryable=True,
            ) from exc

        usage = response.get("usage", {})
        logger.info(
            "Bedrock ok tokens_in=%s tokens_out=%s stop=%s",
            usage.get("inputTokens"),
            usage.get("outputTokens"),
            response.get("stopReason"),
        )

        return self._to_analysis(payload, model_id=model_id, usage=usage)

    def recommend_vendors(
        self,
        *,
        demand: DemandContext,
        vendors: Sequence[VendorContext],
        limit: int = 3,
    ) -> BedrockVendorRanking:
        model_id = settings.BEDROCK_MODEL_ID
        user_message = (
            "【住戶需求】\n"
            f"{_format_demand(demand)}\n\n"
            "【候選廠商】\n"
            f"{_format_vendors(vendors)}"
        )

        logger.info(
            "Bedrock rank_vendors model=%s candidates=%d limit=%d",
            model_id,
            len(vendors),
            limit,
        )

        try:
            response = self.client.converse(
                modelId=model_id,
                system=[
                    {
                        "text": _RANK_SYSTEM_PROMPT.format(
                            tool_name=RANK_TOOL_NAME, limit=limit
                        )
                    }
                ],
                messages=[{"role": "user", "content": [{"text": user_message}]}],
                inferenceConfig={
                    "maxTokens": settings.BEDROCK_MAX_TOKENS,
                    "temperature": settings.BEDROCK_TEMPERATURE,
                },
                toolConfig={
                    "tools": [{"toolSpec": _build_rank_tool_spec()}],
                    "toolChoice": {"tool": {"name": RANK_TOOL_NAME}},
                },
            )
        except ClientError as exc:
            raise _translate_client_error(exc) from exc
        except BotoCoreError as exc:
            raise AIProviderError(
                f"無法連線到 Bedrock（{type(exc).__name__}）。請確認 AWS 憑證與網路設定。",
                code=type(exc).__name__,
                retryable=True,
            ) from exc

        raw = self._extract_tool_input(response, tool_name=RANK_TOOL_NAME)

        try:
            ranking = BedrockVendorRanking.model_validate(raw)
        except ValidationError as exc:
            logger.warning("Bedrock ranking failed validation: %s", exc)
            raise AIProviderError(
                f"Bedrock 回傳的推薦結果不符合規格（{exc.error_count()} 個欄位錯誤）。",
                code="SchemaValidation",
                retryable=True,
            ) from exc

        usage = response.get("usage", {})
        logger.info(
            "Bedrock rank ok picks=%d tokens_in=%s tokens_out=%s",
            len(ranking.recommendations),
            usage.get("inputTokens"),
            usage.get("outputTokens"),
        )
        return ranking

    @staticmethod
    def _extract_tool_input(
        response: dict[str, Any],
        *,
        tool_name: str = DEMAND_TOOL_NAME,
    ) -> dict[str, Any]:
        blocks = response.get("output", {}).get("message", {}).get("content", []) or []

        for block in blocks:
            tool_use = block.get("toolUse")
            if tool_use and tool_use.get("name") == tool_name:
                return tool_use.get("input") or {}

        # Fallback: the model replied with text despite toolChoice.
        for block in blocks:
            text = block.get("text")
            if text:
                recovered = _extract_json_object(text)
                if recovered is not None:
                    logger.warning("Recovered JSON from a text block, not a toolUse block")
                    return recovered

        raise AIProviderError(
            "Bedrock 沒有回傳結構化結果，請確認所選模型支援 tool use。",
            code="NoToolUse",
            retryable=True,
        )

    @staticmethod
    def _to_analysis(
        payload: BedrockDemandPayload,
        *,
        model_id: str,
        usage: dict[str, Any],
    ) -> DemandAnalysis:
        missing: list[MissingField] = normalize_missing_fields(payload.missing_fields)

        return DemandAnalysis(
            title=payload.title,
            summary=payload.summary,
            intent=payload.intent,
            category_code=payload.category_code,
            confidence=payload.confidence,
            model=model_id,
            parsed_data={
                "intent": payload.intent,
                "service_type": payload.service_type,
                "service_label": payload.service_label,
                "budget": payload.budget.model_dump(),
                "location": payload.location.model_dump(),
                "urgency": payload.urgency,
                "preferred_time": payload.preferred_time,
                "contact": {"name": None, "phone": None},
                "attachments": [],
                "keywords": payload.keywords,
                "usage": {
                    "input_tokens": usage.get("inputTokens"),
                    "output_tokens": usage.get("outputTokens"),
                },
            },
            missing_fields=missing,
        )


_ERROR_HINTS: dict[str, tuple[str, bool]] = {
    "AccessDeniedException": (
        "AWS 憑證有效，但沒有權限呼叫這個模型。請到 Bedrock 主控台的 Model access "
        "申請啟用 BEDROCK_MODEL_ID 指定的模型，並確認 IAM 有 bedrock:InvokeModel 權限。",
        False,
    ),
    "ValidationException": (
        "Bedrock 拒絕了這次請求，通常是 BEDROCK_MODEL_ID 在這個區域不存在，"
        "或該模型需要使用 cross-region inference profile（ID 開頭是 us. / eu.）。",
        False,
    ),
    "ResourceNotFoundException": (
        "在目前的 AWS_DEFAULT_REGION 找不到這個模型，請換區域或改用 inference profile ID。",
        False,
    ),
    "ThrottlingException": ("Bedrock 目前限流，請稍後再試。", True),
    "ModelTimeoutException": ("模型回應逾時，請稍後再試。", True),
    "ServiceUnavailableException": ("Bedrock 服務暫時不可用，請稍後再試。", True),
    "UnrecognizedClientException": (
        "AWS 憑證無效，請檢查 AWS_ACCESS_KEY_ID 與 AWS_SECRET_ACCESS_KEY。",
        False,
    ),
    "InvalidSignatureException": (
        "AWS 簽章驗證失敗，通常是 AWS_SECRET_ACCESS_KEY 有誤或主機時間不同步。",
        False,
    ),
}


def _translate_client_error(exc: Exception) -> AIProviderError:
    """Turn a boto3 ClientError into something actionable for the developer."""
    code = "ClientError"
    aws_message = str(exc)
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error", {})
        code = error.get("Code") or code
        aws_message = error.get("Message") or aws_message

    hint, retryable = _ERROR_HINTS.get(code, ("", False))
    message = f"Bedrock 呼叫失敗（{code}）：{aws_message}"
    if hint:
        message = f"{message} — {hint}"

    logger.error("Bedrock ClientError code=%s message=%s", code, aws_message)
    return AIProviderError(message, code=code, retryable=retryable)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

_PROVIDERS: dict[str, Callable[[], AIProvider]] = {
    MockAIProvider.name: MockAIProvider,
    RealAIProvider.name: RealAIProvider,
    "real": RealAIProvider,  # convenience alias
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
    """Hook for future providers."""
    _PROVIDERS[name.strip().lower()] = factory


def available_providers() -> list[str]:
    return sorted(_PROVIDERS)


__all__ = [
    "AIProvider",
    "AIProviderError",
    "MockAIProvider",
    "RealAIProvider",
    "available_providers",
    "build_system_prompt",
    "get_ai_provider",
    "register_provider",
]
