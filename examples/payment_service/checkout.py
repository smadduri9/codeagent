"""HTTP checkout handler (demo fixture)."""

from payment import CardExpiredError, charge


def checkout(card: dict[str, str], amount_cents: int) -> tuple[int, str]:
    try:
        charge(card, amount_cents)
    except CardExpiredError:
        return 500, "internal error"
    return 200, "ok"
