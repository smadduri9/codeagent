#!/usr/bin/env bash
# Optional: re-record a terminal demo with a live Groq key.
# Requires: asciinema or manual screen capture; GROQ_API_KEY in environment.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/demo"
mkdir -p "$OUT"
echo "Record your session, then save as:"
echo "  $OUT/terminal.mp4"
echo "Regenerate GIF for README:"
echo "  ffmpeg -y -i $OUT/terminal.mp4 -vf \"fps=12,scale=900:-1:flags=lanczos\" -loop 0 $OUT/terminal.gif"
echo "Example run (from examples/payment_service):"
echo "  cd $ROOT/examples/payment_service && codeagent run \"Expired cards return HTTP 500 during checkout. Find the cause and fix it. Do not change unrelated behavior.\""
