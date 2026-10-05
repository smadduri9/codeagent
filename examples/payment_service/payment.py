"""Payment processing (demo fixture)."""


class CardExpiredError(Exception):
    """Raised when a card is past its expiry date."""


def charge(card: dict[str, str], amount_cents: int) -> int:
    if card.get("status") == "expired":
        raise CardExpiredError("card expired")
    return amount_cents
