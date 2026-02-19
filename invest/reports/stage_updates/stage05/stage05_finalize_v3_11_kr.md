# stage05_finalize_v3_11_kr

## inputs
- RULEBOOK: `invest/docs/strategy/RULEBOOK_V3.md` (V3.5)
- 데이터 범위: `invest/data/raw/kr/ohlcv/*.csv`, `invest/data/raw/kr/supply/*_supply.csv`
- 고정 정책: KRX only, `external_proxy` 비교군 전용, Stage05 단독 실행(Stage06 미실행)
- 실행 스크립트: `scripts/stage05_finalize_v3_11_kr.py`

## run_command(or process)
- `python3 scripts/stage05_finalize_v3_11_kr.py | tee reports/stage_updates/logs/stage05_finalize_v3_11_kr.log`

## outputs
- `invest/results/validated/stage05_baselines_v3_11_kr.json`
- `reports/stage_updates/stage05/stage05_finalize_v3_11_kr.md`
- `reports/stage_updates/stage05/stage05_crosscheck_v3_11_kr.md`

## quality_gates
- RULEBOOK V3.5 고정값(min_hold=20d, replace_edge=+15%, monthly_replace_cap=30%): **PASS**
- KRX only: **PASS**
- external_proxy 비교군 전용(선발 제외): **PASS**
- numeric freeze + numeric guard(`current >= locked*0.95`): **PASS**
- internal_3000_gate(내부 3종 중 1개 > 3000%): **PASS**
- numeric_only_auto_select_block: **PASS**
- Stage06 본 라운드 미진입(지시 고정): **PASS**

## failure_policy
- KRX guard 위반 시 즉시 `FAIL_STOP`
- numeric_guard FAIL 라운드 즉시 폐기
- changed_params 비어있으면 라운드 폐기
- internal_3000_gate FAIL 시 Stage06+ 진입 금지
- numeric_only_auto_select_block FAIL(auto adopt 발생) 시 결과 무효 처리

## proof
- `invest/results/validated/stage05_baselines_v3_11_kr.json`
- `scripts/stage05_finalize_v3_11_kr.py`
- `reports/stage_updates/logs/stage05_finalize_v3_11_kr.log`
- `reports/stage_updates/logs/stage05_verify_v3_11_kr.log`
- `invest/docs/strategy/RULEBOOK_V3.md`

---

## 1) 브레인스토밍 (실행 전)

### A안 (보수 안정)
- numeric 잠금 유지, qualitative/hybrid 미세 조정
- 장점: 기존 3000%+ numeric 성과 보전
- 단점: 분포 쏠림 완화 폭이 제한될 수 있음

### B안 (수익 우선)
- qualitative 반응도 상향으로 급등 포착 강화
- 장점: qual 단독 수익 상향 가능성
- 단점: hybrid 변동성/일관성 악화 가능

### C안 (균형형, 채택)
- numeric 잠금 + qual 노이즈 완화 + hybrid 안정 우선
- 채택 이유: numeric 훼손 없이 qual/hybrid 동시 개선 가능성이 가장 높음

## 2) 문서반영 (실행 전)
- Stage05 확정 라운드 전용 실행 스크립트 작성: `scripts/stage05_finalize_v3_11_kr.py`
- V3.11 산출물 경로/버전 고정:
  - `invest/results/validated/stage05_baselines_v3_11_kr.json`
- 하드게이트 반영 명시:
  - `policy_enforcement.numeric_only_auto_select_block`
  - `policy_enforcement.stage06_transition` (이번 라운드 Stage06 미실행 고정)

## 3) 실행 결과
- 실행 시각: 2026-02-19 08:56 KST
- adopted_round: `r02_qh_tune`
- backup_round: `r03_qh_tune`
- baseline_internal_best_id: `numeric`
- baseline_internal_best_return: `40.08658392425643` (4008.66%)
- qualitative_return: `6.033227472401938` (603.32%)
- hybrid_return: `4.701117098206695` (470.11%)

## 4) 검증
- internal_3000_gate_pass: `pass`
- numeric_only_auto_select_block: `pass`
  - numeric_top_detected: `true`
  - auto_adopt_executed: `false`
- external_proxy 선발 제외: `true`
- Stage06 transition 상태:
  - entry_gate_by_stage05: `eligible`
  - executed_in_this_round: `false`
  - directive_hold: `true`

## 필수 리포트 항목 요약
- baseline_internal_best_id: `numeric`
- baseline_internal_best_return: `40.08658392425643`
- numeric_only_auto_select_block (pass/fail): **pass**
- Stage06 진입 가능/불가 판정:
  - 게이트 기준: **가능(eligible)**
  - 본 라운드 실행 판정: **불가(미진입 고정, directive_hold=true)**
