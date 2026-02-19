# 독립 정제 검증 리포트

- **생성시각**: 2026-02-17 21:38:50
- **검증기**: `validate_refine_independent.py`
- **대상**: `clean/production` 하위 12개 폴더
- **종합**: ✅ PASS 5 | ⚠️ WARN 4 | ❌ FAIL 3

---

## [GR-1] 레코드 보존법칙

> `total_in == clean + quarantine + dropped_known`

| 폴더 | total_in | clean | quarantine | dropped | 충족 | 비고 |
| :--- | ---: | ---: | ---: | ---: | :---: | :--- |
| kr/ohlcv | 2883 | 2883 | 1239 | 0 | ✅ | raw_exists |
| kr/supply | 2882 | 2882 | 0 | 0 | ✅ | raw_exists |
| kr/dart | 110 | 84 | 0 | 0 | ❌ | raw_exists |
| us/ohlcv | 503 | 503 | 503 | 0 | ✅ | raw_exists |
| market/news/rss | 44 | 44 | 0 | 0 | ✅ | raw_exists |
| market/macro | 12 | 12 | 0 | 0 | ✅ | raw_exists |
| market/google_trends | 8 | 8 | 0 | 0 | ✅ | raw_exists |
| text/blog | 27362 | 27357 | 0 | 0 | ❌ | raw_exists |
| text/telegram | 59 | 54 | 0 | 0 | ❌ | raw_exists |
| text/image_map | 2 | 2 | 0 | 0 | ✅ | raw_exists |
| text/images_ocr | 20 | 20 | 0 | 0 | ✅ | raw_exists |
| text/premium/startale | 21 | 21 | 0 | 0 | ✅ | raw_exists |

## [GR-2] Blind-review 분리 출력

- **판정값 파일** (근거 없음): `verdict_20260217_213815.json`
- **근거 파일** (상세 이유): `evidence/evidence_<폴더>_20260217_213815.json`
- 심사자는 verdict 파일만 먼저 열람 → 개별 판단 후 evidence 파일 참조

## [GR-3] 고위험 상한 캡 (L3 > 20%)

| 폴더 | 전체 레코드 | L3 후보 | L3 비율 | 임계 | 경고 |
| :--- | ---: | ---: | ---: | ---: | :---: |
| kr/ohlcv | 33,469,139 | 0 | 0.0% | 20% | ✅ |
| kr/supply | 7,164,533 | 0 | 0.0% | 20% | ✅ |
| kr/dart | 930,496 | 0 | 0.0% | 20% | ✅ |
| us/ohlcv | 1,243,342 | 0 | 0.0% | 20% | ✅ |
| market/news/rss | 354 | 0 | 0.0% | 20% | ✅ |
| market/macro | 54,693 | 0 | 0.0% | 20% | ✅ |
| market/google_trends | 968 | 0 | 0.0% | 20% | ✅ |
| text/blog | 17,524,014 | 0 | 0.0% | 20% | ✅ |
| text/telegram | 5,099,585 | 0 | 0.0% | 20% | ✅ |
| text/image_map | 4,965 | 0 | 0.0% | 20% | ✅ |
| text/images_ocr | 95 | 0 | 0.0% | 20% | ✅ |
| text/premium/startale | 6,085 | 0 | 0.0% | 20% | ✅ |

## 종합 판정 결과

| 폴더 | 상태 | 파일 수 | 이슈 파일 | 총 레코드 | L3 비율 | GR-1 |
| :--- | :---: | ---: | ---: | ---: | ---: | :---: |
| kr/ohlcv | ⚠️ WARN | 2,883 | 2881 | 33,469,139 | 0.0% | ✅ |
| kr/supply | ⚠️ WARN | 2,882 | 346 | 7,164,533 | 0.0% | ✅ |
| kr/dart | ❌ FAIL | 84 | 0 | 930,496 | 0.0% | ❌ |
| us/ohlcv | ⚠️ WARN | 503 | 503 | 1,243,342 | 0.0% | ✅ |
| market/news/rss | ✅ PASS | 44 | 0 | 354 | 0.0% | ✅ |
| market/macro | ✅ PASS | 12 | 0 | 54,693 | 0.0% | ✅ |
| market/google_trends | ⚠️ WARN | 8 | 8 | 968 | 0.0% | ✅ |
| text/blog | ❌ FAIL | 27,357 | 0 | 17,524,014 | 0.0% | ❌ |
| text/telegram | ❌ FAIL | 54 | 0 | 5,099,585 | 0.0% | ❌ |
| text/image_map | ✅ PASS | 2 | 0 | 4,965 | 0.0% | ✅ |
| text/images_ocr | ✅ PASS | 20 | 0 | 95 | 0.0% | ✅ |
| text/premium/startale | ✅ PASS | 21 | 0 | 6,085 | 0.0% | ✅ |

