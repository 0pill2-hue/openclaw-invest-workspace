# FULL AUDIT — Runtime/Backtest Safety (2026-02-18)

## Scope
- 날짜 인덱스 정합/중복 인덱스/KeyError 재발 포인트
- lookahead/survivorship/bias 재발 가능성
- 예외처리 누락/조용한 실패(silent fail)
- 경고를 오류로 오인/무시하는 구간

검토 대상 핵심 파일:
- `invest/backtest_compare.py`
- `invest/scripts/fetch_ohlcv.py`
- `invest/scripts/fetch_supply.py`
- `invest/scripts/fetch_us_ohlcv.py`
- `invest/scripts/feature_engineer.py`
- `invest/scripts/walk_forward_validator.py`
- `invest/scripts/onepass_refine_full.py`
- `invest/scripts/validate_refine_independent.py`
- `invest/scripts/daily_update.py`

---

## 재발 가능 버그 TOP10 (+ 재현 방법)

## 1) 전역 warning 무시로 핵심 이상 징후 은닉
- **위치**: `invest/backtest_compare.py:37`
- **리스크**: `warnings.filterwarnings('ignore')`로 Pandas 경고(중복 index 재색인, 타입 강제변환, 체인할당 등) 소거. 경고 기반 조기탐지 불가.
- **재현**:
  1. OHLCV CSV에 중복 날짜 1건 삽입
  2. 백테스트 실행
  3. 경고 없이 수치만 출력되어 원인 추적 어려움

## 2) 광범위 `except Exception: continue/pass`로 종목 단위 silent drop
- **위치**: `invest/backtest_compare.py:98-107, 226-245, 362-365`
- **리스크**: 컬럼 누락/파싱 실패 시 종목이 조용히 제외되어 유니버스 왜곡. 실패율 관측 불가.
- **재현**:
  1. 특정 종목 파일에서 `Close` 컬럼 제거
  2. 실행 후 해당 종목이 로그 없이 누락(결과만 변동)

## 3) 증분 append 후 중복 날짜 누적(중복 인덱스 재발 포인트)
- **위치**: `invest/scripts/fetch_ohlcv.py:139-143`, `invest/scripts/fetch_supply.py:113-117`
- **리스크**: 기존 파일에 append만 수행, 중복 제거 없음. 이후 `set_index('Date')` 시 중복 인덱스 상태로 전략 계산 왜곡/KeyError 유사 이슈 유발.
- **재현**:
  1. 같은 날짜 행을 포함하는 증분 fetch 2회 수행
  2. `pd.read_csv(...).Date.duplicated().sum()` 증가 확인

## 4) supply 컬럼 positional 강제 매핑으로 schema drift silent corruption
- **위치**: `invest/scripts/fetch_supply.py:45-47`, `invest/scripts/onepass_refine_full.py:116-118`
- **리스크**: 컬럼명이 바뀌어도 `iloc[:, :6]`로 강제 이름 부여. 값 의미가 뒤바뀌어도 실패 없이 통과.
- **재현**:
  1. supply CSV의 컬럼 순서를 바꾼 파일 투입
  2. 정제 후 컬럼은 정상처럼 보이나 값 의미가 뒤섞임

## 5) 월말 리밸런싱 날짜 불일치 시 월 단위 skip (silent)
- **위치**: `invest/backtest_compare.py:262, 275-276`
- **리스크**: `resample('M').last().index`는 달력 월말 타임스탬프, 실제 거래일 index와 불일치 가능. `continue`로 월 전체 스킵.
- **재현**:
  1. 특정 월 말일 비거래일 데이터셋 사용
  2. 해당 월이 조용히 스킵되어 거래 횟수/수익률 왜곡

## 6) Survivorship bias 완화 주석 대비 실제로는 교집합 고정 유니버스
- **위치**: `invest/backtest_compare.py:73-85`
- **리스크**: OHLCV+Supply **현재 존재 파일 교집합**만 후보. 과거 상장폐지/데이터 단절 종목 배제되어 생존편향 잔존.
- **재현**:
  1. 과거 존재 후 사라진 종목 파일 제거 상태로 실행
  2. 과거 시점 유니버스가 현존 종목 중심으로 과대평가

