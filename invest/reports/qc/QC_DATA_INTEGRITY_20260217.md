# Quality Control Report: Data Integrity
**Date:** 2026-02-17
**Status:** PASS (with remaining risks)

## 1. 정량 데이터 하드게이트 검증 (P0)

### 검증 대상
- KR OHLCV (2,883 symbols)
- US OHLCV (503 symbols)
- KR Supply (2,882 symbols)

### 검증 결과 요약
| 구분 | 검증 항목 | 결과 | 비고 |
|------|-----------|------|------|
| KR OHLCV | 중복/정렬/빈날짜 | **PASS** | 정제 후 해결 |
| US OHLCV | 스키마/빈날짜 | **PASS** | Multi-index 컬럼 정제 후 해결 |
| KR Supply | 중복/정렬/빈날짜 | **PASS** | 정제 후 해결 |
| KR OHLCV | 기본 범위 (Price > 0) | **WARN** | 7개 종목에서 거래량 존재하나 시/고/저가 0인 데이터 발견 |

### 상세 리스크 (Remaining Risks)
- **KR OHLCV 0가 이슈**: 아래 7개 종목에서 특정 일자에 거래량이 있음에도 불구하고 Open, High, Low가 0인 데이터가 존재함. (데이터 공급원 확인 필요)
  - 033790, 215100, 056730, 336570, 060570, 016380, 047810
- **US OHLCV Adj Close**: `Adj Close` 컬럼을 정제 과정에서 확보함.

## 2. 고밀도 텍스트 정제 (P1)

### 정제 대상
- `text/premium/startale`: 21 files
- `text/telegram`: 59 files

### 정제 내용
- 웹 크롤링 부산물(Boilerplate) 제거: "본문 바로가기", "페이지 스크롤 진행률", "SNS 보내기" 등
- 불필요한 메타데이터(Byline, Timestamp) 패턴 제거
- 다중 공백 및 개행 정규화

### 정제 결과
- `invest/data/clean/text/` 경로에 저장 완료.
- 원본 데이터 대비 가독성 및 정보 밀도 향상 확인.

## 3. 다음 액션 (Next Actions)
1. **Clean 데이터 교체**: 현재 `clean` 폴더에 생성된 데이터를 `master` 또는 공식 데이터 경로로 승격 검토.
2. **0가 데이터 보정**: 발견된 7개 종목의 0가 데이터를 종가(Close) 기준으로 보정하는 추가 스크립트 실행 권장.
3. **텍스트 검증**: 정제된 텍스트의 키워드 추출 및 요약 성능 테스트 진행.

---
**보고자:** 조비스 서브에이전트 (Execute Priority Integrity)
**증빙:** 
- `scripts/validate_quant_data.py`
- `scripts/refine_quant_data.py`
- `scripts/refine_text_data.py`
- `invest/data/clean/`
