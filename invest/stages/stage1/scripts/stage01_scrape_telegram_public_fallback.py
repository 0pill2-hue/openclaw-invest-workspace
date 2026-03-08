#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

from pipeline_logger import append_pipeline_event

ROOT = Path(__file__).resolve().parents[4]
ALLOWLIST = ROOT / "invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt"
OUT_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/text/telegram"
STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/telegram_public_fallback_status.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
MSG_RE = re.compile(r'(?is)<div[^>]+class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>')
WRAP_SPLIT_RE = re.compile(r'(?i)(?=<div[^>]+class="[^"]*tgme_widget_message_wrap[^"]*")')
POST_ID_RE = re.compile(r'data-post="[^"]+/(\d+)"')
TIME_RE = re.compile(r'<time[^>]+datetime="([^"]+)"')
EXISTING_POST_BLOCK_RE = re.compile(
    r"(?s)---\nPost:\s*\d+\nPostID:\s*(\d+)\nPostDate:\s*(.*?)\nPostDateTime:\s*(.*?)\n\n(.*?)(?=\n---\nPost:|\Z)"
)


def _parse_target_date(raw: str) -> datetime:
    s = (raw or "").strip()
    if s:
        try:
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime(2016, 1, 1, tzinfo=timezone.utc)


def _resolve_target_date(raw_date: str, target_years: int) -> str:
    if (raw_date or "").strip():
        return raw_date.strip()
    years = max(1, int(target_years))
    return (datetime.now(timezone.utc) - timedelta(days=365 * years)).date().isoformat()


