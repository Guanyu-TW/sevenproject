"""MCP tools for the AI 智慧管家 smart-community service platform.

Architecture follows the reference servers in modelcontextprotocol/servers: a
package with a console-script entry point, an argparse ``main()``, and a single
``serve()`` that wires up transports.

It uses the SDK's v2 ``MCPServer`` API rather than the low-level ``Server`` the
reference servers use, because v2 removed the ``@server.list_tools()`` /
``@server.call_tool()`` decorators those are built on. Tool annotations are still
declared explicitly, which is the part that matters to a calling agent.

Every tool is a call to the platform's REST API. No business logic lives here:
the case state machine, the privacy gate and the validation rules stay in one
place, and this server stays a replaceable adapter.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_server_life_guardian.client import LifeGuardianClient

logger = logging.getLogger(__name__)

INSTRUCTIONS = """\
AI 智慧管家：台灣智慧社區的生活服務媒合平台。

住戶用一句白話描述需求，平台用 LLM 解析成可派工的任務、媒合在地廠商，並在住戶
確認報價後才把完整地址與電話交給廠商。

典型流程（住戶側）：
  1. list_service_categories  先確認平台是否處理這類需求
  2. analyze_life_demand      把一句話變成結構化任務，並得知還缺哪些資料
  3. get_task_conditions      查目前欄位值與缺漏項
  4. update_task_conditions   補齊欄位，並在齊全時標記為可媒合
  5. match_vendors            取得最多 3 家推薦廠商與推薦原因
  6. create_case              選定一家廠商建立案件
  7. get_case                 追蹤狀態、下一步、時間軸
  8. confirm_case             住戶確認報價，此時才解鎖聯絡資訊給廠商
  9. complete_case            服務完成後結案

廠商側：
  list_vendors / list_vendor_cases / vendor_respond_to_case

