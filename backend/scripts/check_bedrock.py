"""Diagnose the Amazon Bedrock setup before wiring it into the app.

Run from the backend directory:

    .venv\\Scripts\\python.exe scripts\\check_bedrock.py

Checks, in order:
  1. configuration (region / model id / whether credentials resolved at all)
  2. STS identity, to prove the credentials are valid
  3. a real analyze_demand() call through RealAIProvider

Credential values are never printed. Only presence and the resolution source.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a plain script from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.schemas.ai import CategoryHint  # noqa: E402

SAMPLE_PROMPT = "嘉義市西區文化路的廚房水龍頭一直滴水，預算大概兩千元，希望這週末處理"

SAMPLE_CATEGORIES = [
    CategoryHint(code="plumbing", name="水電維修"),
    CategoryHint(code="cleaning", name="居家清潔"),
    CategoryHint(code="dining", name="餐飲訂購"),
    CategoryHint(code="shopping", name="代購採買"),
]


def mask_account(arn: str) -> str:
    """Keep the ARN readable without pasting a full account id into logs."""
    parts = arn.split(":")
    if len(parts) > 4 and parts[4].isdigit() and len(parts[4]) >= 6:
        parts[4] = f"{parts[4][:4]}****{parts[4][-2:]}"
    return ":".join(parts)


def step(number: int, title: str) -> None:
    print(f"\n[{number}] {title}")


def main() -> int:
    print("=" * 68)
    print("Amazon Bedrock 設定檢查")
    print("=" * 68)

    step(1, "設定")
    print(f"  AI_PROVIDER          = {settings.AI_PROVIDER}")
    print(f"  AWS_DEFAULT_REGION   = {settings.AWS_DEFAULT_REGION}")
    print(f"  BEDROCK_MODEL_ID     = {settings.BEDROCK_MODEL_ID}")
    print(f"  BEDROCK_MAX_TOKENS   = {settings.BEDROCK_MAX_TOKENS}")
    print(f"  .env 有靜態金鑰       = {settings.has_static_aws_credentials}")

    if settings.AI_PROVIDER.strip().lower() == "mock":
        print("\n  提醒：AI_PROVIDER 目前是 mock，API 仍會回傳假資料。")
        print("        要真的呼叫 Bedrock，請把 backend/.env 的 AI_PROVIDER 改成 bedrock。")

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    except ImportError:
        print("\n  FAIL: boto3 未安裝。請執行 pip install -r requirements.txt")
        return 1

    step(2, "AWS 憑證（STS GetCallerIdentity）")
    session = boto3.session.Session(region_name=settings.AWS_DEFAULT_REGION)
    creds = session.get_credentials()
    if creds is None:
        print("  FAIL: boto3 找不到任何憑證。")
        print("        請在 backend/.env 填入 AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY，")
        print("        或設定 ~/.aws/credentials。")
        return 1
    print(f"  憑證來源 = {creds.method}")

    try:
        identity = session.client("sts").get_caller_identity()
        print(f"  身分     = {mask_account(identity['Arn'])}")
    except (ClientError, BotoCoreError, NoCredentialsError) as exc:
        print(f"  FAIL: 憑證無效 — {type(exc).__name__}: {exc}")
        return 1

    step(3, f"呼叫 Bedrock（{settings.BEDROCK_MODEL_ID}）")
    from app.services.ai_service import AIProviderError, RealAIProvider

    try:
        analysis = RealAIProvider().analyze_demand(
            SAMPLE_PROMPT, categories=SAMPLE_CATEGORIES
        )
    except AIProviderError as exc:
        print(f"  FAIL [{exc.code}]")
        print(f"  {exc}")
        return 1

    print("  OK")
    print(f"\n  測試輸入  : {SAMPLE_PROMPT}")
    print(f"  intent    : {analysis.intent}")
    print(f"  title     : {analysis.title}")
    print(f"  分類      : {analysis.category_code}")
    print(f"  信心      : {analysis.confidence}")
    print(f"  預算      : {analysis.parsed_data.get('budget')}")
    print(f"  地點      : {analysis.parsed_data.get('location')}")
    print(f"  用量      : {analysis.parsed_data.get('usage')}")
    print("  缺少欄位  :")
    for field in analysis.missing_fields:
        print(f"    - {field.field} ({field.input_type}) {field.label}：{field.reason}")

    print("\n所有檢查通過。把 backend/.env 的 AI_PROVIDER 設成 bedrock 就會走真實模型。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
