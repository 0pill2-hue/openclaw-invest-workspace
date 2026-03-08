#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-daily_full}"
shift || true

ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd)"
cd "$ROOT"

ENV_FILE="$HOME/.config/invest/invest_autocollect.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

PYTHON_BIN="${INVEST_PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/python3" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python3"
  else
    PYTHON_BIN="python3"
  fi
fi

exec "$PYTHON_BIN" "$ROOT/invest/stages/stage1/scripts/stage01_daily_update.py" --profile "$PROFILE" "$@"
