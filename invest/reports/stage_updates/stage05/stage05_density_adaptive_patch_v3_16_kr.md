# stage05_density_adaptive_patch_v3_16_kr

## inputs
- base script: `invest/scripts/stage05_rerun_v3_15_kr.py`
- base config: `invest/config/stage05_auto_capture_v3_15_kr.yaml`
- target policy: `reports/stage_updates/stage05/stage05_density_adaptive_brainstorm_v3_16_kr.md`
- 사용자 강화 지시: high-density gate `+0.25 / MDD / turnover<=1.05x`

## run_command(or process)
- `cp invest/scripts/stage05_rerun_v3_15_kr.py invest/scripts/stage05_rerun_v3_16_kr.py`
- `cp invest/config/stage05_auto_capture_v3_15_kr.yaml invest/config/stage05_auto_capture_v3_16_kr.yaml`
- `python3 -m py_compile invest/scripts/stage05_rerun_v3_16_kr.py`

## outputs
- `invest/scripts/stage05_rerun_v3_16_kr.py`
- `invest/config/stage05_auto_capture_v3_16_kr.yaml`
- `reports/stage_updates/stage05/stage05_density_adaptive_patch_v3_16_kr.md`

## quality_gates
- RULEBOOK 하드룰(보유1~6/최소20/+15/월30) 유지: PASS
- KRX only / external_proxy 비교군 전용 유지: PASS
- density-adaptive band 로직(low/mid/high) 코드 반영: PASS
- high-density advantage gate(+0.25 + MDD + turnover) 코드 반영: PASS
- 문법 검증(`py_compile`) 통과: PASS

## failure_policy
- high-density gate 필드 누락 시 `FAIL_STOP`
- density band 계산/적용 누락 시 `FAIL_STOP`
- `non_numeric_top_valid` 산정에서 고밀도 게이트 미연동 시 `FAIL_STOP`

## proof
- code: `invest/scripts/stage05_rerun_v3_16_kr.py` (핵심 라인: 467, 478, 504~584, 615~714, 970~1021, 1270~1369, 1540~1580, 1642~1678)
- config: `invest/config/stage05_auto_capture_v3_16_kr.yaml`
- compile: `python3 -m py_compile invest/scripts/stage05_rerun_v3_16_kr.py`

---

## 변경 diff 요약

### 1) 새 density-adaptive 정책 섹션 추가 (config)
- `density_adaptive.bands.low/mid/high` 신규
  - `qual_lag_extra_days`
  - `qual_buzz/ret/up/anchor mult`
  - `qual_scale`, `noise_mult`
  - `hybrid_quant/qual/agree/pos_boost mult`
  - `mix_ratio_min/max/recommended_min`
- `high_density_advantage_gate` 신규
  - `old_threshold_return_margin: 0.10`
  - `return_margin: 0.25` (최신 하드 기준)
  - `turnover_multiplier_limit: 1.05`
  - `mdd_compare_mode: abs_drawdown_lte_numeric`

### 2) score 계산의 density-adaptive 반영 (script)
- `get_density_band`, `density_band_distribution_by_year` 추가
- `compute_factor_values()`에 band 정책 주입:
  - low/mid/high 별 lag/qual/noise multiplier 적용
- `run_model()`에서 hybrid 결합 가중을 band multiplier로 동적 변환

### 3) 게이트 체계 확장
- Gate1: 기존 regime 중심에서 `density_dominant_band` 기반 mix_ratio 동적밴드 판정으로 확장
- 신규 high-density advantage gate 추가:
  - OOS(워크포워드 테스트 구간) AND high-density 구간 필터
  - `(qual or hybrid)`가 `numeric + 0.25`, `abs(mdd)<=abs(numeric)`, `turnover<=numeric*1.05`를 모두 만족해야 PASS
  - `old(+0.10)` 대비 `new(+0.25)` 동시 기록

### 4) 결과 스키마 확장
- `RoundEval` 필드 추가:
  - `density_dominant_band`, `density_band_distribution`
  - `high_density_advantage_pass`, `high_density_advantage_detail`
- output JSON 확장:
  - `policy_enforcement.density_adaptive_policy`
  - `policy_enforcement.high_density_advantage_gate`
  - `chosen_round_gate.high_density_advantage_pass/detail`
  - `anti_overfit_audit.high_density_advantage_gate`

### 5) 문서 동기화
- `invest/docs/strategy/RULEBOOK_V3.md`에 Rule 6-5 추가
  - density-adaptive 평가 정책
  - high-density advantage gate의 old/new threshold 명시

### 참고 수치(변경량)
- script(v3_15 -> v3_16): `+254 / -103` lines
- config(v3_15 -> v3_16): `+165 / -30` lines
