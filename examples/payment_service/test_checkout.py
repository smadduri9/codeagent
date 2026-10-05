from checkout import checkout


def test_expired_card_returns_402() -> None:
    status, _ = checkout({"status": "expired"}, 100)
    assert status == 402
