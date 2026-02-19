# FULL_AUDIT_RAW_PATHS_20260218

- Scope: `invest/**/*.py`, `invest/scripts/**/*.py`
- Generated: 2026-02-18T01:06:54.512868
- SOP 기준: `invest/docs/operations/OPERATIONS_SOP.md` 4-A (clean-only violation)

## 1) 요약
- Total raw direct refs: **55**
- Severity: HARD **7** / MED **10** / LOW **38**
- 판정 원칙:
  - HARD: feature/train/value/backtest/운영 의사결정 입력이 raw 직접 참조
  - MED: 리포팅/신호추출/절대경로 하드코딩 등 품질·재현성 리스크
  - LOW: 수집(raw 적재), refine(raw→clean), QC(raw 검사)처럼 raw 사용이 본래 목적에 부합

## 2) 전수 목록 (파일/라인/스니펫/판정)

|ID|Severity|SOP 위반|File:Line|Snippet|
|-:|:-:|:-:|---|---|
|1|HARD|Y|`invest/backtest_compare.py:9`|`데이터: invest/data/raw/kr/ohlcv/*.csv, invest/data/raw/kr/supply/*_supply.csv`|
|2|HARD|Y|`invest/backtest_compare.py:46`|`OHLCV_DIR  = os.path.join(BASE_DIR, 'data/raw/kr/ohlcv')`|
|3|HARD|Y|`invest/backtest_compare.py:47`|`SUPPLY_DIR = os.path.join(BASE_DIR, 'data/raw/kr/supply')`|
|4|LOW|N|`invest/scripts/dart_nlp_tagger.py:9`|`DART_DIR = "invest/data/raw/kr/dart"`|
|5|LOW|N|`invest/scripts/dart_nlp_tagger.py:10`|`OUT_DIR = "invest/data/raw/kr/dart/tagged"`|
|6|LOW|N|`invest/scripts/fetch_trends.py:10`|`output_dir = 'invest/data/raw/market/google_trends'`|
|7|LOW|N|`invest/scripts/fetch_ohlcv.py:87`|`raw_output_dir = 'invest/data/raw/kr/ohlcv'`|
|8|LOW|N|`invest/scripts/fetch_ohlcv.py:88`|`legacy_output_dir = 'invest/data/raw/kr/ohlcv'  # backward-compat mirror`|
|9|HARD|Y|`invest/scripts/generate_feature_comparison.py:8`|`OHLCV_PATH = os.path.join(BASE_DIR, 'data/raw/kr/ohlcv/005930.csv')`|
|10|HARD|Y|`invest/scripts/generate_feature_comparison.py:9`|`SUPPLY_PATH = os.path.join(BASE_DIR, 'data/raw/kr/supply/005930_supply.csv')`|
|11|HARD|Y|`invest/scripts/generate_feature_comparison.py:10`|`TREND_PATH = os.path.join(BASE_DIR, 'data/raw/market/google_trends/삼성전자_trends_10y.csv')`|
|12|LOW|N|`invest/scripts/query_helper.py:6`|`DATA_OHLCV = "invest/data/raw/kr/ohlcv"`|
|13|LOW|N|`invest/scripts/query_helper.py:7`|`DATA_SUPPLY = "invest/data/raw/kr/supply"`|
|14|MED|Y|`invest/scripts/scrape_telegram_highspeed.py:50`|`save_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/raw/text/telegram'`|
|15|MED|Y|`invest/scripts/scrape_premium_contents.py:8`|`save_dir = "/Users/jobiseu/.openclaw/workspace/invest/data/raw/text/premium/startale"`|
|16|HARD|Y|`invest/scripts/alert_trigger.py:8`|`VIX_PATH = "invest/data/raw/market/macro/VIXCLS.csv"`|
|17|LOW|N|`invest/scripts/fetch_supply.py:72`|`raw_output_dir = 'invest/data/raw/kr/supply'`|
|18|LOW|N|`invest/scripts/fetch_supply.py:73`|`legacy_output_dir = 'invest/data/raw/kr/supply'  # backward-compat mirror`|
|19|MED|Y|`invest/scripts/scrape_all_posts.py:10`|`base_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/raw/text/blog'`|
|20|MED|Y|`invest/scripts/scrape_all_posts_v2.py:32`|`base_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/raw/text/blog'`|
|21|LOW|N|`invest/scripts/post_collection_validate.py:8`|`US_DIR = "invest/data/raw/us/ohlcv"`|
|22|LOW|N|`invest/scripts/post_collection_validate.py:9`|`RSS_DIR = "invest/data/raw/market/news/rss"`|
|23|MED|Y|`invest/scripts/generate_market_charts.py:20`|`path = f"invest/data/raw/kr/ohlcv/{code}.csv"`|
|24|LOW|N|`invest/scripts/fetch_us_ohlcv.py:11`|`DATA_DIR = "invest/data/raw/us/ohlcv"`|
|25|LOW|N|`invest/scripts/fetch_us_ohlcv.py:16`|`CURSOR_PATH = os.environ.get('US_OHLCV_CURSOR_PATH', 'invest/data/raw/us/ohlcv/_cursor.txt')`|
|26|MED|Y|`invest/scripts/update_dashboard.py:8`|`blog_posts_dir = os.path.join(workspace_dir, 'data/raw/text/blog')`|
|27|MED|Y|`invest/scripts/update_dashboard.py:9`|`tg_logs_dir = os.path.join(workspace_dir, 'data/raw/text/telegram')`|
|28|MED|Y|`invest/scripts/extract_coupling_signals.py:6`|`posts_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/raw/text/blog'`|
|29|MED|Y|`invest/scripts/extract_coupling_signals.py:7`|`premium_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/raw/text/premium/startale'`|
|30|MED|Y|`invest/scripts/extract_coupling_signals.py:8`|`tg_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/raw/text/telegram'`|
|31|LOW|N|`invest/scripts/fetch_news_rss.py:10`|`DATA_DIR = "invest/data/raw/market/news/rss"`|
|32|LOW|N|`invest/scripts/image_harvester.py:13`|`"invest/data/raw/text/telegram",`|
|33|LOW|N|`invest/scripts/image_harvester.py:14`|`"invest/data/raw/text/blog",`|
|34|LOW|N|`invest/scripts/image_harvester.py:17`|`MAP_DIR = "invest/data/raw/text/image_map"`|
|35|LOW|N|`invest/scripts/image_harvester.py:18`|`OUT_DIR = "invest/data/raw/text/images_ocr"`|
|36|LOW|N|`invest/scripts/image_harvester.py:20`|`SEEN_PATH = "invest/data/raw/text/images_ocr/seen_urls.json"`|
|37|LOW|N|`invest/scripts/fetch_dart_disclosures.py:8`|`OUT_DIR = "invest/data/raw/kr/dart"`|
|38|LOW|N|`invest/scripts/fetch_macro_fred.py:7`|`DATA_DIR = "invest/data/raw/market/macro"`|
|39|LOW|N|`invest/scripts/qc_text_sample.py:71`|`'invest/data/raw/text/blog',`|
|40|LOW|N|`invest/scripts/qc_text_sample.py:72`|`'invest/data/raw/text/telegram'`|
|41|LOW|N|`invest/scripts/qc_text_sample.py:89`|`rel_dir = os.path.dirname(os.path.relpath(file_path, 'invest/data/raw/text'))`|
|42|LOW|N|`invest/scripts/qc_rerun_all.py:75`|`"kr/ohlcv": "invest/data/raw/kr/ohlcv/*.csv",`|
|43|LOW|N|`invest/scripts/qc_rerun_all.py:76`|`"kr/supply": "invest/data/raw/kr/supply/*.csv",`|
|44|LOW|N|`invest/scripts/qc_rerun_all.py:77`|`"kr/dart": "invest/data/raw/kr/dart/*.*",`|
|45|LOW|N|`invest/scripts/qc_rerun_all.py:78`|`"us/ohlcv": "invest/data/raw/us/ohlcv/*.csv",`|
|46|LOW|N|`invest/scripts/qc_rerun_all.py:79`|`"market/news/rss": "invest/data/raw/market/news/rss/*.*",`|
|47|LOW|N|`invest/scripts/qc_rerun_all.py:80`|`"market/macro": "invest/data/raw/market/macro/*.csv",`|
|48|LOW|N|`invest/scripts/qc_rerun_all.py:81`|`"market/google_trends": "invest/data/raw/market/google_trends/*.csv",`|
|49|LOW|N|`invest/scripts/qc_rerun_all.py:82`|`"text/blog": "invest/data/raw/text/blog/**/*.md",`|
|50|LOW|N|`invest/scripts/qc_rerun_all.py:83`|`"text/telegram": "invest/data/raw/text/telegram/*.md",`|
|51|LOW|N|`invest/scripts/qc_rerun_all.py:84`|`"text/image_map": "invest/data/raw/text/image_map/*.json",`|
|52|LOW|N|`invest/scripts/qc_rerun_all.py:85`|`"text/images_ocr": "invest/data/raw/text/images_ocr/*.json",`|
|53|LOW|N|`invest/scripts/qc_rerun_all.py:86`|`"text/premium/startale": "invest/data/raw/text/premium/startale/*.md"`|
|54|LOW|N|`invest/scripts/refine_quant_data.py:75`|`raw_base = Path("invest/data/raw")`|
|55|LOW|N|`invest/scripts/refine_text_data.py:28`|`raw_base = Path("invest/data/raw/text")`|

