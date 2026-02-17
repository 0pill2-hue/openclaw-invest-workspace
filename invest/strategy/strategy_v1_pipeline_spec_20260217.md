# Strategy V1 Pipeline Spec (2026-02-17)

## 0) 목적
이 문서는 투자 전략 운영에 필요한 **데이터 수집/정제/검증/밸류산출 파라미터와 가중치**를 한 파일에 고정하기 위한 기준 문서입니다.

---

## 1) 단계 체계 (11단계)
1. 데이터 수집
2. 데이터 정제
3. 정제 검증
4. VALIDATED 밸류 산출
5. 베이스라인 3트랙(정량/텍스트/혼합) 고정
6. 후보군 1차 생성
7. 후보군 단계별 컷
8. Purged CV + OOS 검증
9. 비용/턴오버/리스크 평가
10. 교차리뷰 반영
11. 채택/보류/승격

---

## 2) 수집 데이터 범위 (Raw)
원본(raw)은 수정하지 않고 `invest/data/raw/**`에만 저장한다.

- `kr/ohlcv` : 국장 OHLCV
- `kr/supply` : 국장 수급
- `kr/dart` : 공시
- `us/ohlcv` : 미장 OHLCV
- `market/news/rss` : 외부 뉴스
- `market/macro` : 거시 지표
- `market/google_trends` : 트렌드 지표
- `text/blog` : 블로그 본문
- `text/telegram` : 텔레그램 로그
- `text/image_map` : 이미지 매핑
- `text/images_ocr` : OCR 텍스트
- `text/premium/startale` : 프리미엄 텍스트

### 수집 운영 메모
- US OHLCV는 청크+커서 방식(`fetch_us_ohlcv.py`)으로 타임아웃 내성 운영.
- 수집은 백그라운드 루프에서 지속 실행.

---

## 3) 정제(Refine) 기준
정제 산출물은 `clean/production`, 격리는 `quarantine/production` 사용.

### 공통 원칙
- 원본(raw) 불변
- 파일 전체 폐기보다 행 단위 격리 우선
- 이상치 즉시 삭제 금지(기본은 PENDING/검증 후 확정)

### OHLCV 정제 규칙
- Date 파싱 실패, Close 결측/비정상(<=0) 격리
- OHLC 논리 위반 격리
  - `High < Low`
  - `High < Close`
  - `Low > Close`
- `Volume > 0`인데 `Open/High/Low <= 0`인 행 격리
- Date 정렬 + Date 중복 제거(keep=last)
- 수익률 outlier는 정제단계 즉시 삭제하지 않음(검증단계 경고 처리)

### Supply 정제 규칙
- 컬럼 표준화(Date/Inst/Corp/Indiv/Foreign/Total)
- Date 파싱 실패 및 전 수치 결측 행 격리
- Date 정렬 + 중복 제거(keep=last)

### Text/JSON 정제 규칙
- 너무 짧은 텍스트는 quarantine 이유와 함께 보관
- JSON 파싱 실패 시 quarantine 이유 파일 생성

### 중복 정제 방지
- `invest/scripts/onepass_refine_full.py`에서
  - `_processed_index.json` 기반 증분 스킵
  - 동일 입력 시그니처(크기+mtime+path 해시)면 재정제 생략

---

## 4) 정제 검증(Independent Validate) 기준
검증기는 `invest/scripts/validate_refine_independent.py` 사용.

### Guardrails
- GR-1: 보존법칙(raw vs clean+quarantine)
- GR-2: 판정(verdict)과 근거(evidence) 분리
- GR-3: L3 상한 캡(>20% 경고)

### 현재 경고 해석 원칙
- `return_outlier`는 오류 확정이 아니라 검토 트리거
- 이벤트/웹 교차검증 후 정상 반영 vs 격리 확정

---

## 5) 4단계 밸류 산출 파라미터/가중치 (확정안)

### 팩터별 스무딩
- Momentum: EMA(20) (필요 시 adaptive)
- Flow(수급/텍스트 결합 전 정량 proxy): Median(5) + EMA(10)
- Liquidity: Winsor(2.5%, 97.5%)
- Risk: Winsor(1%, 99%) + EMA(10), 점수 부호 반전

### 통합 점수 식
- Z-score 정규화 후 가중합:
  - Momentum 0.35
  - Flow 0.25
  - Liquidity 0.20
  - RiskAdj 0.20
- 최종 점수 1회 스무딩(턴오버 억제)

### 게이트
- TimeSeries 분리 후 처리(누수 금지)
- 유동성/거래가능성 필터 선행
- 미확정 이상치는 PENDING(학습/평가 입력 금지)

---

## 6) 텍스트(블로그/텔레그램) 반영 위치
- 정량과 텍스트 결합은 5단계(11단계 기준)에서 수행
- 텍스트 신호는 초기에는 보조 가중치로 시작
- 히스토리 부족 구간은 자동 저가중치

---

## 7) 불균형(imbalance) 대응 원칙
- 보정 자체보다 보정 전 게이트 우선
- 필수 조건:
  1) Train/Test 분리 후 보정
  2) 유동성/거래가능성 필터 선행
  3) 소형주 과대노출 하드캡
  4) TimeSeries OOS + Calibration 통과 시만 채택

---

## 8) 채택 규칙
- DRAFT / VALIDATED / PRODUCTION 등급 분리 유지
- 4단계 산출물은 8~10단계 검증 통과 전까지 DRAFT
- 공식 채택은 11단계 승격 조건 충족 시에만

---

## 9) 변경관리
- 파라미터/가중치 변경 시 본 문서 먼저 업데이트
- 변경 시 반드시 다음을 기록:
  - 무엇을 바꿨는지
  - 왜 바꿨는지
  - 검증 근거(리포트 경로)
