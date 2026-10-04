"""Security checks deferred until later phases."""

import pytest


@pytest.mark.skip(reason="command timeout requires run_command (P4-F1)")
def test_command_timeout_works() -> None: ...


@pytest.mark.skip(reason="overwrite protection requires edit_file hashing (P2-F4)")
def test_existing_user_modifications_not_silently_overwritten() -> None: ...
