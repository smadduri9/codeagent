"""Command-line entrypoint; commands are added in subsequent build phases."""

import typer

app = typer.Typer(
    help="A local coding agent with deterministic permissions and verification.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main() -> None:
    """Work with CodeAgent in a local Git repository."""


if __name__ == "__main__":
    app()
