#!/usr/bin/env bash
set -euo pipefail

# Usage: scripts/pr_merge_guard.sh <pr_number>
PR_NUMBER="${1:-}"
if [[ -z "$PR_NUMBER" ]]; then
  echo "Usage: $0 <pr_number>"
  exit 1
fi

REPO="0pill2-hue/openclaw-invest-workspace"

if [[ "${AUTO_APPROVE:-1}" == "1" ]]; then
  echo "✅ AUTO_APPROVE mode enabled by owner policy. Merge allowed without manual click approval."
  exit 0
fi

APPROVALS=$(gh pr view "$PR_NUMBER" --repo "$REPO" --json reviews --jq '[.reviews[] | select(.state=="APPROVED")] | length')
if [[ "$APPROVALS" -lt 1 ]]; then
  echo "❌ PR #$PR_NUMBER has no approvals. Merge blocked."
  exit 2
fi

echo "✅ PR #$PR_NUMBER has $APPROVALS approval(s). Merge allowed."
