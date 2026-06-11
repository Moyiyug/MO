"""模型能力路由（PRD F-012）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..adapters.model_gateway.gateway import (
    ModelCallError,
    ModelConfigError,
    ModelGateway,
    get_model_gateway,
)
from ..adapters.model_gateway.profiles import ProfileStore, get_profile_store
from ..models.model import (
    ModelCapabilitiesResponse,
    ModelProfilePublic,
    ModelTestRequest,
    ModelTestResponse,
)

router = APIRouter(prefix="/api/models", tags=["models"])


def _to_public(store: ProfileStore, profile) -> ModelProfilePublic:
    return ModelProfilePublic(
        id=profile.id,
        provider=profile.provider,
        model_name=profile.model_name,
        capabilities=profile.capabilities,
        has_api_key=store.has_api_key(profile),
        default_temperature=profile.default_temperature,
    )


@router.get("/capabilities", response_model=ModelCapabilitiesResponse)
def list_capabilities(
    store: ProfileStore = Depends(get_profile_store),
) -> ModelCapabilitiesResponse:
    profiles = [_to_public(store, p) for p in store.all()]
    return ModelCapabilitiesResponse(
        profiles=profiles,
        default_routes=store.default_routes,
    )


@router.post("/test", response_model=ModelTestResponse)
async def test_model(
    payload: ModelTestRequest,
    store: ProfileStore = Depends(get_profile_store),
    gateway: ModelGateway = Depends(get_model_gateway),
) -> ModelTestResponse:
    try:
        profile = gateway.select(
            profile_id=payload.profile_id,
            need_reasoning=payload.need_reasoning,
            need_vision=payload.need_vision,
            need_json=payload.need_json,
            long_context=payload.long_context,
        )
    except ModelConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if not store.has_api_key(profile):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"API key not configured: set environment variable {profile.api_key_env}",
        )

    try:
        ok, message, latency_ms = await gateway.test_profile(profile)
    except ModelConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ModelCallError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=message,
        )

    return ModelTestResponse(
        ok=True,
        profile_id=profile.id,
        latency_ms=latency_ms,
        message=message,
    )
