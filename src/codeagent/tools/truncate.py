"""Truncate tool output with an explicit marker."""

from typing import Literal

TRUNCATION_TEMPLATE = "[truncated: {total} chars total; use offset/limit or narrow the search]"


def truncate_content(
    content: str,
    max_chars: int,
    *,
    keep: Literal["head", "tail"] = "tail",
) -> tuple[str, bool]:
    """Return possibly truncated content and whether truncation occurred."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if len(content) <= max_chars:
        return content, False
    marker = TRUNCATION_TEMPLATE.format(total=len(content))
    marker_budget = max_chars
    if len(marker) >= marker_budget:
        return marker[:max_chars], True
    body_budget = max_chars - len(marker) - 1
    if keep == "head":
        body = content[:body_budget]
        return f"{body}\n{marker}", True
    body = content[-body_budget:]
    return f"{marker}\n{body}", True