## 7) feature join 후 전체 `fillna(0)`로 가격결측까지 0 주입 가능
- **위치**: `invest/scripts/feature_engineer.py:53`
- **리스크**: supply 결측 보정 의도이나, 조인 결과 전체 열에 적용되어 OHLC/지표 결측까지 0으로 덮일 수 있음(가짜 수익률 유발).
- **재현**:
  1. OHLCV 일부 결측 포함 파일 사용
  2. `generate_features` 결과에서 가격 관련 NaN이 0으로 치환되는지 확인

## 8) walk-forward 입력 정렬/중복 인덱스 가드 부재
- **위치**: `invest/scripts/walk_forward_validator.py:79-90`
- **리스크**: `to_datetime`만 수행, `sort_index`/중복제거 없음. 비정렬/중복 날짜면 train/val 분할 일관성 붕괴.
- **재현**:
  1. 날짜 역순+중복 데이터 입력
  2. 윈도우별 샘플수/성능이 실행마다 비일관 가능

## 9) 검증기에서 fail trace를 WARN으로만 처리
- **위치**: `invest/scripts/validate_refine_independent.py:622-624, 662-666`
- **리스크**: traceback 흔적이 있어도 FAIL 승격 안 됨. 운영 실패 신호가 품질 경고로 희석.
- **재현**:
  1. clean/production 하위에 `.fail` 파일 생성
  2. 검증 결과가 WARN(또는 PASS+warning)로 남는 케이스 확인

## 10) daily_update가 실패해도 프로세스 exit code 0 가능
- **위치**: `invest/scripts/daily_update.py:52-73`
- **리스크**: 실패는 JSON 상태파일에만 기록, 최종 `raise/SystemExit(1)` 없음. 상위 스케줄러가 성공으로 오인.
- **재현**:
  1. 하위 스크립트 1개 강제 실패
  2. `daily_update.py` 종료코드 확인(성공 처리 가능)

---

## 최소 침습 패치 우선순위

### P0 (즉시)
1. **warning 무시 제거/축소**
   - `backtest_compare.py`의 전역 ignore 제거.
   - 최소: `FutureWarning` 등 특정 카테고리만 제한적으로 필터.
2. **silent except에 카운터+로그 추가**
   - `continue/pass` 전 `error_count_by_reason` 집계 및 마지막 요약 출력.
3. **append 후 날짜 dedup 보장**
   - fetch 저장 직전 `concat -> drop_duplicates(Date, keep='last') -> sort_values(Date)` 공통화.
4. **daily_update 실패 시 non-zero 종료**
   - `if failures: raise SystemExit(1)` 추가.

### P1 (단기)
5. **리밸런싱 날짜를 실제 거래일로 매핑**
   - 월말 기준 계산 후 각 월별 `close_df.index.max()` 실제 거래일 사용.
6. **feature fillna 범위 제한**
   - `df[['Inst','Foreign']] = df[['Inst','Foreign']].fillna(0)`로 한정.
7. **walk-forward index 가드**
   - `data = data[~data.index.duplicated(keep='last')].sort_index()` 추가.

### P2 (중기)
8. **Survivorship 완화 강화**
   - 후보군을 “현재 교집합”이 아닌 시점별 가용 종목으로 구성(상장/상폐 메타 사용).
9. **supply positional 매핑 제거**
   - 명시 컬럼명 매칭 실패 시 FAIL 처리(강제 rename 금지).
10. **검증기 경고 승격 규칙 도입**
   - `.fail/traceback` 발견 시 최소 WARN->FAIL 조건(임계 1건 이상).

---

## 빠른 체크리스트 (패치 후 회귀 방지)
- [ ] 중복 Date가 fetch 산출물에 0건인지 검사
- [ ] backtest 실행 시 symbol drop 통계 출력 여부 확인
- [ ] 리밸런싱 월별 거래 횟수(누락월) 리포트 출력
- [ ] daily_update 실패 시 종료코드 1 확인
- [ ] validate_refine에서 `.fail` 투입 시 FAIL 승격 확인

---

## 결론
현재 코드는 “명시적 크래시”보다 “조용한 제외/무시” 유형의 런타임 리스크가 큽니다. 특히 백테스트 파이프라인은 실패가 수익률 왜곡으로 직결되므로, **P0 4건(경고/예외/중복/종료코드)**을 먼저 반영하면 재발성 높은 장애를 가장 낮은 침습도로 줄일 수 있습니다.
