#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path('/Users/jobiseu/.openclaw/workspace')
RAW = ROOT / 'invest/stages/stage1/outputs/raw'
REPORT_DIR = ROOT / 'invest/stages/stage1/outputs/reports/stage_updates'
TARGET_START = datetime(2016, 1, 1)


@dataclass
class Summary:
    source: str
    path: str
    file_count: int
    item_count: int
    min_date: str | None
    max_date: str | None
    span_years: float | None
    status: str
    reason: str
    evidence: dict


def _years(min_dt: datetime | None, max_dt: datetime | None) -> float | None:
    if min_dt is None or max_dt is None:
        return None
    return round(max(0.0, (max_dt - min_dt).days / 365.25), 2)


def _fmt(dt: datetime | None) -> str | None:
    return dt.date().isoformat() if dt else None


def _dt(raw: str) -> datetime | None:
    s = str(raw or '').strip()
    if not s:
        return None
    s = s.replace('Z', '+00:00')
    ts = pd.to_datetime(s, errors='coerce', utc=True)
    if pd.isna(ts):
        return None
    return ts.to_pydatetime().replace(tzinfo=None)


def _finalize(source: str, path: Path, dates: Iterable[datetime], file_count: int, item_count: int, *, reason: str = '', evidence: dict | None = None, force_status: str | None = None) -> Summary:
    ds = sorted(dates)
    mn = ds[0] if ds else None
    mx = ds[-1] if ds else None
    span = _years(mn, mx)

    if force_status:
        status = force_status
    elif span is not None and span >= 10:
        status = 'PASS'
    elif not ds:
        status = 'BLOCKED'
    else:
        status = 'FAIL'

    if not reason:
        if status == 'PASS':
            reason = 'coverage>=10y'
        elif status == 'FAIL':
            reason = 'coverage<10y'
        else:
            reason = 'date_not_available'

    return Summary(
        source=source,
        path=str(path.relative_to(ROOT)),
        file_count=file_count,
        item_count=item_count,
        min_date=_fmt(mn),
        max_date=_fmt(mx),
        span_years=span,
        status=status,
        reason=reason,
        evidence=evidence or {},
    )


