# RULEBOOK V3.5 (Code-Synced, Trust-Rebuild)

Version: 2026-02-19 (V3.5)
Source of truth: `invest/scripts/stage05_backtest_engine.py`, `scripts/stage05_tuning_loop_v3_7_kr.py`

---

## 목적
Rulebook V3.5는 Stage05 엔진의 **하드 규칙 4개 + Hybrid Crisis Defense + 저회전 교체 가드 + 내부 3000% 하드게이트 + numeric freeze 운영가드**를 코드/운영 기준으로 재정의한 문서다.  
핵심 목표는 고수익 가능성을 열어두되, **생존성/품질/집중/추세/위기대응/저회전/내부게이트/모델일관성/최종선발거버넌스**를 충돌 없이 함께 적용하는 것이다.

> 본 문서는 코드 동기화 문서이며, 불일치 시 코드를 기준으로 즉시 수정한다.

---

## Rule 1) Survival (상장폐지 생존 규칙)
매수 금지 조건(하나라도 True면 금지):
- `admin_issue` (관리종목)
- `capital_erosion` (자본잠식)
- `audit_opinion` (감사의견 거절)

하위호환 키 매핑:
- `management_issue` -> `admin_issue`
- `capital_impairment` -> `capital_erosion`
- `audit_opinion_rejected_history` -> `audit_opinion`

예외 허용(코드 구현 그대로):
- `overheated` 또는 `investment_warning` 또는 `warning_overheated`가 True면,
  Survival 리스크가 있어도 매수 허용 가능.

---

## Rule 2) Quality-Keyword (품질 키워드 블랙리스트)
### 2-1. 키워드 블랙리스트
다음 키워드 포함 시 매수 금지:
- 정치, 대선, 총선, 남북, 북한, 작전, 테마주, 인맥, 이재명, 윤석열, 트럼프

### 2-2. 정확 일치 블랙리스트
- 아난티

---

## Rule 3) Focus 1-6 (집중도 동적 제한)
- 보유 종목 수 상한: `1~6`
- 매핑: `max_pos = round(1 + regime_score * 5)`를 `[1, 6]`로 클리핑
- `regime_score` 범위: `[0, 1]`

레짐별 추가 제한(코드 구현):
- `NORMAL`: 동적 상한 그대로 사용
- `CAUTION`: `max_pos = min(dynamic_max_pos, 3)`
- `CRISIS`: `max_pos = 0` (신규 진입 차단)

추가 배분 규칙:
- **동일가중(1/N) 금지**
- 점수 비례 가중 사용
- 점수 우위 1종목이면 100% 집중 허용

---

## Rule 4) Trend-Trailing (추세 추종 손절)
- 트레일링 스탑 기준: `-20%`
- 정의: `drawdown = (current_price / peak_price) - 1`
- `drawdown <= -0.20`이면 전량 매도

---

## Rule 5) Low-Turnover Replacement Guard (저회전 교체 가드)
- 최소 보유기간: **20 거래일**
- 교체 조건: 신규 후보 점수가 기존 보유 대비 **+15% 우위**일 때만 교체 허용
- 월간 교체 상한: 전체 보유 종목의 **30%** 이내

적용 원칙:
- 위 3개 조건은 Stage05 운영 가드로 우선 적용한다.
- 고점추격/과교체를 방지하기 위해 우위 임계 미달 시 보유 유지가 기본값이다.

## Rule 6) Stage05 Internal 3000% Hard Gate
- Stage05 종료 시 내부 베이스라인 3종(`numeric`, `qualitative`, `hybrid`) 중
  **최소 1개가 누적수익률 3000% 초과(total_return > 30.0)** 해야 PASS.
- 외부 비교모델(`external_proxy`)은 **비교군 전용**이며 선발/게이트 판정에 사용하지 않는다.
- 조건 미충족 시 즉시 `FAIL_STOP` 처리하고 상위 단계(Stage06+)를 중단한다.

