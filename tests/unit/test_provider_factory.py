"""Provider factory tests."""

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from codeagent.config import ConfigError, Settings
from codeagent.providers.factory import build_managed_provider, resolve_model_name


def test_resolve_model_name_requires_main() -> None:
    with pytest.raises(ConfigError, match="~/.codeagent/config.toml"):
        resolve_model_name(Settings())


def test_build_managed_provider_uses_explicit_key(tmp_path: Path) -> None:
    settings = Settings.model_validate({"model": {"main": "test-model"}})
    with patch(
        "codeagent.providers.factory.load_api_key",
        return_value=SecretStr("secret"),
    ):
        with patch("codeagent.providers.factory.OpenAI"):
            provider, model = build_managed_provider(settings, tmp_path)
    assert model == "test-model"
    assert provider.model == "test-model"
