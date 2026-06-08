from typing import Literal

from pydantic import BaseModel

ProviderName = Literal["ollama", "groq", "gemini"]


class RuntimeProviderSchema(BaseModel):
    provider: ProviderName
    label: str
    configured: bool
    active_model: str
    models: list[str]
    next_action: str


class RuntimeSettingsSchema(BaseModel):
    active_provider: ProviderName
    active_model: str
    providers: list[RuntimeProviderSchema]


class RuntimeSettingsUpdate(BaseModel):
    active_provider: ProviderName
    model_name: str
