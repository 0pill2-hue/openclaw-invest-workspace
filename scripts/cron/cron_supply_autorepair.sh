#!/usr/bin/env bash
set -euo pipefail
exec bash invest/scripts/cron/cron_supply_autorepair.sh "$@"
