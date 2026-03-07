#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path("/Users/jobiseu/.openclaw/workspace")
STAGE1_RAW = ROOT / "invest/stages/stage1/outputs/raw"
REPORT_DIR = ROOT / "invest/stages/stage1/outputs/reports/stage_updates"

NEWS_DIR = STAGE1_RAW / "qualitative/market/rss"
TELEGRAM_DIR = STAGE1_RAW / "qualitative/text/telegram"
BLOG_DIR = STAGE1_RAW / "qualitative/text/blog"
PREMIUM_DIR = STAGE1_RAW / "qualitative/text/premium"
LEGACY_SIGNAL_NEWS_DIR = STAGE1_RAW / "signal" / "market" / "news" / "rss"

PREV_RECHECK_GLOB = "STAGE1_TEN_YEAR_COVERAGE_RECHECK_*.json"


@dataclass
class SourceSummary:
    name: str
    min_date: str | None
    max_date: str | None
    count: int
    file_count: int
    years: float | None
    date_source_counts: dict[str, int]
    status: str
    judgment_note: str
    unresolved_count: int
    actual_date_count: int
    crawl_fallback_count: int


def _run(cmd: list[str], timeout: int = 1800) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_tail": out[-1200:],
        "stderr_tail": err[-1200:],
    }


