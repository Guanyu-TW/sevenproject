"""Tests that need no running platform.

The full journey is covered by an end-to-end run against a live API; these cover
the parts that are easy to get wrong and cheap to check in isolation: the tool
surface, the annotations agents rely on, the projections, and the privacy rule
that vendor-facing output stays redacted until the resident confirms.
"""

from __future__ import annotations

import pytest
from mcp import Client
from mcp.shared.exceptions import MCPError

from mcp_server_life_guardian.client import LifeGuardianClient, _detail
from mcp_server_life_guardian.server import (
    _case_view,
    _task_view,
    _vendor_case_view,
    build_server,
)

EXPECTED_TOOLS = {
    "analyze_life_demand",
    "complete_case",
    "confirm_case",
    "create_case",
    "get_case",
    "get_case_by_task",
    "get_resident_dashboard",
    "get_task_conditions",
    "list_service_categories",
    "list_vendor_cases",
    "list_vendors",
    "match_vendors",
    "update_task_conditions",
    "vendor_respond_to_case",
}

READ_ONLY_TOOLS = {
    "get_case",
    "get_case_by_task",
    "get_resident_dashboard",
    "get_task_conditions",
    "list_service_categories",
    "list_vendor_cases",
    "list_vendors",
    "match_vendors",
}

#: Advancing a case cannot be undone through this API.
IRREVERSIBLE_TOOLS = {"confirm_case", "complete_case"}


@pytest.fixture
def server():
    # A base URL that is never called: these tests only inspect metadata.
    return build_server(LifeGuardianClient("http://unused.invalid"))


@pytest.mark.anyio
async def test_exposes_the_whole_journey(server):
    async with Client(server) as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert names == EXPECTED_TOOLS


@pytest.mark.anyio
async def test_annotations_tell_agents_what_is_safe(server):
    async with Client(server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}

    for name in READ_ONLY_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None, name
        assert annotations.read_only_hint is True, name

    for name in IRREVERSIBLE_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None, name
        assert annotations.read_only_hint is False, name
        # A client that asks before destructive calls should ask before these.
        assert annotations.destructive_hint is True, name

    for name in EXPECTED_TOOLS - READ_ONLY_TOOLS:
        assert tools[name].annotations.open_world_hint is False, name


@pytest.mark.anyio
async def test_every_tool_is_described(server):
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
    for tool in tools:
        assert tool.description, tool.name
        assert tool.title, tool.name


@pytest.mark.anyio
async def test_instructions_state_the_privacy_rule(server):
    async with Client(server) as client:
        assert client.instructions is not None
        assert "confirm_case" in client.instructions
        assert "隱私" in client.instructions


@pytest.mark.anyio
async def test_bad_arguments_are_rejected_before_any_http_call(server):
    """The invalid base URL would blow up if the call reached the client."""
    async with Client(server) as client:
        result = await client.call_tool("get_case", {"case_id": 0})
    assert result.is_error


def test_vendor_view_withholds_contact_until_confirmed():
    locked = _vendor_case_view(
        {
            "case_id": 1,
            "status": "vendor_accepted",
            "demand": {
                "title": "馬桶阻塞",
                "area": "嘉義市 西區",
                "contact_unlocked": False,
                "address": None,
                "contact_name": None,
                "contact_phone": None,
                "withheld": ["完整門牌地址", "聯絡電話"],
            },
        }
    )
    assert locked["area"] == "嘉義市 西區"
    assert "address" not in locked
    assert "contact_phone" not in locked
    assert locked["withheld"] == ["完整門牌地址", "聯絡電話"]


def test_vendor_view_exposes_contact_once_confirmed():
    unlocked = _vendor_case_view(
        {
            "case_id": 1,
            "status": "contact_shared",
            "demand": {
                "title": "馬桶阻塞",
                "area": "嘉義市 西區",
                "contact_unlocked": True,
                "address": "嘉義市西區文化路 100 號",
                "contact_name": "王小明",
                "contact_phone": "0912-345-678",
                "withheld": [],
            },
        }
    )
    assert unlocked["address"] == "嘉義市西區文化路 100 號"
    assert unlocked["contact_phone"] == "0912-345-678"
    assert "withheld" not in unlocked


def test_task_view_drops_provider_noise():
    view = _task_view(
        {
            "id": 7,
            "status": "draft",
            "category": {"code": "plumbing", "name": "水電維修"},
            "missing_fields": [{"field": "address", "label": "詳細地址"}],
            "parsed_data": {
                "title": "馬桶阻塞",
                "service_label": "馬桶阻塞疏通",
                "budget": {"amount": 2000, "currency": "TWD"},
                "location": {"city": "嘉義市", "district": "西區"},
                # Noise an agent has no use for.
                "usage": {"input_tokens": 3000, "output_tokens": 600},
                "_meta": {"provider": "bedrock", "model": "claude"},
            },
        }
    )
    assert view["task_id"] == 7
    assert view["category"] == "水電維修"
    assert view["service_label"] == "馬桶阻塞疏通"
    assert view["budget_amount"] == 2000
    assert view["missing_fields"] == [
        {"field": "address", "label": "詳細地址", "reason": None, "input_type": None}
    ]
    assert "usage" not in view
    assert "_meta" not in view


def test_case_view_surfaces_the_privacy_state():
    view = _case_view(
        {
            "id": 3,
            "case_number": "CASE-20260802-0001",
            "task_id": 7,
            "status": "waiting_vendor_response",
            "status_label": "等待廠商回覆",
            "vendor": {"id": 1, "name": "阿明水電行", "rating": 4.8},
            "shared_with_vendor": {
                "contact_unlocked": False,
                "withheld": ["完整門牌地址"],
            },
            "timeline": [{"label": "需求解析完成", "state": "done", "at": None}],
        }
    )
    assert view["case_number"] == "CASE-20260802-0001"
    assert view["contact_unlocked"] is False
    assert view["withheld_from_vendor"] == ["完整門牌地址"]
    assert view["vendor"]["name"] == "阿明水電行"
    assert view["timeline"] == [
        {"step": "需求解析完成", "state": "done", "at": None}
    ]


class _FakeResponse:
    def __init__(self, payload, *, text: str = ""):
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def test_detail_passes_through_the_platform_message():
    assert (
        _detail(_FakeResponse({"detail": "案件目前狀態是「已完成」，無法執行這個操作。"}))
        == "案件目前狀態是「已完成」，無法執行這個操作。"
    )


def test_detail_keeps_the_existing_case_on_a_duplicate():
    message = _detail(
        _FakeResponse(
            {
                "detail": {
                    "message": "任務 #7 已經建立過案件",
                    "case_id": 3,
                    "case_number": "CASE-20260802-0001",
                }
            }
        )
    )
    assert "任務 #7 已經建立過案件" in message
    # An agent needs the existing id to recover instead of retrying blindly.
    assert "CASE-20260802-0001" in message


def test_detail_flattens_validation_errors():
    message = _detail(
        _FakeResponse(
            {"detail": [{"loc": ["body", "prompt"], "msg": "field required"}]}
        )
    )
    assert message == "body.prompt: field required"


@pytest.mark.anyio
async def test_unreachable_api_becomes_an_mcp_error():
    client = LifeGuardianClient("http://127.0.0.1:1/nowhere", timeout=1.0)
    with pytest.raises(MCPError):
        await client.get("/api/health")
    assert await client.healthy() is False


@pytest.fixture
def anyio_backend():
    return "asyncio"