## Rule 6-A) Stage05 Numeric Freeze Guard (v3_7_kr)
Stage05 재설계 라운드(v3_7_kr)에서는 numeric 기준선을 고정하고 qualitative/hybrid만 조정한다.

운영 규칙:
- `numeric_locked=true` 필수 (numeric 잠금 파라미터 변경 금지)
- 잠금 기준은 직전 검증 최고 numeric 설정(`v3_6_kr_r03`)을 사용
- `numeric_guard`: 현재 numeric 수익률이 잠금 기준 대비 **-5% 이내**여야 PASS
  - 수식: `current_numeric >= locked_numeric * 0.95`
- 라운드 보고서에는 다음 4개 필드를 필수 기록:
  - `numeric_locked=true`
  - `numeric_guard_pass/fail`
  - `qual changed_params`
  - `hybrid changed_params`

적용 목적:
- 단일 numeric 쏠림을 완화하면서도, 이미 확보한 numeric 초과성과(3000%+)를 훼손하지 않기 위함.

## Rule 6-1) Stage05-3x3 운영 프로토콜 (v3_9_kr)
Stage05 확장 실행 시 내부 모델을 단일 3개가 아니라 **3x3(총 9개)** 로 운용한다.

운영 규칙:
- 트랙 구성: `numeric 3 / qualitative 3 / hybrid 3`
- 필수 제약 고정: `보유 1~6`, `최소보유 20일`, `교체 +15%`, `월교체 30%`
- `external_proxy`는 **비교군 전용** (best 선발/게이트 제외)
- 트랙별 3개 모델의 `changed_params`는 서로 명확히 달라야 하며, 동일 축 ping-pong 반복 금지

설계 목적:
- 변수 영향이 큰 축(예: `ret_short/ret_mid`, `qual_buzz_w`, `flow_scale`, `trend spans`, `fee`)을
  한 번의 Stage05에서 동시에 관측/비교 가능하게 한다.

산출물(표준):
- `invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`
- `invest/reports/stage_updates/stage05/stage05_3x3_design_v3_9_kr.md`
- `invest/reports/stage_updates/stage05/stage05_3x3_result_v3_9_kr.md`

## Rule 6-2) Stage06 후보 확장 프로토콜 (v4_kr)
Stage06에서는 Stage05-3x3 결과의 track-best seed를 기준으로 후보를 확장한다.

운영 규칙:
- seed: `numeric_best / qualitative_best / hybrid_best`
- 확장안은 `chosen_plan` 문서화 필수(예: 9/12/18 비교 후 1개 채택)
- 각 후보는 `changed_params`를 명시해야 하며 빈 값 금지
- RULEBOOK 하드 제약(보유1~6, 최소보유20일, 교체+15%, 월교체30%, trailing -20%) 변경 금지
- `external_proxy`는 비교군 전용이며 Stage06 후보 선발 목록에 포함 금지
- 동일 축 ping-pong 반복 금지(후보별 변경 목적/리스크를 why/expected_risk로 명시)

산출물(표준):
- `invest/reports/stage_updates/stage06/stage06_brainstorm_plan_v4_kr.md`
- `invest/results/validated/stage06_candidates_v4_kr.json`
- `invest/reports/stage_updates/stage06/stage06_candidates_v4_kr.md`
- `invest/reports/stage_updates/stage06/stage06_crosscheck_v4_kr.md`

## Rule 6-3) Final Selection Anti-Numeric-Monopoly Gate (v3_13_kr, 확정 하드게이트)
`numeric`가 1위(best_id)인 결과는 **최종 채택(ADOPT) 절대 금지**한다.

확정 규칙:
- `baseline_internal_best_id == numeric` 이면 판정은 `HOLD` 또는 `REDESIGN`만 허용
- `baseline_internal_best_id in {qualitative, hybrid}` 인 경우에만 최종 채택 심사 가능
- `external_proxy`는 비교군 전용이며 선발/게이트 판정에서 제외

