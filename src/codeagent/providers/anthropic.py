"""Native Anthropic provider. The SDK is an optional extra, imported lazily."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from codeagent.config_secrets import resolve_env_value
from codeagent.providers.anthropic_mapping import map_stream, to_anthropic_request
from codeagent.providers.base import Message, ModelEvent, ModelRequest
from codeagent.providers.quota_errors import ProviderError

_API_KEY_ENV = "ANTHROPIC_API_KEY"
_MISSING_SDK = "the Anthropic provider needs the optional extra: pip install 'codeagent[anthropic]'"


class AnthropicProvider:
    """Stream Messages API responses as codeagent model events."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], Any] | None = None,
        start_dir: Path | None = None,
        user_dir: Path | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._start_dir = start_dir
        self._user_dir = user_dir

    def _client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        try:
            sdk = importlib.import_module("anthropic")
        except ImportError as exc:
            raise ProviderError(_MISSING_SDK) from exc
        # Same lookup as the Groq key: environment, then repo .env, then ~/.codeagent/.env.
        key = resolve_env_value(
            _API_KEY_ENV,
            self._start_dir or Path.cwd(),
            user_dir=self._user_dir,
        )
        if not key:
            raise ProviderError(f"{_API_KEY_ENV} is not set")
        return sdk.Anthropic(api_key=key)

    def stream(self, req: ModelRequest) -> Iterator[ModelEvent]:
        client = self._client()
        body = to_anthropic_request(req)
        raw = client.messages.create(**body, stream=True)
        yield from map_stream(event.model_dump() for event in raw)

    def count_tokens(self, messages: list[Message]) -> int:
        """Rough estimate: about four characters per token."""
        chars = sum(len(m.content or "") for m in messages)
        return chars // 4 + 1
