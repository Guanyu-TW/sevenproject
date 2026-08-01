"""Vendor matching: hard filter first, then AI ranking.

Two stages on purpose. The hard filter is deterministic SQL so we can always
explain why a vendor was or was not considered, and the LLM only ever ranks and
justifies a candidate set it did not choose. That keeps the AI out of the
correctness path: a hallucinated vendor id simply gets dropped.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import LifeTask, TaskStatus, Vendor
from app.schemas.matching import (
    DemandContext,
    MatchVendorsResponse,
    VendorContext,
)
from app.schemas.vendor import VendorRecommendation
from app.services.ai_service import AIProvider, AIProviderError, _midpoint_price

logger = logging.getLogger(__name__)


class MatchingStateError(RuntimeError):
    """The task is not in a state where matching makes sense."""

    def __init__(self, message: str, *, current_status: str):
        super().__init__(message)
        self.current_status = current_status


def build_demand_context(task: LifeTask) -> DemandContext:
    parsed: dict[str, Any] = task.parsed_data or {}
    budget = parsed.get("budget") or {}
    location = parsed.get("location") or {}

    return DemandContext(
        task_id=task.id,
        title=parsed.get("title"),
        summary=parsed.get("summary"),
        category_name=task.category.name if task.category else None,
        service_type=parsed.get("service_type"),
        budget_amount=_as_float(budget.get("amount")),
        currency=budget.get("currency") or "TWD",
        city=location.get("city"),
        district=location.get("district"),
        address=location.get("address"),
        urgency=parsed.get("urgency"),
        preferred_time=parsed.get("preferred_time"),
        preferred_date=parsed.get("preferred_date"),
        description=parsed.get("description"),
        raw_input=task.raw_input,
    )


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def find_candidates(db: Session, task: LifeTask) -> list[Vendor]:
    """Hard filter: active vendors whose category and area cover the demand.

    City is matched in SQL; district is refined in Python because coverage is
    stored as a JSONB list and the candidate set is small.
    """
    if task.category_id is None:
        logger.info("Task %s has no category, no vendor can be matched", task.id)
        return []

    location = (task.parsed_data or {}).get("location") or {}
    city = (location.get("city") or "").strip() or None
    district = (location.get("district") or "").strip() or None

    # EXISTS via .any() rather than a join, so a vendor listing several
    # categories cannot come back duplicated.
    stmt = (
        select(Vendor)
        .options(selectinload(Vendor.categories))
        .where(
            Vendor.is_active.is_(True),
            Vendor.categories.any(id=task.category_id),
        )
        .order_by(Vendor.rating.desc(), Vendor.id)
    )
    if city:
        stmt = stmt.where(Vendor.service_city == city)

    candidates = list(db.scalars(stmt).all())
    if district:
        candidates = [v for v in candidates if v.covers_district(district)]

    logger.info(
        "Task %s hard filter: category_id=%s city=%s district=%s -> %d candidates",
        task.id,
        task.category_id,
        city,
        district,
        len(candidates),
    )
    return candidates


def _to_context(vendor: Vendor) -> VendorContext:
    return VendorContext(
        id=vendor.id,
        name=vendor.name,
        rating=float(vendor.rating),
        description=vendor.description,
        service_city=vendor.service_city,
        service_districts=[str(d) for d in (vendor.service_districts or [])],
        price_min=vendor.price_min,
        price_max=vendor.price_max,
        categories=[c.name for c in vendor.categories],
    )


def _rule_based_ranking(
    contexts: list[VendorContext],
    demand: DemandContext,
    limit: int,
) -> list[VendorRecommendation]:
    """Deterministic fallback so a Bedrock outage never blocks the flow."""
    ranked = sorted(contexts, key=lambda v: v.rating, reverse=True)[:limit]
    out: list[VendorRecommendation] = []

    for vendor in ranked:
        within_budget = (
            demand.budget_amount is not None
            and vendor.price_min is not None
            and vendor.price_min <= demand.budget_amount
        )
        reason_parts = [f"評分 {vendor.rating} 分"]
        if vendor.service_city:
            districts = (
                "、".join(vendor.service_districts)
                if vendor.service_districts
                else "全市"
            )
            reason_parts.append(f"服務範圍涵蓋{vendor.service_city}{districts}")
        if vendor.price_min is not None and vendor.price_max is not None:
            reason_parts.append(f"報價區間 {vendor.price_min}-{vendor.price_max} 元")
            reason_parts.append("在你的預算內" if within_budget else "可能略高於你的預算")

        out.append(
            VendorRecommendation(
                vendor_id=vendor.id,
                name=vendor.name,
                rating=vendor.rating,
                description=vendor.description,
                service_city=vendor.service_city,
                service_districts=vendor.service_districts,
                price_min=vendor.price_min,
                price_max=vendor.price_max,
                categories=vendor.categories,
                estimated_price=_midpoint_price(vendor, demand.budget_amount),
                match_score=round(min(vendor.rating / 5.0, 1.0), 2),
                recommendation_reason="，".join(reason_parts) + "。（規則式排序，未使用 AI）",
            )
        )
    return out


def match_vendors(
    db: Session,
    *,
    task: LifeTask,
    provider: AIProvider,
    limit: int = 3,
) -> MatchVendorsResponse:
    """Run the full matching pipeline for a task.

    Raises:
        MatchingStateError: if the task is not ready_for_matching.
    """
    if task.status != TaskStatus.READY_FOR_MATCHING:
        raise MatchingStateError(
            f"任務目前狀態是 {task.status}，必須先補齊資料並轉為 "
            f"{TaskStatus.READY_FOR_MATCHING} 才能媒合。",
            current_status=str(task.status),
        )

    demand = build_demand_context(task)
    candidates = find_candidates(db, task)

    if not candidates:
        return MatchVendorsResponse(
            task_id=task.id,
            status=str(task.status),
            category_code=task.category.code if task.category else None,
            candidate_count=0,
            recommendations=[],
            provider=provider.name,
        )

    contexts = [_to_context(v) for v in candidates]
    by_id = {c.id: c for c in contexts}

    fallback_used = False
    fallback_reason: str | None = None
    recommendations: list[VendorRecommendation] = []

    try:
        ranking = provider.recommend_vendors(
            demand=demand, vendors=contexts, limit=limit
        )
        for pick in ranking.recommendations:
            vendor = by_id.get(pick.vendor_id)
            if vendor is None:
                # The model invented an id. Drop it rather than trust it.
                logger.warning(
                    "Provider returned unknown vendor_id=%s for task %s",
                    pick.vendor_id,
                    task.id,
                )
                continue
            recommendations.append(
                VendorRecommendation(
                    vendor_id=vendor.id,
                    name=vendor.name,
                    rating=vendor.rating,
                    description=vendor.description,
                    service_city=vendor.service_city,
                    service_districts=vendor.service_districts,
                    price_min=vendor.price_min,
                    price_max=vendor.price_max,
                    categories=vendor.categories,
                    estimated_price=_clamp_price(pick.estimated_price, vendor),
                    match_score=pick.match_score,
                    recommendation_reason=pick.recommendation_reason.strip(),
                )
            )
    except AIProviderError as exc:
        logger.warning("AI ranking failed for task %s, falling back: %s", task.id, exc)
        fallback_used = True
        fallback_reason = str(exc)

    if not recommendations:
        if not fallback_used:
            fallback_used = True
            fallback_reason = "AI 沒有回傳任何可用的推薦，已改用規則式排序。"
        recommendations = _rule_based_ranking(contexts, demand, limit)

    recommendations.sort(key=lambda r: r.match_score, reverse=True)
    recommendations = recommendations[:limit]

    return MatchVendorsResponse(
        task_id=task.id,
        status=str(task.status),
        category_code=task.category.code if task.category else None,
        candidate_count=len(candidates),
        recommendations=recommendations,
        provider=provider.name,
        model=(task.parsed_data or {}).get("_meta", {}).get("model"),
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
    )


def _clamp_price(value: float | None, vendor: VendorContext) -> int | None:
    """Keep the AI's estimate inside the vendor's advertised range."""
    if value is None:
        return _midpoint_price(vendor, None)
    price = int(value)
    if vendor.price_min is not None:
        price = max(price, vendor.price_min)
    if vendor.price_max is not None:
        price = min(price, vendor.price_max)
    return price


__all__ = [
    "MatchingStateError",
    "build_demand_context",
    "find_candidates",
    "match_vendors",
]