운영 강제:
- Stage07 컷오프와 Stage09 최종 교차검토에서 본 게이트를 필수 판정항목으로 포함한다.
- `numeric_top_detected=true` 상태에서 `ADOPT` 표기 시 즉시 `FAIL_STOP` 처리한다.

## Rule 6-4) Stage05 종료조건 프로토콜 (v3_13_kr, 사용자 확정 업데이트)
Stage05 반복 운영은 `repeat_counter` 기반으로 관리하며, **종료 조건은 하나만 사용**한다.

운영 규칙:
- `repeat_counter`는 **1부터 시작**하며 라운드마다 +1 (누락/역행 금지)
- KRX only / external_proxy 비교군 전용 / 기존 Rulebook 하드룰은 그대로 유지
- numeric 1위가 유지되면 다음 라운드를 자동 반복

종료 조건(유일):
- `baseline_internal_best_id != numeric`
- `stop_reason = NON_NUMERIC_TOP_CONFIRMED`

보고서 강제 필드 (`stage05_result*.md`):
- `repeat_counter`
- `stop_reason` (필수, 공백 금지)
- `baseline_internal_best_id`
- `numeric_top_detected`
- `changed_params`
- `why`
- `proof`

실패 정책:
- `stop_reason` 누락 시 결과 등급을 `DRAFT`로 강등
- `repeat_counter` 불일치(증가 누락/역행) 시 `FAIL_STOP`

## Rule 6-5) Density-Adaptive 평가 + High-Density Advantage Gate (v3_16_kr)
정성/복합 평가는 데이터 밀도(`combined_density`)에 따라 **밴드별로 다른 평가 정책**을 사용한다.

Density band 정의(연도 단위):
- `low`: `combined_density < 0.35`
- `mid`: `0.35 <= combined_density < 0.65`
- `high`: `combined_density >= 0.65`

밴드별 운영 정책(핵심):
- `low`: 정성 과민반응 억제 (`qual_scale down`, `noise_penalty up`, `lag+`), hybrid는 quant 쪽 비중 강화
- `mid`: 중립 결합(기본 파라미터)
- `high`: 정성/합의 신호 강화 (`qual_scale up`, `noise_penalty down`), hybrid는 qual/agree 비중 강화

Gate 강화(사용자 확정 하드룰, OOS 기준):
- high-density OOS 구간에서 `qualitative` 또는 `hybrid`가 아래를 모두 만족해야 high-density gate PASS
  1) `return >= numeric + 0.25` (25%p 우위)
  2) `MDD <= numeric MDD` (drawdown 절대값 기준)
  3) `turnover_proxy <= numeric turnover_proxy * 1.05`
- 이전 임계(`+0.10`)는 비교용 기록만 유지하고, 판정은 `+0.25`를 단일 기준으로 사용
- 미충족 시 `final_decision`은 `HOLD` 또는 `REDESIGN`만 허용 (`ADOPT` 금지)

보고서/산출물 필수 필드:
- `high_density_advantage_pass: true|false`
- `old/new threshold` (`+0.10`, `+0.25`) 병기
- 근거 수치: `numeric/qualitative/hybrid`의 high-density OOS `return, mdd, turnover_proxy`
- `repeat_counter`, `stop_reason`, `final_decision`, `non_numeric_top_valid`

## Rule 7) Hybrid Crisis Defense (정량+정성 결합)
시장 레짐: `NORMAL / CAUTION / CRISIS`

정량(필수):
- 가격/변동성/이평/드로우다운 수치 (`3일 하락`, `vix_proxy`, `120MA`, `drawdown`)

정성(운영 게이트):
- 단계 승격 시 점검(데이터 지연, 체결 품질, 장애 복구 리허설, 승인자 체크리스트)은 Stage 11~12 게이트에서 강제
- 즉, **시그널 트리거는 정량**, **배포 승격/롤백은 정성+운영 근거**로 최종 확정

