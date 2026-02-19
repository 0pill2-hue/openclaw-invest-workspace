# stage05_overfit_brainstorm_v3_15_kr

## inputs
- 기존 Stage05 엔진/라운드 구조: `scripts/stage05_rerun_v3_14_kr.py`, `scripts/stage05_density_repeat_v3_12_kr.py`
- 기존 Stage05 결과/정책: `invest/results/validated/stage05_baselines_v3_12_kr.json`, `reports/stage_updates/stage05/stage05_policy_decision_v3_13_kr.md`
- 운영 룰북: `docs/invest/strategy/RULEBOOK_V3.md`

## run_command(or process)
- 브레인스토밍/설계 문서화 작업 (코드 실행 없음)

## outputs
- `reports/stage_updates/stage05/stage05_overfit_brainstorm_v3_15_kr.md`

## quality_gates
- 고정 종목 없이 자동 포착 로직 3안 제시: PASS
- 과적합 리스크 체크리스트(4항목) 명시: PASS
- 채택안 1개 + reject 사유 + 실행 가드 확정: PASS
- 필수 가드(no whitelist/manual favorites/purged CV-OOS/subperiod stability) 포함: PASS
- Stage05 즉시 패치 가능한 파라미터 목록 제시: PASS

## failure_policy
- 종목명/섹터 하드코딩 허용 시 `FAIL_STOP`
- 데이터 시차 누수 의심 시 `FAIL_STOP` 후 lag/포인트인타임 재검증
- 단일 구간 최적화 정황(워크포워드 미통과) 시 `HOLD` 또는 `REDESIGN`
- OOS 재현성 미달 시 `ADOPT` 금지

## proof
- 본 문서의 `A) 브레인스토밍 3안`, `B) overfit_risks`, `C) chosen/rejected`, `D) anti_overfit_controls`, `E) Stage05 patch`

---

## A) 브레인스토밍 3안

### 안1) 모멘텀/브레이크아웃 중심 (가격·수급 주도)
**핵심 아이디어**
- 유니버스: 매 리밸런싱 시점 유동성 상위 N 자동 선택 (`load_universe` 방식 유지)
- 팩터: 중단기 수익률(20/60), 신고가 돌파(120), 거래대금 가속, 추세 정렬
- 점수: rank-sum 또는 z-score 합산으로 상위 K 선발

**장점**
- 구조 단순, 해석 가능성 높음
- 텍스트 의존도 낮아 누수 리스크 상대적으로 낮음

**단점/리스크**
- 횡보/급반전장에서 whipsaw 리스크
- 단일 팩터 편향 시 레짐 붕괴 가능

---

### 안2) 모멘텀 + 정성 트리거 결합 (촉매 감지 강화)
**핵심 아이디어**
- 안1의 가격·수급 신호를 기본축으로 유지
- 정성 트리거(텍스트 buzz/sentiment/supply narrative)로 진입 우선순위 조정
- 텍스트 신호는 반드시 `lag_days` 적용 + 저밀도 연도 영향 제한

**장점**
- 급등 촉매/테마 확산 초기 포착력 개선 가능
- pure momentum 대비 후보 다양성 증가

**단점/리스크**
- 텍스트 타임스탬프 정합성 불량 시 시차 누수 위험
- 특정 소스(블로그/텔레그램) 편향 가능

---

### 안3) 레짐 게이트 + 멀티팩터 앙상블 (권장)
**핵심 아이디어**
- 레짐 분기(`RISK_ON`, `TRANSITION`, `RISK_OFF`)를 먼저 판정
- 팩터 묶음: 모멘텀, 브레이크아웃, 수급, 변동성 안정성, 정성(지연 반영)
- 레짐별 가중치 템플릿 적용 + 최종은 단일 모델이 아니라 앙상블 랭크(예: median rank)

**장점**
- 단일 시장국면 과최적화 완화
- 특정 팩터 붕괴 시 전체 시스템 내구성 우위
- “특정 종목 맞춤” 대신 “구조적 특성 포착”에 가장 부합

**단점/리스크**
- 파라미터 수 증가로 탐색 폭 관리 실패 시 과적합 가능
- 검증 체계(purged CV + walk-forward) 없으면 복잡성만 증가

---

## B) 과적합 리스크 체크리스트 (overfit_risks)

