#!/usr/bin/env python3
"""
Stage3 입력(JSONL) 생성기
- Stage2 clean의 qualitative/signal 입력(DART/RSS/macro + telegram/blog/premium/selected_articles)을 읽어
  Stage3 입력 포맷으로 정규화한다.
- Telegram PDF는 Stage2 clean `text/telegram` 본문에 inline 승격된 상태를 그대로 Stage3에 인입한다.
- 중복/재전파(동일 본문 fingerprint) 문서는 제거한다.
- 출력이 0건이어도 입력 파일은 생성한다(체인 경로 고정 목적).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    from invest.stages.run_manifest import write_run_manifest
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from run_manifest import write_run_manifest

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = Path(__file__).resolve().parents[1]
INPUTS_ROOT = STAGE_ROOT / "inputs"
REFERENCE_ROOT = INPUTS_ROOT / "reference"
UPSTREAM_STAGE2_CLEAN = INPUTS_ROOT / "upstream_stage2_clean"
STAGE2_CLEAN_ROOTS = [
    UPSTREAM_STAGE2_CLEAN / "production",
    UPSTREAM_STAGE2_CLEAN,
    WORKSPACE_ROOT / "invest/stages/stage2/outputs/clean/production",
]


def _first_existing(candidates: list[Path]) -> Path:
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def _resolve_stage2_qual_kr(rel_path: str) -> Path:
    return _first_existing([root / "qualitative" / "kr" / rel_path for root in STAGE2_CLEAN_ROOTS])


def _resolve_stage2_qual_text(rel_path: str) -> Path:
    """Stage2 clean text 경로 호환: stage3 입력 symlink 우선, legacy flat fallback 지원."""
    candidates = [
        *[root / "qualitative" / "text" / rel_path for root in STAGE2_CLEAN_ROOTS],
        *[root / "text" / rel_path for root in STAGE2_CLEAN_ROOTS],
    ]
    return _first_existing(candidates)


def _resolve_stage2_qual_market(rel_path: str) -> Path:
    candidates = [
        *[root / "qualitative" / "market" / rel_path for root in STAGE2_CLEAN_ROOTS],
        *[root / "market" / rel_path for root in STAGE2_CLEAN_ROOTS],
    ]
    return _first_existing(candidates)


def _resolve_stage2_signal_market(rel_path: str) -> Path:
    return _first_existing([root / "signal" / "market" / rel_path for root in STAGE2_CLEAN_ROOTS])


DART_DIR = _resolve_stage2_qual_kr("dart")
RSS_DIR = _resolve_stage2_qual_market("rss")
MACRO_SUMMARY = _resolve_stage2_signal_market("macro/macro_summary.json")
MASTER_LIST = REFERENCE_ROOT / "kr_stock_list.csv"

TEXT_TELEGRAM_DIR = _resolve_stage2_qual_text("telegram")
TEXT_BLOG_DIR = _resolve_stage2_qual_text("blog")
TEXT_PREMIUM_DIR = _resolve_stage2_qual_text("premium")
SELECTED_ARTICLES_DIR = _resolve_stage2_qual_market("news/selected_articles")

OUT_JSONL_DEFAULT = STAGE_ROOT / "inputs/stage2_text_meta_records.jsonl"
OUT_SUMMARY_DEFAULT = STAGE_ROOT / "outputs/STAGE3_INPUT_BUILD_latest.json"

RISK_ON_WORDS = {
    "완화", "인하", "랠리", "상승", "회복", "risk-on", "risk on", "soft landing", "stimulus", "easing",
}
RISK_OFF_WORDS = {
    "긴축", "인상", "침체", "전쟁", "관세", "하락", "위기", "리스크오프", "risk-off", "risk off", "recession", "conflict", "sanction",
}


def _norm_code(v: object) -> str:
    s = str(v or "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    if not s:
        return ""
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s.upper()


def _latest_csv(path: Path) -> Path | None:
    files = sorted(path.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _latest_json(path: Path) -> Path | None:
    files = sorted(path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _latest_files(path: Path, pattern: str, limit: int) -> list[Path]:
    if not path.exists():
        return []
    files = sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[: max(0, limit)] if limit > 0 else files


def _resolve_cutoff(lookback_days: int) -> pd.Timestamp | None:
    if lookback_days <= 0:
        return None
    return pd.Timestamp.now(tz="Asia/Seoul") - pd.Timedelta(days=lookback_days)


def _normalize_text_for_dedup(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^0-9a-z가-힣 ]+", "", s)
    return s.strip()


def _content_fingerprint(text: str) -> str:
    norm = _normalize_text_for_dedup(text)
    return hashlib.sha1(norm.encode("utf-8", errors="ignore")).hexdigest()


def _parse_datetime_any(value: str) -> str:
    s = str(value or "").strip()
    if not s:
        return ""

    s = s.replace("오전", "AM").replace("오후", "PM")
    s = re.sub(r"\s+", " ", s).strip()

    ts = pd.to_datetime(s, errors="coerce")
    if pd.isna(ts):
        return ""

    if ts.tzinfo is None:
        ts = ts.tz_localize("Asia/Seoul")
    else:
        ts = ts.tz_convert("Asia/Seoul")
    return ts.isoformat(timespec="seconds")


def _extract_inline_datetime(txt: str) -> str:
    if not txt:
        return ""
    patterns = [
        r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2}\.?\s*(?:오전|오후)?\s*\d{1,2}:\d{2})",
        r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})",
    ]
    for p in patterns:
        m = re.search(p, txt)
        if m:
            parsed = _parse_datetime_any(m.group(1))
            if parsed:
                return parsed
    return ""


def _load_name_map(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    pairs: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        canon = {str(fn).strip().lstrip("\ufeff").lower(): fn for fn in fieldnames}
        code_key = canon.get("code")
        name_key = canon.get("name")
        if not code_key or not name_key:
            return []

        for r in reader:
            code = _norm_code(r.get(code_key, ""))
            name = str(r.get(name_key, "")).strip()
            if code and name:
                pairs.append((code, name))
    return pairs


def _extract_symbols_from_text(text: str, name_pairs: list[tuple[str, str]], max_hits: int = 5) -> list[str]:
    if not text:
        return []

    code_set = {code for code, _ in name_pairs}
    text_l = text.lower()
    out: list[str] = []

    for code, name in name_pairs:
        if name.lower() in text_l:
            if code not in out:
                out.append(code)
            if len(out) >= max_hits:
                return out

    for hit in re.findall(r"(?<!\d)(\d{6})(?!\d)", text):
        code = _norm_code(hit)
        if code in code_set and code not in out:
            out.append(code)
            if len(out) >= max_hits:
                break

    return out


def _is_macro_news_text(text: str) -> bool:
    tl = (text or "").lower()
    if not tl:
        return False
    has_on = any(k in tl for k in RISK_ON_WORDS)
    has_off = any(k in tl for k in RISK_OFF_WORDS)
    return has_on or has_off


def _extract_markdown_title(txt: str, fallback: str = "") -> str:
    patterns = [
        r"^#\s*(.+)$",
        r"^Title:\s*(.+)$",
        r"^-\s*Title:\s*(.+)$",
    ]
    for pattern in patterns:
        m = re.search(pattern, txt or "", flags=re.M)
        if m:
            return m.group(1).strip()
    return fallback


def _extract_first_meta_value(txt: str, keys: list[str]) -> str:
    for key in keys:
        m = re.search(rf"^(?:-\s*)?{re.escape(key)}\s*:\s*(.+)$", txt or "", flags=re.M)
        if m:
            return m.group(1).strip()
    return ""


def _clean_web_md_body(txt: str) -> str:
    lines = txt.splitlines()
    if not lines:
        return ""

    start = 0
    for i, line in enumerate(lines):
        if line.startswith("Source:"):
            start = i + 1
            break

    noisy_re = re.compile(
        r"본문 바로가기|블로그 검색|공감|댓글|공유하기|로그인|네이버|레이어 닫기|고객센터|운영정책|전체서비스",
        re.I,
    )
    meta_re = re.compile(
        r"^(LinkEnriched|CanonicalURLs|CanonicalURL|PublishedDate|PublishedAt|Date|Source)\s*:",
        re.I,
    )

    out: list[str] = []
    for raw in lines[start:]:
        s = raw.strip()
        if not s:
            continue
        if s == "[LinkEnrichment]":
            continue
        if noisy_re.search(s) or meta_re.match(s):
            continue
        if len(s) <= 1:
            continue
        out.append(s)

    return "\n".join(out[:180])


def _clean_premium_body(txt: str) -> str:
    parts = re.split(r"(?mi)^##\s*본문\s*$", txt or "", maxsplit=1)
    body = parts[1] if len(parts) > 1 else txt
    if not body:
        return ""

    boilerplate_re = re.compile(
        r"disclaimer|투자 결과에 대한 법적 책임소재|매수.?매도 추천|별도의 투자 상담|구독자 여러분 스스로 공부",
        re.I,
    )
    meta_re = re.compile(
        r"^(?:-\s*)?(URL|PublishedAt|CollectedAt|Status|Reason|isLogin|LinkEnriched|CanonicalURLs|CanonicalURL)\s*:",
        re.I,
    )

    out: list[str] = []
    for raw in body.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s == "[LinkEnrichment]":
            continue
        if meta_re.match(s) or boilerplate_re.search(s):
            continue
        out.append(s)

    return "\n".join(out[:220])


def _selected_articles_text(row: dict) -> str:
    parts = []
    for key in ("title", "summary", "body"):
        value = str(row.get(key, "") or "").strip()
        if value:
            parts.append(value)
    text = "\n".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _build_from_dart() -> tuple[list[dict], str]:
    fp = _latest_json(DART_DIR)
    if fp is None:
        return [], ""

    try:
        obj = json.loads(fp.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            rows = obj.get("rows", [])
        elif isinstance(obj, list):
            rows = obj
        else:
            rows = []
        if not isinstance(rows, list):
            rows = []
    except Exception:
        return [], str(fp)

    out: list[dict] = []

    for i, r in enumerate(rows, start=1):
        code = _norm_code(r.get("stock_code", ""))
        if not code or code == "000000":
            continue

        rcept_dt = str(r.get("rcept_dt", "")).strip()
        if len(rcept_dt) == 8 and rcept_dt.isdigit():
            dt = f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:8]}"
            published_at = f"{dt}T15:30:00+09:00"
        else:
            published_at = datetime.now().astimezone().isoformat(timespec="seconds")

        corp_name = str(r.get("corp_name", "")).strip()
        report_nm = str(r.get("report_nm", "")).strip()
        text = " ".join(x for x in [corp_name, report_nm] if x).strip()
        if not text:
            continue

        rid = str(r.get("rcept_no", "")).strip() or f"dart-row-{i}"
        out.append(
            {
                "record_id": f"dart:{rid}",
                "published_at": published_at,
                "symbols": [code],
                "text": text,
                "source": "dart",
                "content_fingerprint": _content_fingerprint(text),
            }
        )

    return out, str(fp)


def _build_from_rss(name_pairs: list[tuple[str, str]]) -> tuple[list[dict], str, dict]:
    fp = _latest_json(RSS_DIR)
    empty_stats = {
        "rss_items_total": 0,
        "rss_items_nonempty_text": 0,
        "rss_items_with_symbols": 0,
        "rss_items_macro_only": 0,
        "rss_items_skipped_no_symbols": 0,
        "rss_rows_by_feed": {},
    }
    if fp is None:
        return [], "", empty_stats

    obj = json.loads(fp.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        return [], str(fp), empty_stats

    out: list[dict] = []
    stats = dict(empty_stats)
    rows_by_feed: dict[str, int] = {}

    for feed, items in obj.items():
        feed_name = str(feed).strip().lower() or "unknown"
        if not isinstance(items, list):
            continue
        for idx, it in enumerate(items, start=1):
            stats["rss_items_total"] += 1
            if not isinstance(it, dict):
                continue

            title = str(it.get("title", "")).strip()
            summary = str(it.get("summary", "")).strip()
            text = "\n".join(x for x in [title, summary] if x).strip()
            if not text:
                continue
            stats["rss_items_nonempty_text"] += 1

            symbols = _extract_symbols_from_text(text, name_pairs)
            is_macro_only = False
            if not symbols and _is_macro_news_text(text):
                symbols = ["__MACRO__"]
                is_macro_only = True

            if not symbols:
                stats["rss_items_skipped_no_symbols"] += 1
                continue

            published_at = str(it.get("published", "")).strip()
            if not published_at:
                pdate = str(it.get("published_date", "")).strip()
                published_at = (
                    f"{pdate}T09:00:00+09:00"
                    if pdate
                    else datetime.now().astimezone().isoformat(timespec="seconds")
                )

            if is_macro_only:
                stats["rss_items_macro_only"] += 1
                source = f"rss_macro:{feed_name}"
            else:
                stats["rss_items_with_symbols"] += 1
                source = f"rss:{feed_name}"

            rows_by_feed[feed_name] = rows_by_feed.get(feed_name, 0) + 1
            out.append(
                {
                    "record_id": f"rss:{fp.stem}:{feed_name}:{idx}",
                    "published_at": published_at,
                    "symbols": symbols,
                    "text": text,
                    "source": source,
                    "content_fingerprint": _content_fingerprint(text),
                }
            )

    stats["rss_rows_by_feed"] = rows_by_feed
    return out, str(fp), stats


def _build_from_macro_summary() -> tuple[list[dict], dict]:
    out: list[dict] = []
    stats = {"macro_docs_output": 0, "macro_symbols": 0}

    if not MACRO_SUMMARY.exists():
        return out, stats

    try:
        obj = json.loads(MACRO_SUMMARY.read_text(encoding="utf-8"))
    except Exception:
        return out, stats

    latest = obj.get("latest", {}) if isinstance(obj, dict) else {}
    if not isinstance(latest, dict) or not latest:
        return out, stats

    risk_on = 0
    risk_off = 0
    parts = []
    pub_date = ""

    risk_on_set = {"SPY", "QQQ", "SOX"}
    risk_off_set = {"VIX", "DXY", "TNX", "IRX"}

    for sym, item in latest.items():
        if not isinstance(item, dict):
            continue
        d = str(item.get("date", "")).strip()
        if d and d > pub_date:
            pub_date = d
        ch1 = float(item.get("change_1d", 0.0) or 0.0)
        if sym in risk_on_set:
            if ch1 > 0:
                risk_on += 1
            elif ch1 < 0:
                risk_off += 1
        elif sym in risk_off_set:
            if ch1 > 0:
                risk_off += 1
            elif ch1 < 0:
                risk_on += 1
        parts.append(f"{sym}:{ch1:+.4f}")

    if risk_on > risk_off:
        risk_word = "risk-on"
    elif risk_on < risk_off:
        risk_word = "risk-off"
    else:
        risk_word = "neutral"
    text = f"macro summary {risk_word}, risk_on={risk_on}, risk_off={risk_off}, signals=" + ", ".join(parts[:12])

    if pub_date:
        published_at = f"{pub_date}T15:30:00+09:00"
    else:
        published_at = datetime.now().astimezone().isoformat(timespec="seconds")

    rid = hashlib.sha1(f"macro_summary:{published_at}:{text}".encode("utf-8", errors="ignore")).hexdigest()[:20]
    out.append(
        {
            "record_id": f"macro:{rid}",
            "published_at": published_at,
            "symbols": ["__MACRO__"],
            "text": text,
            "source": "rss_macro:market_macro",
            "content_fingerprint": _content_fingerprint(text),
        }
    )
    stats["macro_docs_output"] = 1

    return out, stats


def _build_from_text_telegram(
    name_pairs: list[tuple[str, str]],
    lookback_days: int,
    max_files: int,
    max_messages_per_file: int,
    include_nosymbol: bool,
) -> tuple[list[dict], dict]:
    out: list[dict] = []
    stats = {
        "telegram_files_scanned": 0,
        "telegram_messages_scanned": 0,
        "telegram_messages_with_symbols": 0,
        "telegram_messages_skipped_no_symbols": 0,
        "telegram_messages_included_nosymbol": 0,
    }

    if not TEXT_TELEGRAM_DIR.exists():
        return out, stats

    cutoff = _resolve_cutoff(lookback_days)

    files = _latest_files(TEXT_TELEGRAM_DIR, "*.md", max_files)
    for fp in files:
        stats["telegram_files_scanned"] += 1
        txt = fp.read_text(encoding="utf-8", errors="ignore")

        parts = re.split(r"\n---\s*\nDate:\s*([^\n]+)\n", txt)
        msgs: list[tuple[str, str]] = []
        if len(parts) >= 3:
            for i in range(1, len(parts), 2):
                d = parts[i].strip()
                body = parts[i + 1].strip() if i + 1 < len(parts) else ""
                msgs.append((d, body))
        else:
            msgs.append(("", txt))

        for d_raw, body in msgs[: max(1, max_messages_per_file)]:
            stats["telegram_messages_scanned"] += 1
            published_at = _parse_datetime_any(d_raw)
            if not published_at:
                continue

            ts = pd.to_datetime(published_at, errors="coerce")
            if pd.isna(ts):
                continue
            if cutoff is not None and ts < cutoff:
                continue

            text = re.sub(r"\n{3,}", "\n\n", body).strip()
            if not text or len(text) < 20:
                continue

            symbols = _extract_symbols_from_text(text, name_pairs)
            source_family = "text_telegram"
            if not symbols:
                stats["telegram_messages_skipped_no_symbols"] += 1
                if not include_nosymbol:
                    continue
                symbols = ["__NOSYMBOL__"]
                source_family = "text_telegram_nosymbol"
                stats["telegram_messages_included_nosymbol"] += 1
            else:
                stats["telegram_messages_with_symbols"] += 1

            rid_seed = f"{fp.name}:{d_raw}:{text[:160]}:{source_family}"
            rid = hashlib.sha1(rid_seed.encode("utf-8", errors="ignore")).hexdigest()[:20]
            out.append(
                {
                    "record_id": f"text_telegram:{rid}",
                    "published_at": published_at,
                    "symbols": symbols,
                    "text": text,
                    "source": f"text/telegram:{fp.stem}",
                    "source_family": source_family,
                    "content_fingerprint": _content_fingerprint(text),
                }
            )

    return out, stats


def _build_from_text_blog(
    name_pairs: list[tuple[str, str]],
    lookback_days: int,
    max_files: int,
    include_nosymbol: bool,
) -> tuple[list[dict], dict]:
    out: list[dict] = []
    stats = {
        "blog_files_scanned": 0,
        "blog_docs_with_symbols": 0,
        "blog_docs_skipped_no_symbols": 0,
        "blog_docs_included_nosymbol": 0,
    }

    if not TEXT_BLOG_DIR.exists():
        return out, stats

    cutoff = _resolve_cutoff(lookback_days)
    files = sorted(TEXT_BLOG_DIR.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[: max(0, max_files)] if max_files > 0 else files

    for fp in files:
        stats["blog_files_scanned"] += 1
        txt = fp.read_text(encoding="utf-8", errors="ignore")

        title = _extract_markdown_title(txt, fallback=fp.stem)
        date_raw = _extract_first_meta_value(txt, ["Date", "PublishedDate", "PublishedAt"])

        published_at = _parse_datetime_any(date_raw)
        if not published_at:
            published_at = _extract_inline_datetime(txt)
        if not published_at:
            continue
        ts = pd.to_datetime(published_at, errors="coerce")
        if pd.isna(ts) or (cutoff is not None and ts < cutoff):
            continue

        body = _clean_web_md_body(txt)
        text = "\n".join(x for x in [title, body] if x).strip()
        if len(text) < 30:
            continue

        symbols = _extract_symbols_from_text(text, name_pairs)
        source_family = "text_blog"
        if not symbols:
            stats["blog_docs_skipped_no_symbols"] += 1
            if not include_nosymbol:
                continue
            symbols = ["__NOSYMBOL__"]
            source_family = "text_blog_nosymbol"
            stats["blog_docs_included_nosymbol"] += 1
        else:
            stats["blog_docs_with_symbols"] += 1

        rid = hashlib.sha1(f"{str(fp)}:{source_family}".encode("utf-8", errors="ignore")).hexdigest()[:20]
        out.append(
            {
                "record_id": f"text_blog:{rid}",
                "published_at": published_at,
                "symbols": symbols,
                "text": text,
                "source": f"text/blog:{fp.parent.name}",
                "source_family": source_family,
                "content_fingerprint": _content_fingerprint(text),
            }
        )

    return out, stats


def _build_from_text_premium(
    name_pairs: list[tuple[str, str]],
    lookback_days: int,
    max_files: int,
    include_nosymbol: bool,
) -> tuple[list[dict], dict]:
    out: list[dict] = []
    stats = {
        "premium_files_scanned": 0,
        "premium_docs_with_symbols": 0,
        "premium_docs_skipped_no_symbols": 0,
        "premium_docs_skipped_linkmeta": 0,
        "premium_docs_included_nosymbol": 0,
    }

    if not TEXT_PREMIUM_DIR.exists():
        return out, stats

    cutoff = _resolve_cutoff(lookback_days)
    files = sorted(TEXT_PREMIUM_DIR.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[: max(0, max_files)] if max_files > 0 else files

    for fp in files:
        stats["premium_files_scanned"] += 1
        txt = fp.read_text(encoding="utf-8", errors="ignore")
        if "# STARTALE PREMIUM LINK" in txt:
            stats["premium_docs_skipped_linkmeta"] += 1
            continue

        title = _extract_markdown_title(txt, fallback=fp.stem)
        date_raw = _extract_first_meta_value(txt, ["PublishedAt", "Date", "PublishedDate"])

        published_at = _parse_datetime_any(date_raw)
        if not published_at:
            published_at = _extract_inline_datetime(txt)
        if not published_at:
            continue

        ts = pd.to_datetime(published_at, errors="coerce")
        if pd.isna(ts) or (cutoff is not None and ts < cutoff):
            continue

        body = _clean_premium_body(txt)
        text = "\n".join(x for x in [title, body] if x).strip()
        if len(text) < 30:
            continue

        symbols = _extract_symbols_from_text(text, name_pairs)
        source_family = "text_premium"
        if not symbols:
            stats["premium_docs_skipped_no_symbols"] += 1
            if not include_nosymbol:
                continue
            symbols = ["__NOSYMBOL__"]
            source_family = "text_premium_nosymbol"
            stats["premium_docs_included_nosymbol"] += 1
        else:
            stats["premium_docs_with_symbols"] += 1

        rid = hashlib.sha1(f"{str(fp)}:{source_family}".encode("utf-8", errors="ignore")).hexdigest()[:20]
        out.append(
            {
                "record_id": f"text_premium:{rid}",
                "published_at": published_at,
                "symbols": symbols,
                "text": text,
                "source": f"text/premium:{fp.parent.name}",
                "source_family": source_family,
                "content_fingerprint": _content_fingerprint(text),
            }
        )

    return out, stats


def _build_from_market_selected_articles(
    name_pairs: list[tuple[str, str]],
    lookback_days: int,
    max_files: int,
    include_nosymbol: bool,
) -> tuple[list[dict], dict]:
    out: list[dict] = []
    stats = {
        "selected_articles_files_scanned": 0,
        "selected_articles_rows_scanned": 0,
        "selected_articles_rows_with_symbols": 0,
        "selected_articles_rows_skipped_no_symbols": 0,
        "selected_articles_rows_included_nosymbol": 0,
        "selected_articles_rows_invalid_json": 0,
    }

    if not SELECTED_ARTICLES_DIR.exists():
        return out, stats

    cutoff = _resolve_cutoff(lookback_days)
    files = sorted(SELECTED_ARTICLES_DIR.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[: max(0, max_files)] if max_files > 0 else files

    for fp in files:
        stats["selected_articles_files_scanned"] += 1
        with fp.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    stats["selected_articles_rows_invalid_json"] += 1
                    continue
                if not isinstance(row, dict):
                    stats["selected_articles_rows_invalid_json"] += 1
                    continue

                stats["selected_articles_rows_scanned"] += 1
                published_at = _parse_datetime_any(str(row.get("published_at") or row.get("published_date") or ""))
                if not published_at:
                    continue

                ts = pd.to_datetime(published_at, errors="coerce")
                if pd.isna(ts) or (cutoff is not None and ts < cutoff):
                    continue

                text = _selected_articles_text(row)
                if len(text) < 30:
                    continue

                symbols = _extract_symbols_from_text(text, name_pairs)
                source_family = "market_selected_articles"
                if not symbols:
                    stats["selected_articles_rows_skipped_no_symbols"] += 1
                    if not include_nosymbol:
                        continue
                    symbols = ["__NOSYMBOL__"]
                    source_family = "market_selected_articles_nosymbol"
                    stats["selected_articles_rows_included_nosymbol"] += 1
                else:
                    stats["selected_articles_rows_with_symbols"] += 1

                row_url = str(row.get("url") or "").strip()
                rid_seed = f"{fp.name}:{line_no}:{row_url}:{source_family}"
                rid = hashlib.sha1(rid_seed.encode("utf-8", errors="ignore")).hexdigest()[:20]
                source_domain = str(row.get("source_domain") or "").strip() or "unknown"
                out.append(
                    {
                        "record_id": f"market_selected_articles:{rid}",
                        "published_at": published_at,
                        "symbols": symbols,
                        "text": text,
                        "source": f"market/selected_articles:{source_domain}",
                        "source_family": source_family,
                        "content_fingerprint": _content_fingerprint(text),
                    }
                )

    return out, stats


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage3 input JSONL from Stage2 clean artifacts")
    p.add_argument("--out-jsonl", default=str(OUT_JSONL_DEFAULT))
    p.add_argument("--summary-json", default=str(OUT_SUMMARY_DEFAULT))
    p.add_argument("--text-lookback-days", type=int, default=0)
    p.add_argument("--telegram-max-files", type=int, default=0)
    p.add_argument("--telegram-max-messages-per-file", type=int, default=120)
    p.add_argument("--blog-max-files", type=int, default=0)
    p.add_argument("--premium-max-files", type=int, default=0)
    p.add_argument("--selected-articles-max-files", type=int, default=0)
    p.add_argument("--include-nosymbol", dest="include_nosymbol", action="store_true", default=True)
    p.add_argument("--exclude-nosymbol", dest="include_nosymbol", action="store_false")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_jsonl = Path(args.out_jsonl)
    summary_json = Path(args.summary_json)

    name_pairs = _load_name_map(MASTER_LIST)

    dart_rows, dart_src = _build_from_dart()
    rss_rows, rss_src, rss_stats = _build_from_rss(name_pairs)
    macro_rows, macro_stats = _build_from_macro_summary()
    tg_rows, tg_stats = _build_from_text_telegram(
        name_pairs,
        lookback_days=args.text_lookback_days,
        max_files=args.telegram_max_files,
        max_messages_per_file=args.telegram_max_messages_per_file,
        include_nosymbol=args.include_nosymbol,
    )
    blog_rows, blog_stats = _build_from_text_blog(
        name_pairs,
        lookback_days=args.text_lookback_days,
        max_files=args.blog_max_files,
        include_nosymbol=args.include_nosymbol,
    )
    premium_rows, premium_stats = _build_from_text_premium(
        name_pairs,
        lookback_days=args.text_lookback_days,
        max_files=args.premium_max_files,
        include_nosymbol=args.include_nosymbol,
    )
    selected_article_rows, selected_article_stats = _build_from_market_selected_articles(
        name_pairs,
        lookback_days=args.text_lookback_days,
        max_files=args.selected_articles_max_files,
        include_nosymbol=args.include_nosymbol,
    )

    merged: list[dict] = []
    seen_record_id: set[str] = set()
    seen_fingerprint: set[str] = set()
    dropped_duplicate_record_id = 0
    dropped_duplicate_fingerprint = 0

    all_rows = [
        *dart_rows,
        *rss_rows,
        *macro_rows,
        *tg_rows,
        *blog_rows,
        *premium_rows,
        *selected_article_rows,
    ]
    for r in all_rows:
        rid = str(r.get("record_id", "")).strip()
        if not rid:
            continue
        if rid in seen_record_id:
            dropped_duplicate_record_id += 1
            continue

        fp = str(r.get("content_fingerprint", "")).strip()
        if fp and fp in seen_fingerprint:
            dropped_duplicate_fingerprint += 1
            continue

        seen_record_id.add(rid)
        if fp:
            seen_fingerprint.add(fp)
        merged.append(r)

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def _infer_missing_reasons(stats_obj: dict, *, files_key: str, skipped_key: str, invalid_key: str = "") -> list[str]:
        reasons: list[str] = []
        files_scanned = int(stats_obj.get(files_key, 0) or 0)
        skipped_no_symbols = int(stats_obj.get(skipped_key, 0) or 0)
        invalid_rows = int(stats_obj.get(invalid_key, 0) or 0) if invalid_key else 0
        if files_scanned <= 0:
            reasons.append("입력 없음")
        if invalid_rows > 0:
            reasons.append("파싱실패")
        if skipped_no_symbols > 0:
            reasons.append("심볼필터")
        if not reasons:
            reasons.append("입력 없음")
        return reasons

    ingestion_validation = {
        "rows_from_market_selected_articles": {
            "rows": len(selected_article_rows),
            "status": "OK" if len(selected_article_rows) > 0 else "WARN",
            "missing_reasons": (
                _infer_missing_reasons(
                    selected_article_stats,
                    files_key="selected_articles_files_scanned",
                    skipped_key="selected_articles_rows_skipped_no_symbols",
                    invalid_key="selected_articles_rows_invalid_json",
                )
                if len(selected_article_rows) == 0
                else []
            ),
        },
    }

    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "stage": "stage3_input_build",
        "dart_source": dart_src,
        "rss_source": rss_src,
        "rows_from_dart": len(dart_rows),
        "rows_from_rss": len(rss_rows),
        "rows_from_macro_summary": len(macro_rows),
        "rows_from_text_telegram": len(tg_rows),
        "rows_from_text_blog": len(blog_rows),
        "rows_from_text_premium": len(premium_rows),
        "rows_from_market_selected_articles": len(selected_article_rows),
        "rows_before_dedup": len(all_rows),
        "rows_output": len(merged),
        "dropped_duplicate_record_id": dropped_duplicate_record_id,
        "dropped_duplicate_fingerprint": dropped_duplicate_fingerprint,
        "rss_items_total": rss_stats.get("rss_items_total", 0),
        "rss_items_nonempty_text": rss_stats.get("rss_items_nonempty_text", 0),
        "rss_items_with_symbols": rss_stats.get("rss_items_with_symbols", 0),
        "rss_items_macro_only": rss_stats.get("rss_items_macro_only", 0),
        "rss_items_skipped_no_symbols": rss_stats.get("rss_items_skipped_no_symbols", 0),
        "rss_rows_by_feed": rss_stats.get("rss_rows_by_feed", {}),
        "macro_stats": macro_stats,
        "telegram_stats": tg_stats,
        "blog_stats": blog_stats,
        "premium_stats": premium_stats,
        "selected_articles_stats": selected_article_stats,
        "text_lookback_days": args.text_lookback_days,
        "caps_effective": {
            "text_lookback_days": args.text_lookback_days,
            "lookback_unlimited": args.text_lookback_days <= 0,
            "telegram_max_files": args.telegram_max_files,
            "blog_max_files": args.blog_max_files,
            "premium_max_files": args.premium_max_files,
            "selected_articles_max_files": args.selected_articles_max_files,
            "max_files_unlimited": {
                "telegram": args.telegram_max_files <= 0,
                "blog": args.blog_max_files <= 0,
                "premium": args.premium_max_files <= 0,
                "selected_articles": args.selected_articles_max_files <= 0,
            },
            "include_nosymbol": bool(args.include_nosymbol),
        },
        "ingestion_validation": ingestion_validation,
        "output_jsonl": str(out_jsonl),
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest_path = STAGE_ROOT / "outputs" / f"manifest_stage3_input_build_{ts}.json"
    write_run_manifest(
        run_type="stage3_input_build",
        params={
            "text_lookback_days": args.text_lookback_days,
            "telegram_max_files": args.telegram_max_files,
            "telegram_max_messages_per_file": args.telegram_max_messages_per_file,
            "blog_max_files": args.blog_max_files,
            "premium_max_files": args.premium_max_files,
            "selected_articles_max_files": args.selected_articles_max_files,
            "include_nosymbol": bool(args.include_nosymbol),
        },
        inputs=[
            str(DART_DIR),
            str(RSS_DIR),
            str(MACRO_SUMMARY),
            str(MASTER_LIST),
            str(TEXT_TELEGRAM_DIR),
            str(TEXT_BLOG_DIR),
            str(TEXT_PREMIUM_DIR),
            str(SELECTED_ARTICLES_DIR),
        ],
        outputs=[str(out_jsonl), str(summary_json)],
        out_path=str(manifest_path),
        workdir=str(WORKSPACE_ROOT),
    )

    print(f"STAGE3_INPUT_BUILD_DONE output={out_jsonl}")
    print(f"STAGE3_INPUT_BUILD_SUMMARY={summary_json}")
    print(f"STAGE3_INPUT_BUILD_MANIFEST={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
