import json
import pathlib
import sys

data = json.loads(pathlib.Path(__file__).with_name("expected.json").read_text(encoding="utf-8"))
out = pathlib.Path(__file__).with_name("outcome.json")
if not out.is_file():
    sys.exit(1)
got = json.loads(out.read_text(encoding="utf-8"))
for key, value in data.items():
    if got.get(key) != value:
        sys.exit(2)
