import subprocess
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / "examples" / "payment_service"


def test_scripted_payment_demo_fixes_expired_card(tmp_path: Path) -> None:
    import shutil

    work = tmp_path / "payment"
    shutil.copytree(FIXTURE, work)
    assert subprocess.run(["python", "-m", "pytest", "-q"], cwd=work, check=False).returncode != 0
    import importlib.util

    spec = importlib.util.spec_from_file_location("demo_fix", work / "demo_fix.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    checkout = work / "checkout.py"
    text = checkout.read_text(encoding="utf-8")
    checkout.write_text(
        text.replace('return 500, "internal error"', 'return 402, "payment required"'),
        encoding="utf-8",
    )
    assert subprocess.run(["python", "-m", "pytest", "-q"], cwd=work, check=False).returncode == 0
