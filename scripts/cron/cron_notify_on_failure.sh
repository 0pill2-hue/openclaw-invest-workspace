#!/usr/bin/env bash
set -euo pipefail
exec bash invest/scripts/cron/cron_notify_on_failure.sh "$@"
