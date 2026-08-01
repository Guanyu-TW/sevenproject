"""broaden the service catalogue and seed vendors for the new categories

Revision ID: 0008_more_categories
Revises: 0007_contact_shared
Create Date: 2026-08-02

Four categories made every plumbing-ish request land on 水電維修, so the vendor
portal looked like it only knew one kind of job. Six more are added here.

Every new category ships with at least one active vendor in 嘉義市 (the demo
city) and one in 台南市. Matching hard-filters on category *and* city, so a
category with no vendor behind it would dead-end the flow the moment the AI
classified something into it.

The category list is read from the database and injected into the LLM system
prompt, so nothing else has to change for the model to start using these.
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_more_categories"
down_revision: Union[str, None] = "0007_contact_shared"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_CATEGORIES = [
    ("appliance", "家電維修"),
    ("aircon", "冷氣空調"),
    ("handyman", "居家修繕"),
    ("pest", "除蟲消毒"),
    ("moving", "搬家搬運"),
    ("eldercare", "長者照護"),
]

# name, rating, city, districts, price_min, price_max, category codes, description
NEW_VENDORS: list[tuple[str, float, str, list[str], int, int, list[str], str]] = [
    (
        "家電醫生維修中心",
        4.7,
        "嘉義市",
        ["西區", "東區"],
        600,
        8000,
        ["appliance"],
        "冰箱、洗衣機、烘乾機到場檢修，原廠零件並提供三個月保固。",
    ),
    (
        "台南家電急救隊",
        4.4,
        "台南市",
        ["東區", "北區", "中西區"],
        700,
        9000,
        ["appliance"],
        "大型家電搬運與維修一次到位，檢測費可折抵修繕費用。",
    ),
    (
        "涼快冷氣工程",
        4.8,
        "嘉義市",
        ["西區", "東區"],
        1200,
        25000,
        ["aircon", "appliance"],
        "分離式冷氣安裝、灌冷媒與深度清洗，夏季可預約假日時段。",
    ),
    (
        "府城空調專家",
        4.5,
        "台南市",
        ["東區"],
        1500,
        30000,
        ["aircon"],
        "商用與住宅空調規劃，附冷氣耗電評估與節能建議。",
    ),
    (
        "巧手居家修繕",
        4.6,
        "嘉義市",
        ["西區", "東區"],
        500,
        15000,
        ["handyman", "plumbing"],
        "門窗、鎖具、櫥櫃與油漆補土等零星修繕，小工程也願意接。",
    ),
    (
        "南方木作工班",
        4.9,
        "台南市",
        ["中西區", "東區"],
        3000,
        60000,
        ["handyman"],
        "客製木作與系統櫃安裝，現場丈量免費並提供 3D 示意圖。",
    ),
    (
        "無蟲居環境防治",
        4.5,
        "嘉義市",
        [],
        1500,
        12000,
        ["pest"],
        "白蟻、蟑螂與跳蚤處理，使用低氣味藥劑，寵物與幼童家庭適用。",
    ),
    (
        "台南除蟲消毒行",
        4.2,
        "台南市",
        ["東區", "安平區"],
        1200,
        10000,
        ["pest", "cleaning"],
        "定期消毒約與單次施作皆可，附施作前後環境紀錄照片。",
    ),
    (
        "順心搬家公司",
        4.4,
        "嘉義市",
        ["西區", "東區"],
        2500,
        30000,
        ["moving"],
        "小資套房到整層住家搬遷，含紙箱借用與家具拆裝。",
    ),
    (
        "台南輕鬆搬",
        4.1,
        "台南市",
        [],
        2000,
        26000,
        ["moving", "shopping"],
        "機車、鋼琴等特殊物件搬運，可代購包材並現場報價。",
    ),
    (
        "安心長照陪伴",
        4.9,
        "嘉義市",
        ["西區", "東區"],
        800,
        6000,
        ["eldercare"],
        "陪同就醫、居家陪伴與備餐，照服員皆持有照顧服務員證照。",
    ),
    (
        "府城照護管家",
        4.6,
        "台南市",
        ["東區", "北區"],
        1000,
        7500,
        ["eldercare", "cleaning"],
        "長者日常照護搭配居家清潔，可配合復健療程安排時段。",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()

    service_categories = sa.table(
        "service_categories",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        service_categories,
        [{"code": code, "name": name} for code, name in NEW_CATEGORIES],
    )

    categories = {
        row.code: row.id
        for row in bind.execute(
            sa.text("SELECT id, code FROM service_categories")
        ).fetchall()
    }

    for name, rating, city, districts, low, high, codes, description in NEW_VENDORS:
        # Same shape as 0004: every vendor row needs an owning user.
        user_id = bind.execute(
            sa.text(
                "INSERT INTO users (name, role) VALUES (:name, 'vendor') RETURNING id"
            ),
            {"name": name},
        ).scalar_one()

        vendor_id = bind.execute(
            sa.text(
                """
                INSERT INTO vendors
                    (user_id, name, rating, description, service_city,
                     service_districts, price_min, price_max, is_active)
                VALUES
                    (:user_id, :name, :rating, :description, :city,
                     CAST(:districts AS jsonb), :low, :high, true)
                RETURNING id
                """
            ),
            {
                "user_id": user_id,
                "name": name,
                "rating": rating,
                "description": description,
                "city": city,
                "districts": json.dumps(districts, ensure_ascii=False),
                "low": low,
                "high": high,
            },
        ).scalar_one()

        for code in codes:
            category_id = categories.get(code)
            if category_id is None:
                continue
            bind.execute(
                sa.text(
                    "INSERT INTO vendor_service_categories (vendor_id, category_id) "
                    "VALUES (:vendor_id, :category_id)"
                ),
                {"vendor_id": vendor_id, "category_id": category_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    names = [v[0] for v in NEW_VENDORS]
    codes = tuple(code for code, _ in NEW_CATEGORIES)

    # vendor_service_categories rows go away through ON DELETE CASCADE.
    bind.execute(
        sa.text("DELETE FROM vendors WHERE name IN :names").bindparams(
            sa.bindparam("names", value=names, expanding=True)
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM users WHERE role = 'vendor' AND name IN :names"
        ).bindparams(sa.bindparam("names", value=names, expanding=True))
    )
    # life_tasks.category_id is ON DELETE SET NULL, so this is safe even if a
    # task was already classified into one of these.
    bind.execute(
        sa.text("DELETE FROM service_categories WHERE code IN :codes").bindparams(
            sa.bindparam("codes", value=codes, expanding=True)
        )
    )
