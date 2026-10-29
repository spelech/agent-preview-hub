#!/usr/bin/env bash
set -euo pipefail

python3 verify_release.py
pytest --cov=agent_preview_hub --cov-fail-under=80
git add -A
git commit -m "${1:-chore: update agent-preview-hub}"
