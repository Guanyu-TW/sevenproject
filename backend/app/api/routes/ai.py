from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.models import LifeTask
from app.schemas.ai import AnalyzeDemandRequest
from app.schemas.life_task import LifeTaskRead
from app.services.ai_service import AIProviderError, get_ai_provider
from app.services.life_task_service import (
    create_task_from_analysis,
    list_category_hints,
    resolve_user,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/analyze-demand",
    response_model=LifeTaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Turn free-form resident input into a draft LifeTask",
)
def analyze_demand(payload: AnalyzeDemandRequest, db: DbSession) -> LifeTask:
    """Analyse a demand, persist it as a draft task, and return the saved row.

    The provider is resolved from settings, so the caller never depends on
    whether the mock or Amazon Bedrock answered.
    """
    try:
        provider = get_ai_provider()
    except ValueError as exc:  # misconfigured AI_PROVIDER
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    try:
        user = resolve_user(db, payload.user_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    try:
        analysis = provider.analyze_demand(
            payload.prompt,
            categories=list_category_hints(db),
        )
    except AIProviderError as exc:
        # 503 when retrying could plausibly help, 502 when the upstream call is
        # broken in a way the caller cannot fix by retrying.
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.retryable
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc

    return create_task_from_analysis(
        db,
        user=user,
        prompt=payload.prompt,
        analysis=analysis,
        provider_name=provider.name,
    )
