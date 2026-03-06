#!/usr/bin/env bash
set -euo pipefail
cd /Users/jobiseu/.openclaw/workspace
mkdir -p invest/stages/stage1/outputs/logs/runtime
/usr/bin/python3 invest/stages/stage1/scripts/stage01_run_images_ocr_rolling.py \
  --batch-size "${STAGE01_OCR_ROLLING_BATCH:-60}" \
  --max-scan "${STAGE01_OCR_ROLLING_SCAN:-4000}" \
  >> invest/stages/stage1/outputs/logs/runtime/launchd_stage01_images_ocr_rolling.log 2>&1
