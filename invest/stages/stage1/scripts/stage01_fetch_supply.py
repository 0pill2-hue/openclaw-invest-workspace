import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

import pandas as pd
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from pipeline_logger import append_pipeline_event
except ImportError:
    def append_pipeline_event(*args, **kwargs):
        pass


RUNTIME_STATUS_PATH = 'invest/stages/stage1/outputs/runtime/kr_supply_status.json'
STOCK_LIST_PATH = 'invest/stages/stage1/outputs/master/kr_stock_list.csv'
RAW_OUTPUT_DIR = 'invest/stages/stage1/outputs/raw/signal/kr/supply'
NAVER_URL = 'https://finance.naver.com/item/frgn.naver'
NAVER_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://finance.naver.com/',
}
MAX_PAGES_DEFAULT = 320
REQUEST_SLEEP_SEC = 0.05


def _write_runtime_status(payload: dict):
    os.makedirs(os.path.dirname(RUNTIME_STATUS_PATH), exist_ok=True)
    with open(RUNTIME_STATUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _probe_krx_supply_access() -> dict:
    page_url = 'https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020302'
    endpoint = 'https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd'
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': page_url,
    }
    try:
        page = requests.get(page_url, headers=headers, timeout=20, allow_redirects=True)
        text = page.text[:1000]
        if '로그인 또는 회원가입이 필요합니다' in text:
            return {
                'ok': False,
                'external_blocked_login_required': True,
                'reason': 'krx_login_required',
                'page_status_code': page.status_code,
                'page_url': page.url,
            }
        resp = requests.post(
            endpoint,
            headers=headers,
            data={
                'bld': 'dbms/MDC/STAT/standard/MDCSTAT02302',
                'strtDd': (datetime.now() - timedelta(days=3)).strftime('%Y%m%d'),
                'endDd': datetime.now().strftime('%Y%m%d'),
                'isuCd': 'KR7005930003',
                'inqTpCd': '2',
                'trdVolVal': '2',
                'askBid': '3',
            },
            timeout=20,
        )
        body = (resp.text or '').strip()
        if resp.status_code >= 400 or body == 'LOGOUT':
            return {
                'ok': False,
                'external_blocked_login_required': True,
                'reason': 'krx_supply_endpoint_logout',
                'endpoint_status_code': resp.status_code,
                'endpoint_body': body[:200],
            }
        return {'ok': True, 'external_blocked_login_required': False, 'reason': 'accessible'}
    except Exception as exc:
        return {
            'ok': False,
            'external_blocked_login_required': False,
            'reason': f'probe_error:{type(exc).__name__}',
        }


def _to_int(text: str) -> int:
    raw = str(text or '').strip().replace(',', '').replace('%', '').replace(' ', '')
    raw = raw.replace('+', '')
    if raw in ('', '-', '--'):
        return 0
    return int(raw)


def _extract_last_page(soup: BeautifulSoup) -> int:
    link = soup.select_one('td.pgRR a[href]')
    if not link:
        return 1
    href = link.get('href', '')
    query = parse_qs(urlparse(href).query)
    try:
        return max(1, int(query.get('page', ['1'])[0]))
    except Exception:
        return 1


def _extract_page_rows(soup: BeautifulSoup) -> list[dict]:
    rows = []
    for tr in soup.select('table tr'):
        cells = [td.get_text(' ', strip=True) for td in tr.select('td')]
        if len(cells) < 9:
            continue
        if not re.match(r'^\d{4}\.\d{2}\.\d{2}$', cells[0]):
            continue
        try:
            dt = pd.to_datetime(cells[0], format='%Y.%m.%d', errors='raise')
            inst = _to_int(cells[5])
            foreign = _to_int(cells[6])
        except Exception:
            continue
        corp = 0
        indiv = -(inst + foreign)
        total = 0
        rows.append(
            {
                'Date': dt,
                'Inst': inst,
                'Corp': corp,
                'Indiv': indiv,
                'Foreign': foreign,
                'Total': total,
            }
        )
    return rows


