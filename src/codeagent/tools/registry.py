"""Tool registration, schema validation, and dispatch."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from codeagent.providers.base import ToolCall
from codeagent.tools.base import ToolResult, ToolSpec


class ToolValidationError(Exception):
    """Arguments failed schema validation before execution."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnknownToolError(Exception):
    """Tool name is not registered."""

    def __init__(self, name: str) -> None:
        super().__init__(f"unknown tool: {name}")
        self.name = name


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _EchoArgs(StrictArgs):
    message: str


def _echo_handler(args: _EchoArgs) -> ToolResult:
    return ToolResult(ok=True, summary="echo", content=args.message, truncated=False)


class ToolRegistry:
    """Register tools with Pydantic-validated arguments."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._models: dict[str, type[BaseModel]] = {}
        self._handlers: dict[str, Callable[[Any], ToolResult]] = {}
        self.register_echo()

    def register(
        self,
        name: str,
        description: str,
        args_model: type[BaseModel],
        handler: Callable[[Any], ToolResult],
        *,
        parameters: dict[str, object] | None = None,
    ) -> None:
        schema = parameters if parameters is not None else _model_json_schema(args_model)
        self._specs[name] = ToolSpec(name=name, description=description, parameters=schema)
        self._models[name] = args_model
        self._handlers[name] = handler

    def register_echo(self) -> None:
        self.register(
            "echo",
            "Return the message unchanged (test tool).",
            _EchoArgs,
            _echo_handler,
            parameters={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
                "additionalProperties": False,
            },
        )

    def list_specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def lookup(self, name: str) -> ToolSpec:
        try:
            return self._specs[name]
        except KeyError as exc:
            raise UnknownToolError(name) from exc

    def validate(self, call: ToolCall) -> BaseModel:
        if call.name not in self._models:
            raise UnknownToolError(call.name)
        model = self._models[call.name]
        try:
            return model.model_validate(call.args)
        except ValidationError as exc:
            raise ToolValidationError(str(exc.errors()[0]["msg"])) from exc

    def run_validated(self, call: ToolCall, args: BaseModel) -> ToolResult:
        handler = self._handlers[call.name]
        return handler(args)

    def run(self, call: ToolCall) -> ToolResult:
        validated = self.validate(call)
        return self.run_validated(call, validated)

    def tool_error(self, call: ToolCall, message: str) -> ToolResult:
        return ToolResult(
            ok=False,
            summary=f"{call.name} failed",
            content=message,
            truncated=False,
        )


def _model_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema()
