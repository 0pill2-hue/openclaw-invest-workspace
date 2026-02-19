# stage05_result_v3_16_kr

## inputs
- 실행 스크립트: `invest/scripts/stage05_rerun_v3_16_kr.py`
- 설정: `invest/config/stage05_auto_capture_v3_16_kr.yaml`
- 비교 기준:
  - `invest/results/validated/stage05_baselines_v3_12_kr.json`
  - `invest/results/validated/stage05_baselines_v3_14_kr.json`
- 데이터:
  - `invest/data/raw/kr/ohlcv/*.csv`
  - `invest/data/raw/kr/supply/*_supply.csv`
  - `invest/data/raw/text/blog/**/*.md`
  - `invest/data/raw/text/telegram/*.md`

## run_command(or process)
- `python3 invest/scripts/stage05_rerun_v3_16_kr.py | tee reports/stage_updates/logs/stage05_rerun_v3_16_kr.log`

## outputs
- `invest/results/validated/stage05_baselines_v3_16_kr.json`
- `reports/stage_updates/stage05/stage05_result_v3_16_kr.md`
- `reports/stage_updates/stage05/stage05_density_adaptive_patch_v3_16_kr.md`

## quality_gates
- RULEBOOK V3.x 하드룰(보유1~6, 최소보유20, 교체+15%, 월교체30): PASS
- KRX only: PASS
- external_proxy 비교군 전용: PASS
- density-adaptive band 정책(low/mid/high) 반영: PASS
- high-density advantage gate(+0.25/MDD/turnover) 반영: PASS
- non_numeric_top_valid 판정 기록: PASS (`false`)
- 과적합 가드:
  - Gate3(subperiod stability): **FAIL**
  - Gate4(purged CV + walkforward OOS): PASS
  - high-density advantage gate: PASS

## failure_policy
- `high_density_advantage_pass=false`면 최종 `ADOPT` 금지 (`HOLD/REDESIGN`만 허용)
- `gate3_subperiod_stability_pass=false`면 `non_numeric_top_valid=false` 처리
- `repeat_counter/stop_reason/final_decision` 누락 시 결과 무효

## proof
- JSON: `invest/results/validated/stage05_baselines_v3_16_kr.json`
- log: `reports/stage_updates/logs/stage05_rerun_v3_16_kr.log`
- code: `invest/scripts/stage05_rerun_v3_16_kr.py`

---

## 1) final_decision / stop_reason / repeat_counter
- repeat_counter_start: `13`
- repeat_counter_final: `18`
- stop_reason: `MAX_REPEAT_REACHED_REDESIGN`
- final_decision: `REDESIGN`
- non_numeric_top_valid: `false`

선정 라운드(`r06_auto_grid_3779135`) 핵심:
- gate1_pass: `false` (`hybrid_qual_mix_ratio=0.58 > max 0.56`)
- gate2_pass: `true`
- gate3_pass: `false`
- gate4_pass: `true`
- high_density_advantage_pass: `true`

---

## 2) density_band별 실제 적용 파라미터 (chosen round 기준)
chosen round base:
- `signal_lag_days=5`
- `hybrid_quant_w=0.75`, `hybrid_qual_w=0.34`, `hybrid_agree_w=0.24`, `hybrid_pos_boost=0.10`

### low band (`density < 0.35`)
- effective lag: `7` (=5+2)
- qualitative: `buzz 0.72x`, `ret 0.85x`, `up 0.85x`, `anchor 1.12x`, `qual_scale 0.72x`, `noise_mult 1.35x`
- hybrid effective ratio(정규화):
  - quant `0.6316`, qual `0.2096`, agree `0.1588`
  - pos_boost `0.0700`

### mid band (`0.35 <= density < 0.65`)
- effective lag: `6` (=5+1)
- qualitative/hybrid multiplier: 중립(1.0x)
- hybrid effective ratio:
  - quant `0.5639`, qual `0.2556`, agree `0.1805`
  - pos_boost `0.1000`

### high band (`density >= 0.65`)
- effective lag: `5` (=5+0)
- qualitative: `buzz 1.20x`, `ret 1.18x`, `up 1.12x`, `anchor 0.95x`, `qual_scale 1.18x`, `noise_mult 0.78x`
- hybrid effective ratio:
  - quant `0.4817`, qual `0.2996`, agree `0.2187`
  - pos_boost `0.1180`

---

## 3) high-density advantage gate 결과 (필수)
- high_density_advantage_pass: **true**
- 샘플: `12` (walkforward test windows 내 high-density months)
- threshold 기록:
  - old: `return >= numeric + 0.10`
  - new: `return >= numeric + 0.25` (현재 하드 기준)
  - mdd: `abs(candidate_mdd) <= abs(numeric_mdd)`
  - turnover: `candidate_turnover <= numeric_turnover * 1.05`

근거 수치(high-density OOS):
- numeric: return `0.4318`, mdd `-0.0924`, turnover `1.0000`
- qualitative: return `0.6987`, mdd `-0.0282`, turnover `0.7500`
- hybrid: return `0.0822`, mdd `-0.0361`, turnover `0.8333`

판정:
- qualitative는 new threshold(+0.25) 충족 (`0.6987 >= 0.6818`) + mdd/turnover 조건 모두 충족
- 따라서 high-density gate는 PASS

---

## 4) v3_12 / v3_14 대비 qualitative/hybrid 변화
총수익(total_return) 기준:
- v3_12: numeric `40.0866`, qualitative `21.4663`, hybrid `40.0866`
- v3_14: numeric `26.8169`, qualitative `7.2930`, hybrid `15.2135`
- v3_16: numeric `-0.1328`, qualitative `1.6761`, hybrid `0.5829`

delta (v3_16 - baseline):
- vs v3_12
  - qualitative: `-19.7903`
  - hybrid: `-39.5037`
- vs v3_14
  - qualitative: `-5.6169`
  - hybrid: `-14.6306`

해석:
- 이번 라운드는 high-density gate는 통과했지만,
  - gate1 하드밴드 초과,
  - gate3(subperiod stability) 미통과로
  최종 선발(`non_numeric_top_valid`)이 막혀 REDESIGN으로 종료.

---

## 5) 과적합 가드 상태
- no_ticker_whitelist: PASS
- no_manual_favorites: PASS
- static_no_hardcoded_ticker_scan: PASS
- gate4(purged CV + walkforward): PASS
- gate3(subperiod stability): **FAIL** (pass_ratio `0.333 < 0.67`)
- high_density_advantage_gate: PASS

최종: 과적합 가드 전체는 **부분 실패**(gate3 실패) → ADOPT 불가
