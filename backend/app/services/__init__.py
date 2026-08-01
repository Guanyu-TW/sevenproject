from app.services.ai_service import (
    AIProvider,
    AIProviderError,
    MockAIProvider,
    RealAIProvider,
    available_providers,
    get_ai_provider,
    register_provider,
)
from app.services.case_service import (
    CaseCreationError,
    DuplicateCaseError,
    create_case,
    find_active_case,
    get_case,
    to_case_read,
)
from app.services.health_service import check_database
from app.services.life_task_service import (
    TaskTransitionError,
    create_task_from_analysis,
    get_or_create_demo_user,
    get_task,
    list_category_hints,
    resolve_user,
    update_task,
)
from app.services.matching_service import (
    MatchingStateError,
    build_demand_context,
    find_candidates,
    match_vendors,
)
from app.services.missing_fields import (
    ALLOWED_FIELD_KEYS,
    FIELD_CATALOG,
    apply_filled_fields,
    normalize_missing_fields,
)

__all__ = [
    "ALLOWED_FIELD_KEYS",
    "AIProvider",
    "AIProviderError",
    "CaseCreationError",
    "DuplicateCaseError",
    "FIELD_CATALOG",
    "MatchingStateError",
    "create_case",
    "find_active_case",
    "get_case",
    "to_case_read",
    "MockAIProvider",
    "RealAIProvider",
    "TaskTransitionError",
    "apply_filled_fields",
    "available_providers",
    "build_demand_context",
    "check_database",
    "create_task_from_analysis",
    "find_candidates",
    "get_ai_provider",
    "get_or_create_demo_user",
    "get_task",
    "list_category_hints",
    "match_vendors",
    "normalize_missing_fields",
    "register_provider",
    "resolve_user",
    "update_task",
]
