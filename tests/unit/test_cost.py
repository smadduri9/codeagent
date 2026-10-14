"""Cost includes cache-write tokens at the configured write price."""

from codeagent.config import Price, Settings
from codeagent.providers.base import Usage
from codeagent.providers.cost import compute_cost


def test_cache_write_is_billed() -> None:
    settings = Settings(
        prices={"m": Price(input=1, output=0, cache_read=0, cache_write=1.25)},
    )
    usage = Usage(input=1_000_000, output=0, cache_read=0, cache_write=1_000_000)
    cost, note = compute_cost("m", usage, settings)
    assert note is None
    assert cost == 2.25
