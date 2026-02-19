#!/usr/bin/env bash
set -euo pipefail
exec bash invest/scripts/cron/cron_rss_telegram_date_fix.sh "$@"
