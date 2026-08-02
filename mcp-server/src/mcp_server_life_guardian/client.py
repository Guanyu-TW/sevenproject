"""Thin async client over the AI 智慧管家 REST API.

The MCP server owns no business logic. Every tool is a call to the platform's
own HTTP API, which keeps one source of truth for state machines, privacy rules
and validation, and lets the MCP server be deployed and scaled separately.

It also keeps the dependency trees apart: the platform runs FastAPI (pinned to
starlette <0.42), while the MCP SDK wants a much newer starlette. Installing
both into one interpreter breaks FastAPI outright.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

# v2 renamed this from McpError and takes code/message directly rather than an
# ErrorData object. The reference servers in modelcontextprotocol/servers still
# use the 1.x spelling.
from mcp.shared.exceptions import MCPError
from mcp.types import INTERNAL_ERROR, INVALID_PARAMS

logger = logging.getLogger(__name__)

#: The platform answers slowly when Bedrock is in the loop: a demand analysis
#: is one LLM round trip, and vendor ranking is another.
DEFAULT_TIMEOUT = 90.0


def _fail(message: str, *, code: int = INVALID_PARAMS) -> MCPError:
    """Build an error the calling model can read and act on."""
    return MCPError(code, message)


class LifeGuardianClient:
    """HTTP wrapper that turns API failures into MCP errors."""

    def __init__(self, base_url: str, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Call the platform API and return the decoded body.

        Raises:
            McpError: on transport failure or any non-2xx response. The API's
                own Chinese ``detail`` message is passed straight through,
                because it is already written for a human to act on.
        """
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                response = await http.request(
                    method, url, json=json, params=_clean(params)
                )
        except httpx.TimeoutException as exc:
            raise _fail(
                f"呼叫 {path} 逾時（{self._timeout:.0f} 秒）。"
                "需求解析與廠商推薦都會呼叫大型語言模型，請稍後重試。",
                code=INTERNAL_ERROR,
            ) from exc
        except httpx.HTTPError as exc:
            raise _fail(
                f"無法連線到 AI 智慧管家 API（{self.base_url}）：{exc}",
                code=INTERNAL_ERROR,
            ) from exc

        if response.is_success:
            if not response.content:
                return None
            return response.json()

        logger.warning("%s %s -> HTTP %s", method, path, response.status_code)
        raise _fail(
            f"{method} {path} 失敗（HTTP {response.status_code}）："
            f"{_detail(response)}",
            # 5xx is the platform's problem, 4xx is something the caller can fix.
            code=INTERNAL_ERROR if response.status_code >= 500 else INVALID_PARAMS,
        )

    async def get(self, path: str, **params: Any) -> Any:
        return await self.request("GET", path, params=params)

    async def post(
        self, path: str, *, json: Any | None = None, **params: Any
    ) -> Any:
        return await self.request("POST", path, json=json, params=params)

    async def patch(self, path: str, *, json: Any | None = None) -> Any:
        return await self.request("PATCH", path, json=json)

    async def healthy(self) -> bool:
        """Whether the platform API is reachable, for the readiness probe."""
        try:
            await self.get("/api/health")
        except MCPError:
            return False
        return True


def _clean(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop None values so they are not serialised as the string "None"."""
    if not params:
        return None
    cleaned = {k: v for k, v in params.items() if v is not None}
    return cleaned or None


def _detail(response: httpx.Response) -> str:
    """Pull the most useful message out of a FastAPI error body."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:400] or "（沒有錯誤內容）"

    detail = body.get("detail") if isinstance(body, dict) else body
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        # Duplicate-case conflicts carry the existing case in the detail object,
        # which the caller needs in order to recover.
        message = detail.get("message")
        extras = {k: v for k, v in detail.items() if k != "message"}
        if message and extras:
            return f"{message}（{extras}）"
        if message:
            return str(message)
    if isinstance(detail, list):
        # Pydantic validation errors.
        parts = [
            f"{'.'.join(str(p) for p in item.get('loc', []))}: {item.get('msg')}"
            for item in detail
            if isinstance(item, dict)
        ]
        if parts:
            return "；".join(parts)
    return str(detail)[:400]


__all__ = ["DEFAULT_TIMEOUT", "LifeGuardianClient"]
