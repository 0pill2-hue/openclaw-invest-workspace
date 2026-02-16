#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   GRADE=DRAFT ./automation/prevention/check_result_governance.sh <result_file>

GRADE="${GRADE:-DRAFT}"
RESULT_FILE="${1:-}"

if [[ -z "$RESULT_FILE" ]]; then
  echo "[FAIL] result file path required"
  exit 1
fi

if [[ ! -f "$RESULT_FILE" ]]; then
  echo "[FAIL] result file not found: $RESULT_FILE"
  exit 1
fi

case "$GRADE" in
  DRAFT|VALIDATED|PRODUCTION) ;;
  *) echo "[FAIL] invalid GRADE=$GRADE"; exit 1 ;;
esac

# Rule 1: Missing/unknown label is not allowed in pipeline usage.
if [[ -z "$GRADE" ]]; then
  echo "[FAIL] grade missing"
  exit 1
fi

# Rule 2: DRAFT must contain TEST ONLY marker for text/csv/md reports.
if [[ "$GRADE" == "DRAFT" ]]; then
  if [[ "$RESULT_FILE" =~ \.(txt|md|csv)$ ]]; then
    if ! grep -q "TEST ONLY" "$RESULT_FILE"; then
      echo "[FAIL] DRAFT file must include 'TEST ONLY' marker"
      exit 1
    fi
  fi
fi

# Rule 3: output path guard
if [[ "$GRADE" == "PRODUCTION" ]]; then
  [[ "$RESULT_FILE" == *"/invest/results/prod/"* ]] || { echo "[FAIL] PRODUCTION must be under invest/results/prod/"; exit 1; }
elif [[ "$GRADE" == "VALIDATED" ]]; then
  [[ "$RESULT_FILE" == *"/invest/results/validated/"* ]] || { echo "[FAIL] VALIDATED must be under invest/results/validated/"; exit 1; }
else
  [[ "$RESULT_FILE" == *"/invest/results/test/"* ]] || { echo "[FAIL] DRAFT must be under invest/results/test/"; exit 1; }
fi

echo "[PASS] governance check passed (GRADE=$GRADE)"
