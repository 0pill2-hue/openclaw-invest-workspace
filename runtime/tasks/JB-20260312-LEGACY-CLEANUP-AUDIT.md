# JB-20260312-LEGACY-CLEANUP-AUDIT

- checked_at: 2026-03-12 KST
- mode: read-only audit
- guardrail: Telegram PDF recovery **code change 없음** (문서/정리 후보만 감사)

## scope checked
- `docs/invest/` 루트 SSOT 문서 + `stage1~stage12/` 하위 문서
- `invest/stages/` 중 `stage1/scripts`, `stage2/scripts`, `stage3/scripts` 중심 spot-check
- `scripts/` 루트 + `tasks/`, `directives/`, `watchdog/`, `heartbeat/` 구조 확인
- `runtime/tasks/` 루트 문서(정책/보고/증빙 인덱스 성격 파일) 확인

## out of scope / intentionally not touched
- Telegram PDF recovery 로직 자체 수정
- `invest/stages/*/outputs`, `runtime/*.log`, DB WAL/SHM 같은 단순 런타임 찌꺼기 대청소
- 실제 삭제/이동/리네임 실행

## top legacy candidates
1. **Stage1 selected_articles 문서 계약 불일치**
   - 코드/실행은 Naver-only lane으로 옮겨졌는데, Stage1 canonical 문서 3개가 아직 generic collector를 live writer처럼 적고 있음.
2. **Stage2 Telegram PDF 경로 문서 불일치**
   - Stage1/실코드는 bucketed flat artifact를 쓰는데, Stage2 문서는 아직 `msg_<id>/` 레거시 디렉터리를 현재 구조처럼 설명함.
3. **`docs/invest/STAGE123_REDESIGN_DECISIONS.md`**
   - DRAFT 설계 메모인데 현행 Stage1/Stage3 canonical과 충돌하는 내용이 남아 있음.
4. **reserved/historical stage 문서가 active docs 트리에 그대로 남아 있음**
   - 특히 stage8 업데이트/placeholder 문서가 canonical tree에서 혼선을 줌.
5. **죽은 wrapper/obsolete script/legacy pycache**
   - `scrape_all_posts.py`, `update_dashboard.py`, `scripts/__pycache__/*legacy*.pyc` 류가 현재 표준 경로와 충돌.
6. **runtime/tasks 루트의 정책 승격 보고서 중복**
   - 이미 `AGENTS.md`/`docs/operations/governance/OPERATING_GOVERNANCE.md`에 반영된 규칙을 task report가 다시 들고 있어 canonical 오인 가능성이 있음.