## 폴더별 이슈 상세

### ⚠️ kr/ohlcv


**이슈 파일 2881개** (최대 10개 표시):

  - `000020.csv`: date:duplicate_count=12415, ohlc:Low<Close_count=13902
  - `000040.csv`: date:duplicate_count=12211, range:return_outlier_count=5, ohlc:High<Close_count=177, ohlc:Low<Close_count=14094
  - `000050.csv`: date:duplicate_count=12346, ohlc:High<Close_count=13, ohlc:Low<Close_count=13501
  - `000070.csv`: date:duplicate_count=12326, ohlc:Low<Close_count=13544
  - `000080.csv`: date:duplicate_count=12415, ohlc:Low<Close_count=13986
  - `000087.csv`: date:duplicate_count=12415, ohlc:Low<Close_count=13590
  - `000100.csv`: date:duplicate_count=12396, ohlc:High<Close_count=591, ohlc:Low<Close_count=14627
  - `000105.csv`: date:duplicate_count=12236, ohlc:High<Close_count=1985, ohlc:Low<Close_count=14215
  - `000120.csv`: date:duplicate_count=12415, ohlc:Low<Close_count=14010
  - `000140.csv`: date:duplicate_count=12415, ohlc:Low<Close_count=14064
  - *... 외 2871개 → evidence 파일 참조*

### ⚠️ kr/supply


**이슈 파일 346개** (최대 10개 표시):

  - `000080_supply.csv`: date:duplicate_count=4902
  - `000100_supply.csv`: date:duplicate_count=4896
  - `000120_supply.csv`: date:duplicate_count=4902
  - `000150_supply.csv`: date:duplicate_count=7314
  - `000155_supply.csv`: date:duplicate_count=4876
  - `000240_supply.csv`: date:duplicate_count=4902
  - `000250_supply.csv`: date:duplicate_count=4902
  - `000270_supply.csv`: date:duplicate_count=7353
  - `000500_supply.csv`: date:duplicate_count=4902
  - `000660_supply.csv`: date:duplicate_count=7353
  - *... 외 336개 → evidence 파일 참조*

### ❌ kr/dart

- ❌ `ERR:GR1_preservation_violated (raw=110, preserved=84)`

### ⚠️ us/ohlcv


**이슈 파일 503개** (최대 10개 표시):

  - `A.csv`: ohlc:Low<Close_count=2535
  - `AAPL.csv`: ohlc:Low<Close_count=2538
  - `ABBV.csv`: ohlc:Low<Close_count=2537
  - `ABNB.csv`: ohlc:Low<Close_count=1300
  - `ABT.csv`: ohlc:Low<Close_count=2526
  - `ACGL.csv`: ohlc:Low<Close_count=2534
  - `ACN.csv`: ohlc:Low<Close_count=2537
  - `ADBE.csv`: ohlc:Low<Close_count=2540
  - `ADI.csv`: ohlc:Low<Close_count=2537
  - `ADM.csv`: ohlc:Low<Close_count=2525
  - *... 외 493개 → evidence 파일 참조*

### ✅ market/news/rss

- 이상 없음 ✅

### ✅ market/macro

- 이상 없음 ✅

### ⚠️ market/google_trends


**이슈 파일 8개** (최대 10개 표시):

  - `SK하이닉스_trends_10y.csv`: schema:missing_value_column
  - `드론_trends_10y.csv`: schema:missing_value_column
  - `로봇_trends_10y.csv`: schema:missing_value_column
  - `삼성전자_trends_10y.csv`: schema:missing_value_column
  - `전기차_trends_10y.csv`: schema:missing_value_column
  - `제이에스링크_trends_10y.csv`: schema:missing_value_column
  - `태양광_trends_10y.csv`: schema:missing_value_column
  - `희토류_trends_10y.csv`: schema:missing_value_column

### ❌ text/blog

- ❌ `ERR:GR1_preservation_violated (raw=27362, preserved=27357)`

### ❌ text/telegram

- ❌ `ERR:GR1_preservation_violated (raw=59, preserved=54)`

### ✅ text/image_map

- 이상 없음 ✅

### ✅ text/images_ocr

- 이상 없음 ✅

### ✅ text/premium/startale

- 이상 없음 ✅

## .fail / traceback 흔적 탐지

이상 없음 ✅

---
*generated by validate_refine_independent.py @ 2026-02-17T21:38:50.897936*