## 3) SOP 위반 핵심 포인트
- **HARD** `invest/backtest_compare.py:9` — Stage5 백테스트가 raw를 직접 입력으로 사용(4-A clean-only 위반)
- **HARD** `invest/backtest_compare.py:46` — Stage5 백테스트가 raw를 직접 입력으로 사용(4-A clean-only 위반)
- **HARD** `invest/backtest_compare.py:47` — Stage5 백테스트가 raw를 직접 입력으로 사용(4-A clean-only 위반)
- **HARD** `invest/scripts/generate_feature_comparison.py:8` — 피처 비교 산출이 raw를 직접 참조(분석/평가 단계 clean-only 위반)
- **HARD** `invest/scripts/generate_feature_comparison.py:9` — 피처 비교 산출이 raw를 직접 참조(분석/평가 단계 clean-only 위반)
- **HARD** `invest/scripts/generate_feature_comparison.py:10` — 피처 비교 산출이 raw를 직접 참조(분석/평가 단계 clean-only 위반)
- **MED** `invest/scripts/scrape_telegram_highspeed.py:50` — 절대경로 하드코딩(이식성/재현성 저하), 상대경로/Path 기준으로 교체 필요
- **MED** `invest/scripts/scrape_premium_contents.py:8` — 절대경로 하드코딩(이식성/재현성 저하), 상대경로/Path 기준으로 교체 필요
- **HARD** `invest/scripts/alert_trigger.py:8` — 운영 알림 트리거가 raw 매크로 CSV 직접 참조(운영 입력 clean 게이트 우회)
- **MED** `invest/scripts/scrape_all_posts.py:10` — 절대경로 하드코딩(이식성/재현성 저하), 상대경로/Path 기준으로 교체 필요
- **MED** `invest/scripts/scrape_all_posts_v2.py:32` — 절대경로 하드코딩(이식성/재현성 저하), 상대경로/Path 기준으로 교체 필요
- **MED** `invest/scripts/generate_market_charts.py:20` — 리포팅 차트가 raw를 직접 참조(권장 clean 전환)
- **MED** `invest/scripts/update_dashboard.py:8` — 대시보드 집계가 raw 텍스트 직접 참조(게이트 미적용)
- **MED** `invest/scripts/update_dashboard.py:9` — 대시보드 집계가 raw 텍스트 직접 참조(게이트 미적용)
- **MED** `invest/scripts/extract_coupling_signals.py:6` — 신호 추출이 raw 텍스트 직접 참조(후속 모델 입력 가능성)
- **MED** `invest/scripts/extract_coupling_signals.py:7` — 신호 추출이 raw 텍스트 직접 참조(후속 모델 입력 가능성)
- **MED** `invest/scripts/extract_coupling_signals.py:8` — 신호 추출이 raw 텍스트 직접 참조(후속 모델 입력 가능성)

