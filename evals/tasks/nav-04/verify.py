import pathlib
import sys

expected = pathlib.Path(__file__).with_name("expected.txt").read_text(encoding="utf-8").strip()
answer = pathlib.Path(__file__).with_name("answer.txt")
if not answer.is_file():
    sys.exit(1)
if answer.read_text(encoding="utf-8").strip() != expected:
    sys.exit(2)
