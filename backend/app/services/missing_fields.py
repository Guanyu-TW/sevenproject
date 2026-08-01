"""Canonical catalogue of the fields the AI is allowed to ask for.

One table drives three things, which is why it lives on its own:
  * the prompt   -- which keys the LLM may emit
  * the frontend -- which input control to render (``input_type``)
  * write-back   -- where a submitted value belongs inside ``parsed_data``
    (``path``)

Adding an askable field is therefore a single edit here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.schemas.ai import BedrockMissingField, InputType, MissingField


@dataclass(frozen=True)
class FieldSpec:
    label: str
    input_type: InputType = "text"
    placeholder: str | None = None
    unit: str | None = None
    reason: str | None = None
    #: Where the value is stored inside LifeTask.parsed_data.
    path: tuple[str, ...] = field(default=())
    #: Coerce the submitted string before storing it.
    cast: str = "str"


FIELD_CATALOG: dict[str, FieldSpec] = {
    "address": FieldSpec(
        label="詳細地址",
        placeholder="例如：嘉義市西區文化路 100 號 5 樓",
        reason="需要完整地址才能派工。",
        path=("location", "address"),
    ),
    "city": FieldSpec(
        label="縣市",
        placeholder="例如：嘉義市",
        reason="需要知道服務地區才能找到附近的廠商。",
        path=("location", "city"),
    ),
    "district": FieldSpec(
        label="行政區",
        placeholder="例如：西區",
        reason="需要行政區才能派給附近的師傅。",
        path=("location", "district"),
    ),
    "budget": FieldSpec(
        label="預算",
        input_type="number",
        placeholder="2000",
        unit="TWD",
        reason="預算範圍會影響可以配合的廠商。",
        path=("budget", "amount"),
        cast="number",
    ),
    "preferred_time": FieldSpec(
        label="希望到場時間",
        input_type="datetime-local",
        reason="需要知道你方便的時間才能安排。",
        path=("preferred_time",),
    ),
    "preferred_date": FieldSpec(
        label="希望日期",
        input_type="date",
        reason="需要知道你希望的日期才能安排。",
        path=("preferred_date",),
    ),
    "contact_name": FieldSpec(
        label="聯絡人姓名",
        placeholder="例如：王小明",
        reason="師傅到場時需要找的人。",
        path=("contact", "name"),
    ),
    "contact_phone": FieldSpec(
        label="聯絡電話",
        input_type="tel",
        placeholder="09xx-xxx-xxx",
        reason="廠商需要電話才能跟你確認細節。",
        path=("contact", "phone"),
    ),
    "photos": FieldSpec(
        label="現場照片",
        input_type="file",
        reason="照片可以讓廠商先判斷零件與報價。",
        path=("attachments",),
        cast="list",
    ),
    "area_size": FieldSpec(
        label="坪數",
        input_type="number",
        placeholder="25",
        unit="坪",
        reason="坪數會影響清潔或裝修的報價。",
        path=("area_size",),
        cast="number",
    ),
    "headcount": FieldSpec(
        label="人數",
        input_type="number",
        placeholder="10",
        unit="人",
        reason="需要知道人數才能估算份量。",
        path=("headcount",),
        cast="number",
    ),
    "quantity": FieldSpec(
        label="數量",
        input_type="number",
        placeholder="1",
        unit="份",
        reason="需要知道數量才能報價。",
        path=("quantity",),
        cast="number",
    ),
    "description": FieldSpec(
        label="補充說明",
        input_type="textarea",
        placeholder="還有什麼需要廠商知道的？",
        reason="多一點細節可以讓報價更準確。",
        path=("description",),
    ),
}

#: Exposed to the prompt so the model only ever emits keys we can render.
ALLOWED_FIELD_KEYS: list[str] = sorted(FIELD_CATALOG)


def _slugify(raw: str) -> str:
    return raw.strip().lower().replace(" ", "_").replace("-", "_")


def normalize_missing_fields(
    raw_fields: Iterable[BedrockMissingField | MissingField | dict],
) -> list[MissingField]:
    """Turn provider output into renderable ``MissingField`` entries.

    Unknown keys are kept rather than dropped: they still render as a plain
    text input using whatever label the model supplied, so an LLM that invents
    a sensible new field degrades gracefully instead of vanishing. Bedrock
    treats the tool schema ``enum`` as a hint, not a hard constraint, so this
    path really does get exercised.
    Duplicates are collapsed on the field key, first occurrence wins.
    """
    normalized: dict[str, MissingField] = {}

    for item in raw_fields:
        if isinstance(item, dict):
            key_raw = str(item.get("field") or "").strip()
            label = item.get("label")
            reason = item.get("reason")
        else:
            key_raw = (item.field or "").strip()
            label = item.label
            reason = item.reason

        if not key_raw:
            continue

        key = _slugify(key_raw)
        if key in normalized:
            continue

        spec = FIELD_CATALOG.get(key)
        if spec is not None:
            normalized[key] = MissingField(
                field=key,
                label=label or spec.label,
                reason=reason or spec.reason,
                required=True,
                input_type=spec.input_type,
                placeholder=spec.placeholder,
                unit=spec.unit,
            )
        else:
            normalized[key] = MissingField(
                field=key,
                label=label or key_raw,
                reason=reason,
                required=True,
                input_type="text",
            )

    return list(normalized.values())


def catalog_field(key: str) -> MissingField:
    """Build a ``MissingField`` straight from the catalogue (used by the mock)."""
    spec = FIELD_CATALOG[key]
    return MissingField(
        field=key,
        label=spec.label,
        reason=spec.reason,
        required=True,
        input_type=spec.input_type,
        placeholder=spec.placeholder,
        unit=spec.unit,
    )


def _coerce(value: Any, cast: str) -> Any:
    if cast == "number":
        if isinstance(value, (int, float)):
            return value
        digits = "".join(ch for ch in str(value) if ch.isdigit() or ch == ".")
        if not digits:
            return None
        try:
            number = float(digits)
        except ValueError:
            return None
        return int(number) if number.is_integer() else number
    if cast == "list":
        if isinstance(value, list):
            return value
        return [value] if value else []
    return str(value)


def _assign(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    """Write ``value`` into ``target`` at ``path``, creating dicts as needed."""
    cursor = target
    for key in path[:-1]:
        nested = cursor.get(key)
        if not isinstance(nested, dict):
            nested = {}
            cursor[key] = nested
        cursor = nested
    cursor[path[-1]] = value


def apply_filled_fields(
    parsed_data: dict[str, Any],
    filled: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Merge user-submitted values into ``parsed_data``.

    Returns the updated copy plus the list of field keys that were actually
    stored, so the caller can prune ``missing_fields``. Blank submissions are
    ignored: a user clicking through without typing must not overwrite what the
    AI already extracted.
    """
    updated = dict(parsed_data)
    applied: list[str] = []

    for key, raw_value in filled.items():
        normalized_key = _slugify(str(key))
        if raw_value is None:
            continue
        if isinstance(raw_value, str) and not raw_value.strip():
            continue
        if isinstance(raw_value, list) and not raw_value:
            continue

        spec = FIELD_CATALOG.get(normalized_key)
        if spec is None:
            # Unknown key: keep it, but quarantine it under extra_fields so it
            # can never collide with a structured key we rely on.
            extra = dict(updated.get("extra_fields") or {})
            extra[normalized_key] = raw_value
            updated["extra_fields"] = extra
            applied.append(normalized_key)
            continue

        value = _coerce(
            raw_value.strip() if isinstance(raw_value, str) else raw_value, spec.cast
        )
        if value is None:
            continue

        _assign(updated, spec.path or (normalized_key,), value)
        applied.append(normalized_key)

    return updated, applied


__all__ = [
    "ALLOWED_FIELD_KEYS",
    "FIELD_CATALOG",
    "FieldSpec",
    "apply_filled_fields",
    "catalog_field",
    "normalize_missing_fields",
]