def audit_rss() -> Summary:
    rss_dir = RAW / 'qualitative/market/rss'
    files = sorted(rss_dir.glob('rss_*.json'))
    dates: list[datetime] = []
    items = 0
    latest_meta = {}

    for fp in files:
        try:
            obj = json.loads(fp.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if '_meta' in obj and isinstance(obj['_meta'], dict):
            latest_meta = obj['_meta']
        for name, arr in obj.items():
            if name == '_meta' or not isinstance(arr, list):
                continue
            for it in arr:
                if not isinstance(it, dict):
                    continue
                items += 1
                for key in ('published', 'published_date', 'published_raw'):
                    dt = _dt(it.get(key, ''))
                    if dt is not None:
                        dates.append(dt)
                        break

    summary = _finalize('qualitative/market/rss', rss_dir, dates, len(files), items)

    feeds_meta = latest_meta.get('feeds', []) if isinstance(latest_meta, dict) else []
    oldest_from_meta = []
    reached_target_any = False
    for m in feeds_meta:
        if not isinstance(m, dict):
            continue
        od = _dt(m.get('oldest_published', ''))
        if od is not None:
            oldest_from_meta.append(od)
            if od <= TARGET_START:
                reached_target_any = True

    if summary.status != 'PASS' and oldest_from_meta and not reached_target_any:
        oldest_feed = min(oldest_from_meta)
        summary.status = 'BLOCKED'
        summary.reason = 'rss_provider_retention_limit'
        summary.evidence = {
            'oldest_feed_date_seen': oldest_feed.date().isoformat(),
            'target_start': TARGET_START.date().isoformat(),
            'feeds_with_dates': len(oldest_from_meta),
            'feeds_meta_count': len(feeds_meta),
            'paged_backfill_enabled': latest_meta.get('feeds', [{}])[0].get('paged_backfill_enabled') if feeds_meta else None,
        }

    return summary


def audit_dart() -> Summary:
    p = RAW / 'qualitative/kr/dart'
    files = sorted(p.glob('dart_list_*.csv'))
    dates: list[datetime] = []
    rows = 0
    for fp in files:
        try:
            df = pd.read_csv(fp, usecols=['rcept_dt'])
        except Exception:
            continue
        s = pd.to_datetime(df['rcept_dt'].astype(str), format='%Y%m%d', errors='coerce').dropna()
        rows += int(s.shape[0])
        dates.extend(t.to_pydatetime().replace(tzinfo=None) for t in s)
    return _finalize('qualitative/kr/dart', p, dates, len(files), rows)


def audit_telegram() -> Summary:
    p = RAW / 'qualitative/text/telegram'
    files = sorted(p.rglob('*.md'))
    dates: list[datetime] = []
    item_count = 0
    date_pat = re.compile(r'(?m)^Date:\s*([^\n]+)')
    post_date_pat = re.compile(r'(?m)^PostDate:\s*([^\n]+)')

    for fp in files:
        txt = fp.read_text(encoding='utf-8', errors='ignore')
        for m in post_date_pat.finditer(txt):
            if '미확인' in m.group(1):
                continue
            dt = _dt(m.group(1).strip())
            if dt is not None:
                dates.append(dt)
                item_count += 1
        for m in date_pat.finditer(txt):
            dt = _dt(m.group(1).strip())
            if dt is not None:
                dates.append(dt)
                item_count += 1

    return _finalize('qualitative/text/telegram', p, dates, len(files), item_count)


def audit_blog() -> Summary:
    p = RAW / 'qualitative/text/blog'
    files = sorted(p.rglob('*.md'))
    dates: list[datetime] = []
    item_count = 0
    pat = re.compile(r'(?m)^PublishedDate:\s*([^\n]+)')
    for fp in files:
        txt = fp.read_text(encoding='utf-8', errors='ignore')
        m = pat.search(txt)
        if not m:
            continue
        dt = _dt(m.group(1).strip())
        if dt is not None:
            dates.append(dt)
            item_count += 1
    return _finalize('qualitative/text/blog', p, dates, len(files), item_count)


def audit_premium() -> Summary:
    p = RAW / 'qualitative/text/premium'
    files = sorted(p.rglob('*.md'))
    crawl_dates: list[datetime] = []
    actual_publish_fields = 0
    crawl_pat = re.compile(r'(?m)^Date:\s*([^\n]+)')
    pub_pat = re.compile(r'(?m)^(PublishedDate|PostDate):\s*([^\n]+)')

    for fp in files:
        txt = fp.read_text(encoding='utf-8', errors='ignore')
        for m in crawl_pat.finditer(txt):
            dt = _dt(m.group(1).strip())
            if dt is not None:
                crawl_dates.append(dt)
        if pub_pat.search(txt):
            actual_publish_fields += 1

    if actual_publish_fields == 0:
        return _finalize(
            'qualitative/text/premium',
            p,
            crawl_dates,
            len(files),
            len(crawl_dates),
            force_status='BLOCKED',
            reason='premium_linkmeta_no_original_publish_timestamp',
            evidence={
                'actual_publish_fields': 0,
                'crawl_date_only_files': len(files),
                'target_start': TARGET_START.date().isoformat(),
            },
        )

    return _finalize('qualitative/text/premium', p, crawl_dates, len(files), len(crawl_dates))


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = REPORT_DIR / f'STAGE1_BACKFILL_10Y_COVERAGE_{ts}.json'

    summaries = [
        audit_rss(),
        audit_dart(),
        audit_telegram(),
        audit_blog(),
        audit_premium(),
    ]

    payload = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'target_start': TARGET_START.date().isoformat(),
        'target_end': datetime.now().date().isoformat(),
        'sources': {
            s.source: {
                'path': s.path,
                'file_count': s.file_count,
                'item_count': s.item_count,
                'min_date': s.min_date,
                'max_date': s.max_date,
                'span_years': s.span_years,
                'status': s.status,
                'reason': s.reason,
                'evidence': s.evidence,
            }
            for s in summaries
        },
        'status_counts': {
            'PASS': sum(1 for s in summaries if s.status == 'PASS'),
            'FAIL': sum(1 for s in summaries if s.status == 'FAIL'),
            'BLOCKED': sum(1 for s in summaries if s.status == 'BLOCKED'),
        },
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'coverage_json': str(out_path.relative_to(ROOT))}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
