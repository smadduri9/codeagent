"""Reference fix applied by the scripted demonstration test."""

from pathlib import Path

CHECKOUT = Path(__file__).with_name("checkout.py")


def apply() -> None:
    text = CHECKOUT.read_text(encoding="utf-8")
    fixed = text.replace('return 500, "internal error"', 'return 402, "payment required"')
    CHECKOUT.write_text(fixed, encoding="utf-8")
