"""Provider-side quota and retry errors."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base provider failure."""


class ContextOverflowError(ProviderError):
    """Non-retryable request-too-large response."""


class QuotaExhaustedError(ProviderError):
    """Daily or long-wait quota exhaustion."""

    def __init__(self, message: str, *, reset_at: str | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


class RateLimitError(ProviderError):
    """Retryable rate limit."""

    def __init__(self, message: str, *, retry_after_s: float) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s