## classification table
| path | action | concrete evidence | blocker / note |
| --- | --- | --- | --- |
| `docs/invest/stage1/RUNBOOK.md` | CANONICALIZE | 아직 `stage01_collect_selected_news_articles.py` 수동 실행을 canonical처럼 적고 있음. 실제 orchestrator `invest/stages/stage1/scripts/stage01_daily_update.py`는 `daily_full`/`selected_articles_naver_only`에서 `stage01_collect_selected_news_articles_naver.py`를 사용. `runtime/tasks/JB-20260311-SELECTED-ARTICLES-ALT-PATH.md`도 live corpus가 Naver-only라고 검증함. | generic collector를 “보조/legacy/manual only”로 남길지 먼저 결정 필요 |
| `docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md` | CANONICALIZE | `daily_full`/`news_backfill` profile 표가 아직 generic `stage01_collect_selected_news_articles.py`를 적고 있음. 실코드는 Naver-only wrapper 연결. | 위와 동일 |
| `docs/invest/stage1/stage01_data_collection.md` | CANONICALIZE | 4.4는 `stage01_collect_selected_news_articles.py`를 live output writer처럼 설명하지만, 같은 문서 후반에는 generic collector가 더 이상 live `selected_articles/`에 직접 쓰지 않는다고 적혀 있어 **문서 내부 self-conflict**가 있음. | canonical script 필드를 무엇으로 둘지 명확화 필요 |
| `docs/invest/stage2/STAGE2_PDF_REFINEMENT_DESIGN.md` | CANONICALIZE | 아직 Stage1 attachment root를 `attachments/telegram/<channel_slug>/msg_<message_id>/`로 설명. 반면 Stage1 canonical(`RUNBOOK.md`, `STAGE1_RULEBOOK_AND_REPRO.md`, `stage01_data_collection.md`)은 `bucket_<nn>/msg_<id>__meta.json` flat 구조를 SSOT로 둠. Stage2 code(`stage02_onepass_refine_full.py`)도 `_telegram_attach_bucket_*`를 사용하고 legacy dir는 fallback only다. | historical note는 남기되 “current observed fact”에서 분리 권장 |
| `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md` | CANONICALIZE | Telegram PDF section이 legacy `msg_<message_id>/` fallback wording 중심이라 현재 Stage1/Stage2 코드 계약보다 뒤처짐. | legacy fallback은 note로만 강등하면 됨 |
| `docs/invest/STAGE123_REDESIGN_DECISIONS.md` | ARCHIVE | status가 `DRAFT`. Stage1 파트는 quarantine를 Stage1 책임처럼 적지만, current canonical은 Stage1 non-scope / Stage2 quarantine. Stage3 파트도 현행 `builder + qualitative axes gate` 구현 계약이 아니라 별도 Stage3-A/B 구상 메모 성격. | 삭제보다 historical design memo로 archive 적합 |
| `docs/invest/stage1/PDF_DELIVERABLE_CONTRACT.md` | MERGE | `INVEST_STRUCTURE_POLICY.md`는 Stage1 문서 템플릿을 `README/RUNBOOK/RULEBOOK_AND_REPRO/source appendix/TODO` 5개로 고정했는데, 이 파일은 별도 6번째 canonical-like contract로 남아 있음. 내용도 Stage1 PDF artifact / coverage / deliverable 규칙으로 `RUNBOOK.md` + `stage01_data_collection.md`와 역할이 겹침. | PDF success criteria 필드는 보존 필요. 문서 삭제 전 흡수 위치 결정 필요 |
| `docs/invest/stage8/stage_updates/stage08_cutoff_design_v5_kr.md` | ARCHIVE | `docs/invest/stage8/README.md`가 이미 `RESERVED / HISTORICAL_ONLY`라고 선언. 그런데 이 문서는 missing `scripts/stage08_cutoff_v5_kr.py`와 missing validated output을 참조함. active tree에서 실행 문서처럼 보이기 쉬움. | historical backtest 근거가 필요하면 archive만 |
| `docs/invest/stage8/stage_updates/stage08_cutoff_v5_kr.md` | DELETE | 본문이 `DRAFT_PLACEHOLDER` 2줄뿐이라 실질 정보가 없음. reserved stage의 placeholder가 canonical docs tree를 소음화함. | inbound link 미확인 시 archive로 낮춰도 됨 |
| `invest/stages/stage1/scripts/scrape_all_posts.py` | DELETE | 파일 자체가 `from stage01_scrape_all_posts_v2 import main`만 수행하는 2-line wrapper. canonical docs와 orchestrator는 `stage01_scrape_all_posts_v2.py`를 직접 사용. AGENTS hard rule도 legacy compat wrapper를 남기지 말라고 함. | 외부 쉘 alias/launchd가 직접 호출 중인지 미확인 |
| `invest/stages/stage1/scripts/update_dashboard.py` | DELETE | repo 내 참조가 없고, 코드가 missing path `invest/web/index.html`을 하드코딩. 현재 트리 기준 실행 불가/obsolete dashboard helper로 보임. 또 외부 auth path를 직접 참조함. | repo 밖 cron/수동 alias 사용 여부 미확인 |
| `scripts/__pycache__/directivesdb.cpython-314.pyc` 등 `scripts/__pycache__/*legacy*.pyc` | DELETE | `scripts/README.md`가 flat path(`scripts/taskdb.py` 등)는 더 이상 표준이 아니라고 명시. 그런데 `scripts/__pycache__/taskdb.cpython-314.pyc`, `directivesdb.cpython-314.pyc`, `task_gate.cpython-314.pyc` 등 **이미 없는 flat 소스용 pyc**가 남아 있어 구조 오인을 유발. | 파생 산출물이라 blocker 거의 없음 |
| `runtime/tasks/JB-20260311-TASK-OPS-RULE-CANONICALIZE.md` | ARCHIVE | 파일 스스로 “운영 규칙을 canonical 문서로 승격했다”고 적고 proof를 `AGENTS.md`, `docs/operations/governance/OPERATING_GOVERNANCE.md`로 둠. 즉 이 파일은 역사 보고서이지 현재 규칙 SSOT가 아님. | task DB proof path 보존 필요 시 archive move만 |
| `runtime/tasks/JB-20260311-MEMORY-TO-CANONICAL-RULES.md` | ARCHIVE | 바로 위 파일과 거의 같은 규칙/증빙을 반복 보고. canonical은 이미 `AGENTS.md`/`docs/operations/governance/OPERATING_GOVERNANCE.md`/skill 문서로 승격됨. | same |
| `runtime/tasks/JB-20260312-STAGE3-BRAIN-BENCHMARK.md` | ARCHIVE | 이 메모는 `docs/invest/stage3/STAGE3_BRAIN_SCORING_DESIGN.md`가 missing이라고 적지만, 현재 workspace에는 해당 문서가 존재하고 sibling task reports도 그 proof path를 가리킴. 시점성 blocker memo이지 현재 canonical 상태 설명이 아님. | chronology 보존 위해 archive 권장 |
| `runtime/tasks/README.md` | KEEP | 현재 runtime task 운영 인덱스로 실제 DB/log/programs 경로와 운영 예시를 모아 둔 문서. root clutter가 아니라 진입점 역할. | 계속 유지 |
| `docs/invest/STAGE_EXECUTION_SPEC.md` | KEEP | `docs/invest/README.md`와 `STRATEGY_MASTER.md`가 가리키는 stage 진입 인덱스 SSOT. | 계속 유지 |
| `invest/stages/stage1/scripts/selected_articles_live_summary.py` | KEEP | `stage01_update_coverage_manifest.py`가 실제 참조하는 active helper. 이름이 “summary”라 stale처럼 보일 수 있으나 현재 live directory summary 계약을 계산하는 구현체임. | 계속 유지 |
| `docs/invest/stage12/stage_updates/stage12_adopt_hold_promote.md` | KEEP | stage12 README가 가리키는 governance canonical 메타 문서. reserved stage라도 현재 역할이 명확함. | 계속 유지 |