### 5-1. Soft Trigger (CAUTION)
아래 중 하나 충족 시:
- 최근 3영업일 하락률 `> 5%`
- `vix_proxy > vix_threshold(기본 28)`

동작(코드 기준):
- 레짐 `CAUTION`
- 신규 매수 차단 (`block_new_buys=True`)
- 기존 보유 각 포지션 `50%` 축소 시도 (`_sell_fraction(..., 0.5)`)
- 신규 매수 1회당 가중치 상한 `0.5` (`max_exposure_cap=0.5`)
- 과대 단일 포지션은 포지션 비중 `<=50%`가 되도록 추가 축소 시도 (`_reduce_exposure_to_cap`)

> 주의: 코드의 `cap=0.5`는 **총포트폴리오 순노출 50%를 직접 강제하는 로직이 아님**.  
> 포지션 단위 축소 + 신규진입 제한으로 보수화하는 구조다.

### 5-2. Hard Trigger (CRISIS)
아래 모두 충족 시:
- `kospi < kospi_120ma`
- `drawdown <= -15%`

동작:
- 레짐 `CRISIS`
- 전량 청산 (`_liquidate_all`)
- 신규 매수 전면 차단
- 신규 매수 가중치 상한 0%

`drawdown` 산출 기준:
- 입력값이 있으면 입력 `drawdown` 사용
- 없으면 엔진 내부 `kospi_peak` 대비 계산

### 5-3. Re-entry (CRISIS 해제)
- `kospi >= kospi_120ma` 상태가 3영업일 연속 확인되면 `NORMAL` 복귀
- 신규 매수 재개, 가중치 상한 100% 복구

---

## Rule 간 충돌 해소 원칙 (확정)
1. **Survival/Quality > Crisis > Focus > Trend 운용순서**
   - 진입 자격(Survival/Quality) 미통과 종목은 레짐/집중 규칙보다 우선 배제
2. **Crisis는 포트폴리오 레벨 안전장치**, Trend는 종목 레벨 손절
   - Hard Trigger 전량청산이 Trend보다 우선
3. **Focus(집중)와 Crisis(디레버리지) 충돌 시 Crisis 우선**
   - CAUTION/CRISIS에서 `max_pos`와 신규매수 차단이 추가로 강화됨
4. **과소 제약 방지**
   - CRISIS 해제는 3일 안정성 확인 후에만 허용
5. **과도 제약 방지**
   - CAUTION은 즉시 전량청산이 아니라 절반 축소 + 제한 운용

---

## 제거된 구규칙 (금지)
다음 숫자 기반 필터는 V3.5에서도 사용 금지:
- `min_market_cap`
- `min_profit`
- `min_revenue`

즉, **시가총액/이익/매출 하한 숫자 조건은 매수 필터로 쓰지 않는다.**

---

## Stage05 코드 일치 체크 포인트
- 클래스: `BacktestEngine`
- 핵심 함수:
  - `is_survival_risk()`
  - `is_blacklist()`
  - `set_dynamic_max_positions()`
  - `update_trailing_stop()`
  - `update_market_regime()`
- 보정 함수:
  - `is_overheated_allowed()`
  - `get_dynamic_weights()`
  - `_liquidate_all()`, `_reduce_exposure_to_cap()`

---

## 운영 원칙
- 문서보다 코드 우선(Code-first)
- 규칙 추가/삭제 시 본 문서와 Stage 로드맵 즉시 동기화
- V3.5 핵심: “생존 필터 + 품질 필터 + 동적 집중 + 추세 손절 + 하이브리드 위기방어 + 저회전 교체가드 + 내부3000%게이트 + numeric freeze 가드 + numeric 1위 최종채택 금지 + Stage05 종료조건(repeat_counter/stop_reason)”