## 4) 자동 수정 가능한 패치 제안 (미적용 diff)

### P1 backtest_compare: raw→clean 경로 전환 + BASE_DIR 상대화
```diff
--- a/invest/backtest_compare.py
+++ b/invest/backtest_compare.py
@@
-BASE_DIR   = '/Users/jobiseu/.openclaw/workspace/invest'
-OHLCV_DIR  = os.path.join(BASE_DIR, 'data/raw/kr/ohlcv')
-SUPPLY_DIR = os.path.join(BASE_DIR, 'data/raw/kr/supply')
+BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
+OHLCV_DIR  = os.path.join(BASE_DIR, 'data/clean/kr/ohlcv')
+SUPPLY_DIR = os.path.join(BASE_DIR, 'data/clean/kr/supply')
```

### P2 generate_feature_comparison: raw→clean 입력 전환
```diff
--- a/invest/scripts/generate_feature_comparison.py
+++ b/invest/scripts/generate_feature_comparison.py
@@
-BASE_DIR = '/Users/jobiseu/.openclaw/workspace/invest'
-OHLCV_PATH = os.path.join(BASE_DIR, 'data/raw/kr/ohlcv/005930.csv')
-SUPPLY_PATH = os.path.join(BASE_DIR, 'data/raw/kr/supply/005930_supply.csv')
-TREND_PATH = os.path.join(BASE_DIR, 'data/raw/market/google_trends/삼성전자_trends_10y.csv')
+BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
+OHLCV_PATH = os.path.join(BASE_DIR, 'data/clean/kr/ohlcv/005930.csv')
+SUPPLY_PATH = os.path.join(BASE_DIR, 'data/clean/kr/supply/005930_supply.csv')
+TREND_PATH = os.path.join(BASE_DIR, 'data/clean/market/google_trends/삼성전자_trends_10y.csv')
```