## recommended next cleanup order
1. **Stage1 selected_articles 문서 일괄 canonicalize**
   - 대상: `RUNBOOK.md` + `STAGE1_RULEBOOK_AND_REPRO.md` + `stage01_data_collection.md`
   - 이유: 현재 코드/운영 경로와 문서가 직접 충돌하므로 우선순위 최고.
2. **Stage2 Telegram PDF path 문서 정렬**
   - 대상: `STAGE2_RULEBOOK_AND_REPRO.md` + `STAGE2_PDF_REFINEMENT_DESIGN.md`
   - 이유: Stage1/Stage2 code는 bucketed 구조인데 문서가 legacy dir를 현재형으로 서술.
3. **DRAFT/historical docs archive batch**
   - 대상: `STAGE123_REDESIGN_DECISIONS.md`, `docs/invest/stage8/stage_updates/*`, 필요 시 stage10 historical refs도 함께 검토
   - 이유: canonical tree 소음 감소.
4. **dead code / compat wrapper / legacy pycache batch**
   - 대상: `scrape_all_posts.py`, `update_dashboard.py`, `scripts/__pycache__/*legacy*.pyc`
   - 이유: 코드 탐색 시 false-positive를 줄임.
5. **runtime/tasks root 문서 slim-down**
   - 대상: 이미 canonical 승격이 끝난 정책 보고서들
   - 이유: `runtime/tasks/`를 active proof/index 중심으로 유지.
6. **Stage1 extra doc merge 판정**
   - 대상: `PDF_DELIVERABLE_CONTRACT.md`
   - 이유: 가치 있는 계약은 유지하되 Stage1 문서 템플릿 밖 SSOT를 줄여야 함.

## helpful follow-up batches / commands
```bash
# Batch A: Stage1 selected_articles contract mismatch grep
grep -RIn 'stage01_collect_selected_news_articles.py\|stage01_collect_selected_news_articles_naver.py\|selected_articles_naver_only' \
  docs/invest/stage1 invest/stages/stage1/scripts runtime/tasks/JB-20260311-SELECTED-ARTICLES-ALT-PATH.md

# Batch B: Telegram PDF path doc-vs-code mismatch grep
grep -RIn 'msg_<message_id>/\|bucket_<nn>\|__meta.json' \
  docs/invest/stage1 docs/invest/stage2 invest/stages/stage2/scripts/stage02_onepass_refine_full.py

# Batch C: dead wrapper / obsolete script usage check
grep -RIl 'scrape_all_posts.py\|update_dashboard.py' docs invest/stages scripts runtime/tasks

# Batch D: legacy pycache candidates
find scripts/__pycache__ -maxdepth 1 -type f | sort

# Batch E: runtime/tasks root docs that are likely archive-only after canonical promotion
ls runtime/tasks/JB-20260311-* runtime/tasks/JB-20260312-STAGE3-BRAIN-BENCHMARK.md
```

## summary judgment
- 가장 먼저 정리해야 할 것은 **문서-코드 직접 충돌**이다. 특히 Stage1 selected_articles와 Stage2 Telegram PDF path 문서는 지금도 사람을 잘못된 경로로 안내할 수 있다.
- 그 다음은 **DRAFT/historical memo를 canonical tree 밖으로 빼는 일**이다.
- 마지막으로 **dead wrapper / obsolete script / legacy pycache**를 정리하면 탐색 비용이 크게 줄어든다.
