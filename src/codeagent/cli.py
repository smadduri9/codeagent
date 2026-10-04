"""Command-line entrypoint; commands are added in subsequent build phases."""

import typer

from codeagent.cli_run import run_command

app = typer.Typer(
    help="A local coding agent with deterministic permissions and verification.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main() -> None:
    """Work with CodeAgent in a local Git repository."""


app.command("run")(run_command)


if __name__ == "__main__":
    app()
