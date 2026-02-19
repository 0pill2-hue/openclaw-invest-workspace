# stage05_result_v3_15_kr

## inputs
- design doc: `reports/stage_updates/stage05/stage05_overfit_brainstorm_v3_15_kr.md`
- patch spec: `reports/stage_updates/stage05/stage05_patch_diff_v3_15_kr.md`
- config: `invest/config/stage05_auto_capture_v3_15_kr.yaml`
- runner: `invest/scripts/stage05_rerun_v3_15_kr.py`
- data:
  - `invest/data/raw/kr/ohlcv/*.csv`
  - `invest/data/raw/kr/supply/*_supply.csv`
  - `invest/data/raw/text/blog/**/*.md`
  - `invest/data/raw/text/telegram/*.md`

## run_command(or process)
- `python3 -m py_compile invest/scripts/stage05_rerun_v3_15_kr.py`
- `python3 invest/scripts/stage05_rerun_v3_15_kr.py | tee reports/stage_updates/logs/stage05_rerun_v3_15_kr.log`

## outputs
- `invest/results/validated/stage05_baselines_v3_15_kr.json`
- `reports/stage_updates/stage05/stage05_result_v3_15_kr.md`
- `reports/stage_updates/stage05/stage05_patch_diff_v3_15_kr.md`
- `reports/stage_updates/logs/stage05_rerun_v3_15_kr.log`
- `reports/stage_updates/logs/stage05_no_whitelist_scan_v3_15_kr.log`
- `reports/stage_updates/logs/stage05_dynamic_universe_v3_15_kr.json`

## quality_gates
- KRX only guard: PASS
- no ticker whitelist: PASS
- no manual favorites: PASS
- purged CV/OOS mandatory: PASS (`cv_pass_ratio=0.80`, `walkforward_pass_ratio=1.00`)
- subperiod stability check: FAIL (`pass_ratio=0.333 < 0.67`)
- search-space freeze/hash logging: PASS (`config_hash`, `search_space_hash` 기록)
- numeric 단독 자동채택 금지: PASS (`numeric_auto_select_block=true`)
- high-density policy sync(+25%p, MDD/turnover<=1.05x): PASS (Gate2 detail 기록)

## failure_policy
- Gate3 또는 Gate4 미통과 시 `ADOPT` 금지
- overfit guard 항목 중 핵심 하드가드 미통과 시 `FAIL_STOP` 또는 `REDESIGN`
- 본 실행은 `subperiod_stability_check=false`로 `MAX_REPEAT_REACHED_REDESIGN` 종료

## proof
- result json: `invest/results/validated/stage05_baselines_v3_15_kr.json`
- run log: `reports/stage_updates/logs/stage05_rerun_v3_15_kr.log`
- static scan: `reports/stage_updates/logs/stage05_no_whitelist_scan_v3_15_kr.log`
- dynamic universe: `reports/stage_updates/logs/stage05_dynamic_universe_v3_15_kr.json`
- config hash: `6108eca6df755960bffe0fa0020e03087f3e9581a86917cde9bebdb53a7de79b`
- search hash: `f20652b8a2b5d54b08921eb85dee63dd862fb8954b88407c0a76490c922233c9`

---

## 1) 최종 판정 요약
- result_grade: `VALIDATED`
- repeat_counter: `13 -> 18`
- stop_reason: `MAX_REPEAT_REACHED_REDESIGN`
- final_decision: `REDESIGN`
- non_numeric_top_valid: `false`

### 성과(최종 라운드 r06_auto_grid_3779135)
- numeric_return: `-0.144699`
- qualitative_return: `0.934137`
- hybrid_return: `1.081578` (non-numeric candidate)
- tie_detected: `false`
- clone_detected: `false`

## 2) high_density_advantage_pass + 수치 근거
- high_density_advantage_pass: `true`
- high_density_mode: `false` (`avg_density=0.276576`, threshold=`0.5`)
- advantage(non_numeric - numeric): `+1.226277` (요구치 `+0.25` 대비 충족)
- mdd 비교: non_numeric `-0.251139` vs numeric `-0.374771` → `mdd_superior=true`
- turnover ratio: `0.867769` (요구치 `<=1.05`) → `high_density_risk_pass=true`

> 정책 동기화 반영: high-density 모드에서는 `advantage>=0.25` + `MDD/turnover 우위` 동시 필요하도록 Gate2 구현 완료.

## 3) overfit_guard_pass (항목별)
- no_ticker_whitelist: `true`
- no_manual_favorites: `true`
- purged_cv_oos_mandatory: `true`
- subperiod_stability_check: `false`
- search_space_freeze_hash_logging: `true`
- numeric_auto_adopt_block: `true`
- high_density_advantage_pass: `true`
- static_no_hardcoded_ticker_scan: `true`

## 4) anti-overfit 검증 상세
### A. 정적 스캔 (티커 하드코딩 탐지)
- 파일: `reports/stage_updates/logs/stage05_no_whitelist_scan_v3_15_kr.log`
- 결과: `scan_pass=true` (allowlist/favorites/ticker literal hit 없음)

### B. 동적 유니버스 증빙
- 파일: `reports/stage_updates/logs/stage05_dynamic_universe_v3_15_kr.json`
- 규칙: `liquidity_top_n`, `limit=180`, `min_history_days=700`
- membership hash: `ba2ae9dbb6f3c71522e0032bdec362048bb3c2681805d4de2ec96c33c8eab200`

### C. OOS / Purged CV 증빙
- purged CV pass ratio: `0.80` (4/5 pass, 기준 0.60)
- walkforward pass ratio: `1.00` (3/3 pass, 기준 0.67)
- 결론: Gate4 `PASS`

### D. Subperiod 안정성
- pass ratio: `0.333` (1/3, 기준 0.67)
- sp_2016_2019: PASS
- sp_2020_2022: FAIL
- sp_2023_2026: FAIL
- 결론: Gate3 `FAIL` → ADOPT 차단

## 5) repeat_counter / stop_reason
- repeat_counter_start: `13`
- repeat_counter_final: `18`
- stop_reason: `MAX_REPEAT_REACHED_REDESIGN`