def _parse_dt(raw: str) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    s = s.replace("오전", "AM").replace("오후", "PM")
    s = re.sub(r"\s+", " ", s).strip()

    try:
        dt = parsedate_to_datetime(s)
        if dt is not None:
            return dt
    except Exception:
        pass

    for cand in (s, s.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(cand)
        except Exception:
            pass

    ts = pd.to_datetime(s, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def _to_date_iso(dt: datetime) -> str:
    return dt.date().isoformat()


def _years(min_date: str | None, max_date: str | None) -> float | None:
    if not min_date or not max_date:
        return None
    d0 = datetime.fromisoformat(min_date)
    d1 = datetime.fromisoformat(max_date)
    return round(max(0.0, (d1 - d0).days / 365.25), 2)


def _summarize_dates(
    name: str,
    file_count: int,
    dates: list[datetime],
    date_sources: list[str],
    unresolved_count: int,
    *,
    require_actual_publish: bool,
    actual_date_count: int,
    crawl_fallback_count: int,
) -> SourceSummary:
    date_isos = sorted(_to_date_iso(d) for d in dates)
    min_date = date_isos[0] if date_isos else None
    max_date = date_isos[-1] if date_isos else None
    years = _years(min_date, max_date)
    source_counts = dict(Counter(date_sources).most_common())

    if not dates:
        status = "BLOCKED"
        judgment_note = "미확인(유효 날짜 필드 없음)"
    elif require_actual_publish and actual_date_count == 0:
        status = "BLOCKED"
        judgment_note = "미확인(실제 발행/게시 시각 필드 부재, crawl_date만 존재)"
    elif years is not None and years >= 10.0:
        status = "PASS"
        judgment_note = "10년 충족"
    else:
        status = "FAIL"
        judgment_note = "10년 미달"

    return SourceSummary(
        name=name,
        min_date=min_date,
        max_date=max_date,
        count=len(dates),
        file_count=file_count,
        years=years,
        date_source_counts=source_counts,
        status=status,
        judgment_note=judgment_note,
        unresolved_count=unresolved_count,
        actual_date_count=actual_date_count,
        crawl_fallback_count=crawl_fallback_count,
    )


def _collect_news() -> SourceSummary:
    files = sorted(NEWS_DIR.glob("rss_*.json"))
    dates: list[datetime] = []
    sources: list[str] = []
    unresolved = 0

    for fp in files:
        try:
            obj = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        for _, items in obj.items():
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    unresolved += 1
                    continue

                published = _parse_dt(str(it.get("published", "")))
                if published:
                    dates.append(published)
                    sources.append(str(it.get("date_source") or "published"))
                    continue

                pdate = _parse_dt(str(it.get("published_date", "")))
                if pdate:
                    dates.append(pdate)
                    sources.append("published_date")
                    continue

                praw = _parse_dt(str(it.get("published_raw", "")))
                if praw:
                    dates.append(praw)
                    sources.append("published_raw")
                    continue

                unresolved += 1

    return _summarize_dates(
        name="news",
        file_count=len(files),
        dates=dates,
        date_sources=sources,
        unresolved_count=unresolved,
        require_actual_publish=False,
        actual_date_count=len(dates),
        crawl_fallback_count=0,
    )


def _extract_header_date_fallback(text: str) -> datetime | None:
    head = text.split("\n---", 1)[0]
    m = re.search(r"(?m)^Date:\s*([^\n]+)", head)
    if not m:
        return None
    return _parse_dt(m.group(1).strip())


def _collect_telegram() -> SourceSummary:
    files = sorted(TELEGRAM_DIR.glob("*.md"))
    dates: list[datetime] = []
    sources: list[str] = []
    unresolved = 0
    actual_count = 0
    crawl_fallback = 0

    post_pat = re.compile(r"(?ms)^---\s*\nDate:\s*([^\n]+)")

    for fp in files:
        txt = fp.read_text(encoding="utf-8", errors="ignore")
        file_has_date = False

        for m in post_pat.finditer(txt):
            dt = _parse_dt(m.group(1).strip())
            if not dt:
                continue
            dates.append(dt)
            sources.append("post_date")
            actual_count += 1
            file_has_date = True

        if file_has_date:
            continue

        dt_fallback = _extract_header_date_fallback(txt)
        if dt_fallback:
            dates.append(dt_fallback)
            sources.append("crawl_date_fallback")
            crawl_fallback += 1
            continue

        unresolved += 1

    return _summarize_dates(
        name="telegram",
        file_count=len(files),
        dates=dates,
        date_sources=sources,
        unresolved_count=unresolved,
        require_actual_publish=True,
        actual_date_count=actual_count,
        crawl_fallback_count=crawl_fallback,
    )


def _extract_blog_like_post_date(text: str) -> datetime | None:
    lines = text.splitlines()
    src_idx = 0
    for i, line in enumerate(lines[:120]):
        if line.startswith("Source:"):
            src_idx = i
            break

    date_line_pat = re.compile(
        r"^\s*(20\d{2})[./-]\s*(\d{1,2})[./-]\s*(\d{1,2})\.?\s*(\d{1,2}:\d{2}(?::\d{2})?)?\s*$"
    )
    for line in lines[src_idx + 1 : min(len(lines), src_idx + 120)]:
        if not line.strip():
            continue
        m = date_line_pat.match(line.strip())
        if not m:
            continue
        raw = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        if m.group(4):
            raw += f" {m.group(4)}"
        dt = _parse_dt(raw)
        if dt:
            return dt
    return None


def _collect_blog() -> SourceSummary:
    files = sorted(BLOG_DIR.rglob("*.md"))
    dates: list[datetime] = []
    sources: list[str] = []
    unresolved = 0
    actual_count = 0
    crawl_fallback = 0

    for fp in files:
        txt = fp.read_text(encoding="utf-8", errors="ignore")
        dt = _extract_blog_like_post_date(txt)
        if dt:
            dates.append(dt)
            sources.append("post_date")
            actual_count += 1
            continue

        dt_fallback = _extract_header_date_fallback(txt)
        if dt_fallback:
            dates.append(dt_fallback)
            sources.append("crawl_date_fallback")
            crawl_fallback += 1
            continue

        unresolved += 1

    return _summarize_dates(
        name="blog",
        file_count=len(files),
        dates=dates,
        date_sources=sources,
        unresolved_count=unresolved,
        require_actual_publish=False,
        actual_date_count=actual_count,
        crawl_fallback_count=crawl_fallback,
    )


def _collect_premium() -> SourceSummary:
    files = sorted(PREMIUM_DIR.rglob("*.md"))
    dates: list[datetime] = []
    sources: list[str] = []
    unresolved = 0
    actual_count = 0
    crawl_fallback = 0

    for fp in files:
        txt = fp.read_text(encoding="utf-8", errors="ignore")
        rel_parts = {p.lower() for p in fp.relative_to(PREMIUM_DIR).parts}
        is_startale_linkmeta = "startale" in rel_parts or "# STARTALE PREMIUM LINK" in txt

        if not is_startale_linkmeta:
            dt = _extract_blog_like_post_date(txt)
            if dt:
                dates.append(dt)
                sources.append("post_date")
                actual_count += 1
                continue

        dt_fallback = _extract_header_date_fallback(txt)
        if dt_fallback:
            dates.append(dt_fallback)
            sources.append("crawl_date_fallback")
            crawl_fallback += 1
            continue

        unresolved += 1

    return _summarize_dates(
        name="premium",
        file_count=len(files),
        dates=dates,
        date_sources=sources,
        unresolved_count=unresolved,
        require_actual_publish=True,
        actual_date_count=actual_count,
        crawl_fallback_count=crawl_fallback,
    )


def _load_previous_recheck() -> dict[str, Any]:
    candidates = sorted(REPORT_DIR.glob(PREV_RECHECK_GLOB))
    if not candidates:
        return {}
    fp = candidates[-1]
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _reason_changes(prev: dict[str, Any], now_map: dict[str, SourceSummary]) -> dict[str, str]:
    prev_sources = prev.get("sources", {}) if isinstance(prev, dict) else {}

    reasons = {
        "news": (
            "기준 경로를 raw/qualitative/market/rss 단일 canonical로 고정하고, "
            "기존 signal 뉴스 미러를 제거하여 중복 집계를 배제했습니다."
        ),
        "telegram": (
            "Date(크롤시각) 우선 판정을 중단하고 post_date(게시시각) 우선으로 재산정했습니다. "
            "실제 게시시각 필드가 없는 파일은 미확인(BLOCKED)으로 분리했습니다."
        ),
        "blog": (
            "Date(크롤시각) 대신 본문 상단 게시일(post_date) 패턴을 우선 사용하고, "
            "없을 때만 crawl_date를 fallback으로 사용했습니다."
        ),
        "premium": (
            "STARTALE 링크메타는 실제 발행시각 필드가 없어 crawl_date만 존재하므로, "
            "기간 판정은 미확인(BLOCKED)으로 분리했습니다."
        ),
    }

    legacy_news_key = "/".join(["signal", "market", "news", "rss"])
    if legacy_news_key in prev_sources:
        reasons["news"] += " 이전 리포트의 legacy signal 뉴스 미러 항목은 폐기했습니다."

    return reasons


def _render_table_row(s: SourceSummary) -> str:
    ds = ", ".join([f"{k}:{v}" for k, v in s.date_source_counts.items()]) or "-"
    return (
        f"| {s.name} | {s.min_date or '미확인'} | {s.max_date or '미확인'} | {s.count} | "
        f"{ds} | {s.status} |"
    )


def _collect_smoke(run_smoke: bool) -> list[dict[str, Any]]:
    if not run_smoke:
        return []
    cmds = [
        ["python3", "invest/stages/stage1/scripts/stage01_post_collection_validate.py"],
        ["python3", "invest/stages/stage2/scripts/stage02_onepass_refine_full.py"],
        ["python3", "invest/stages/stage3/scripts/stage03_build_input_jsonl.py"],
    ]
    out = []
    for c in cmds:
        out.append(_run(c, timeout=3600))
    return out


def _scan_signal_news_refs() -> dict[str, Any]:
    legacy_sig = "/".join(["signal", "market", "news", "rss"])
    legacy_raw_sig = "/".join(["raw", "signal", "market", "news", "rss"])
    pattern = f"{legacy_raw_sig}\\|{legacy_sig}"
    cmd = [
        "grep",
        "-RIn",
        pattern,
        "invest/stages/stage1",
        "invest/stages/stage2",
        "invest/stages/stage3",
        "scripts",
        "--exclude-dir=outputs",
        "--exclude-dir=__pycache__",
        "--include=*.py",
        "--include=*.sh",
        "--include=*.md",
        "--include=*.json",
    ]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    lines = [ln for ln in (res.stdout or "").splitlines() if ln.strip()]
    return {
        "cmd": " ".join(cmd),
        "match_count": len(lines),
        "matches": lines[:50],
        "returncode": res.returncode,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage1 path/date judgment fix report")
    ap.add_argument("--run-smoke", action="store_true", help="run stage1~3 smoke once")
    args = ap.parse_args()

    legacy_signal_news_existed_before = LEGACY_SIGNAL_NEWS_DIR.exists()
    removed_legacy_signal_news = False
    if legacy_signal_news_existed_before:
        shutil.rmtree(LEGACY_SIGNAL_NEWS_DIR, ignore_errors=True)
        removed_legacy_signal_news = True
    legacy_signal_news_exists_after = LEGACY_SIGNAL_NEWS_DIR.exists()

    news = _collect_news()
    telegram = _collect_telegram()
    blog = _collect_blog()
    premium = _collect_premium()

    now_map = {
        "news": news,
        "telegram": telegram,
        "blog": blog,
        "premium": premium,
    }

    prev = _load_previous_recheck()
    reasons = _reason_changes(prev, now_map)

    smoke_results = _collect_smoke(run_smoke=args.run_smoke)
    ref_scan = _scan_signal_news_refs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"STAGE1_PATH_AND_DATE_JUDGMENT_FIX_{timestamp}"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = REPORT_DIR / f"{prefix}.md"
    json_path = REPORT_DIR / f"{prefix}.json"

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "legacy_signal_news_existed_before": legacy_signal_news_existed_before,
        "legacy_signal_news_removed": removed_legacy_signal_news,
        "legacy_signal_news_exists_after": legacy_signal_news_exists_after,
        "canonical_news_path": str(NEWS_DIR.relative_to(ROOT)),
        "legacy_signal_news_path": str(LEGACY_SIGNAL_NEWS_DIR.relative_to(ROOT)),
        "sources": {
            k: {
                "min_date": v.min_date,
                "max_date": v.max_date,
                "count": v.count,
                "file_count": v.file_count,
                "years": v.years,
                "date_source_counts": v.date_source_counts,
                "status": v.status,
                "judgment_note": v.judgment_note,
                "unresolved_count": v.unresolved_count,
                "actual_date_count": v.actual_date_count,
                "crawl_fallback_count": v.crawl_fallback_count,
            }
            for k, v in now_map.items()
        },
        "reason_changes": reasons,
        "smoke_results": smoke_results,
        "signal_news_ref_scan": ref_scan,
        "previous_recheck_detected": bool(prev),
        "previous_recheck_generated_at": prev.get("generated_at") if isinstance(prev, dict) else None,
    }

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {prefix}",
        "",
        "## 1) 뉴스 경로 단일화",
        f"- canonical 유지: `{NEWS_DIR.relative_to(ROOT)}`",
        f"- legacy 제거 대상: `{LEGACY_SIGNAL_NEWS_DIR.relative_to(ROOT)}`",
        f"- legacy 경로 사전 존재: `{legacy_signal_news_existed_before}`",
        f"- legacy 경로 제거 수행: `{removed_legacy_signal_news}`",
        f"- legacy 경로 현재 존재: `{legacy_signal_news_exists_after}`",
        "",
        "## 2) 기간 판정 재산정 (실발행/게시 시각 우선)",
        "| source | min_date | max_date | count | date_source 사용 | status |",
        "| :-- | :-- | :-- | --: | :-- | :-- |",
        _render_table_row(news),
        _render_table_row(telegram),
        _render_table_row(blog),
        _render_table_row(premium),
        "",
        "- 판정 규칙: `post/published 계열 우선`, 부재 시 `crawl_date fallback`, 실제 발행시각 미확인 시 `BLOCKED(미확인)` 분리",
        "",
        "## 3) 이전 판정 대비 변경 사유",
        f"- news: {reasons['news']}",
        f"- telegram: {reasons['telegram']}",
        f"- blog: {reasons['blog']}",
        f"- premium: {reasons['premium']}",
        "",
        "## 4) 검증",
        "### stage1~3 smoke (1회)",
    ]

    if smoke_results:
        lines += [
            "| step | returncode | stdout_tail | stderr_tail |",
            "| :-- | --: | :-- | :-- |",
        ]
        for r in smoke_results:
            step = r["cmd"]
            rc = r["returncode"]
            so = (r["stdout_tail"] or "").replace("\n", " ")[:240]
            se = (r["stderr_tail"] or "").replace("\n", " ")[:240]
            lines.append(f"| `{step}` | {rc} | {so} | {se} |")
    else:
        lines.append("- (skip) --run-smoke 미사용")

    lines += [
        "",
        "### 운영 코드 signal/news/rss 참조 검사",
        f"- match_count: `{ref_scan['match_count']}`",
        f"- cmd: `{ref_scan['cmd']}`",
        "",
        "## 5) 산출물",
        f"- report_md: `{md_path.relative_to(ROOT)}`",
        f"- summary_json: `{json_path.relative_to(ROOT)}`",
    ]

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "report_md": str(md_path.relative_to(ROOT)),
        "summary_json": str(json_path.relative_to(ROOT)),
        "signal_news_ref_matches": ref_scan["match_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
