# path_migration_report_v3_22

## 무엇이 깨져 있었는가
- 참조 경로가 `reports/stage_updates/stageXX_...` (구조 평면형)와
  `reports/stage_updates/stageXX/stageXX_...` (신규 폴더형)로 혼재되어 있었음.
- 일부 실행 스크립트는 여전히 `REPORTS / "stage05_..."` 형태로 출력하여
  신규 폴더 구조와 불일치 가능성이 있었음.

## 무엇을 고쳤는가
### 1) 전수 치환(문자열 경로)
- 치환 규칙:
  - `reports/stage_updates/stageNN_...`
  - → `reports/stage_updates/stageNN/stageNN_...`
- 적용 범위:
  - `invest/scripts/`
  - `docs/`
  - `invest/strategy/`
  - `reports/` (템플릿/운영 문서 범위)

### 2) 스크립트 출력 경로 동기화
- Stage05/06 관련 스크립트에서 폴더형 경로로 고정:
  - `invest/scripts/stage05_incremental_external_v3_20_kr.py`
  - `invest/scripts/stage05_incremental_external_v3_21_kr.py`
  - `invest/scripts/stage05_generate_readable_detailed_v3_20_kr.py`
  - `invest/scripts/stage05_tuning_loop_v3_6_kr.py`
  - `invest/scripts/stage05_3x3_v3_9_kr.py`
  - `invest/scripts/stage05_09_v3_3_pipeline.py`
  - `invest/scripts/run_stage05_09_v3_4_kr.py`
  - `invest/scripts/stage06_candidates_v4_kr.py`
  - `invest/scripts/stage06_candidates_v5_kr.py`
  - `invest/scripts/stage06_candidate_gen_v3.py` (기본 output path)
  - `invest/scripts/extract_real_top_picks.py`, `invest/scripts/extract_real_top5_picks.py` (기본 output path)
- 필요한 parent 디렉토리 생성 로직(`mkdir(parents=True, exist_ok=True)`) 보강.

### 3) 문서 canonical 경로 보정
- `docs/openclaw/WORKSPACE_STRUCTURE.md`
- `docs/openclaw/CONTEXT_MANIFEST.json`
- `invest/strategy/MASTER_STRATEGY_RUNBOOK_V1_20260218.md`
- `invest/strategy/STAGE04_BASELINE_FIXED_20260218.md`
- `invest/strategy/strategy_v1_replication_spec_20260217.md`

### 4) 깨진 내부 링크 보정
- 생성(placeholder):
  - `reports/stage_updates/stage06/stage06_crosscheck_v5_kr.md`
  - `reports/stage_updates/stage07/stage07_cutoff_v5_kr.md`

## 검증
### A. 구경로 잔존 grep
- 명령:
  - `git grep -n -E "reports/stage_updates/stage[0-9]{2}_" -- scripts docs invest/strategy reports/stage_updates`
- 결과: **0건**

### B. 링크/출력 경로 존재성 점검
- 점검 대상: `scripts`, `docs`, `invest/strategy`, `reports/stage_updates`
- 패턴: `reports/stage_updates/stageNN/stageNN_*.{md,csv,json,png,jpg,jpeg}`
- 결과:
  - 총 참조: 134
  - 미존재: 7

허용목록(의도적/동적/템플릿):
1. `invest/scripts/stage05_tuning_loop_v3_6_kr.py`의 `stage05_tuning_round_rXX.md` (템플릿 경로)
2. `invest/scripts/stage05_tuning_loop_v3_6_kr.py`의 `stage05_tuning_progress_v3_6_kr.md` (실행 전 미생성 가능)
3. `invest/scripts/extract_real_top_picks.py`의 `stage06_real_top_picks.md` (실행 산출물)
4. `invest/scripts/stage06_candidate_gen_v3.py`의 `stage06_candidates_v3.md` (실행 산출물)
5. `invest/scripts/extract_real_top5_picks.py`의 `stage06_real_top5_picks.md` (실행 산출물)
6. `reports/stage_updates/stage05/stage05_readable_report_template_v3_19_kr.md`의 `stage05_trade_events_vX_kr.csv` (템플릿 placeholder)
7. `reports/stage_updates/stage05/stage05_readable_report_template_v3_19_kr.md`의 `stage05_portfolio_timeline_vX_kr.csv` (템플릿 placeholder)

## 재발방지
- 스크립트 기본 출력 경로를 폴더형(`stageNN/stageNN_...`)으로 고정.
- 문서 canonical 목록(Workspace/Context Manifest) 동기화 완료.
- 신규 문서/스크립트 반영 시 동일 grep 체크를 릴리즈 게이트로 유지.

## 최종 정합성 체크 결과
- **PASS (허용목록 7건 제외 시 깨진 경로 0)**
