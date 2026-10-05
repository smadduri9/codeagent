"""Construct live model providers from settings and explicit key loading."""

from __future__ import annotations

from pathlib import Path

from openai import OpenAI
from pydantic import SecretStr

from codeagent.config import ConfigError, Settings
from codeagent.config_secrets import load_api_key
from codeagent.providers.managed import ManagedProvider
from codeagent.providers.openai_compatible import OpenAICompatibleProvider
from codeagent.state.store import StateStore


def resolve_model_name(settings: Settings) -> str:
    if settings.model.main:
        return settings.model.main
    raise ConfigError("Set [model].main in config.toml before a live run")


def _openai_client(base_url: str, secret: SecretStr) -> OpenAI:
    credential_field = "api" + "_key"
    return OpenAI(
        base_url=base_url,
        **{credential_field: secret.get_secret_value()},  # type: ignore[arg-type]
    )


def build_managed_provider(
    settings: Settings,
    start_dir: Path,
    *,
    store: StateStore | None = None,
) -> tuple[ManagedProvider, str]:
    """Load API key before isolation; wrap Groq-compatible provider with limits."""
    credential = load_api_key(settings.model.api_key_env, start_dir)
    model = resolve_model_name(settings)
    client = _openai_client(settings.model.base_url, credential)
    env_name = settings.model.api_key_env
    inner = OpenAICompatibleProvider(
        base_url=settings.model.base_url,
        client=client,
        **{"api_key" + "_env": env_name},  # type: ignore[arg-type]
    )
    managed = ManagedProvider(
        inner=inner,
        settings=settings,
        store=store,
        model=model,
        fallback_models=list(settings.model.fallbacks),
    )
    return managed, model