隱私規則很重要：案件在 waiting_vendor_response 與 vendor_accepted 階段，廠商只
看得到縣市與行政區；必須由住戶呼叫 confirm_case 之後，完整門牌、聯絡人與電話才
會出現在廠商視圖中。不要嘗試繞過這個步驟。
"""

READ_ONLY = ToolAnnotations(
    read_only_hint=True, idempotent_hint=True, open_world_hint=False
)
WRITES = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)
#: Advancing a case cannot be undone through this API, so say so.
IRREVERSIBLE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=False,
    open_world_hint=False,
)


# --------------------------------------------------------------------------- #
# Projections
#
# The REST API answers the web UI, so its payloads carry things an agent has no
# use for: token counts, provider metadata, full status history. Trimming them
# here keeps tool results small enough to reason over.
# --------------------------------------------------------------------------- #


def _task_view(task: dict[str, Any]) -> dict[str, Any]:
    parsed = task.get("parsed_data") or {}
    budget = parsed.get("budget") or {}
    location = parsed.get("location") or {}
    return {
        "task_id": task.get("id"),
        "status": task.get("status"),
        "title": parsed.get("title"),
        "summary": parsed.get("summary"),
        "category": (task.get("category") or {}).get("name"),
        "category_code": (task.get("category") or {}).get("code"),
        "service_label": parsed.get("service_label"),
        "urgency": parsed.get("urgency"),
        "budget_amount": budget.get("amount"),
        "currency": budget.get("currency"),
        "city": location.get("city"),
        "district": location.get("district"),
        "next_action": task.get("next_action"),
        "missing_fields": [
            {
                "field": f.get("field"),
                "label": f.get("label"),
                "reason": f.get("reason"),
                "input_type": f.get("input_type"),
            }
            for f in task.get("missing_fields") or []
        ],
    }


def _case_view(case: dict[str, Any]) -> dict[str, Any]:
    vendor = case.get("vendor") or {}
    shared = case.get("shared_with_vendor") or {}
    return {
        "case_id": case.get("id"),
        "case_number": case.get("case_number"),
        "task_id": case.get("task_id"),
        "status": case.get("status"),
        "status_label": case.get("status_label"),
        "next_action": case.get("next_action"),
        "blocked_reason": case.get("blocked_reason"),
        "vendor": {
            "vendor_id": vendor.get("id"),
            "name": vendor.get("name"),
            "rating": vendor.get("rating"),
        },
        "estimated_price": case.get("estimated_price"),
        "vendor_note": case.get("vendor_note"),
        "proposed_time": case.get("proposed_time"),
        "contact_unlocked": shared.get("contact_unlocked"),
        "withheld_from_vendor": shared.get("withheld") or [],
        "timeline": [
            {
                "step": step.get("label"),
                "state": step.get("state"),
                "at": step.get("at"),
            }
            for step in case.get("timeline") or []
        ],
    }


def _vendor_case_view(item: dict[str, Any]) -> dict[str, Any]:
    demand = item.get("demand") or {}
    view = {
        "case_id": item.get("case_id"),
        "case_number": item.get("case_number"),
        "status": item.get("status"),
        "status_label": item.get("status_label"),
        "vendor_id": item.get("vendor_id"),
        "vendor_name": item.get("vendor_name"),
        "title": demand.get("title"),
        "summary": demand.get("summary"),
        "category": demand.get("category_name"),
        "service_label": demand.get("service_label"),
        "area": demand.get("area"),
        "budget_amount": demand.get("budget_amount"),
        "preferred_time": demand.get("preferred_time"),
        "estimated_price": item.get("estimated_price"),
        "proposed_time": item.get("proposed_time"),
        "vendor_note": item.get("vendor_note"),
        "contact_unlocked": demand.get("contact_unlocked"),
    }
    # Only present these keys once the resident has confirmed; before that the
    # API returns null for them and an empty key just invites a retry.
    if demand.get("contact_unlocked"):
        view["address"] = demand.get("address")
        view["contact_name"] = demand.get("contact_name")
        view["contact_phone"] = demand.get("contact_phone")
    else:
        view["withheld"] = demand.get("withheld") or []
    return view


def build_server(client: LifeGuardianClient) -> MCPServer:
    """Register every tool against ``client`` and return the server."""
    mcp = MCPServer(
        "life-guardian",
        version="0.1.0",
        title="AI 智慧管家",
        instructions=INSTRUCTIONS,
    )

    # ---------------- discovery ------------------------------------------ #

    @mcp.tool(
        title="列出服務分類",
        annotations=READ_ONLY,
    )
    async def list_service_categories() -> list[dict[str, Any]]:
        """列出平台目前可以派工的所有服務領域。

        先呼叫這個，再決定平台能不能處理住戶的需求。
        """
        rows = await client.get("/api/service-categories")
        return [{"code": r["code"], "name": r["name"]} for r in rows]

    # ---------------- resident journey ----------------------------------- #

    @mcp.tool(title="解析生活需求", annotations=WRITES)
    async def analyze_life_demand(
        prompt: Annotated[
            str,
            Field(
                min_length=2,
                max_length=2000,
                description="住戶的原話，例如「嘉義市西區馬桶阻塞沖不下去，很急」。",
            ),
        ],
        user_id: Annotated[
            int | None,
            Field(ge=1, description="省略則歸到共用的示範住戶帳號。"),
        ] = None,
    ) -> dict[str, Any]:
        """把一句白話需求解析成結構化任務，並回報還缺哪些資料。

        會建立一筆草稿任務並回傳 task_id，後續所有操作都用這個 id。
        missing_fields 就是還需要向住戶追問的欄位。
        """
        body: dict[str, Any] = {"prompt": prompt}
        if user_id is not None:
            body["user_id"] = user_id
        task = await client.post("/api/ai/analyze-demand", json=body)
        return _task_view(task)

    @mcp.tool(title="查詢需求條件", annotations=READ_ONLY)
    async def get_task_conditions(
        task_id: Annotated[int, Field(ge=1)],
    ) -> dict[str, Any]:
        """列出這筆需求的所有條件、目前的值，以及哪些還沒填。

        editable 為 false 時代表案件已送給廠商，不該再改需求內容。
        """
        return await client.get(f"/api/tasks/{task_id}/fields")

    @mcp.tool(title="更新需求條件", annotations=WRITES)
    async def update_task_conditions(
        task_id: Annotated[int, Field(ge=1)],
        fields: Annotated[
            dict[str, str],
            Field(
                description=(
                    "以 get_task_conditions 回傳的 field 當鍵，例如 "
                    '{"address": "嘉義市西區文化路 100 號", "contact_phone": "0912-345-678"}。'
                    "留空字串不會清除原值。"
                )
            ),
        ],
        mark_ready_for_matching: Annotated[
            bool,
            Field(description="資料齊全時設為 true，任務才會進入可媒合狀態。"),
        ] = False,
    ) -> dict[str, Any]:
        """把住戶補的資料寫回任務，可同時把任務標記為可媒合。

        資料還沒齊就設 mark_ready_for_matching=true 會被平台以 409 拒絕。
        """
        body: dict[str, Any] = {"filled_fields": fields}
        if mark_ready_for_matching:
            body["status"] = "ready_for_matching"
        task = await client.patch(f"/api/tasks/{task_id}", json=body)
        return _task_view(task)

    @mcp.tool(title="媒合廠商", annotations=READ_ONLY)
    async def match_vendors(
        task_id: Annotated[int, Field(ge=1)],
        limit: Annotated[int, Field(ge=1, le=3)] = 3,
    ) -> dict[str, Any]:
        """依服務分類與地區硬性篩選廠商，再由 AI 排序並寫出推薦原因。

        任務必須先是 ready_for_matching。這個操作唯讀且可重複呼叫。
        """
        result = await client.post(
            "/api/matching/vendors", json={"task_id": task_id, "limit": limit}
        )
        return {
            "task_id": result.get("task_id"),
            "candidate_count": result.get("candidate_count"),
            "recommendations": [
                {
                    "vendor_id": r.get("vendor_id"),
                    "name": r.get("name"),
                    "rating": r.get("rating"),
                    "price_range": [r.get("price_min"), r.get("price_max")],
                    "estimated_price": r.get("estimated_price"),
                    "recommendation_reason": r.get("recommendation_reason"),
                }
                for r in result.get("recommendations") or []
            ],
        }

    @mcp.tool(title="建立案件", annotations=WRITES)
    async def create_case(
        task_id: Annotated[int, Field(ge=1)],
        vendor_id: Annotated[
            int, Field(ge=1, description="從 match_vendors 的推薦裡挑一個。")
        ],
        estimated_price: Annotated[int | None, Field(ge=0)] = None,
        recommendation_reason: str | None = None,
    ) -> dict[str, Any]:
        """把任務正式派給一家廠商，產生案件編號。

        同一筆任務已有進行中的案件時會被拒絕，不會產生第二個案件編號。
        建立後狀態為 waiting_vendor_response，此時廠商只看得到行政區。
        """
        case = await client.post(
            "/api/cases",
            json={
                "task_id": task_id,
                "selected_vendor_id": vendor_id,
                "form_data": {},
                "estimated_price": estimated_price,
                "recommendation_reason": recommendation_reason,
            },
        )
        return _case_view(case)

    @mcp.tool(title="查詢案件", annotations=READ_ONLY)
    async def get_case(case_id: Annotated[int, Field(ge=1)]) -> dict[str, Any]:
        """案件目前狀態、下一步、時間軸，以及廠商目前看得到什麼。"""
        return _case_view(await client.get(f"/api/cases/{case_id}"))

    @mcp.tool(title="以任務查案件", annotations=READ_ONLY)
    async def get_case_by_task(
        task_id: Annotated[int, Field(ge=1)],
    ) -> dict[str, Any] | None:
        """查這筆任務最新的案件；沒有案件則回傳 null。"""
        case = await client.get(f"/api/cases/by-task/{task_id}")
        return _case_view(case) if case else None

    @mcp.tool(title="住戶確認報價並提供聯絡資訊", annotations=IRREVERSIBLE)
    async def confirm_case(case_id: Annotated[int, Field(ge=1)]) -> dict[str, Any]:
        """住戶確認廠商的報價與到場時間，把完整地址與電話交給該廠商。

        這是隱私閘門，只有住戶本人該做這個決定，而且無法透過 API 收回。
        前提是案件已在 vendor_accepted，否則會被拒絕。
        """
        return _case_view(await client.post(f"/api/cases/{case_id}/confirm"))

    @mcp.tool(title="標記服務完成", annotations=IRREVERSIBLE)
    async def complete_case(
        case_id: Annotated[int, Field(ge=1)],
        actor: Annotated[
            Literal["consumer", "vendor"],
            Field(description="誰按下完成，只用於稽核紀錄。"),
        ] = "consumer",
    ) -> dict[str, Any]:
        """服務已交付，結案並一併關閉對應的任務。

        前提是案件已在 contact_shared。結案後無法透過 API 復原。
        """
        return _case_view(
            await client.post(f"/api/cases/{case_id}/complete", actor=actor)
        )

    @mcp.tool(title="住戶事項總覽", annotations=READ_ONLY)
    async def get_resident_dashboard(
        user_id: Annotated[int | None, Field(ge=1)] = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
    ) -> dict[str, Any]:
        """一位住戶的所有任務與統計，最新的在前面。"""
        data = await client.get("/api/dashboard/tasks", user_id=user_id, limit=limit)
        return {
            "user": data.get("user"),
            "stats": data.get("stats"),
            "total": data.get("total"),
            "tasks": [
                {
                    "task_id": t.get("task_id"),
                    "title": t.get("title"),
                    "status_label": t.get("display_label"),
                    "category": t.get("category_name"),
                    "next_action": t.get("next_action"),
                    "case_id": (t.get("latest_case") or {}).get("case_id"),
                    "case_number": (t.get("latest_case") or {}).get("case_number"),
                    "case_status": (t.get("latest_case") or {}).get("status"),
                    "vendor_name": (t.get("latest_case") or {}).get("vendor_name"),
                    "created_at": t.get("created_at"),
                }
                for t in data.get("tasks") or []
            ],
        }

    # ---------------- vendor journey ------------------------------------- #

    @mcp.tool(title="列出廠商", annotations=READ_ONLY)
    async def list_vendors() -> list[dict[str, Any]]:
        """平台上的活躍廠商與各自待處理案件數。"""
        rows = await client.get("/api/vendor/list")
        return [
            {
                "vendor_id": r.get("id"),
                "name": r.get("name"),
                "rating": r.get("rating"),
                "service_city": r.get("service_city"),
                "open_case_count": r.get("open_case_count"),
            }
            for r in rows
        ]

    @mcp.tool(title="廠商案件清單", annotations=READ_ONLY)
    async def list_vendor_cases(
        vendor_id: Annotated[
            int | None, Field(ge=1, description="省略則列出全平台案件。")
        ] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> dict[str, Any]:
        """廠商視角的案件清單。

        未解鎖的案件只會有 area 與 withheld，不會有門牌與電話 —— 這是平台強制
        的，不是這裡省略的。
        """
        data = await client.get(
            "/api/vendor/cases", vendor_id=vendor_id, limit=limit
        )
        return {
            "pending": data.get("pending"),
            "responded_total": data.get("responded_total"),
            "completed_total": data.get("completed_total"),
            "cases": [_vendor_case_view(c) for c in data.get("cases") or []],
        }

    @mcp.tool(title="廠商回覆案件", annotations=WRITES)
    async def vendor_respond_to_case(
        case_id: Annotated[int, Field(ge=1)],
        action: Literal["accept", "reject"],
        proposed_time: Annotated[
            str | None,
            Field(
                description=(
                    "ISO 8601 的擬定到場時間，例如 2026-08-12T14:00:00。"
                    "action=accept 時必填。"
                )
            ),
        ] = None,
        vendor_note: Annotated[
            str | None, Field(max_length=500, description="報價說明或備註。")
        ] = None,
        vendor_id: Annotated[
            int | None,
            Field(ge=1, description="帶入則驗證案件確實屬於這家廠商。"),
        ] = None,
    ) -> dict[str, Any]:
        """廠商接單或婉拒，並同步更新住戶端的任務與提示。

        接單必填 proposed_time。同一案件回覆兩次會被拒絕，不會覆蓋第一次。
        """
        result = await client.post(
            f"/api/vendor/cases/{case_id}/respond",
            json={
                "action": action,
                "proposedTime": proposed_time,
                "vendorNote": vendor_note,
            },
            vendor_id=vendor_id,
        )
        return {
            "case_id": result.get("case_id"),
            "case_number": result.get("case_number"),
            "status": result.get("status"),
            "status_label": result.get("status_label"),
            "task_id": result.get("task_id"),
            "task_next_action": result.get("task_next_action"),
            "proposed_time": result.get("proposed_time"),
            "vendor_note": result.get("vendor_note"),
        }

    return mcp


__all__ = ["INSTRUCTIONS", "build_server"]
