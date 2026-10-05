from codeagent.context.prompts import load_system_prompt, prompt_hash


def test_prompt_regression_hashes_stable() -> None:
    text = load_system_prompt()
    assert prompt_hash(text) == prompt_hash(text)


def test_prompt_covers_required_themes() -> None:
    text = load_system_prompt().lower()
    for phrase in ("tool", "verify", "grep", "denied", "budget"):
        assert phrase in text
