#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
STAGE06_DIR = BASE / "invest/stages/stage6/outputs/reports/stage_updates"
TEMPLATE_UI = STAGE06_DIR / "template/ui/index.html"


def main() -> None:
    ap = argparse.ArgumentParser(description="Create stage06 version folder from template UI")
    ap.add_argument("version", help="예: v4_1")
    ap.add_argument("--force", action="store_true", help="기존 index.html 덮어쓰기")
    args = ap.parse_args()

    target_ui = STAGE06_DIR / args.version / "ui"
    target_ui.mkdir(parents=True, exist_ok=True)

    if not TEMPLATE_UI.exists():
        raise SystemExit(f"template not found: {TEMPLATE_UI}")

    target_index = target_ui / "index.html"
    if target_index.exists() and not args.force:
        raise SystemExit(f"already exists: {target_index} (use --force)")

    shutil.copy2(TEMPLATE_UI, target_index)

    print(f"OK: created {target_index.relative_to(BASE)} from template {TEMPLATE_UI.relative_to(BASE)}")


if __name__ == "__main__":
    main()
