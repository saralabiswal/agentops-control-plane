from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import get_db
from app.models.model_pricing import ModelPricing
from app.schemas.settings import (
    ProviderName,
    RuntimeProviderSchema,
    RuntimeSettingsSchema,
    RuntimeSettingsUpdate,
)

__author__ = "Sarala Biswal"

router = APIRouter()

PROVIDER_LABELS: dict[ProviderName, str] = {
    "ollama": "Ollama",
    "groq": "Groq",
    "gemini": "Gemini",
}

PROVIDER_NEXT_ACTIONS: dict[ProviderName, str] = {
    "ollama": "Run a platform or domain demo locally with priced token accounting.",
    "groq": "Add AGENTOPS_GROQ_API_KEY in backend/.env before live Groq runs.",
    "gemini": "Add AGENTOPS_GEMINI_API_KEY in backend/.env before live Gemini runs.",
}

PROVIDER_ORDER: tuple[ProviderName, ...] = ("ollama", "groq", "gemini")


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _is_configured(settings: Settings, provider: ProviderName) -> bool:
    if provider == "ollama":
        return True
    if provider == "groq":
        return bool(settings.groq_api_key)
    return bool(settings.gemini_api_key)


def _set_default_model(settings: Settings, provider: ProviderName, model_name: str) -> None:
    if provider == "ollama":
        settings.ollama_model = model_name
    elif provider == "groq":
        settings.groq_model = model_name
    else:
        settings.gemini_model = model_name


async def _priced_models(db: AsyncSession) -> dict[str, list[str]]:
    result = await db.scalars(
        select(ModelPricing).where(ModelPricing.effective_to.is_(None))
    )
    models: dict[str, list[str]] = {}
    for pricing in result:
        models.setdefault(pricing.provider, [])
        if pricing.model_name not in models[pricing.provider]:
            models[pricing.provider].append(pricing.model_name)
    return models


def _response(settings: Settings, models: dict[str, list[str]]) -> RuntimeSettingsSchema:
    active_provider: ProviderName = (
        settings.active_provider
        if settings.active_provider in PROVIDER_ORDER
        else "ollama"
    )
    providers = [
        RuntimeProviderSchema(
            provider=provider,
            label=PROVIDER_LABELS[provider],
            configured=_is_configured(settings, provider),
            active_model=settings.default_model_for(provider),
            models=models.get(provider, []),
            next_action=PROVIDER_NEXT_ACTIONS[provider],
        )
        for provider in PROVIDER_ORDER
    ]
    return RuntimeSettingsSchema(
        active_provider=active_provider,
        active_model=settings.default_model_for(active_provider),
        providers=providers,
    )


@router.get("/settings/runtime", response_model=RuntimeSettingsSchema)
async def get_runtime_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RuntimeSettingsSchema:
    """Return runtime provider/model options with priced models for the UI settings screen."""
    settings = _settings(request)
    models = await _priced_models(db)
    return _response(settings, models)


@router.patch("/settings/runtime", response_model=RuntimeSettingsSchema)
async def update_runtime_settings(
    payload: RuntimeSettingsUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RuntimeSettingsSchema:
    """Apply the active provider/model when the provider is configured for live execution."""
    settings = _settings(request)
    provider = payload.active_provider
    models = await _priced_models(db)
    if payload.model_name not in models.get(provider, []):
        raise HTTPException(
            status_code=400,
            detail=f"No active pricing row for {provider}:{payload.model_name}",
        )
    if not _is_configured(settings, provider):
        detail = (
            f"{PROVIDER_LABELS[provider]} is not configured. "
            f"{PROVIDER_NEXT_ACTIONS[provider]}"
        )
        raise HTTPException(
            status_code=400,
            detail=detail,
        )
    settings.active_provider = provider
    _set_default_model(settings, provider, payload.model_name)
    return _response(settings, models)
