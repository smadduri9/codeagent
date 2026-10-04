"""Validated configuration; loading settings never loads an API key."""

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

PositiveInt = Annotated[int, Field(gt=0)]
Nonempty = Annotated[str, Field(min_length=1, pattern=r"\S")]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class ConfigError(ValueError):
    """Configuration cannot be used; diagnostics must not include values."""


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class ModelSettings(ConfigModel):
    provider: Literal["openai_compatible"] = "openai_compatible"
    base_url: str = "https://api.groq.com/openai/v1"
    api_key_env: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")] = "GROQ_API_KEY"
    main: Nonempty | None = None
    cheap: Nonempty | None = None
    fallbacks: list[Nonempty] = Field(default_factory=list)
    reasoning_effort: Nonempty = "low"
    profile: Literal["free_tier", "standard"] = "free_tier"

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        from urllib.parse import urlsplit

        try:
            url = urlsplit(value)
            port = url.port
        except ValueError:
            raise ValueError("base_url must be a valid HTTP(S) endpoint") from None
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or any(char.isspace() for char in value)
            or port == 0
        ):
            raise ValueError("base_url must be an HTTP(S) endpoint without credentials")
        return value


class LimitSettings(ConfigModel):
    max_iterations: PositiveInt = 30
    max_tool_calls: PositiveInt = 100
    max_total_tokens: PositiveInt = 150000
    max_cost_usd: Nonnegative = 5.0
    max_runtime_minutes: PositiveInt = 90


class RequestSettings(ConfigModel):
    max_request_tokens: PositiveInt = 6500
    max_output_tokens: PositiveInt = 1000


class ToolSettings(ConfigModel):
    max_output_chars: PositiveInt = 8000
    read_default_lines: PositiveInt = 120
    instructions_max_tokens: PositiveInt = 1500


class RateLimits(ConfigModel):
    rpm: PositiveInt
    rpd: PositiveInt
    tpm: PositiveInt
    tpd: PositiveInt


class PermissionSettings(ConfigModel):
    edit_mode: Literal["allow", "ask"] = "allow"
    extra_allow: list[Nonempty] = Field(default_factory=list)
    web_allowlist: list[Nonempty] = Field(default_factory=list)
    secret_paths: list[Nonempty] = Field(default_factory=lambda: [".env", ".env.*"])


class IsolationSettings(ConfigModel):
    mode: Literal["worktree", "branch", "docker"] = "worktree"


class VerifySettings(ConfigModel):
    commands: list[list[Nonempty]] = Field(default_factory=list)
    timeout_s: PositiveInt = 600

    @field_validator("commands")
    @classmethod
    def commands_have_executable(cls, value: list[list[str]]) -> list[list[str]]:
        if any(not command for command in value):
            raise ValueError("verification commands must contain an executable")
        return value


class IndexSettings(ConfigModel):
    enabled: bool = False


class Price(ConfigModel):
    input: Nonnegative
    output: Nonnegative
    cache_read: Nonnegative


class Settings(ConfigModel):
    model: ModelSettings = Field(default_factory=ModelSettings)
    limits: LimitSettings = Field(default_factory=LimitSettings)
    request: RequestSettings = Field(default_factory=RequestSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    rate_limits: dict[Nonempty, RateLimits] = Field(default_factory=dict)
    permissions: PermissionSettings = Field(default_factory=PermissionSettings)
    isolation: IsolationSettings = Field(default_factory=IsolationSettings)
    verify: VerifySettings = Field(default_factory=VerifySettings)
    index: IndexSettings = Field(default_factory=IndexSettings)
    prices: dict[Nonempty, Price] = Field(default_factory=dict)


def find_git_root(start_dir: Path) -> Path:
    """Resolve the launch directory before isolation, without spawning a child."""
    start = start_dir.resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").is_dir() or (candidate / ".git").is_file():
            return candidate
    raise ConfigError("Start CodeAgent inside a Git repository")


def _read_toml(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise ConfigError("Cannot read configuration: expected valid UTF-8 TOML") from None


def _merge(base: dict[str, object], layer: Mapping[str, object]) -> dict[str, object]:
    result = base.copy()
    for key, value in layer.items():
        previous = result.get(key)
        if isinstance(previous, dict) and isinstance(value, dict):
            result[key] = _merge(previous, value)
        else:
            result[key] = value
    return result


def load_settings(
    start_dir: Path,
    *,
    user_dir: Path | None = None,
    overrides: Mapping[str, object] | None = None,
) -> Settings:
    """Merge defaults, user TOML, repository TOML, and nested flag overrides."""
    root = find_git_root(start_dir)
    home = user_dir if user_dir is not None else Path.home() / ".codeagent"
    data: dict[str, object] = {}
    for path in (home / "config.toml", root / ".codeagent" / "config.toml"):
        data = _merge(data, _read_toml(path))
    data = _merge(data, overrides or {})
    try:
        return Settings.model_validate(data)
    except ValidationError:
        # Never include input values (or arbitrary user-provided field names).
        raise ConfigError("Invalid configuration: check keys, types, and value ranges") from None
