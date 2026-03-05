#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

STAGE7_INPUT_DIR = Path("invest/stages/stage7/inputs")
STAGE7_RESULTS_DIR = Path("invest/stages/stage7/outputs/results")
STAGE4_UPSTREAM_DIR = STAGE7_INPUT_DIR / "upstream_stage4_outputs"
STAGE4_REPORT_DIR = STAGE4_UPSTREAM_DIR / "reports"
STAGE4_MANIFEST_DIR = STAGE4_UPSTREAM_DIR
STAGE4_VALUE_DIR = STAGE4_UPSTREAM_DIR / "value"


def _latest_path(base: Path, pattern: str) -> Path | None:
    files = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def build_interface() -> dict:
    latest_report = _latest_path(STAGE4_REPORT_DIR, "STAGE4_VALUE_RUN_*.json")
    latest_manifest = _latest_path(STAGE4_MANIFEST_DIR, "manifest_stage4_value_*.json")

    payload = {
        "schema_version": "stage7_interface.v1",
        "generated_at_kst": pd.Timestamp.now(tz="Asia/Seoul").isoformat(),
        "source": {
            "stage4_value_root": str(STAGE4_VALUE_DIR),
            "stage4_report": str(latest_report) if latest_report else "미확인",
            "stage4_manifest": str(latest_manifest) if latest_manifest else "미확인",
        },
        "stage7_input_contract": {
            "required_columns": [
                "Date",
                "VALUE_SCORE",
                "QUALITATIVE_SIGNAL",
                "STAGE3_MISSING",
            ],
            "forbidden_in_stage4": [
                "COMPOSITE_SCORE",
                "STAGE4_NUMERIC_WEIGHT",
                "STAGE3_QUAL_WEIGHT",
            ],
            "tuning_owner": "stage7",
        },
        "automation": {
            "hook_type": "stage4_to_stage7_input_placeholder",
            "stage7_auto_execute": False,
            "hybrid_auto_tuning_connected": False,
        },
    }
    return payload


def main() -> int:
    p = argparse.ArgumentParser(description="Build Stage4->Stage7 tuning input interface placeholder")
    p.add_argument("--output-dir", default=str(STAGE7_INPUT_DIR))
    p.add_argument("--result-dir", default=str(STAGE7_RESULTS_DIR))
    args = p.parse_args()

    out_dir = Path(args.output_dir)
    result_dir = Path(args.result_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    payload = build_interface()
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    ts_path = out_dir / f"stage7_tuning_input_from_stage4_{ts}.json"
    latest_path = out_dir / "stage7_tuning_input_from_stage4_latest.json"
    ts_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")

    result_ts_path = result_dir / f"stage7_interface_build_{ts}.json"
    result_latest_path = result_dir / "stage7_interface_build_latest.json"
    result_ts_path.write_text(text, encoding="utf-8")
    result_latest_path.write_text(text, encoding="utf-8")

    print(f"STAGE7_INTERFACE_WRITTEN={ts_path}")
    print(f"STAGE7_INTERFACE_LATEST={latest_path}")
    print(f"STAGE7_RESULT_WRITTEN={result_ts_path}")
    print(f"STAGE7_RESULT_LATEST={result_latest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
