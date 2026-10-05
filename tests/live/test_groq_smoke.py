import os

import pytest

from codeagent.config import Settings
from codeagent.providers.openai_compatible import OpenAICompatibleProvider
from tests.providers.test_contract import run_contract_suite


@pytest.mark.live
def test_groq_smoke_when_key_present() -> None:
    settings = Settings()
    if not os.environ.get(settings.model.api_key_env):
        pytest.skip("live provider key not set")
    provider = OpenAICompatibleProvider(
        base_url=settings.model.base_url,
        api_key_env=settings.model.api_key_env,
    )
    run_contract_suite(provider)
