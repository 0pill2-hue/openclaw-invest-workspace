# stage05_patch_diff_v3_18_kr

## inputs
- base runner: `scripts/stage05_rerun_v3_16_kr.py`
- base config: `invest/config/stage05_auto_capture_v3_16_kr.yaml`
- policy doc: `reports/stage_updates/stage05/stage05_effective_window_policy_v3_18_kr.md`

## run_command(or process)
- `cp scripts/stage05_rerun_v3_16_kr.py scripts/stage05_rerun_v3_18_kr.py`
- `python3 -m py_compile scripts/stage05_rerun_v3_18_kr.py`
- `python3 scripts/stage05_rerun_v3_18_kr.py | tee reports/stage_updates/logs/stage05_rerun_v3_18_kr.log`

## outputs
- `scripts/stage05_rerun_v3_18_kr.py`
- `invest/config/stage05_auto_capture_v3_18_kr.yaml`
- `reports/stage_updates/stage05/stage05_patch_diff_v3_18_kr.md`

## quality_gates
- Stage04 입력 변경 없음: PASS
- 평가 로직(게이트/스코어) 유효구간 적용: PASS
- KRX only / external_proxy 비교군 전용 유지: PASS
- high-density 강화 게이트(+0.25, MDD, turnover<=1.05x) 유지: PASS
- 문법 검증(`py_compile`) 통과: PASS

## failure_policy
- 유효구간 공식치 미적용 상태로 final_decision 계산 시 `FAIL_STOP`
- 유효구간 샘플 부족인데 PASS 처리 시 `FAIL_STOP`
- gate1~gate4/high_density_advantage_pass 누락 시 `FAIL_STOP`

## proof
- code: `scripts/stage05_rerun_v3_18_kr.py`
- config: `invest/config/stage05_auto_capture_v3_18_kr.yaml`
- run log: `reports/stage_updates/logs/stage05_rerun_v3_18_kr.log`
- result: `invest/results/validated/stage05_baselines_v3_18_kr.json`

---

## diff summary

### 1) 설정 추가 (v3_18)
- `effective_window_policy` 신규:
  - `density_min: 0.35`
  - `min_total_months: 36`
  - `min_years: 3`
  - `min_months_per_year: 6`
  - `min_subperiod_samples: 6`
  - `min_cv_samples: 18`
  - `apply_to: gate2/gate3/gate4/high_density_advantage_gate/final_decision`

### 2) 평가 컨텍스트 도입
- `EvalWindowContext` 추가
- `build_effective_window_context()` 추가
  - density + sample 기준으로 official 마스크 생성
  - full/reference 마스크와 분리

### 3) Gate2 수정
- 기존: full-period `run.stats` 중심 비교
- 변경: **official(유효구간)** 지표로 pass/fail 판단
- full-period 값은 `metrics_full`로 함께 기록(참고)

### 4) Gate3 / Gate4 수정
- subperiod stability, purged CV + walkforward 모두 official 마스크 기반 평가
- 유효 샘플 부족 시 명시적 fail reason 반환

### 5) high-density advantage gate 수정
- 기존 OOS & high-density 필터에
- **official 마스크를 추가 교차**하여 평가
- 강화 조건(+0.25, MDD 우위, turnover<=1.05x) 유지

### 6) 출력 스키마 확장
- `policy_enforcement.effective_window_policy`
- `chosen_round_gate.official_scope/effective_window_detail`
- `performance_reference.reference_full_period`
- `performance_reference.official_effective_window`
- `anti_overfit_audit.effective_window/gate2_eval_scope`
