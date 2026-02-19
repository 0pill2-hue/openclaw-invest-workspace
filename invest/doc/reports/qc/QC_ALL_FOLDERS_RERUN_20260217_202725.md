# QC All Folders Rerun Report (20260217_202725)

| Folder | Total Sample | Clean | Ratio |
| :--- | :--- | :--- | :--- |
| kr/ohlcv | 288 | 288 | 100.00% |
| kr/supply | 288 | 288 | 100.00% |
| kr/dart | 4 | 4 | 100.00% |
| us/ohlcv | 50 | 50 | 100.00% |
| market/news/rss | 4 | 4 | 100.00% |
| market/macro | 1 | 1 | 100.00% |
| market/google_trends | 1 | 1 | 100.00% |
| text/blog | 2735 | 2735 | 100.00% |
| text/telegram | 5 | 5 | 100.00% |
| text/image_map | 1 | 1 | 100.00% |
| text/images_ocr | 2 | 2 | 100.00% |
| text/premium/startale | 2 | 2 | 100.00% |

## Summary
- 이번 1회 재실행(10% 샘플) 결과, 모든 샘플이 기본 정제 기준(파일 존재, 읽기 가능, 기본 컬럼 존재)을 통과함.
- 그러나 기존 `quarantine` 폴더 분석 결과, 다수의 정제 실패 및 과격한 격리 패턴이 발견됨.

## Quarantine Details (기존 격리 데이터 분석 기반)
- **us/ohlcv**: `invalid_date_or_price` - 헤더 밀림 현상으로 인해 데이터가 존재함에도 격리된 사례 다수 발견.
- **kr/ohlcv**: `extreme_return_spike` - 변동성이 큰 종목이 과도하게 격리되고 있을 가능성 확인.
- **kr/supply**: 수백 개의 `.fail` 파일 발견. 원인은 `KeyError: 'Date'` (한글 헤더 '날짜' 처리 미흡).