def _fetch_naver_supply(session: requests.Session, code: str, start_date: str, end_date: str, max_pages: int) -> pd.DataFrame:
    start_dt = pd.to_datetime(start_date, format='%Y%m%d', errors='coerce')
    end_dt = pd.to_datetime(end_date, format='%Y%m%d', errors='coerce')
    if pd.isna(start_dt) or pd.isna(end_dt):
        return pd.DataFrame(columns=['Inst', 'Corp', 'Indiv', 'Foreign', 'Total'])

    page = 1
    last_page = None
    rows: list[dict] = []

    while page <= max_pages:
        resp = session.get(NAVER_URL, params={'code': code, 'page': page}, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        if last_page is None:
            last_page = _extract_last_page(soup)
        page_rows = _extract_page_rows(soup)
        if not page_rows:
            break

        oldest_dt = min(row['Date'] for row in page_rows)
        for row in page_rows:
            dt = row['Date']
            if dt < start_dt or dt > end_dt:
                continue
            rows.append(row)

        if oldest_dt < start_dt or page >= last_page:
            break
        page += 1
        time.sleep(REQUEST_SLEEP_SEC)

    if not rows:
        return pd.DataFrame(columns=['Inst', 'Corp', 'Indiv', 'Foreign', 'Total'])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=['Date']).sort_values('Date')
    return df.set_index('Date')[['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']]


def fetch_supply_data():
    full_collection = os.environ.get('FULL_COLLECTION', '0').strip().lower() in ('1', 'true', 'yes')
    max_pages = int(os.environ.get('NAVER_SUPPLY_MAX_PAGES', str(MAX_PAGES_DEFAULT)))

    if not os.path.exists(STOCK_LIST_PATH):
        print('Stock list not found.')
        return

    df_stocks = pd.read_csv(STOCK_LIST_PATH)
    df_stocks['Code'] = df_stocks['Code'].astype(str).str.zfill(6)
    os.makedirs(RAW_OUTPUT_DIR, exist_ok=True)

    end_date = datetime.now().strftime('%Y%m%d')
    base_start_date = (datetime.now() - timedelta(days=365 * 10)).strftime('%Y%m%d')
    print(f'Starting Naver supply collection for {len(df_stocks)} stocks up to {end_date} (incremental enabled)...')

    krx_probe = _probe_krx_supply_access()
    session = requests.Session()
    session.headers.update(NAVER_HEADERS)

    success_count = 0
    fail_count = 0
    skipped_count = 0
    fail_samples = []

    for idx, row in df_stocks.iterrows():
        code = row['Code']
        name = row['Name']
        file_path = os.path.join(RAW_OUTPUT_DIR, f'{code}_supply.csv')

        start_date = base_start_date
        if (not full_collection) and os.path.exists(file_path):
            try:
                df_existing = pd.read_csv(file_path)
                if '날짜' in df_existing.columns:
                    last_date = pd.to_datetime(df_existing['날짜']).max()
                else:
                    last_date = pd.to_datetime(df_existing.iloc[:, 0]).max()
                next_date = (last_date + timedelta(days=1)).strftime('%Y%m%d')
                if next_date > end_date:
                    skipped_count += 1
                    continue
                start_date = next_date
            except Exception:
                start_date = base_start_date

        try:
            df_new = _fetch_naver_supply(session, code, start_date, end_date, max_pages=max_pages)
            if df_new is not None and not df_new.empty:
                if os.path.exists(file_path):
                    df_new.to_csv(file_path, mode='a', header=False)
                else:
                    df_new.to_csv(file_path)
                success_count += 1
                if success_count % 50 == 0:
                    print(f'Progress: {idx+1}/{len(df_stocks)} stocks collected.')
            else:
                fail_count += 1
                if len(fail_samples) < 20:
                    fail_samples.append({'code': code, 'name': name, 'reason': 'empty_from_naver'})
            time.sleep(REQUEST_SLEEP_SEC)
        except Exception as e:
            fail_count += 1
            if len(fail_samples) < 20:
                fail_samples.append({'code': code, 'name': name, 'reason': f'{type(e).__name__}:{e}'})
            print(f'Error fetching supply for {code} ({name}): {e}')
            time.sleep(0.2)

    status = 'OK' if fail_count == 0 else 'WARN'
    runtime_payload = {
        'timestamp': datetime.now().isoformat(),
        'status': status,
        'source': 'naver_finance_item_frgn',
        'external_blocked_login_required': False,
        'krx_external_blocked_login_required': bool(krx_probe.get('external_blocked_login_required')),
        'reason': 'collection_completed_via_naver',
        'krx_probe': krx_probe,
        'success_count': success_count,
        'fail_count': fail_count,
        'skipped_count': skipped_count,
        'expected_count': int(len(df_stocks)),
        'max_pages': max_pages,
        'fail_samples': fail_samples,
    }
    _write_runtime_status(runtime_payload)
    append_pipeline_event(
        source='fetch_supply',
        status=status,
        count=success_count,
        errors=[sample['reason'] for sample in fail_samples[:5]],
        note=f'Naver supply done. total={len(df_stocks)} ok={success_count} fail={fail_count} skipped={skipped_count}',
    )
    print(json.dumps(runtime_payload, ensure_ascii=False))


if __name__ == '__main__':
    fetch_supply_data()
