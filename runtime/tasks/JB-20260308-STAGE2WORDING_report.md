# JB-20260308-STAGE2WORDING report

## 범위/제약 준수
- Stage2 실행 없음
- Stage3 실행 없음
- 비파괴 정적 검증만 수행
- taskdb/directives 미변경

## 조사 결과
- canonical 문서: `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- 구현 핵심: `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`, `invest/stages/stage2/scripts/stage02_qc_cleaning_full.py`
- `invest/stages/stage2/outputs/`에는 현재 보고서 JSON/MD가 없고 로그만 존재함. 따라서 이번 정렬은 **다음 Stage2 실행 시 생성될 report md/json taxonomy** 기준으로 맞췄음.

## 실제 taxonomy 요약표

| Scope | 분류 | canonical reason / pattern |
| --- | --- | --- |
| QC signal | invalid | `basic_invalid_or_low_liquidity`, `zero_candle`, `return_spike_gt_35pct`, `invalid_date_or_nonnumeric` |
| QC signal | duplicate | `duplicate_date` |
| selected_articles JSONL | invalid | `selected_articles_missing_url`, `selected_articles_missing_title`, `selected_articles_missing_published_date`, `selected_articles_effective_body_too_short`, `jsonl_parse_error:<Exception>`, `jsonl_row_not_object`, `empty_jsonl` |
| text/* | invalid | `text_too_short`, `blog_missing_required_metadata`, `telegram_missing_required_metadata`, `premium_missing_required_metadata`, `blog_effective_body_empty`, `blog_effective_body_too_short`, `telegram_effective_body_empty`, `telegram_effective_body_too_short`, `premium_effective_body_empty_or_boilerplate`, `premium_effective_body_too_short` |
| text/* | fetch-fail | `blog_link_body_fetch_failed`, `telegram_link_body_fetch_failed`, `premium_link_body_fetch_failed` |
| premium/startale | terminal | `premium_bad_status_<STATUS>`, `premium_paywall_or_blocked_reason` |
| qualitative CSV/JSON | invalid | `missing_required_columns:<cols>`, `invalid_rcept_dt`, `invalid_<date_column>`, `missing_report_nm`, `missing_rcept_no`, `missing_corp_or_stock_code`, `missing_title_body_url`, `empty_after_strip`, `rss_no_entries`, `rss_missing_required_fields(title/datetime/url)`, `empty_json`, `invalid_json` |
| corpus qualitative dedup | duplicate | `duplicate_canonical_url`, `duplicate_title_date`, `duplicate_content_fingerprint`, `duplicate_rcept_no`, `duplicate_date_title`, `duplicate_<id_column>` |
| refine runtime | terminal | `exception:<ExceptionType>:<message>` |
| clean policy | max-available | minimum contract 충족 시 clean 유지, 별도 reason string 없음 |

## 식별된 불일치/모호점
1. report taxonomy snapshot에 `selected_articles_row_not_object`가 있었으나 canonical sanitize 경로 실제 emitted reason은 `jsonl_row_not_object`였음.
2. report taxonomy snapshot에 `unsupported_jsonl_folder`, `invalid_text`가 있었으나 canonical folder 계약/실행 경로 기준 미도달 fallback wording이었음.
3. 실제 emitted reason인 `invalid_<date_column>`, `text_too_short`가 taxonomy snapshot/docs에 누락되어 있었음.
4. JSON parse 실패 시 문서상 canonical name은 `invalid_json`인데, 구현은 raw exception string을 reason으로 노출할 수 있었음.
5. text sanitize 예외도 문서/스냅샷은 `exception:<ExceptionType>:<message>` 패턴이었지만 구현은 raw exception string이었음.
6. future report JSON에는 full reason taxonomy가 별도 필드로 노출되지 않아 md/json 간 대조가 약했음.

## 적용 변경
- `stage02_onepass_refine_full.py`
  - `_reason_taxonomy_snapshot()`를 정비해 terminal/max-available/duplicate/invalid/fetch_fail 상위 분류와 실제 quarantine reason group을 함께 노출하도록 수정.
  - `selected_articles_row_not_object`, `unsupported_jsonl_folder`, `invalid_text`를 canonical taxonomy snapshot에서 제거.
  - `invalid_<date_column>`, `text_too_short`를 taxonomy snapshot에 추가.
  - `sanitize_json()` parse failure reason을 `invalid_json`으로 표준화.
  - `sanitize_text()` exception reason을 `exception:<ExceptionType>:<message>` 패턴으로 표준화.
  - future refine report JSON payload에 `'reason_taxonomy'` 필드를 추가.
  - future refine report MD 섹션명을 `Reason / Filter / Quarantine Taxonomy`로 명시화.
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
  - canonical taxonomy 표 추가.
  - terminal / max-available / duplicate / invalid / fetch-fail 관계와 disposition을 명시.
- `docs/invest/stage2/README.md`
  - taxonomy canonical source pointer 추가.

## 비파괴 검증
실행 명령:
```bash
python3 -m py_compile invest/stages/stage2/scripts/stage02_onepass_refine_full.py invest/stages/stage2/scripts/stage02_qc_cleaning_full.py
python3 - <<'PY'
import importlib.util
import pathlib
import tempfile
repo = pathlib.Path('/Users/jobiseu/.openclaw/workspace')
mod_path = repo / 'invest/stages/stage2/scripts/stage02_onepass_refine_full.py'
spec = importlib.util.spec_from_file_location('stage2_refine', mod_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
tax = mod._reason_taxonomy_snapshot()
assert set(['terminal','max_available','duplicate','invalid','fetch_fail']).issubset(tax['reason_filter_taxonomy'].keys())
assert 'invalid_<date_column>' in tax['quarantine_reason_groups']['qualitative_csv_or_json_invalid']
assert 'text_too_short' in tax['quarantine_reason_groups']['text_body_quality']
assert 'selected_articles_row_not_object' not in tax['quarantine_reason_groups']['selected_articles_invalid_row']
assert 'unsupported_jsonl_folder' not in tax['quarantine_reason_groups']['unexpected_processing_exception']
assert 'invalid_text' not in tax['quarantine_reason_groups']['unexpected_processing_exception']
with tempfile.NamedTemporaryFile('w+', suffix='.json', encoding='utf-8', delete=False) as tf:
    tf.write('{not-json}')
    bad_json_path = tf.name
_, json_reason = mod.sanitize_json(bad_json_path, folder='market/rss')
assert json_reason == 'invalid_json'
_, text_reason, _ = mod.sanitize_text('/definitely/missing/file.txt', folder='text/blog')
assert text_reason.startswith('exception:FileNotFoundError:')
rulebook = (repo / 'docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md').read_text(encoding='utf-8')
readme = (repo / 'docs/invest/stage2/README.md').read_text(encoding='utf-8')
assert 'Reason / Filter / Quarantine Taxonomy (canonical)' in rulebook
assert 'reason/filter/quarantine taxonomy canonical source' in readme
print('VERIFY_OK')
PY
```

검증 결과 요약:
- `VERIFY_OK`
- `reason_filters= duplicate,fetch_fail,invalid,max_available,terminal`
- `invalid_json_reason= invalid_json`
- `text_exception_reason= exception:FileNotFoundError:[Errno 2] No such file or directory: '/definitely/missing/file.txt'`

## 라인 기준 proof
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py:1015` text exception reason pattern
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py:1083` invalid_json standardization
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py:1462` reason taxonomy snapshot
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py:2131` future report JSON reason_taxonomy payload
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md:57` canonical taxonomy section
- `docs/invest/stage2/README.md:5` taxonomy pointer
