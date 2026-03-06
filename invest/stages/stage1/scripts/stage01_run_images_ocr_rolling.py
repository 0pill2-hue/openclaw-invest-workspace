#!/usr/bin/env python3
"""Stage1 이미지 OCR 롤링 워커.
- telegram_attach_tmp/image_map 하위 이미지 파일을 큐로 수집
- checkpoint 기반 재실행 이어받기
- 배치 단위 OCR 텍스트(.txt) 저장
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_ATTACH_DIR = WORKSPACE_ROOT / "invest/stages/stage1/outputs/runtime/telegram_attach_tmp"
RAW_IMAGE_MAP_DIR = WORKSPACE_ROOT / "invest/stages/stage1/outputs/raw/qualitative/text/image_map"
OUT_TXT_DIR = WORKSPACE_ROOT / "invest/stages/stage1/outputs/raw/qualitative/text/images_ocr"
CHECKPOINT_PATH = WORKSPACE_ROOT / "invest/stages/stage1/outputs/runtime/stage01_images_ocr_rolling_checkpoint.json"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage1 rolling OCR worker")
    p.add_argument("--batch-size", type=int, default=30)
    p.add_argument("--max-scan", type=int, default=3000)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ocr-lang", default="kor+eng")
    p.add_argument("--min-text-len", type=int, default=5)
    return p.parse_args()


def _load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {"processed": {}, "last_run": "", "total_processed": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"processed": {}, "last_run": "", "total_processed": 0}


def _save_checkpoint(path: Path, checkpoint: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_image_file(p: Path) -> bool:
    if p.suffix.lower() in IMAGE_EXTS:
        return True
    if not p.is_file() or p.stat().st_size <= 0:
        return False
    try:
        with p.open("rb") as f:
            sig = f.read(16)
        return sig.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"RIFF", b"BM"))
    except Exception:
        return False


def _file_key(p: Path) -> str:
    st = p.stat()
    return f"{p}:{int(st.st_mtime)}:{st.st_size}"


def _collect_candidates(max_scan: int) -> list[Path]:
    roots = [RUNTIME_ATTACH_DIR, RAW_IMAGE_MAP_DIR]
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for fp in root.rglob("*"):
            if len(found) >= max_scan:
                return found
            if fp.is_file() and _is_image_file(fp):
                found.append(fp)
    return found


def _ocr_file(img_path: Path, out_txt: Path, lang: str) -> tuple[bool, str]:
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_base = out_txt.with_suffix("")
    cmd = ["tesseract", str(img_path), str(out_base), "-l", lang]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    except Exception as e:
        return False, f"tesseract_exec_error:{type(e).__name__}"
    if p.returncode != 0:
        return False, (p.stderr or p.stdout or "tesseract_failed").strip()[:200]
    txt_path = out_base.with_suffix(".txt")
    if not txt_path.exists():
        return False, "ocr_output_missing"
    if txt_path != out_txt:
        txt_path.replace(out_txt)
    return True, "ok"


def main() -> int:
    args = parse_args()
    checkpoint = _load_checkpoint(CHECKPOINT_PATH)
    processed_map: dict[str, dict] = checkpoint.get("processed", {})

    candidates = sorted(_collect_candidates(args.max_scan), key=lambda p: p.stat().st_mtime)
    queue: list[Path] = []
    for fp in candidates:
        key = _file_key(fp)
        if key in processed_map:
            continue
        queue.append(fp)

    queue = queue[: max(0, args.batch_size)]
    processed_now = 0
    success = 0
    failed = 0

    for fp in queue:
        key = _file_key(fp)
        digest = hashlib.sha1(str(fp).encode("utf-8", errors="ignore")).hexdigest()[:16]
        rel = fp.relative_to(WORKSPACE_ROOT) if fp.is_relative_to(WORKSPACE_ROOT) else fp
        out_txt = OUT_TXT_DIR / "rolling" / f"{digest}.txt"

        if args.dry_run:
            print(f"[DRY] OCR_QUEUE item={rel} -> {out_txt.relative_to(WORKSPACE_ROOT)}")
            processed_map[key] = {
                "status": "dry-run",
                "source": str(rel),
                "processed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            processed_now += 1
            continue

        ok, reason = _ocr_file(fp, out_txt, args.ocr_lang)
        if ok:
            txt = out_txt.read_text(encoding="utf-8", errors="ignore").strip()
            if len(txt) < args.min_text_len:
                reason = "ocr_text_too_short"
                failed += 1
                out_txt.unlink(missing_ok=True)
                status = "failed"
            else:
                success += 1
                status = "ok"
        else:
            failed += 1
            status = "failed"

        processed_map[key] = {
            "status": status,
            "reason": reason,
            "source": str(rel),
            "output_txt": str(out_txt.relative_to(WORKSPACE_ROOT)) if ok else "",
            "processed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        processed_now += 1

    checkpoint["processed"] = processed_map
    checkpoint["last_run"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    checkpoint["total_processed"] = int(checkpoint.get("total_processed", 0)) + processed_now
    _save_checkpoint(CHECKPOINT_PATH, checkpoint)

    print(
        "OCR_ROLLING_DONE "
        f"queued={len(queue)} processed_now={processed_now} success={success} failed={failed} "
        f"remaining_est={max(0, len(candidates)-len(queue))} dry_run={args.dry_run}"
    )
    print(f"OCR_ROLLING_CHECKPOINT={CHECKPOINT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
