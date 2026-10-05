from codeagent.config import Settings, apply_profile
from codeagent.providers.base import Usage
from codeagent.providers.cost import compute_cost, prices_active


def test_free_tier_defaults_unchanged() -> None:
    settings = Settings()
    assert apply_profile(settings) is settings


def test_zero_prices_skip_cost() -> None:
    settings = Settings()
    assert not prices_active(settings)
    cost, note = compute_cost("any", Usage(input=100, output=50), settings)
    assert cost is None and note
