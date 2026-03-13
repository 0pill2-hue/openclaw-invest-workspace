# JB-20260311-STAGE-CONTRACT-ALIGN subagent report

## 요약
- Stage1/Stage2 계약 점검 결과, 핵심 리스크는 2개였습니다.
  1) `raw_db_sync` 상태 파일이 실행 중/실패/락해제 시점을 충분히 드러내지 못해 **truthful status contract**가 약함
  2) `selected_articles_merged_summary.json`이 live dir에 남아 있지만 실제 canonical 입력(`selected_articles_*.jsonl`)과 불일치할 수 있어 **consumer 오해 유발**
- 최소 안전 수정(minimum safe fix)으로 위 2개를 코드/실행 검증까지 반영했습니다.

---

## 점검 결과 (root cause 중심)

### 1) raw_db_sync 상태-락 계약
- 점검 파일:
  - `invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
  - `invest/stages/common/stage_raw_db.py`
- 원인:
  - 기존에는 사실상 최종 상태(`full_sync`) 중심이라, 실행 중에는 이전 PASS 상태가 남아 보이거나, 락 파일만 보고 상태를 해석해야 했습니다.
  - `status_only_from_sync_meta` 모드/복수 실행 이력과 섞이면 status 관측 시점 해석이 모호했습니다.
- 결론:
  - “상태가 락 해제 전에 최종 PASS로 기록되는가?”를 명시적으로 방지/판독 가능하게 만드는 메타데이터가 필요했습니다.

### 2) selected_articles summary/consumer 계약
- 점검 파일:
  - `invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`
  - `runtime/tasks/JB-20260311-SELECTED-ARTICLES-ALT-PATH.md`
  - Stage2 consumer 경로(`invest/stages/stage2/scripts/stage02_onepass_refine_full.py`) 확인
- 원인:
  - `selected_articles_merged_summary.json`가 live dir에 있으나, 실제 canonical 소비는 `selected_articles_*.jsonl` 집합입니다.
  - stale summary가 남아 있으면 coverage/운영자가 잘못된 corpus를 참조할 수 있습니다.
- 결론:
  - summary를 제거하기보다, **live jsonl 기반 파생 요약**으로 재정의하고 coverage scope에 계약 문구를 넣는 것이 최소/안전했습니다.

---

## 적용한 최소 안전 수정

### A) raw_db_sync truthful lifecycle status 강화
수정 파일: `invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`

- 실행 중 상태 기록 추가:
  - `status=RUNNING`, `status_mode=full_sync_running`
  - lock payload(`pid`, `acquired_at`, 경로/run 메타) 포함
- 실패 상태 기록 추가:
  - `status=FAIL`, `status_mode=full_sync_failed`, `error` 포함
- 최종 성공 상태 강화:
  - `status=PASS`, `status_mode=full_sync`
  - `lock.released_at` 기록
- 락/상태 경로 테스트 가능화:
  - `STAGE1_DB_RUNTIME_DIR`, `STAGE1_DB_STATUS_PATH`, `STAGE1_DB_LOCK_PATH` 지원

효과:
- 실행 중/실패/성공 상태가 명확히 구분되고, 최종 상태에 락 해제시점이 남아 해석 모호성이 크게 줄었습니다.

### B) selected_articles summary를 live-canonical 파생 요약으로 전환
수정 파일: `invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`

- `selected_articles_*.jsonl`만 live corpus로 집계(legacy merged 산출물 제외)
- `selected_articles_merged_summary.json`를 매 manifest 업데이트 시 **live dir 파생 요약**으로 재생성
  - `summary_mode=directory_jsonl_summary`
  - `output_file=""` (merged 단일 파일을 canonical로 주장하지 않음)
  - `contract_note` 명시
- `news_selected_articles` coverage scope에 계약 명시 추가:
  - `selected_articles_summary_file`
  - `selected_articles_live_file_count`
  - `selected_articles_contract`

효과:
- summary artifact가 stale/고아 상태로 소비자에게 오해를 주는 문제를 최소 수정으로 해소.

---

## 검증 (실행/결과)

### 1) 문법 검증
- 명령:
  - `python3 -m py_compile invest/stages/stage1/scripts/stage01_sync_raw_to_db.py invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`
- 결과: PASS

### 2) raw_db_sync lifecycle 계약 검증 (격리 temp run)
- 명령: Python harness로 임시 raw/db/runtime 경로 생성 후 `stage01_sync_raw_to_db.py` 실행
- 확인 포인트:
  - 실행 중 `status=RUNNING`, `status_mode=full_sync_running` 관측
  - 종료 후 `status=PASS`, `lock.released_at` 존재
  - lock 파일 truncate(크기 0)
- 결과: PASS

### 3) 실제 coverage 갱신 실행
- 명령:
  - `python3 invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`
- 결과: PASS (`ok: true`, `index_path: invest/stages/stage1/outputs/raw/source_coverage_index.json`)

### 4) 실제 raw_db_sync 실행
- 명령:
  - `python3 invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
- 결과: PASS
  - `raw_db_sync_status.json`에서 `status=PASS`, `status_mode=full_sync`, `lock.released_at` 확인
  - `raw_db_sync.lock` 파일 크기 0 확인

### 5) selected_articles summary/coverage 계약 확인
- 확인 결과:
  - `selected_articles_merged_summary.json`
    - `summary_mode=directory_jsonl_summary`
    - `output_file=""`
    - `contract_note` 존재
  - `source_coverage_index.json > sources.news_selected_articles.scope`
    - `selected_articles_summary_file` 존재
    - `selected_articles_live_file_count` 존재
    - `selected_articles_contract` 존재
- 결과: PASS

---

## touched paths (code)
- `invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
- `invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`

## touched paths (runtime artifacts by validation run)
- `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`
- `invest/stages/stage1/outputs/runtime/raw_db_sync.lock`
- `invest/stages/stage1/outputs/raw/source_coverage_index.json`
- `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_merged_summary.json`
- `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3` (sync 반영)

---

## 우선 개선 순서 (명시 답변)
1. **첫째:** `raw_db_sync` 상태 계약을 lifecycle 기준(RUNNING/FAIL/PASS + lock release metadata)으로 유지/강제
2. **둘째:** `selected_articles` canonical 입력을 `selected_articles_*.jsonl`로 고정하고, summary는 파생 산출물임을 문서/scope에 명시
3. **셋째:** coverage/consumer 계층에 계약 단위 회귀검증(예: summary가 live 파일셋과 불일치하면 FAIL) 추가

---

## 최종 판정
DONE_CANDIDATE