1. **종목명/섹터 하드코딩 여부**
   - 리스크: 특정 티커/섹터를 고정하면 성과가 과거 우연에 종속
   - 체크: 코드 내 allowlist/favorites/manual pick 사용 금지
   - 현재 관찰: `stage05_rerun_v3_14_kr.py`는 유동성 기반 유니버스 자동 구성(긍정), 다만 라운드 파라미터가 수동 튜닝 중심

2. **데이터 시차 누수 여부**
   - 리스크: 미래 시점 텍스트/가격이 현재 의사결정에 유입
   - 체크: 텍스트 특징 lag 강제, rebalancing 시점 point-in-time 스냅샷 보장
   - 현재 관찰: `signal_lag_days` 축은 존재하나, 검증 게이트로 누수 테스트가 별도 강제되진 않음

3. **단일 구간 과최적화 여부**
   - 리스크: 2016~2026 전체 누적 한 구간 최적화로 구조 왜곡
   - 체크: 서브기간(예: 2016~2019, 2020~2022, 2023~2026) 안정성 통과 필요
   - 현재 관찰: round repeat는 있으나 subperiod stability 하드게이트는 미약

4. **OOS/워크포워드 재현성 여부**
   - 리스크: in-sample 성과만 높고 실전 재현 실패
   - 체크: purged CV + embargo + walk-forward OOS 통과를 ADOPT 전 필수화
   - 현재 관찰: Stage05에는 전용 강제 게이트 부재(주로 Stage06 이후 스캐폴드에 존재)

---

## C) 채택안 선정 + reject 사유

### chosen
**안3 (레짐 게이트 + 멀티팩터 앙상블)**

### chosen 이유
- “고정 종목 없이 자동 포착” 요구에 가장 직접적으로 부합:
  - 종목이 아니라 **특성(모멘텀·돌파·수급·안정성·정성촉매)** 을 스캔
- 단일 신호 의존도를 낮춰, 특정 시기/특정 종목 맞춤 리스크를 구조적으로 완화
- 기존 Stage05 코드 자산(레짐/게이트/hybrid 구조)을 확장하기 쉬움

### rejected
- **안1 reject**: 단순·견고하나 레짐 변화 대응이 약해 단일 팩터 과적합 가능성이 상대적으로 큼
- **안2 reject**: 촉매 포착력은 좋지만 텍스트 누수/소스편향 통제가 강제되지 않으면 맞춤형 위험이 빠르게 커짐

---

## D) anti_overfit_controls (실행 가드 확정)

아래는 Stage05 ADOPT 전 **필수 하드게이트**:

1. **no ticker whitelist**
   - 티커 allowlist/고정 종목 목록/수동 favorites 금지
   - 예외: 시장 범위 제약(KRX only) 같은 범주형 스코프 제약은 허용

2. **no manual favorites**
   - 라운드별 수동 종목 삽입/삭제 금지
   - 유니버스는 유동성·데이터완전성 기반 자동 산출만 허용

3. **purged CV + OOS 필수**
   - 최소 `folds=5`, `purge_days=20`, `embargo_days=20`
   - 워크포워드 OOS에서 성과/리스크 하한 통과 필수

4. **stability across subperiods**
   - 최소 3개 서브기간에서 모두 `MDD/turnover/수익` 안정성 조건 충족
   - 특정 1개 구간만 압도적이고 나머지 붕괴면 `REDESIGN`

5. **파라미터 탐색 과열 제한**
   - 탐색 회수 상한(예: max_trials) + 사전 정의 탐색공간 고정
   - 결과 보고 시 `search_space_hash`, `config_hash` 기록

6. **선발 논리 감사가능성**
   - 결과 JSON에 `universe_build_rule`, `selection_reason`, `gate_fail_codes` 필수 저장

---

## E) Stage05 바로 실행 가능한 패치 제안

### E-1) 변경 대상 파일
- 스크립트: `scripts/stage05_rerun_v3_14_kr.py` (v3_15로 분기 권장)
- 신규 설정: `invest/config/stage05_auto_capture_v3_15_kr.yaml` (신규)
- 결과 필드 확장: `invest/results/validated/stage05_baselines_v3_15_kr.json` (신규)

### E-2) scripts/config에서 바꿀 파라미터 목록