def _save_status(payload: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_post_dt(raw: str) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None
    for cand in (s, s.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(cand)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _http_get(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _strip_html(s: str) -> str:
    s = re.sub(r"(?is)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)<[^>]+>", " ", s)
    s = unescape(s)
    s = re.sub(r"\r", "", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def _extract_page_messages(html: str) -> list[dict]:
    out = []
    for chunk in WRAP_SPLIT_RE.split(html):
        if "tgme_widget_message_wrap" not in chunk:
            continue
        id_m = POST_ID_RE.search(chunk)
        txt_m = MSG_RE.search(chunk)
        if not id_m or not txt_m:
            continue
        text = _strip_html(txt_m.group(1))
        if len(text) < 20:
            continue
        dt_m = TIME_RE.search(chunk)
        dt = dt_m.group(1) if dt_m else ""
        date_only = dt[:10] if len(dt) >= 10 else ""
        out.append({
            "post_id": int(id_m.group(1)),
            "post_datetime": dt,
            "post_date": date_only,
            "text": text,
        })
    out.sort(key=lambda x: x["post_id"], reverse=True)
    return out


def _collect_channel_messages(uname: str, max_msgs: int, max_pages: int, target_date: datetime) -> tuple[list[dict], str]:
    collected: list[dict] = []
    seen_ids: set[int] = set()
    before: int | None = None
    page = 0
    reached_target_date = False

    while len(collected) < max(0, max_msgs) and page < max(1, max_pages):
        suffix = f"?before={before}" if before else ""
        html = _http_get(f"https://t.me/s/{uname}{suffix}")
        batch = _extract_page_messages(html)
        if not batch:
            break

        page += 1
        new_count = 0
        min_id = None
        oldest_dt_on_page: datetime | None = None

        for item in batch:
            pid = item["post_id"]
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            collected.append(item)
            new_count += 1
            min_id = pid if min_id is None else min(min_id, pid)

            dt = _parse_post_dt(item.get("post_datetime", ""))
            if dt is not None:
                oldest_dt_on_page = dt if oldest_dt_on_page is None else min(oldest_dt_on_page, dt)

            if len(collected) >= max(0, max_msgs):
                break

        if new_count == 0 or min_id is None:
            break

        if oldest_dt_on_page is not None and oldest_dt_on_page <= target_date:
            reached_target_date = True
            break

        before = min_id

    collected.sort(key=lambda x: x["post_id"], reverse=True)
    if len(collected) > max(0, max_msgs):
        collected = collected[: max(0, max_msgs)]

    note = (
        f"pages={page} collected={len(collected)} target_date={target_date.date().isoformat()} "
        f"reached_target={int(reached_target_date)}"
    )
    return collected, note


def _load_allowlist() -> list[str]:
    out = []
    if ALLOWLIST.exists():
        for line in ALLOWLIST.read_text(encoding="utf-8", errors="ignore").splitlines():
            v = line.strip()
            if not v or v.startswith("#"):
                continue
            v = v.lstrip("@")
            if v and re.match(r"^[A-Za-z0-9_]{4,}$", v) and re.search(r"[A-Za-z_]", v):
                out.append(v)
    return sorted(set(out))


def _load_existing_posts(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    out: dict[int, dict] = {}
    for m in EXISTING_POST_BLOCK_RE.finditer(txt):
        try:
            pid = int(m.group(1).strip())
        except Exception:
            continue
        out[pid] = {
            "post_id": pid,
            "post_date": (m.group(2) or "").strip(),
            "post_datetime": (m.group(3) or "").strip(),
            "text": (m.group(4) or "").strip(),
        }
    return out


def run(
    limit_channels: int = 200,
    max_msgs_per_channel: int = 5000,
    max_pages_per_channel: int = 300,
    min_saved_files: int = 1,
    min_saved_msgs: int = 1,
    target_date_raw: str = "2016-01-01",
) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    channels = _load_allowlist()
    if limit_channels > 0:
        channels = channels[:limit_channels]
    target_date = _parse_target_date(target_date_raw)
    saved_files = 0
    saved_msgs = 0
    errors = []
    channel_results: list[dict] = []

    for uname in channels:
        try:
            msgs, note = _collect_channel_messages(uname, max_msgs_per_channel, max_pages_per_channel, target_date)
            out = OUT_DIR / f"{uname}_public_fallback.md"
            existing = _load_existing_posts(out)

            if not msgs and not existing:
                channel_results.append({"channel": uname, "status": "SKIP", "reason": "no_public_messages"})
                continue

            merged: dict[int, dict] = dict(existing)
            for item in msgs:
                merged[int(item["post_id"])] = {
                    "post_id": int(item["post_id"]),
                    "post_date": str(item.get("post_date") or ""),
                    "post_datetime": str(item.get("post_datetime") or ""),
                    "text": str(item.get("text") or ""),
                }

            merged_items = sorted(merged.values(), key=lambda x: int(x.get("post_id", 0)), reverse=True)

            now = datetime.now().isoformat(timespec="seconds")
            body = [f"# Telegram Public Fallback: {uname}", "", f"Date: {now}", f"Source: https://t.me/s/{uname}", ""]
            for i, item in enumerate(merged_items, start=1):
                dline = f"PostDate: {item['post_date']}" if item.get("post_date") else "PostDate: 미확인"
                tline = f"PostDateTime: {item['post_datetime']}" if item.get("post_datetime") else "PostDateTime: 미확인"
                body.append(
                    f"---\nPost: {i}\nPostID: {item['post_id']}\n{dline}\n{tline}\n\n{item['text']}\n"
                )
            out.write_text("\n".join(body), encoding="utf-8")
            saved_files += 1
            saved_msgs += len(merged_items)
            channel_results.append({
                "channel": uname,
                "status": "OK",
                "saved_messages": len(merged_items),
                "new_messages": len(msgs),
                "existing_messages": len(existing),
                "oldest_post_id": min(m["post_id"] for m in merged_items),
                "newest_post_id": max(m["post_id"] for m in merged_items),
                "note": note,
                "output": str(out),
            })
        except Exception as e:
            err = str(e)
            errors.append(f"{uname}:{err}")
            channel_results.append({"channel": uname, "status": "ERROR", "reason": err})

    fail_reasons = []
    if saved_files < max(0, min_saved_files):
        fail_reasons.append(f"saved_files={saved_files} < min_saved_files={min_saved_files}")
    if saved_msgs < max(0, min_saved_msgs):
        fail_reasons.append(f"saved_msgs={saved_msgs} < min_saved_msgs={min_saved_msgs}")

    status = "FAIL" if fail_reasons else ("OK" if saved_files > 0 else "WARN")
    pipeline_errors = errors[:20] + fail_reasons
    allowlist_total = len(channels)
    ok_channels = sum(1 for item in channel_results if item.get("status") == "OK")
    result = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "allowlist_total": allowlist_total,
        "channels_checked": len(channels),
        "channels_ok": ok_channels,
        "channels_uncovered": max(0, allowlist_total - ok_channels),
        "all_channels_satisfied": allowlist_total > 0 and ok_channels == allowlist_total,
        "saved_files": saved_files,
        "saved_msgs": saved_msgs,
        "max_msgs_per_channel": max_msgs_per_channel,
        "max_pages_per_channel": max_pages_per_channel,
        "target_date": target_date.date().isoformat(),
        "min_saved_files": min_saved_files,
        "min_saved_msgs": min_saved_msgs,
        "fail_reasons": fail_reasons,
        "errors": errors,
        "channel_results": channel_results,
    }
    _save_status(result)
    append_pipeline_event(
        source="scrape_telegram_public_fallback",
        status=status,
        count=saved_msgs,
        errors=pipeline_errors,
        note=(
            f"channels={len(channels)} files={saved_files} msgs={saved_msgs} "
            f"max_msgs={max_msgs_per_channel} max_pages={max_pages_per_channel} target_date={target_date.date().isoformat()} "
            f"min_files={min_saved_files} min_msgs={min_saved_msgs} all_channels_satisfied={int(result['all_channels_satisfied'])}"
        ),
    )
    return result


def main() -> None:
    limit_channels = int(os.environ.get("TG_PUBLIC_FALLBACK_LIMIT", "0"))
    max_msgs = int(os.environ.get("TG_PUBLIC_FALLBACK_MAX_MSGS", "5000"))
    max_pages = int(os.environ.get("TG_PUBLIC_FALLBACK_MAX_PAGES", "300"))
    min_saved_files = int(os.environ.get("TG_PUBLIC_FALLBACK_MIN_SAVED_FILES", "1"))
    min_saved_msgs = int(os.environ.get("TG_PUBLIC_FALLBACK_MIN_SAVED_MSGS", "1"))
    target_years = int(os.environ.get("TG_PUBLIC_FALLBACK_TARGET_YEARS", "10"))
    target_date = _resolve_target_date(os.environ.get("TG_PUBLIC_FALLBACK_TARGET_DATE", ""), target_years)
    result = run(limit_channels, max_msgs, max_pages, min_saved_files, min_saved_msgs, target_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
