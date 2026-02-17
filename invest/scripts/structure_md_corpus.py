import os
import re
import json
import glob
import hashlib
from datetime import datetime, timezone
from run_manifest import write_run_manifest

BASE = '/Users/jobiseu/.openclaw/workspace/invest/data'
BLOG_RAW = os.path.join(BASE, 'raw/text/blog')
TG_RAW = os.path.join(BASE, 'raw/text/telegram')

OUT_CLEAN_BLOG = os.path.join(BASE, 'clean/text/blog/blog_structured.jsonl')
OUT_CLEAN_TG = os.path.join(BASE, 'clean/text/telegram/telegram_structured.jsonl')
OUT_Q_BLOG = os.path.join(BASE, 'quarantine/text/blog/blog_quarantine.jsonl')
OUT_Q_TG = os.path.join(BASE, 'quarantine/text/telegram/telegram_quarantine.jsonl')
OUT_AUDIT_BLOG = os.path.join(BASE, 'audit/text/blog/blog_audit.jsonl')
OUT_AUDIT_TG = os.path.join(BASE, 'audit/text/telegram/telegram_audit.jsonl')

RULE_VERSION = 'md-structure-v1'
AD_PAT = re.compile(r'모집|광고|구독|이벤트|신청|체험단|쿠폰|지원금', re.I)

for p in [OUT_CLEAN_BLOG, OUT_CLEAN_TG, OUT_Q_BLOG, OUT_Q_TG, OUT_AUDIT_BLOG, OUT_AUDIT_TG]:
    os.makedirs(os.path.dirname(p), exist_ok=True)


def parse_md(path, source):
    try:
        txt = open(path, encoding='utf-8', errors='ignore').read()
    except Exception:
        return None

    title_m = re.search(r'^Title:\s*(.+)$', txt, flags=re.M)
    date_m = re.search(r'^Date:\s*(.+)$', txt, flags=re.M)
    src_m = re.search(r'^Source:\s*(.+)$', txt, flags=re.M)

    title = title_m.group(1).strip() if title_m else os.path.basename(path)
    pub = date_m.group(1).strip() if date_m else None
    src = src_m.group(1).strip() if src_m else None

    body = txt
    h = hashlib.sha256(txt.encode('utf-8', errors='ignore')).hexdigest()
    rec_id = f'{source}:{h[:16]}'

    is_ad = bool(AD_PAT.search((title or '') + '\n' + body[:1200]))
    reason = 'recruit_or_ad_keyword' if is_ad else None

    rec = {
        'record_id': rec_id,
        'source': source,
        'author': os.path.basename(os.path.dirname(path)) if source == 'blog' else os.path.basename(path).replace('.md',''),
        'published_at_raw': pub,
        'collected_at_utc': datetime.now(timezone.utc).isoformat(),
        'content_hash': h,
        'title': title,
        'source_url': src,
        'path': path,
        'status': 'quarantine' if is_ad else 'clean',
        'rule_version': RULE_VERSION,
        'reason': reason,
    }
    return rec


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def main():
    blog_rows, tg_rows = [], []

    for p in glob.glob(os.path.join(BLOG_RAW, '**/*.md'), recursive=True):
        r = parse_md(p, 'blog')
        if r:
            blog_rows.append(r)

    for p in glob.glob(os.path.join(TG_RAW, '**/*.md'), recursive=True):
        r = parse_md(p, 'telegram')
        if r:
            tg_rows.append(r)

    blog_clean = [r for r in blog_rows if r['status'] == 'clean']
    blog_q = [r for r in blog_rows if r['status'] == 'quarantine']
    tg_clean = [r for r in tg_rows if r['status'] == 'clean']
    tg_q = [r for r in tg_rows if r['status'] == 'quarantine']

    write_jsonl(OUT_CLEAN_BLOG, blog_clean)
    write_jsonl(OUT_Q_BLOG, blog_q)
    write_jsonl(OUT_AUDIT_BLOG, blog_rows)

    write_jsonl(OUT_CLEAN_TG, tg_clean)
    write_jsonl(OUT_Q_TG, tg_q)
    write_jsonl(OUT_AUDIT_TG, tg_rows)

    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    manifest_path = f"/Users/jobiseu/.openclaw/workspace/invest/reports/data_quality/structure_md_manifest_{ts}.json"
    write_run_manifest(
        run_type='structure_md_corpus',
        params={'rule_version': RULE_VERSION},
        inputs=[BLOG_RAW, TG_RAW],
        outputs=[OUT_CLEAN_BLOG, OUT_Q_BLOG, OUT_AUDIT_BLOG, OUT_CLEAN_TG, OUT_Q_TG, OUT_AUDIT_TG],
        out_path=manifest_path,
        workdir='/Users/jobiseu/.openclaw/workspace'
    )

    print('blog_total', len(blog_rows), 'blog_clean', len(blog_clean), 'blog_quarantine', len(blog_q))
    print('tg_total', len(tg_rows), 'tg_clean', len(tg_clean), 'tg_quarantine', len(tg_q))
    print('manifest', manifest_path)


if __name__ == '__main__':
    main()
