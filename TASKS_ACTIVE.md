# TASKS_ACTIVE.md

## PRIORITY QUEUE (오늘)
1) P0: JB-20260305-037 TASKS 프로그램 전환(SQLite CLI) + 티켓 강제 게이트 도입
2) P0: JB-20260305-026/027 — Stage1 데이터 기간/미수집 백필(최우선)
3) P1: JB-20260305-025 — 데이터 입력 정리 잔여 처리
4) P1: JB-20260305-018 — Stage1~6 실행검증 상태 반영/정리
5) P2: JB-20260305-019/020/021/022/023 — 구조/문서/재실행 잔여 정리

## ACTIVE NOW
- (empty)

## BACKLOG (의미 있는 미완)
- [ ] BLOCKED: JB-20260305-030 Telegram 인증기반 full 수집 확장
  - scope: TELEGRAM_API_ID/TELEGRAM_API_HASH/session 준비 후 fallback 63.64% 한계를 인증기반으로 확대
  - blocked: 인증 자격정보 미입력(외부의존)
  - proof(last): invest/stages/stage1/outputs/reports/stage_updates/_jb025_auth_block_check_20260305_161844.json

- [ ] BLOCKED: JB-20260307-002 dispatch_tick Brain1 고정 + assign-next 중복할당 가드
  - scope: scripts/tasks/dispatch_tick.py, scripts/tasks/db.py만 수정
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-07 01:33:47
  - blocked: watchdog_stale_in_progress>30m

