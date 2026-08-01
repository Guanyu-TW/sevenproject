"""Redaction of resident PII from vendor-facing text.

Withholding the structured ``location.address`` field is not enough: the
LLM-written ``summary`` happily repeats a street name the resident mentioned in
their original sentence. That made the "完整門牌地址尚未提供給廠商" promise on
the tracking board false.

So the guarantee is enforced here, deterministically, rather than trusted to
the prompt. The prompt also asks the model to avoid precise addresses, but that
is a nicety on top -- this module is what makes the claim true.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

PLACEHOLDER = "（已隱藏）"

#: Street-level tokens: a short run of CJK ending in a road/lane suffix.
_ROAD_RE = re.compile(r"[\u4e00-\u9fff]{1,8}?(?:路|街|大道|巷|弄)")

#: Patterns that are unambiguously address or phone material.
_GENERIC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"09\d{2}[-\s]?\d{3}[-\s]?\d{3}"),          # mobile
    re.compile(r"0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}"),       # landline
    re.compile(r"\d+\s*號(?:\s*\d+\s*樓)?"),                # 100 號 5 樓
    re.compile(r"\d+\s*樓"),                                # 5 樓
    re.compile(r"[\u4e00-\u9fff]{1,8}?(?:路|街|大道)\s*[一二三四五六七八九十\d]+\s*段"),
)


def _road_tokens(address: str, *, drop: Iterable[str | None]) -> set[str]:
    """Street names inside ``address``, with city/district removed first.

    Dropping the city and district keeps the redaction minimal: those two are
    deliberately shared with the vendor, so they must not be swallowed into a
    longer match such as ``嘉義市西區文化路``.
    """
    text = address
    for part in drop:
        if part:
            text = text.replace(part, " ")
    return {token for token in _ROAD_RE.findall(text) if len(token) >= 2}


def sensitive_terms(
    parsed_data: dict[str, Any] | None,
    form_data: dict[str, Any] | None = None,
) -> set[str]:
    """Literal strings that must never reach a vendor.

    Derived from the resident's own values, which keeps false positives low:
    only this resident's street, name and number get redacted.
    """
    terms: set[str] = set()
    parsed = parsed_data or {}
    location = parsed.get("location") or {}
    contact = parsed.get("contact") or {}

    city = location.get("city")
    district = location.get("district")

    candidates: list[Any] = [
        location.get("address"),
        contact.get("name"),
        contact.get("phone"),
    ]
    for key in ("address", "contact_name", "contact_phone"):
        candidates.append((form_data or {}).get(key))

    for value in candidates:
        if not isinstance(value, str):
            continue
        value = value.strip()
        if len(value) < 2:
            continue
        terms.add(value)
        terms.update(_road_tokens(value, drop=(city, district)))
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 8:
            terms.add(digits)

    # Never redact the two fields we intend to share.
    terms.discard(city or "")
    terms.discard(district or "")
    terms.discard("")
    return terms


def redact(text: str | None, terms: Iterable[str]) -> str | None:
    """Mask every known term plus any generic address/phone pattern."""
    if not text:
        return text

    result = text
    # Longest first so a full address is masked before its street fragment.
    for term in sorted({t for t in terms if t}, key=len, reverse=True):
        if term in result:
            result = result.replace(term, PLACEHOLDER)

    for pattern in _GENERIC_PATTERNS:
        result = pattern.sub(PLACEHOLDER, result)

    # Collapse runs of placeholders produced by overlapping rules.
    result = re.sub(f"(?:{re.escape(PLACEHOLDER)})+", PLACEHOLDER, result)
    return result


__all__ = ["PLACEHOLDER", "redact", "sensitive_terms"]