#### (1) Universe 자동화/비맞춤형 고정
- `universe_mode`: `liquidity_top_n`
- `universe_limit`: `180` (기존 유지 가능)
- `min_history_days`: `700`
- `no_ticker_whitelist`: `true`
- `no_manual_favorites`: `true`

#### (2) 레짐 게이트
- `regime_enabled`: `true`
- `risk_off_drawdown`: `-0.15`
- `risk_off_vol_z`: `1.5`
- `regime_min_persistence_days`: `20`

#### (3) 멀티팩터 앙상블
- `factor_set`: `[momentum, breakout, flow, volatility_stability, qualitative_lagged]`
- `ensemble_method`: `median_rank`
- `factor_weight_cap`: `0.40`
- `factor_weight_floor`: `0.10`
- `hybrid_mix_ratio_band`: `[0.35, 0.60]` (기존 게이트와 정합)

#### (4) 누수 방지/정성 신호 처리
- `signal_lag_days_min`: `2`
- `signal_lag_days_max`: `7`
- `timestamp_alignment`: `strict_point_in_time`
- `low_density_threshold`: `0.35~0.55` (레짐별)
- `low_density_scale`: `0.60~0.82` (레짐별)

#### (5) 과적합 방지 검증 게이트
- `purged_cv_folds`: `5`
- `purge_days`: `20`
- `embargo_days`: `20`
- `walkforward_windows`: 최소 3개
- `subperiod_pass_ratio_min`: `0.67`
- `stability_mdd_delta_max`: `0.10`
- `stability_turnover_ratio_max`: `1.30`

### E-3) 구현 포인트(코드 레벨)
1. `make_rounds()` 수동 spec 나열을 축소하고, config 기반 후보 생성기로 전환
2. `evaluate_gate3_stability()` 추가:
   - 서브기간별 total_return/mdd/turnover 계산 후 안정성 판정
3. `evaluate_gate4_purged_cv_oos()` 추가:
   - purged CV + walk-forward OOS 통과 여부를 `ADOPT` 필수조건으로 연결
4. 출력 JSON 확장:
   - `anti_overfit_audit` 블록(`no_whitelist_pass`, `no_manual_favorites_pass`, `purged_cv_pass`, `subperiod_stability_pass`, `config_hash`)

### E-4) “종목 맞춤형 아님” 증빙 방법

필수 4종 증빙:
1. **정적 코드 증빙**
   - 티커 allowlist/favorites 키워드 스캔 로그 저장(예: `reports/stage_updates/logs/stage05_no_whitelist_scan.log`)
2. **동적 유니버스 증빙**
   - 각 리밸런싱 날짜별 유니버스 산출 근거(유동성 순위/데이터완전성) 저장
   - 결과 JSON에 `universe_membership_by_date` 해시 기록
3. **재현성 증빙**
   - 동일 config 재실행 2회에서 후보/점수/선발 결과 동일성 확인(`config_hash` 일치)
4. **일반화 증빙(OOS)**
   - purged CV + walk-forward 표를 함께 제출하여 단일 구간 우연 성과가 아님을 입증

---

## chosen/rejected (요약 필드)
- chosen: `안3_레짐게이트_멀티팩터앙상블`
- rejected:
  - `안1_모멘텀브레이크아웃_단일팩터편향리스크`
  - `안2_모멘텀정성결합_누수소스편향리스크`

## overfit_risks (요약 필드)
- `ticker_or_sector_hardcoding_risk`
- `lookahead_leakage_risk`
- `single_period_overoptimization_risk`
- `oos_walkforward_nonreproducibility_risk`

## anti_overfit_controls (요약 필드)
- `no_ticker_whitelist`
- `no_manual_favorites`
- `purged_cv_oos_required`
- `stability_across_subperiods_required`
- `search_space_freeze_and_hash_logging`

## next_steps
1. `scripts/stage05_rerun_v3_15_kr.py` 분기 생성 후 config 로더 연결
2. `invest/config/stage05_auto_capture_v3_15_kr.yaml` 추가 및 기본값 세팅
3. Gate3(서브기간 안정성), Gate4(Purged CV/OOS) 구현
4. `stage05_baselines_v3_15_kr.json`에 `anti_overfit_audit` 블록 출력
5. 결과 보고서(`stage05_result_v3_15_kr.md`)에 비맞춤형 증빙 4종 첨부
