#!/usr/bin/env bash
set -euo pipefail
python "$(dirname "$0")/scan_secrets.py"
