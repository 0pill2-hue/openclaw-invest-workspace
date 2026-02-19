#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/jobiseu/.openclaw/workspace"
BEGIN="# >>> DATA_AUTOMATION_V3_22_KR >>>"
END="# <<< DATA_AUTOMATION_V3_22_KR <<<"

BLOCK=$(cat <<'CRON'
# >>> DATA_AUTOMATION_V3_22_KR >>>
PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
*/30 * * * * /Users/jobiseu/.openclaw/workspace/invest/scripts/cron/cron_supply_autorepair.sh
15 * * * * /Users/jobiseu/.openclaw/workspace/invest/scripts/cron/cron_dart_backfill_autopilot.sh
25 */3 * * * /Users/jobiseu/.openclaw/workspace/invest/scripts/cron/cron_rss_telegram_date_fix.sh
# <<< DATA_AUTOMATION_V3_22_KR <<<
CRON
)

MODE="${1:-print}"

if [ "$MODE" = "print" ] || [ "$MODE" = "--print" ]; then
  echo "$BLOCK"
  exit 0
fi

if [ "$MODE" != "apply" ] && [ "$MODE" != "--apply" ]; then
  echo "usage: $0 [print|apply]" >&2
  exit 2
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

EXISTING=""
if crontab -l >/dev/null 2>&1; then
  EXISTING="$(crontab -l)"
fi

# 기존 managed block 제거
printf '%s
' "$EXISTING" | awk -v b="$BEGIN" -v e="$END" '
  $0==b {inblk=1; next}
  $0==e {inblk=0; next}
  !inblk {print}
' > "$TMP"

# 공백 정리 후 새 block append
{
  cat "$TMP"
  echo
  echo "$BLOCK"
} | crontab -

echo "Applied cron block: DATA_AUTOMATION_V3_22_KR"
