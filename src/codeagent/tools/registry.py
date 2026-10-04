"""Tool registration, schema validation, and dispatch."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from codeagent.config import ToolSettings
from codeagent.providers.base import ToolCall
from codeagent.tools.base import RiskLevel, StrictArgs, ToolResult, ToolSpec
from codeagent.tools.command_tools import (
    BashArgs,
    CommandToolContext,
    RunCommandArgs,
    handle_bash,
    handle_run_command,
)
from codeagent.tools.file_tools import (
    DeletePathArgs,
    EditFileArgs,
    GlobArgs,
    GrepArgs,
    ListDirArgs,
    MovePathArgs,
    ReadFileArgs,
    WriteFileArgs,
    _bind,
    handle_delete_path,
    handle_edit_file,
    handle_glob,
    handle_grep,
    handle_list_dir,
    handle_move_path,
    handle_read_file,
    handle_write_file,
)
from codeagent.tools.git_tools import (
    GitDiffArgs,
    GitLogArgs,
    GitShowArgs,
    GitStatusArgs,
    GitToolContext,
    handle_git_diff,
    handle_git_log,
    handle_git_show,
    handle_git_status,
)
from codeagent.tools.workspace_context import WorkspaceToolContext


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
        risk_level: RiskLevel | None = None,
    ) -> None:
        schema = parameters if parameters is not None else _model_json_schema(args_model)
        self._specs[name] = ToolSpec(
            name=name,
            description=description,
            parameters=schema,
            risk_level=risk_level,
        )
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

    def register_filesystem_tools(
        self,
        workspace: Path,
        settings: ToolSettings | None = None,
        *,
        context: WorkspaceToolContext | None = None,
    ) -> WorkspaceToolContext:
        """Register read, search, and mutation tools bound to ``workspace``."""
        ws = Path(workspace)
        ctx = context or WorkspaceToolContext(
            workspace=ws,
            settings=settings or ToolSettings(),
        )
        self.register(
            "read_file",
            (
                "Read a text file inside the workspace with line numbers. "
                "Do not use bash or cat for reading. "
                "Use offset and limit for large files."
            ),
            ReadFileArgs,
            _bind(ctx, handle_read_file),
            risk_level="READ_ONLY",
        )
        self.register(
            "list_dir",
            (
                "List one directory (non-recursive). Respects .gitignore. "
                "Do not use ls for workspace inspection."
            ),
            ListDirArgs,
            _bind(ctx, handle_list_dir),
            risk_level="READ_ONLY",
        )
        self.register(
            "glob",
            "Find files by glob pattern; respects .gitignore. Sorted by modification time.",
            GlobArgs,
            _bind(ctx, handle_glob),
            risk_level="READ_ONLY",
        )
        self.register(
            "grep",
            (
                "Search file contents with ripgrep (files, lines, or count). "
                "Do not use bash grep for code search."
            ),
            GrepArgs,
            _bind(ctx, handle_grep),
            risk_level="READ_ONLY",
        )
        self.register(
            "write_file",
            "Create a new file only; fails if the path already exists. Creates parent directories.",
            WriteFileArgs,
            _bind(ctx, handle_write_file),
            risk_level="LOCAL_MUTATION",
        )
        self.register(
            "edit_file",
            (
                "Replace exact old_string with new_string in a file that was read earlier. "
                "Fails on missing or ambiguous matches."
            ),
            EditFileArgs,
            _bind(ctx, handle_edit_file),
            risk_level="LOCAL_MUTATION",
        )
        self.register(
            "move_path",
            "Move or rename a path inside the workspace.",
            MovePathArgs,
            _bind(ctx, handle_move_path),
            risk_level="LOCAL_MUTATION",
        )
        self.register(
            "delete_path",
            "Delete a file or directory inside the workspace. Always requires approval.",
            DeletePathArgs,
            _bind(ctx, handle_delete_path),
            risk_level="DESTRUCTIVE",
        )
        return ctx

    def register_command_tools(
        self,
        workspace: Path,
        settings: ToolSettings | None = None,
        *,
        context: CommandToolContext | None = None,
    ) -> CommandToolContext:
        """Register ``run_command`` and ``bash`` bound to ``workspace``."""
        ws = Path(workspace)
        ctx = context or CommandToolContext(
            workspace=ws,
            settings=settings or ToolSettings(),
        )
        self.register(
            "run_command",
            (
                "Run a command without a shell (argv array). "
                "No glob expansion or variable interpolation."
            ),
            RunCommandArgs,
            _bind_command(ctx, handle_run_command),
            risk_level="EXTERNAL_SIDE_EFFECT",
        )
        self.register(
            "bash",
            "Run a shell command string (classified by the permission engine).",
            BashArgs,
            _bind_command(ctx, handle_bash),
            risk_level="EXTERNAL_SIDE_EFFECT",
        )
        return ctx

    def register_git_tools(
        self,
        repo: Path,
        settings: ToolSettings | None = None,
        *,
        context: GitToolContext | None = None,
    ) -> GitToolContext:
        """Register read-only git tools for ``repo``."""
        root = Path(repo)
        ctx = context or GitToolContext(repo=root, settings=settings or ToolSettings())
        self.register(
            "git_status",
            "Git status (short, with branch).",
            GitStatusArgs,
            _bind_git(ctx, handle_git_status),
            risk_level="READ_ONLY",
        )
        self.register(
            "git_diff",
            "Git diff for the working tree or staged changes.",
            GitDiffArgs,
            _bind_git(ctx, handle_git_diff),
            risk_level="READ_ONLY",
        )
        self.register(
            "git_log",
            "Recent commits (oneline).",
            GitLogArgs,
            _bind_git(ctx, handle_git_log),
            risk_level="READ_ONLY",
        )
        self.register(
            "git_show",
            "Show a commit (stat and patch).",
            GitShowArgs,
            _bind_git(ctx, handle_git_show),
            risk_level="READ_ONLY",
        )
        return ctx


def _bind_command[ArgModel: BaseModel](
    ctx: CommandToolContext,
    handler: Callable[[CommandToolContext, ArgModel], ToolResult],
) -> Callable[[ArgModel], ToolResult]:
    def wrapped(args: ArgModel) -> ToolResult:
        return handler(ctx, args)

    return wrapped


def _bind_git[ArgModel: BaseModel](
    ctx: GitToolContext,
    handler: Callable[[GitToolContext, ArgModel], ToolResult],
) -> Callable[[ArgModel], ToolResult]:
    def wrapped(args: ArgModel) -> ToolResult:
        return handler(ctx, args)

    return wrapped


def _model_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema()
