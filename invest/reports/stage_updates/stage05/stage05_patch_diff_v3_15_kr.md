# stage05_patch_diff_v3_15_kr

## inputs
- design source: `reports/stage_updates/stage05/stage05_overfit_brainstorm_v3_15_kr.md` (E안 채택: 레짐 게이트 + 멀티팩터 앙상블)
- baseline reference code: `invest/scripts/stage05_rerun_v3_14_kr.py`
- policy sync (2026-02-19 10:28 KST):
  - high-density 구간에서 non-numeric 우위 임계 `+25%p`
  - MDD/turnover 동시 우위 요구 (turnover `<= 1.05x`)
  - 결과 리포트에 `high_density_advantage_pass` + 수치 근거 필수

## run_command(or process)
- `python3 -m py_compile invest/scripts/stage05_rerun_v3_15_kr.py`
- `python3 invest/scripts/stage05_rerun_v3_15_kr.py | tee reports/stage_updates/logs/stage05_rerun_v3_15_kr.log`

## outputs
- new config: `invest/config/stage05_auto_capture_v3_15_kr.yaml`
- new runner: `invest/scripts/stage05_rerun_v3_15_kr.py`
- static scan log: `reports/stage_updates/logs/stage05_no_whitelist_scan_v3_15_kr.log`
- dynamic universe log: `reports/stage_updates/logs/stage05_dynamic_universe_v3_15_kr.json`
- validated result: `invest/results/validated/stage05_baselines_v3_15_kr.json`

## quality_gates
- 문서 E안 핵심 구현(레짐 게이트 + 멀티팩터 앙상블): PASS
- no ticker whitelist / no manual favorites 하드가드: PASS (config + static scan)
- purged CV/OOS mandatory 게이트 구현: PASS
- subperiod stability check 게이트 구현: PASS (실행 결과 pass/fail 산출)
- search-space freeze/hash logging 구현: PASS (`config_hash`, `search_space_hash`, sampled indices)
- numeric 단독 자동채택 금지 유지: PASS (`numeric_auto_select_block=true`)
- high-density 상향 정책(+25%p, turnover<=1.05x) 동기화: PASS (Gate2 상세 반영)

## failure_policy
- `no_ticker_whitelist` 또는 `no_manual_favorites` false면 즉시 `FAIL_STOP`
- static scan에서 allowlist/favorites/티커 literal 탐지 시 `FAIL_STOP`
- Gate3(서브기간 안정성) 또는 Gate4(purged CV/OOS) 미통과 시 `ADOPT` 금지
- Gate2 high-density 모드에서 `advantage < 0.25` 또는 `MDD/turnover 우위` 미충족 시 Gate2 FAIL

## proof
- code: `invest/scripts/stage05_rerun_v3_15_kr.py`
- config: `invest/config/stage05_auto_capture_v3_15_kr.yaml`
- compile proof: `python3 -m py_compile invest/scripts/stage05_rerun_v3_15_kr.py` (success)
- run log: `reports/stage_updates/logs/stage05_rerun_v3_15_kr.log`
- static scan proof: `reports/stage_updates/logs/stage05_no_whitelist_scan_v3_15_kr.log`
- dynamic universe proof: `reports/stage_updates/logs/stage05_dynamic_universe_v3_15_kr.json`
- result json proof: `invest/results/validated/stage05_baselines_v3_15_kr.json`

---

## diff summary (핵심 변경점)

### 1) 신규 설정 파일 도입
- `invest/config/stage05_auto_capture_v3_15_kr.yaml`
  - universe: `liquidity_top_n`, `universe_limit=180`, `min_history_days=700`
  - hard flags: `no_ticker_whitelist=true`, `no_manual_favorites=true`
  - regime templates: `RISK_ON/TRANSITION/RISK_OFF` factor weight
  - anti-overfit: `purged_cv_folds=5`, `purge_days=20`, `embargo_days=20`, walkforward/subperiod 기준
  - **policy sync**:
    - `high_density_threshold=0.5`
    - `high_density_advantage_pp=0.25`
    - `high_density_turnover_ratio_max=1.05`

### 2) v3_15 실행기 신규 생성
- `invest/scripts/stage05_rerun_v3_15_kr.py`
  - config 기반 round 생성 + search-space deterministic sampling(`max_trials=6`)
  - 레짐 판정기(`RISK_ON/TRANSITION/RISK_OFF`) 추가
  - 멀티팩터 앙상블(`momentum/breakout/flow/volatility_stability/qualitative_lagged`) + median rank
  - 정적 스캔(`allowlist/favorites/ticker literal`) 자동 수행 및 로그 저장
  - 동적 유니버스 membership hash 로깅 (`universe_membership_by_date_hash`)
  - Gate3: subperiod stability 평가 추가
  - Gate4: purged CV + walk-forward OOS 평가 추가
  - 결과 JSON 확장:
    - `anti_overfit_audit`
    - `overfit_guard_pass`
    - `gate2_high_density_advantage`
    - `config_hash`, `search_space_hash`

### 3) Gate2 정책 동기화 (10:28 지시 반영)
- high-density 모드(`avg_density >= high_density_threshold`)에서:
  - non-numeric 우위 임계: `advantage >= 0.25`
  - 리스크 동시 조건: `mdd_superior=true` AND `turnover_ratio <= 1.05`
  - `high_density_advantage_pass` / 상세 수치(`advantage`, `turnover_ratio`, `mdd`) 기록
- 리포트용 필드 추가:
  - `chosen_round_gate.high_density_advantage_pass`
  - `chosen_round_gate.high_density_advantage_detail`
  - `anti_overfit_audit.gate2_high_density_advantage`