- [ ] BLOCKED: JB-20260307-005 Stage1 잔여 canonical: KR supply 외부 로그인 차단 대응 + selected articles 2016 coverage 완료 + 최종 체인 검증
  - scope: invest/stages/stage1/*, launchd/profile orchestration, selected_articles coverage, KR supply 대체/운영판정
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-07 10:13:56
  - blocked: remaining canonical stage1 blockers only: (1) KRX 수급 endpoint 로그인 요구로 KR supply freshness fail, (2) selected articles 2016 coverage 미완, (3) 두 이슈 해결 후 final validate/chain pass 필요

- [ ] BLOCKED: 5 메인/서브 작업 분리 등록 규칙 및 task ledger 개선
  - scope: runtime/tasks/tasks.db 운영 규칙, scripts/tasks/*, current-task/task 상태 표현 개선
  - note: phase: main_exec
  - note: priority=P1; task ledger rule hardening after stage1 primary work
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-07 20:54:06
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-07 22:04:07
  - blocked: watchdog_stale_in_progress>30m

- [ ] BLOCKED: JB-20260305-036 Stage2 링크본문 확장수집 + 중복링크 제거
  - scope: text/blog·telegram·premium 정제 시 링크만 있는 본문은 링크 대상 본문을 제한적으로 수집해 보강하고, URL canonicalization + content hash로 중복 제거
  - blocked: owner_pause_non_stage1
  - proof(pending): subagent runId=미확인

- [ ] BLOCKED: JB-20260304-023 Core 방식 정성게이트 기준 생존/탈락 분류 리포트
  - scope: -
  - blocked: owner_pause_non_stage1

- [ ] BLOCKED: JB-20260305-034 Stage2 strict 재생성(legacy 완전 제거, signal/qualitative 전용)
  - scope: Stage2 legacy 호환 경로/코드(dual-write) 삭제, 기존 legacy 데이터 폴더 삭제 후 clean/quarantine를 signal/qualitative 체계로 완전 재생성
  - blocked: owner_pause_non_stage1
  - proof(pending): subagent runId=미확인

- [ ] BLOCKED: JB-20260305-019 재번호/파일명/in-out 경로 최종 정합 마감
  - scope: Stage1~6 재번호 표기 잔존 제거 + in/out 오경로 0 + 순차 실행 검증
  - blocked: owner_pause_non_stage1
  - proof(pending): subagent runId=209ce04f-d804-470c-b9ae-d34edafe0a08

- [ ] BLOCKED: JB-20260305-033 Stage3 정성축 재설계(감성/주목도 제거, 4축 점수화) + 문서/스크립트 반영
  - scope: Stage3를 upside/downside_risk/bm_sector_fit/persistence 중심으로 재설계, 이중카운팅 방지 가드 적용, 입력은 qualitative 전원천 기준으로 정리, dart 분석결과 signal 출력 분리
  - blocked: owner_pause_non_stage1
  - proof(last): invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py, invest/stages/stage3/scripts/stage03_build_input_jsonl.py, invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv, invest/stages/stage3/outputs/signal/dart_event_signal.csv

- [ ] BLOCKED: JB-20260305-020 stage1~12 I/O code↔doc 1:1 매트릭스 검증(누락/불일치 0 기준)
  - scope: 모든 stage 입력/출력 경로를 코드-폴더-문서 3축 대조, code-only/doc-only 불일치 제거
  - blocked: owner_pause_non_stage1
  - proof(pending): sessions_send runId=3ba2d0a8-d32b-40e0-a41c-e9e83e4a78ce (runId=209ce04f-d804-470c-b9ae-d34edafe0a08에 병합)

- [ ] BLOCKED: JB-20260305-021 Stage3~6 구버전 산출 정리 + 재생성 + Stage3 항목 감사
  - scope: 틀어진 downstream 데이터 삭제, Stage3→6 재실행, Stage3 가중치 외 항목 점검/문서 동기화
  - blocked: owner_pause_non_stage1
  - proof(pending): subagent runId=f64e0ef4-20b8-454b-8401-ce36b3b3f174

- [ ] BLOCKED: JB-20260305-022 Stage1 raw signal/qualitative 분리 + 버핏지수/신용오실레이터 추가 수집
  - scope: Stage1 raw 경로 이원화, stage2~6 경로 정합, 추가 지표 수집, 문서 동기화, 스모크 검증
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-07 00:13:17
  - blocked: watchdog_stale_in_progress>30m
  - proof(pending): subagent runId=f932947a-ccff-4b15-8fc8-e20263ec2336

- [ ] BLOCKED: JB-20260305-025 데이터 입력 정리(필요한 것 확장, 불필요한 것 제외)
  - scope: premium 링크메타 점수입력 차단, telegram/blog 커버리지 확장, DART/뉴스 커버리지 표, blocked 분리
  - note: fallback 기준 정리는 완료, 인증기반 텔레그램 확장은 별도 외부의존 티켓으로 분리
  - blocked: owner_pause_non_stage1
  - proof(last): invest/stages/stage1/outputs/reports/stage_updates/STAGE_TASK_024_025_STATUS_SYNC_20260305_155043.md, invest/stages/stage1/outputs/reports/stage_updates/_jb025_auth_block_check_20260305_161844.json, invest/stages/stage1/outputs/reports/stage_updates/STAGE_TASK_024_027_STATUS_SYNC_20260305_161844.md

- [ ] BLOCKED: JB-20260305-018 번호재정렬 후 신규 Stage1~6 실행검증(input/output 경로 정합 포함)
  - scope: 신규 stage1→6 순차 실행 + stage별 in/out 경로 정확성 체크 + 오경로 쓰기 탐지
  - blocked: owner_pause_non_stage1
  - proof(pending): subagent runId=091a489c-16e1-42ef-ab09-1a8731df3a7a
  - proof(last): invest/stages/stage1/outputs/reports/stage_updates/STAGE_RENUMBER_AND_INOUT_FINAL_FIX_20260305_0948.md

- [ ] BLOCKED: JB-20260306-006 메인 오케스트레이션 기반 자동할당 루프 구축
  - scope: launchd 트리거→메인 에이전트→서브에이전트 spawn/review-pass-rework 반영
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-07 00:13:17
  - blocked: watchdog_stale_in_progress>30m
  - proof: scripts/taskdb.py assign-next hardened + scripts/task_dispatch_tick.py + launchd auto-dispatch plist + manual tick assigned JB-20260305-022

- [ ] BLOCKED: JB-20260306-003 Stage6 시뮬 수익률 일치 허용오차 고정
  - scope: 시뮬레이션 parity 검증 허용오차를 일일1bp/누적5bp/체결2bp로 고정 및 fail-close 반영
  - blocked: owner_pause_non_stage1
  - proof: scripts/taskdb.py summary, scripts/directivesdb.py summary, TASKS.md, DIRECTIVES.md, runtime/tasks/README.md, runtime/directives/README.md updated; summary rc=0

- [ ] BLOCKED: JB-20260306-007 Stage1~3 전량 정제/이미지 OCR 누락 보완
  - scope: cap 제거/완화, 미처리 백로그 롤링, image_map/images_ocr 지속 처리 및 Stage3 유입 보장
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-07 00:13:17
  - blocked: watchdog_stale_in_progress>30m

## DONE (recent)
- [x] DONE: 1 stage1 문서 정책/템플릿 확정 및 stage1 정합성 정비
  - scope: docs/invest/*, invest/stages/stage1/* 및 직접 연결 공통 유틸 점검/수정
  - note: phase: main_review
  - note: priority=P0; stage1 Telegram mismatch/supply stale/doc-code alignment fix
  - note: subagent result received; reviewing evidence and applying stage1 fixes
  - note: stage1 verification child callback/p proof wait
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-07 21:14:06
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-07 22:04:07
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-08 07:24:16
  - blocked: watchdog_stale_in_progress>30m
  - proof: docs/invest stage1 문서/SSOT 정비 완료; proof existing + 2026-03-08 RUNBOOK/STAGE1_RULEBOOK/README/profile 정리 반영

- [x] DONE: JB-20260305-017 Stage 번호 재정렬(2.5→3, 이후 단계 +1 시프트) + 문서 정합화
  - scope: stage 디렉토리/경로/문서/launchd 전면 치환 및 검증
  - proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE_RENUMBER_AND_INOUT_FINAL_FIX_20260305_0948.md

- [x] DONE: JB-20260305-037 TASKS 프로그램 전환(SQLite CLI) + 티켓 강제 게이트 도입
  - scope: task 원장을 문서에서 프로그램(SQLite)로 전환하고, ticket_id 없는 작업 시작/완료 보고를 fail-close로 차단
  - proof: scripts/taskdb.py; scripts/task_gate.py; runtime/tasks/README.md

- [x] DONE: JB-20260307-001 DART/DB별 coverage summary SSOT 생성 및 문서화
  - scope: invest/stage1 coverage manifest
  - proof: invest/stages/stage1/outputs/raw/qualitative/kr/dart/coverage_summary.json; invest/stages/stage1/outputs/runtime/stage01_source_coverage_index.json; invest/stages/stage1/scripts/stage01_update_coverage_manifest.py; invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py; invest/stages/stage1/docs/RUNBOOK.md; invest/docs/AUTOCOLLECT_OPERATIONS.md; python3 invest/stages/stage1/scripts/stage01_update_coverage_manifest.py --db dart; python3 -m py_compile invest/stages/stage1/scripts/stage01_update_coverage_manifest.py invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py

- [x] DONE: JB-20260307-003 invest docs 최소화 + stage1 SSOT + 경로 하드코딩 제거
  - scope: invest/docs/*, invest/stages/stage1/docs/*, stage01_daily_update.py, run_stage1234_chain.sh
  - note: auto_recover: watchdog_stale_in_progress>30m @ 2026-03-07 08:43:54
  - blocked: watchdog_stale_in_progress>30m
  - proof: invest docs 최소화 + stage1 SSOT + context_policy/runtime_env 경로 하드코딩 제거 + stage01_daily_update/profile 문서 정합성 반영

- [x] DONE: JB-20260307-006 stage1 설계변경 직전 상태로 롤백
  - scope: HEAD(eacf09dcc) 변경분 되돌리기
  - proof: git revert created 55d8d23b8 for eacf09dcc; verified via git log -n2 and git status --short

- [x] DONE: JB-20260308-STAGE1CHK Stage1 daily update 경로/cwd/중복 실행 점검 및 수정
  - scope: stage01_daily_update.py, launchd, RUNBOOK, STAGE1_RULEBOOK_AND_REPRO
  - proof: updated stage01_daily_update.py + RUNBOOK + STAGE1_RULEBOOK_AND_REPRO; py_compile ok; import-from-/tmp verified absolute status path and blog/telegram opt-in boundary; launchctl confirmed dedicated blog/telegram jobs

- [x] DONE: JB-20260308-STAGE1CLEAN Stage1 미사용 레거시 정리
  - scope: unused launch agents / obsolete profile-transition leftovers / doc mismatches
  - note: phase: SUBAGENT_LAUNCHED
  - note: auto-orchestrate run_id=20260308082810
  - proof: removed unused live LaunchAgent com.jobiseu.openclaw.invest.pipeline.stage1-4.chain-daily.plist; cleaned RUNBOOK legacy env refs

- [x] DONE: JB-20260308-STAGE1PROF Stage1 프로필형 orchestrator 및 selected articles 백필 cadence 정리
  - scope: stage01_daily_update.py, launchd plists/sh, selected articles backfill scheduling, docs
  - blocked: subagent spawned (agent:main:subagent:b1273769-ace2-481e-ba9b-b580d26807d5); implementation and verification result pending before safe close
  - proof: stage01_daily_update profile orchestration + news_backfill skip-existing/backfill chain + com.jobiseu.invest.stage1.backfill.news(1800s) verified by py_compile/bash -n/plutil

- [x] DONE: 2 컨텍스트 리셋 복구 게이트/현재작업 스냅샷 강화
  - scope: scripts/context_policy.py, docs/operations/*, runtime/current-task.md, scripts/README.md
  - proof: scripts/context_policy.py, AGENTS.md, docs/operations/CONTEXT_LOAD_POLICY.md, docs/operations/CONTEXT_RESET_READLIST.md, docs/operations/OPERATIONS_BOOK.md, scripts/README.md, runtime/current-task.md

- [x] DONE: 3 메인브레인가드 설계/문서화 및 task watchdog 운영 점검
  - scope: docs/operations/*, scripts/tasks/*, launchd 상태, runtime/tasks/* 점검 및 정리
  - proof: py_compile: scripts/tasks/dispatch_tick.py,scripts/tasks/watchdog_validate.py,scripts/tasks/watchdog_recover.py; watchdog_validate: ok=true; launchctl: com.jobiseu.openclaw.tasks.auto-dispatch/com.jobiseu.openclaw.invest.stage01.watchdog/com.jobiseu.openclaw.heartbeat.local-brain-guard loaded; files: docs/operations/MAIN_BRAIN_GUARD.md,runtime/tasks/README.md,scripts/tasks/dispatch_tick.py,scripts/tasks/launchd_watchdog.sh

- [x] DONE: JB-20260304-024 실거래 체결 일치 보장 모드 구축(체결원장 강제 + 불일치 FAIL-CLOSE)
  - proof: owner_decision_20260306_no_live_trade_out_of_scope

- [x] DONE: JB-20260305-016 Stage2~6 레거시 하드 정리(표식 유지가 아닌 실제 삭제)
  - scope: 비운영/레거시 파일 실삭제 + 참조 0 재검증 + docs canonical 정리
  - proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE2_TO_6_LEGACY_HARD_CLEANUP_20260305_0901.md

- [x] DONE: JB-20260308-CTX01 context_policy.py ROOT 하드코딩 제거 및 runtime_env 경로계산 리팩터링
  - scope: scripts/context_policy.py, scripts/lib/runtime_env.py
  - proof: scripts/context_policy.py, scripts/lib/runtime_env.py; python3 scripts/context_policy.py {show,reload,decide,resume-check}; no hardcoded workspace path

- [x] DONE: JB-20260308-GIT01 tracked-ignore 파일 Git 추적 해제
  - scope: .gitignore에 걸리지만 tracked 상태인 파일들 untrack
  - proof: git rm --cached + commit 4b85b8762 (untrack ignored private artifacts); local files preserved; git ls-files target empty

- [x] DONE: JB-20260305-015 Stage2~6 구조/레거시/문서 1:1 정합성 전수 정리
  - scope: stage2~6 canonical 구조 점검, 레거시 제거, docs 1:1 경로 매치 및 일관성 정리
  - proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE2_TO_6_STRUCTURE_LEGACY_DOCS_AUDIT_20260305_0847.md

- [x] DONE: JB-20260305-029 TASKS 연속실행 체인(완료 후 다음 티켓 자동착수)
  - scope: TASKS DONE 게이트 준수, JB-024/025/026/027 상태 동기화, 실행가능 티켓 순차 처리 후 blocked/대기 정리
  - proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE_TASK_PROGRESS_CHAIN_20260305.md, invest/stages/stage1/outputs/reports/stage_updates/STAGE_TASK_024_027_STATUS_SYNC_20260305_161844.md

- [x] DONE: JB-20260305-024 Google Trends 완전 제외 + Stage1~6 참조 제거
  - scope: stage1 수집/검증/stage3~6 입력·점수에서 trends 의존 제거, 문서 동기화, 스모크 검증
  - proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE_TASK_024_025_STATUS_SYNC_20260305_155043.md, invest/stages/stage1/outputs/reports/stage_updates/_jb024_recheck_google_trends_operating_20260305_161844.txt, invest/stages/stage1/outputs/reports/stage_updates/_jb024_recheck_google_trends_docs_20260305_161844.txt, invest/stages/stage1/outputs/reports/stage_updates/STAGE_TASK_024_027_STATUS_SYNC_20260305_161844.md

- [x] DONE: JB-20260305-032 Stage2 폴더구조(signal/qualitative) 복구 + 정제규칙 강화
  - scope: Stage2 onepass 출력 경로를 signal/qualitative 체계로 정합화하고, 데이터 종류별(ohlcv/supply/dart/news/text/image/premium) 정제 규칙 강화 후 재실행 검증
  - proof: subagent runId=365f39a0-b911-416f-85b8-6ff7981ac189, invest/stages/stage2/outputs/reports/stage_updates/STAGE2_STRUCTURE_AND_RULE_HARDENING_20260305.md, invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_20260305_212951.json

- [x] DONE: JB-20260305-028 Stage1 검증 게이트 fail-close 하드닝
  - scope: post_collection_validate 확장, checkpoint_gate exit code 연동, run_stage1234_chain에 Stage1 gate 배선
  - proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE1_FAIL_CLOSE_GATE_HARDENING_20260305_125612.md

- [x] DONE: JB-20260305-031 텔레그램 제외 Stage1 데이터 수집 완료 즉시 보고 게이트
  - scope: 텔레그램 제외 수집(kr/us 시세·수급·DART·매크로·뉴스·블로그·프리미엄) 완료 시 담당 서브에이전트가 즉시 완료 보고
  - proof: superseded_by_JB-20260306-005_full_stage1_including_telegram

- [x] DONE: JB-20260305-026 Stage1 데이터 기간 커버리지 전수 감사(파일기준/내용기준 분리)
  - scope: signal/qualitative 전 항목 최소일·최대일·기간(년) 산출, PASS/FAIL/N/A 판정, 미수집 목록 확정
  - note: 완전 수집 기준 미충족 상태로 재검증/갱신 계속 진행
  - proof: merged_into_JB-20260306-005_coverage_audit_included

- [x] DONE: JB-20260305-023 Stage1 raw signal/qualitative 분리 마감 + 텍스트 수집기(telegram/blog) 복구 + 지표확장
  - scope: 경로 분리, 수집기 복구, 버핏/신용오실레이터 추가, stage2~3 연동 검증
  - proof: merged_into_JB-20260306-005_and_JB-20260305-022

- [x] DONE: JB-20260305-027 Stage1 미수집 항목 백필(가능 범위)
  - scope: 026 FAIL 항목 중 수집 가능 소스 백필 실행, 불가 항목은 blocked/미확인 사유 고정
  - note: 10년 확장 지시 반영으로 collector 코드 수정+실행검증 재진행
  - proof: merged_into_JB-20260306-005_backfill_scope_included

- [x] DONE: JB-20260306-001 DIRECTIVES 프로그램 전환(SQLite) + 강제 게이트
  - scope: DIRECTIVES.md를 DB SSOT로 전환하고 등록/상태전이를 CLI로 강제
  - proof: scripts/directivesdb.py, scripts/directives_gate.py, runtime/directives/README.md, runtime/directives/directives_archive.md

- [x] DONE: JB-20260306-002 Stage1 텔레그램 첨부(레포트/이미지) 본문 추출 + Stage2 연동
  - scope: 텔레그램 링크/첨부 레포트/이미지 본문 추출로 누락 최소화 후 Stage2 재정제
  - proof: Updated docs for DB SSOT alignment: AGENTS.md; docs/openclaw/CONTEXT_LOAD_POLICY.md; docs/openclaw/CONTEXT_RESET_READLIST.md; docs/openclaw/RULES_INDEX.md; docs/openclaw/WORKSPACE_STRUCTURE.md. Removed QUICK RESUME SNAPSHOT/NOW ACTIVE wording; verified 0 refs for TASKS_ACTIVE.md/TASKS_RULES.md in target files.

- [x] DONE: JB-20260306-004 Git 추적 제외 확대(stage1/stage3 고변동 산출물)
  - scope: 고변동 output/input 산출물 추적 제외 및 cached 해제로 dirty 최소화
  - blocked: owner_pause_non_stage1
  - proof: commit:367785149 untrack stage1/stage3 generated artifacts + .gitignore/README policy

- [x] DONE: JB-20260306-099 E2E auto dispatch test ticket
  - scope: orchestration
  - proof: runtime/tasks/proofs/JB-20260306-099.txt

- [x] DONE: 4 메인브레인가드 상위 집계 스크립트 + Telegram 채널 health-check 구현
  - scope: scripts/heartbeat/* 또는 대응 상위 guard 스크립트, docs/operations/*, 상태 JSON 집계
  - proof: Implemented main brain guard aggregator in scripts/heartbeat/main_brain_guard.py; updated docs/operations/MAIN_BRAIN_GUARD.md, HEARTBEAT.md, and memory/2026-03-07.md; verified with 'python3 -m py_compile scripts/heartbeat/main_brain_guard.py' (ok) and 'python3 scripts/heartbeat/main_brain_guard.py' (ok=true; local_brain/telegram/watchdog/auto_dispatch/current_task all OK).

- [x] DONE: JB-20260307-004 invest launchd 자동수집 운영화 + 재현문서 + 검증체계
  - scope: launchd 기반 자동수집 운영 설계/구현. 데이터셋별 주기, 10년 백필→incremental 전환, 파일명 규칙, 이미지/OCR 후처리, postprocess 검증, 재현 가능한 운영/실행/검증 문서 포함.
  - proof: 문서/구현/검증 완료. Proof: invest/docs/AUTOCOLLECT_OPERATIONS.md ; invest/ops/launchd/jobs.registry.json ; invest/ops/launchd/env/invest_autocollect.env.example ; invest/ops/launchd/plists/com.jobiseu.invest.*.plist ; invest/stages/stage1/scripts/stage01_ocr_postprocess_validate.py ; invest/stages/stage1/scripts/stage01_post_collection_validate.py ; invest/stages/stage1/scripts/stage01_run_images_ocr_rolling.py ; invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh ; 검증: py_compile 통과, OCR validator 실행 확인, post_collection_validate는 현재 raw/signal/kr/supply freshness 초과로 운영 데이터 이슈 확인.
