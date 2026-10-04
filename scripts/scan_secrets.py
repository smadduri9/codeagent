"""Scan tracked content without printing matches or opening forbidden paths."""

import re
import subprocess
from pathlib import Path

PATTERNS = (
    rb"gsk" + rb"_[A-Za-z0-9]{20,}",
    rb"sk" + rb"-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}",
    rb"-----BEGIN " + rb"(?:[A-Z0-9]+ )*PRIVATE KEY-----",
    rb"(?im)^\s*(?:export\s+)?(?:[A-Z][A-Z0-9_]*)?(?:API_KEY|TOKEN|SECRET|PASSWORD)"
    rb"\s*=\s*[\"']?[^\s\"']{8,}",
)
EXAMPLE_PLACEHOLDERS = {b"your_groq_key_here", b"your-key-here"}


def is_example_placeholder(line: bytes) -> bool:
    """Allow only complete known values, optionally wrapped in matching quotes."""
    value = line.partition(b"=")[2].strip()
    if len(value) >= 2 and value[:1] in {b"'", b'"'} and value[-1:] == value[:1]:
        value = value[1:-1]
    return value in EXAMPLE_PLACEHOLDERS


def contains_secret(data: bytes, *, example: bool) -> bool:
    """Apply key patterns to all content and narrowly exempt example values."""
    if any(re.search(pattern, data) for pattern in PATTERNS[:-1]):
        return True
    if example:
        data = b"\n".join(
            b"" if is_example_placeholder(line) else line for line in data.split(b"\n")
        )
    return re.search(PATTERNS[-1], data) is not None


def forbidden(path: Path) -> bool:
    """Reject state directories and secret files before accessing content."""
    return (
        any(part in {".codeagent", ".autobuild"} for part in path.parts)
        or path.suffix == ".db"
        or (path.name.startswith(".env") and path.name != ".env.example")
    )


def main() -> int:
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    entries = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
    failures = 0
    for entry in filter(None, entries):
        relative = Path(entry.decode("utf-8", errors="surrogateescape"))
        if forbidden(relative):
            print(f"Forbidden tracked path: {str(relative)!r}")
            failures += 1
            continue
        # Check the index as well as the checkout: an unstaged edit must not hide
        # a staged secret. git show does not follow tracked symbolic links.
        staged = subprocess.check_output(["git", "show", f":{relative}"], cwd=root)
        path = root / relative
        contents = [staged]
        if path.is_file() and not path.is_symlink():
            contents.append(path.read_bytes())
        if any(contains_secret(data, example=relative.name == ".env.example") for data in contents):
            print(f"Potential secret in tracked file: {str(relative)!r}")
            failures += 1
    if failures:
        print(f"Secret scan failed: {failures} tracked file(s); contents withheld.")
        return 1
    print("Secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
