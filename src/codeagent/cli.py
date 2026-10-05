"""Command-line entrypoint; commands are added in subsequent build phases."""

import typer

from codeagent.cli_init import init_command
from codeagent.cli_resume import resume_command
from codeagent.cli_rollback import rollback_command
from codeagent.cli_run import run_command
from codeagent.cli_status import status_command
from codeagent.cli_trace import trace_command

app = typer.Typer(
    help="A local coding agent with deterministic permissions and verification.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main() -> None:
    """Work with CodeAgent in a local Git repository."""


app.command("run")(run_command)
app.command("resume")(resume_command)
app.command("status")(status_command)
app.command("rollback")(rollback_command)
app.command("init")(init_command)
app.command("trace")(trace_command)


if __name__ == "__main__":
    app()