### P3 alert_trigger: VIX 원천 clean 경로 우선
```diff
--- a/invest/scripts/alert_trigger.py
+++ b/invest/scripts/alert_trigger.py
@@
-VIX_PATH = "invest/data/raw/market/macro/VIXCLS.csv"
+VIX_PATH = os.environ.get("VIX_PATH", "invest/data/clean/market/macro/VIXCLS.csv")
```

### P4 절대경로 하드코딩 제거 (scrape/update/extract 계열)
```diff
--- a/invest/scripts/update_dashboard.py
+++ b/invest/scripts/update_dashboard.py
@@
-workspace_dir = '/Users/jobiseu/.openclaw/workspace/invest'
+workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
--- a/invest/scripts/extract_coupling_signals.py
+++ b/invest/scripts/extract_coupling_signals.py
@@
-posts_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/raw/text/blog'
+BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
+posts_dir = os.path.join(BASE_DIR, 'data/raw/text/blog')
```

## 5) 메모
- 본 감사는 문자열/경로 상수 기반 정적 스캔입니다.
- `VALUE_SCORE_RAW`(컬럼명) 같이 경로와 무관한 `raw` 토큰은 제외 처리했습니다.
- 이번 산출물은 **제안만 포함**하며 코드 수정은 적용하지 않았습니다.