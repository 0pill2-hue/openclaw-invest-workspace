# QC All Folders Brainstorm Review (20260217_202725)

## 1. 잘못 격리 의심 패턴 (False Positives)
- **US OHLCV (Shifting Headers)**: `UAL.csv` 등 다수 파일에서 pandas multi-index 스타일의 복합 헤더가 생성되어 데이터가 오른쪽으로 밀려 들어감. 이로 인해 앞쪽 컬럼이 NaN으로 인식되어 `invalid_date_or_price`로 격리됨.
  - **해결책**: CSV 로드 시 컬럼 매핑 로직 보강 또는 데이터 수집 단계의 정규화 필요.
- **KR Supply (Header Mismatch)**: `001420_supply.csv` 등에서 한글 헤더 `날짜`를 `Date`로 인식하지 못해 `KeyError` 발생 및 `.fail` 처리됨.
  - **해결책**: `Date` 컬럼을 찾을 때 `['Date', '날짜', 'date']` 등 별칭 리스트 사용.

## 2. 과격 기준 여부 (Aggressive Criteria)
- **KR OHLCV (`extreme_return_spike`)**: 상한가나 변동성이 극심한 신규 상장 종목 등이 기계적으로 격리되고 있을 가능성.
  - **검토**: 현재 30% 이상 변동 시 격리하는 기준이 있다면, 시장 상황이나 종목 특성을 고려한 완화 필요.
- **Text Content Length**: 10자 미만의 짧은 텍스트(단순 링크, 사진 공지 등)를 일괄 격리하는 것은 유의미한 정보 손실일 수 있음.

## 3. 스크립트 오류 흔적 (Tracebacks/.fail)
- **KR Supply Folder**: `invest/data/quarantine/kr/supply/*.fail` 파일이 다수 발견됨.
- **Traceback 분석**: `invest/scripts/onepass_qc_all.py` 내 `sanitize_supply` 함수에서 `x['Date']` 접근 시 `KeyError` 발생.

## 4. clean 0건 유입 폴더
- 샘플링 데이터에서는 발견되지 않았으나, `kr/supply`의 상당수 종목이 헤더 문제로 인해 `clean`으로 넘어가지 못하고 있는 상태로 추정됨.

## 5. 즉시 수정 액션 제안
1.  **KR Supply 헤더 매핑 수정**: `onepass_qc_all.py`에서 `날짜` -> `Date` 매핑 추가.
2.  **US OHLCV 헤더 클렌징**: 데이터 로드 전 빈 컬럼 또는 인덱스 찌꺼기 제거 로직 삽입.
3.  **Quarantine 복구 실행**: 위 1, 2번 수정 후 `quarantine`에 있는 파일들을 대상으로 재처리(Reprocess) 수행.
