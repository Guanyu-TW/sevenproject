"""seed demo vendors across categories, cities and price bands

Revision ID: 0004_seed_vendors
Revises: 0003_vendor_matching
Create Date: 2026-08-01

"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_seed_vendors"
down_revision: Union[str, None] = "0003_vendor_matching"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# name, rating, city, districts, price_min, price_max, category codes, description
VENDORS: list[tuple[str, float, str, list[str], int, int, list[str], str]] = [
    (
        "阿明水電行",
        4.8,
        "嘉義市",
        ["西區", "東區"],
        800,
        3500,
        ["plumbing"],
        "在地經營 20 年的老字號，專精漏水抓漏與衛浴管線，可當日到場。",
    ),
    (
        "快修水電 24H",
        4.3,
        "嘉義市",
        [],
        1200,
        6000,
        ["plumbing"],
        "24 小時緊急派工，全嘉義市服務，深夜與假日不加價。",
    ),
    (
        "誠信管線工程",
        4.9,
        "嘉義市",
        ["西區"],
        2000,
        12000,
        ["plumbing"],
        "承接較大型的管線更換與防水工程，報價透明並提供一年保固。",
    ),
    (
        "潔淨家事服務",
        4.6,
        "嘉義市",
        ["西區", "東區"],
        1500,
        5000,
        ["cleaning"],
        "定期居家清潔與深度打掃，家事人員皆有勞保與教育訓練。",
    ),
    (
        "亮晶晶清潔公司",
        4.1,
        "嘉義市",
        [],
        1000,
        4000,
        ["cleaning"],
        "價格實惠的鐘點清潔，適合小坪數與租屋族退租打掃。",
    ),
    (
        "台南速修水電",
        4.5,
        "台南市",
        ["東區", "中西區", "北區"],
        1000,
        5000,
        ["plumbing"],
        "台南市區 60 分鐘到場，馬桶阻塞與漏水搶修為主力項目。",
    ),
    (
        "府城生活管家",
        4.7,
        "台南市",
        ["東區"],
        1800,
        7000,
        ["cleaning", "shopping"],
        "同時承接居家清潔與代購跑腿，適合忙碌雙薪家庭長期合作。",
    ),
    (
        "嘉義好食便當",
        4.4,
        "嘉義市",
        ["西區", "東區"],
        80,
        200,
        ["dining"],
        "團體訂餐與會議便當，10 份以上免運，可配合素食與過敏需求。",
    ),
    (
        "隔壁鄰居代買",
        4.0,
        "嘉義市",
        ["西區"],
        100,
        800,
        ["shopping"],
        "社區內代購與領取包裹，適合臨時缺東西的小額採買。",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()

    categories = {
        row.code: row.id
        for row in bind.execute(
            sa.text("SELECT id, code FROM service_categories")
        ).fetchall()
    }

    for name, rating, city, districts, low, high, codes, description in VENDORS:
        # Every vendor row needs an owning user, so create one per vendor.
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
    names = [v[0] for v in VENDORS]
    bind = op.get_bind()
    # vendor_service_categories rows go away through ON DELETE CASCADE.
    bind.execute(
        sa.text("DELETE FROM vendors WHERE name IN :names").bindparams(
            sa.bindparam("names", value=names, expanding=True)
        )
    )
    bind.execute(
        sa.text("DELETE FROM users WHERE role = 'vendor' AND name IN :names").bindparams(
            sa.bindparam("names", value=names, expanding=True)
        )
    )
