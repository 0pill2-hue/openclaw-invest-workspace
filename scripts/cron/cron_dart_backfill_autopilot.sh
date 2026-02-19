#!/usr/bin/env bash
set -euo pipefail
exec bash invest/scripts/cron/cron_dart_backfill_autopilot.sh "$@"
