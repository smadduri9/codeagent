"""Security: output truncation preserves tail marker."""

from codeagent.tools.truncate import TRUNCATION_TEMPLATE, truncate_content


def test_output_truncation_works() -> None:
    content = "a" * 10_000
    truncated, did = truncate_content(content, 500, keep="tail")
    assert did
    assert TRUNCATION_TEMPLATE.format(total=len(content))[:20] in truncated
    assert len(truncated) <= 500
