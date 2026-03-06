# DIRECTIVES.md

⚠️ TOKEN GUARD (강제):
- 기본 로드 범위는 **상단 QUICK RESUME SNAPSHOT (L1)** 까지만.
- 아래 상세 원문(P1/P2/P3)은 **증빙 확인/상태 변경 시에만** 필요한 구간만 부분 조회.
- 리셋 직후 전체 스크롤/전체 읽기 금지.

주인님 지시 원문/요약을 누락 없이 기록하는 고정 로그.

## 기록 규칙
- 모든 지시를 수신 즉시 1줄로 추가
- 필드: `time | message_id | directive | due | status | first_action | proof`
- 상태: `OPEN | IN_PROGRESS | DONE | BLOCKED`
- 완료 시 반드시 proof(파일/리포트 경로) 기입
- 임의 룰 추가 시 코드 폐기 (주인님 명령/Rulebook 미근거 규칙 삽입 금지)
- proof에 `archive legacy path(invest/scripts/...)`가 보이면 과거 증빙 경로 표기이며, 현재 canonical 실행 경로는 `invest/stages/**/scripts/` 기준으로 해석한다.

## QUICK RESUME SNAPSHOT (L1)
- 상태 합계: `IN_PROGRESS 21 / DONE 49`
- P1 현재 진행중 핵심
  - 4947: 11단계·운영선정 규칙 혼선 재발 방지 (proof: memory/2026-02-18.md)
  - 5053: 4/5 게이트 통과 후 Git 업데이트 선행 (proof: -)
- P2 현재 진행중 핵심
  - 3530: 제출물 비교표 3종 필수 포함
  - 3579: 커뮤니티/특이점 사례조사
  - 3780: 단계별 브레인스토밍 확정안 운영
- 사용 규칙: 리셋 직후에는 이 섹션만 먼저 확인 후, 필요 시 원문 항목 상세 확인

## Priority Buckets (WIP=1)

### P1-오늘 (정확히 1개)
- 2026-02-18 20:00 | 6149 | 컨텍스트 한도 초과 재발방지책 수립 후 문서에 기록 | 즉시 | DONE | first_action: 토큰 예산/출력 상한/분할응답/사전 점검 규칙을 memory에 고정 반영 | proof: memory/2026-02-18.md, MEMORY.md
- 2026-02-18 16:17 | 5844 | 진행 보고 포맷 고정(단계 종료/시작 또는 실패/재시도만 초간단 보고) | 즉시 | DONE | first_action: 이후 단계 보고를 지정 포맷으로만 전송 | proof: -
- 2026-02-18 15:47 | 5807 | 답변 길이 규칙 고정(짧은건 1회, 긴건 시작/종료 2회 보고) | 즉시 | DONE | first_action: 이후 모든 응답 cadence를 신규 규칙으로 적용 | proof: -
- 2026-02-18 15:46 | 5806 | 다른 계열 검증 결과 즉시 보고 | 즉시 | IN_PROGRESS | first_action: Opus/Sonnet/agpro 단계별 감사 결과를 PASS/FAIL로 요약 보고 | proof: -
- 2026-02-18 15:23 | 5783 | 7단계/8단계 진행(승급 포함) | 즉시 | DONE | first_action: stage07/stage08 QC --promote 실행 | proof: invest/results/validated/stage07_candidates_cut.json, invest/results/validated/stage08_purged_cv_oos.json
- 2026-02-18 15:19 | 5775 | 8단계 브레인스토밍 기반 설계 문서화(재현필드 완비) + 다른 계열 검증 | 즉시 | DONE | first_action: Stage08(Purged CV/OOS) 설계 브레인스토밍 3모델 후 canonical 문서 작성 및 비-Codex 교차검증 수행 | proof: invest/reports/stage_updates/stage08/stage08_purged_cv_oos.md, archive legacy path(invest/scripts/stage08_purged_cv_oos.py), archive legacy path(invest/scripts/stage08_purged_cv_oos_qc.py), invest/results/validated/stage08_purged_cv_oos.json
- 2026-02-18 15:13 | 5761 | 7단계 브레인스토밍 후 설계 문서 작성 + 자체검증 필요 시 포함 설계 | 즉시 | DONE | first_action: Stage07 컷 기준 브레인스토밍 3모델 실행 후 canonical 문서/자체검증 스크립트 설계 반영 | proof: invest/reports/stage_updates/stage07/stage07_candidate_stage_cut.md, archive legacy path(invest/scripts/stage07_candidate_stage_cut.py), archive legacy path(invest/scripts/stage07_candidate_cut_qc.py), invest/results/validated/stage07_candidates_cut.json
- 2026-02-18 14:04 | 5658 | 5단계 문서 참조 기반으로 6단계 설계 브레인스토밍 후 문서 업데이트 | 즉시 | DONE | first_action: stage05 baseline/pass 문서를 입력으로 stage06 canonical 문서를 템플릿 필드 포함 형태로 재작성 | proof: invest/reports/stage_updates/stage06/stage06_candidate_gen_v1.md, invest/reports/stage_updates/STAGE06_ENTRY_PREP_20260218.md
- 2026-02-18 14:11 | 5671 | heartbeat가 메인작업을 멈추지 않도록 복귀루틴을 문서가 아닌 강제 절차로 수정 | 즉시 | OPEN | first_action: foreground anchor/heartbeat 분리/3분 복귀 타임박스 규칙을 SOP+readlist에 강제 반영 | proof: invest/docs/operations/OPERATIONS_SOP.md, docs/openclaw/CONTEXT_RESET_READLIST.md, runtime/foreground_anchor.json
- 2026-02-18 14:52 | 5705 | Stage06 설계 기준으로 실제 실행 진행 | 즉시 | DONE | first_action: stage06 생성 스크립트/검증 스크립트 준비 후 실행 | proof: archive legacy path(invest/scripts/stage06_candidate_gen_v1.py), archive legacy path(invest/scripts/stage06_candidate_qc.py), invest/results/validated/stage06_candidates.json
- 2026-02-18 13:42 | 5637 | 리팩토링 명목으로 미뤄진 지시(함수별 입출력/기능 주석 명시, 문서 리팩토링) 즉시 재개 및 누락 없이 처리 | 즉시 | OPEN | first_action: 미이행 항목 인벤토리 작성 후 코드 주석 반영 범위/문서 리팩토링 범위 확정 | proof: -
- 2026-02-18 05:45 | 4947 | 지시/합의사항(특히 11단계·운영선정 규칙) 즉시 문서화하고 동일 혼선 재발 금지 | 상시 | IN_PROGRESS | first_action: memory/2026-02-18.md에 합의 규칙(택1 운영, 4→5 반복, 예외 시 2→3 재진입) 고정 기록 | proof: memory/2026-02-18.md
- 2026-02-18 05:52 | 4969 | 1번 단계를 수집으로 고정하고 단계 문서 전체를 재정렬/업데이트 | 즉시 | DONE | first_action: stage 문서 번호/명칭을 11단계 canonical에 맞게 재작성 | proof: invest/reports/stage_updates/README.md, stage01_data_collection.md ~ stage11_adopt_hold_promote.md, invest/docs/strategy/RULEBOOK_V1_20260218.md
- 2026-02-18 05:53 | 4970 | 컨텍스트 비운 뒤 먼저 읽을 문서 목록을 메모리에 고정 | 즉시 | DONE | first_action: memory/2026-02-18.md에 재로딩 체크리스트 추가 | proof: memory/2026-02-18.md
- 2026-02-18 06:03 | 4996 | stage01~04 명시 게이트 브레인스토밍 후 문서 반영, 실제 동작 점검 1회 실행 | 즉시 | DONE | first_action: stage02~04 gate 설계/반영 후 gate-check 스모크 실행 | proof: invest/reports/stage_updates/stage02/stage02_data_cleaning.md, stage03_cleaning_validation.md, stage04_validated_value.md, archive legacy path(invest/scripts/stage_gate_check_1to4.py) 실행결과(SUMMARY:FAIL, stage04:grade_present:FAIL)
- 2026-02-18 06:05 | 5001 | RULEBOOK/Stage 문서 추가·수정 필요점 브레인스토밍 후 적용 | 즉시 | DONE | first_action: RULEBOOK의 운영선정/충돌룰 모순 제거 + stage gate 연결 섹션 추가 + README 동기화 + gate-check 재실행 | proof: invest/docs/strategy/RULEBOOK_V1_20260218.md, invest/reports/stage_updates/README.md, archive legacy path(invest/scripts/stage_gate_check_1to4.py) 실행결과(SUMMARY:FAIL, stage04:grade_present:FAIL)
- 2026-02-18 06:13 | 5009 | OpenClaw 시스템/폴더/설정 문서를 invest 밖에 작성하고 컨텍스트 초기화 시 강제 재로딩 규칙 추가 | 즉시 | DONE | first_action: 시스템 브레인스토밍 후 baseline 문서 2종 작성 + AGENTS/메모리 체크리스트 반영 | proof: docs/openclaw/OPENCLAW_SYSTEM_BASELINE.md, docs/openclaw/WORKSPACE_STRUCTURE.md, docs/openclaw/CONTEXT_RESET_READLIST.md, AGENTS.md
- 2026-02-18 06:17 | 5017 | 시스템/알고리즘 변경 시 문서 업데이트 강제 | 상시 | DONE | first_action: AGENTS.md에 Documentation Sync Gate 추가 | proof: AGENTS.md
- 2026-02-18 06:20 | 5027 | 문서는 전부 재현 가능한 수준으로 작성 | 상시 | DONE | first_action: stage/rulebook/openclaw 문서에 실행·입력·출력·게이트·증빙 필드 점검 및 누락 보강 | proof: AGENTS.md Documentation Sync Gate(재현 필드 최소요건 명시), memory/2026-02-18.md
- 2026-02-18 06:22 | 5033 | 시스템 불필요 파일 브레인스토밍 후 제거 | 즉시 | DONE | first_action: 안전 대상(캐시/컴파일 산출물) 선별 후 trash 이동 | proof: workspace 전체 __pycache__/pyc/.DS_Store 제거 확인(find 결과 없음)
- 2026-02-18 06:24 | 5037 | 폴더구조 적합성 브레인스토밍 후 문제 없이 수정 | 즉시 | DONE | first_action: 실제 디렉터리 트리와 문서 기준 비교 후 불일치 문서만 수정 | proof: docs/openclaw/WORKSPACE_STRUCTURE.md
- 2026-02-18 06:25 | 5038 | 문서 추가/보강 필요점 브레인스토밍 후 점검 | 즉시 | DONE | first_action: docs/openclaw + stage/rulebook 대상 갭 분석 후 추가/보강안 반영 | proof: docs/openclaw/DOCS_MAINTENANCE_PLAYBOOK.md, docs/openclaw/CONTEXT_RESET_READLIST.md, invest/reports/stage_updates/stage02/stage02_data_cleaning.md, stage03_cleaning_validation.md, stage04_validated_value.md
- 2026-02-18 06:30 | 5051 | 메모리 파일 보강 필요점 브레인스토밍 및 반영 | 즉시 | DONE | first_action: MEMORY/memory/*.md 갭 점검 후 최소 보강안 적용 | proof: MEMORY.md(2026-02-18 섹션 추가), memory/INDEX.md(2026-02-17/18 인덱스 보강)
- 2026-02-18 06:31 | 5053 | 4/5 게이트 통과 후 Git 업데이트 선행, 그 다음 리팩토링 진행 | 상시 | IN_PROGRESS | first_action: 4/5 게이트 통과 확인 전에는 리팩토링 제안/실행 보류, 통과 즉시 git 업데이트부터 수행 | proof: -
- 2026-02-18 07:09 | 5132 | 리팩토링 시 input/output path 안정성 보장 | 리팩토링 시점 | DONE | first_action: 경로 변경 시 alias/호환레이어 유지 + run/gate/manfiest 경로 회귀검증 포함 | proof: invest/reports/stage_updates/REFACTOR_FINAL_REPORT_20260218_FLASH.md
- 2026-02-18 07:11 | 5138 | 리팩토링 누락 파일 전수 탐색/검증 | 리팩토링 종료 전 | DONE | first_action: 네이밍 룰 기준 전체 파일 스캔 후 미반영 목록/수정 목록 리포트 생성 | proof: invest/reports/stage_updates/REFACTOR_FINAL_REPORT_20260218_FLASH.md
- 2026-02-18 07:36 | 5157 | 미완료 작업 종료 시 남은 할일+다음 제안 자동 포함 규칙 고정 | 즉시 | DONE | first_action: SOP에 종료보고 제안 규칙 추가 | proof: invest/docs/operations/OPERATIONS_SOP.md 섹션 8
- 2026-02-18 07:42 | 5165 | 검수코드/중요작업은 다른 계열 고성능 모델에 교차 배정 규칙 추가 | 즉시 | DONE | first_action: SOP에 교차모델 배정 규칙 신설 | proof: invest/docs/operations/OPERATIONS_SOP.md 섹션 9
- 2026-02-18 07:43 | 5167 | 구버전 지시 잔존/충돌 재발 방지 규칙 문서화 | 즉시 | DONE | first_action: SOP에 지시 충돌 정리 절차(상태전환+해소메모+proof보강) 추가 | proof: invest/docs/operations/OPERATIONS_SOP.md 섹션 10
- 2026-02-18 07:52 | 5185 | 정시/예약 보고의 REPORT_QUEUE 선등록 누락 재발 방지 | 즉시 | DONE | first_action: SOP에 선등록 규칙 추가 + 08:00 pending 즉시 등록 | proof: invest/docs/operations/OPERATIONS_SOP.md 섹션 11, TASKS.md REPORT_QUEUE
- 2026-02-18 08:01 | 5199 | 문서별 포맷 표준 확정 | 즉시 | DONE | first_action: 문서 유형별 템플릿(단계/운영/리포트) 표준 문서 신설 및 readlist 연동 | proof: docs/openclaw/DOC_TEMPLATES.md, docs/openclaw/CONTEXT_RESET_READLIST.md
- 2026-02-18 08:11 | 5221 | 정시 보고 완료 후 PENDING 잔존 경고 재발 방지 | 즉시 | DONE | first_action: TASKS REPORT_QUEUE 즉시 종료 반영 + 점검 크론에 자동정리/재알림 억제 규칙 추가 | proof: TASKS.md 08:00 DONE_REPORT, cron job 531714af payload update
- 2026-02-18 08:22 | 5234 | US OHLCV freshness 오탐 재발 방지 | 즉시 | DONE | first_action: post_collection_validate의 US freshness 룰에 KST 장중/비장중 분기 임계치 적용 | proof: archive legacy path(invest/scripts/post_collection_validate.py), 실행검증 ok=true (08:22)
- 2026-02-18 08:54 | 5256 | 리팩토링 우선, 기타 4개 블록 처리 후 본작업 집중 | 즉시 | DONE | first_action: 추가 대응은 4개 블록으로 제한하고 리팩토링 본작업 시간 블록 고정 | proof: invest/reports/stage_updates/REFACTOR_FINAL_REPORT_20260218_FLASH.md
- 2026-02-18 07:47 | 5173 | 특갤 참고사항 중 적용가능 항목 선별·반영 | 즉시 | DONE | first_action: 우회팁 제외, 운영원칙(작업성격별 모델모드 선택/임시복구 핸들링)만 문서 반영 | proof: docs/openclaw/OPERATING_GOVERNANCE.md
- 2026-02-18 06:43 | 5079 | 네이밍 룰 우선 수립 | 즉시 | DONE | first_action: 파일/함수/리포트/매니페스트 네이밍 초안 제시 후 승인받기 | proof: docs/openclaw/NAMING_STRATEGY.md, docs/openclaw/CONTEXT_RESET_READLIST.md
- 2026-02-18 06:47 | 5089 | 코딩 룰 브레인스토밍 후 고정 | 즉시 | DONE | first_action: 운영/재현/게이트 중심 코딩 룰 초안 작성 | proof: docs/openclaw/CODING_RULES.md, docs/openclaw/CONTEXT_RESET_READLIST.md
- 2026-02-18 06:49 | 5093 | 운영전략(게이트/SOP/SLA/Git) 브레인스토밍 후 문서 고정 | 즉시 | DONE | first_action: 상위 운영 문서에 4개 기준을 canonical로 추가 | proof: docs/openclaw/OPERATING_GOVERNANCE.md, docs/openclaw/CONTEXT_RESET_READLIST.md, invest/docs/operations/OPERATIONS_SOP.md
- 2026-02-17 10:34 | 3737 | 작업 순서를 순차 처리로 고정(꼬임 방지) | due 해제(주인님 지시) | IN_PROGRESS | first_action: 1) 데이터 정제 완료 2) 정제 검증 3) VALIDATED 밸류 산출 4) 비교표/후속 작업 순서로 진행 | proof: -

### P2-이번주
- 2026-02-17 05:57 | 3530 | 제출물에 피처 비교표 3종(내vs이웃 점수/기여도·방향성/clean 전후 차이열) 필수 포함 | due 해제(주인님 지시) | IN_PROGRESS | first_action: `invest/results/validated|test`에서 내지표/이웃지표 결과 파일 경로 확정 후 표 템플릿 생성 | proof: -
- 2026-02-17 05:42 | 3500 | 완료 최우선 + 남는 시간 자동 검증/로그 안정화 보강 | due 해제(주인님 지시) | IN_PROGRESS | first_action: `archive legacy path(invest/scripts/)` 자동검증 스크립트 실행 로그 경로 1차 수집 | proof: -
- 2026-02-17 06:21 | 3579 | OpenClaw 커뮤니티+특이점이온다에서 동일 문제 사례/해결안 조사 | due 해제(주인님 지시) | IN_PROGRESS | first_action: OpenClaw Discord/GitHub/특이점이온다 게시글 근거 링크 수집 후 5줄 요약 작성 | proof: -
- 2026-02-17 10:53 | 3780 | 전체 프로세스/후보 선정 단계별 브레인스토밍 후 확정안으로 진행 | due 해제(주인님 지시) | IN_PROGRESS | first_action: 후보 생성→필터→검증→채택 전 과정을 다모델 브레인스토밍으로 설계 | proof: -
- 2026-02-17 10:57 | 3784 | 각 단계 완료 시 타 모델 교차검증 필수, 지표 기준 임의변경·DRAFT 사용 전면 차단 | 상시 | IN_PROGRESS | first_action: 단계별 `교차검증 체크포인트`와 `DRAFT 차단 게이트`를 SOP에 고정 반영 | proof: -
- 2026-02-17 10:59 | 3786 | 동일 지표의 내/이웃 기준 불일치 재발 금지, DRAFT 데이터의 학습/평가 입력 전면 금지 | 상시 | IN_PROGRESS | first_action: 공통 지표 스키마 단일화 + 입력 게이트에서 `grade!=VALIDATED` 즉시 차단 규칙 추가 | proof: -
- 2026-02-17 11:00 | 3788 | 교차검증은 칭찬성 확인이 아닌 질적 검증(가정/데이터/통계/실행리스크 반증)으로 수행 | 상시 | IN_PROGRESS | first_action: 단계별 `질적 검증 체크리스트`(반증 질문+실패 시나리오+재현성)를 필수 게이트로 추가 | proof: -
- 2026-02-17 11:05 | 3797 | 단기 사용 목적보다 전 단계 완결 후 최고 성능 모델 목표로 진행 | due 해제(주인님 지시) | IN_PROGRESS | first_action: 중간 타협 없이 정제→검증→밸류→후보컷→질적검증→최종선정 전체 완료 기준으로 계획 고정 | proof: -
- 2026-02-17 11:06 | 3799 | 전체 작업 명칭을 '알고리즘개발프로젝트'로 통일 | 상시 | IN_PROGRESS | first_action: 보고/문서/체크리스트 헤더를 `알고리즘개발프로젝트` 명칭으로 표준화 | proof: -
- 2026-02-17 11:12 | 3803 | 08:00~22:00 매시 정기 보고 규칙(블로그/텔레 상세·핫이슈 유무·단계%·문제점 해결상태) 고정 | 상시 | IN_PROGRESS | first_action: `간이보고(1시간)` 크론의 시간대/포맷을 새 규칙으로 업데이트 | proof: cron job `86edd049-b00d-4547-b904-1b2d29a5aa20` updated
- 2026-02-17 11:17 | 3809 | GitHub에 보고 폴더 생성(시간별/일일/주간) 및 알아보기 쉬운 파일명으로 업데이트 | 상시 | DONE | first_action: `reports/algorithm_dev_project/{hourly,daily,weekly}` 생성 후 보고 크론 저장 경로/파일명 규칙 업데이트 | proof: commit `c961ae8`, cron `86edd049` `77f38f52` `84cfae2b` updated
- 2026-02-17 11:19 | 3813 | 보고는 수집운영 일반현황이 아니라 알고리즘개발프로젝트 중심으로 작성 | 상시 | IN_PROGRESS | first_action: 시간별/일일/주간 보고 프롬프트에 '프로젝트 단계/검증/결정/리스크' 중심 규칙을 강제 반영 | proof: cron `86edd049` `77f38f52` `84cfae2b` updated
- 2026-02-17 11:21 | 3815 | 폴더명/파일명에서 '알고리즘' 명칭 제거, 단순 시간별/일일/주간 네이밍 사용 | 즉시 | DONE | first_action: 저장 경로를 `reports/{hourly,daily,weekly}`로, 파일명을 중립 규칙으로 변경 | proof: commit `9788d1c`, cron `86edd049` `77f38f52` `84cfae2b` updated
- 2026-02-17 11:22 | 3817 | 3814 메시지 맥락은 보고 내용 수정 지시가 아니었음(의도 오해 금지) | 즉시 | DONE | first_action: 사용자 확인 없이 범위 확장 변경 금지, 애매하면 1문장 확인 후 적용 | proof: reply `3818`(의도 오해 인정/확인 후 수정 원칙 명시)
- 2026-02-17 11:32 | 3825 | 알고리즘 보고 시 1단계부터 전체 나열 + 단계별 진행바(예: ■■■□□□50%), 단계 완료마다 별도 업데이트 보고서 생성(예: 내지표 vs 이웃지표 표) | 상시 | DONE | first_action: 시간별/일일 보고 포맷과 단계완료 리포트 규칙을 크론 프롬프트/보고 폴더에 반영 | proof: cron `86edd049` `77f38f52` updated, commit `d176d97`
- 2026-02-17 11:33 | 3826 | 단계완료 보고는 GitHub 업데이트 + 보고채널 전송을 동시에 수행 | 상시 | DONE | first_action: `invest/reports/stage_updates/` 생성 후 단계완료 시 별도 파일 저장 및 채널 별도 보고 규칙 추가 | proof: `invest/reports/stage_updates/README.md`, cron `86edd049` 단계완료 별도 메시지 규칙 반영
- 2026-02-17 11:40 | 3832 | 진행 보고 기준을 6단계가 아닌 10단계로 통일 | 상시 | IN_PROGRESS | first_action: 시간별/일일 보고 프롬프트의 단계 나열/진행바를 10단계 기준으로 변경 | proof: -
- 2026-02-17 11:46 | 3844 | 대회 평가셋 3개를 블라인드 데이터로 구성하고 대회 기준 점수/등수 수준 산출 | 상시 | DONE | first_action: 대회 3종 선정 후 공통 평가 매핑표(점수→등수구간) 설계 및 블라인드 홀드아웃 구축 | proof: message `3951` 지시로 대회 블라인드 사용 중단, 국내 시장 하이브리드 블라인드로 전환
- 2026-02-17 11:47 | 3848 | 전체 프로세스를 11단계(마지막 블라인드 평가 포함)로 확정 | 상시 | IN_PROGRESS | first_action: 시간별/일일 보고 단계 나열을 11단계 기준으로 업데이트 | proof: -
- 2026-02-17 12:06 | 3853 | 블라인드 평가데이터는 한국 대회/한국시장 기준으로 구성 | 상시 | IN_PROGRESS | first_action: 해외 대회 후보 제외, 국내 대회 3종 데이터셋 후보군으로 재선정 | proof: -
- 2026-02-17 12:14 | 3863 | 모델 구조는 이웃지표를 메인으로, 내지표는 보조 룰(필터/가드)로 운용 | 상시 | IN_PROGRESS | first_action: 전략 스키마를 `main=이웃지표, rule=내지표`로 고정하고 비교표/보고서에 역할 분리 명시 | proof: -
- 2026-02-17 12:25 | 3888 | 왕복 패널티 상향 검토 및 적용 | 상시 | DONE | first_action: 3.0% 대비 3.5%/4.0% 민감도 비교 후 기본값 상향안 확정 | proof: 왕복 3~4% 보수 가정 + 교체임계치 병행으로 MEMORY.md 반영
- 2026-02-17 12:26 | 3891 | 종목 교체 빈도 낮은(저회전) 전략 기준으로 브레인스토밍 및 룰 설계 | 상시 | DONE | first_action: 저회전 포트폴리오 룰(홀딩기간/교체 임계치/리밸런싱 주기) 초안 제시 | proof: 교체임계치 +15% 적용 지시(3895) 반영
- 2026-02-17 12:29 | 3899 | 목표가는 질적검증 결과를 계속 반영해 동적 수정되도록 적용 | 상시 | DONE | first_action: 목표가 조정폭 룰(경고 1개당 -3%, 강한 경고 -7%)을 운영 기준에 추가 | proof: MEMORY.md 목표가 운영 항목 반영
- 2026-02-17 12:31 | 3905 | 수익률 KPI 기준은 연평균(CAGR)으로 고정, 목표는 연평균 70% 수준 | 상시 | DONE | first_action: KPI 정의를 CAGR 기준으로 명시하고 목표값 70% 반영 | proof: MEMORY.md KPI 목표 반영
- 2026-02-17 12:32 | 3907 | 2025년은 연수익률 300% 수준 목표로 별도 추적 | 상시 | DONE | first_action: 기본 KPI(연평균 70%)와 분리된 스트레치 목표로 기록 | proof: MEMORY.md 연도별 목표 추가
- 2026-02-17 12:37 | 3921 | 블라인드 무결성 게이트 적용(구간 명시/manifest/학습혼입 차단/해시증빙) | 상시 | DONE | first_action: 블라인드 구간 확정 전 검증 금지, 혼입 시 즉시 실패 규칙 추가 | proof: MEMORY.md 블라인드 무결성 원칙 반영
- 2026-02-17 12:48 | 3947 | 블라인드/질적데이터 정책 충돌 여부 점검 후 단일 원칙으로 확정 | 즉시 | DONE | first_action: 블라인드는 전체 피처 통합 미노출 원칙, 기간 선택은 코로나 제외 가능으로 분리 정리 | proof: reply 3948 정책 단일화 공지
- 2026-02-17 12:48 | 3949 | 블라인드 기간/질적데이터 정책 브레인스토밍 후 확정 | 즉시 | DONE | first_action: 다중 모델 브레인스토밍 3건 병렬 실행 후 단일안 확정 보고 | proof: 하이브리드 확정(특수구간 보존+일반구간 25~30% 통합 블라인드), reply `3953`
- 2026-02-17 12:50 | 3954 | 블라인드 하이브리드 정책(특수구간 보존+일반구간 통합 블라인드) 즉시 적용 | 즉시 | DONE | first_action: 메모리/운영원칙에 하이브리드 정책 및 보조 규칙(시차/롤링/키워드배제) 반영 | proof: MEMORY.md 블라인드 운용 확정 항목 추가
- 2026-02-17 12:51 | 3959 | 대회데이터 블라인드 제외 + 국내 실데이터 하이브리드 블라인드로 최종 확정 | 상시 | DONE | first_action: 대회 기준은 참고치로만 사용, 채택 판단은 국내시장 기준으로 고정 | proof: reply `3956`, `3958`
- 2026-02-17 13:02 | 3970/3976/3980/4010 | 시간별 보고 규칙 통합(5항목 고정포맷+1단계부터 진행바+핫이슈 외부뉴스 기준) | 즉시 | DONE | first_action: 간이보고 크론 프롬프트를 통합 규칙으로 재작성 | proof: cron `86edd049` payload 통합 수정, 보고채널 재전송 messageId `78`, `80`
- 2026-02-17 13:10 | 3987 | 잘못 생성된 `reports/algorithm_dev_project` 폴더 삭제 | 즉시 | DONE | first_action: 해당 폴더 git 삭제 후 커밋/푸시 | proof: commit `604ad38`
- 2026-02-17 13:18 | 3997 | 블로그/텔레그램은 장애여부가 아니라 질적분석(주요내용) 요약으로 보고 | 즉시 | DONE | first_action: 간이보고 크론 프롬프트를 내용 중심 질적요약 규칙으로 수정 후 재실행 | proof: cron `86edd049` payload 수정, 보고채널 messageId `72`
- 2026-02-17 13:20 | 3998 | 지시사항 누락 없이 기억/이행 | 상시 | IN_PROGRESS | first_action: DIRECTIVES.md 상시 점검 유지 + 보고 전 OPEN/IN_PROGRESS 재확인 | proof: -
- 2026-02-17 13:25 | 4007 | 보고서 완벽 재작성 후 승인 받을 수준으로 제출 | 즉시 | DONE | first_action: 질적요약+진행률 분리 방식으로 보고서 재작성 및 보고채널 원문 전송 | proof: `reports/hourly/HOURLY_2026-02-17_1300_KST.md`, 보고채널 messageId `75`
- 2026-02-17 13:55 | 4024 | 기존 value 산출물 삭제(폐기) | 즉시 | DONE | first_action: invest/results 내 value 산출 결과 파일 삭제 후 잔존 확인 | proof: `invest/results` 잔존 파일 3개(`generate_chart.py`, `_governance_smoke.md`, `RESULT_GOVERNANCE.md`)
- 2026-02-17 13:57 | 4028 | 선행 위반/오염 가능 산출물 전량 폐기("다 버려") | 즉시 | DONE | first_action: reports 산출물 및 관련 임시 산출물 일괄 삭제 후 잔존 확인 | proof: reports 잔존 파일 6개(README/.gitkeep만 유지), value 결과는 기존에 전량 삭제 완료
- 2026-02-17 14:42 | 4130 | 전략 보강 항목 즉시 반영(가드레일/게이트) | 즉시 | DONE | first_action: OPERATIONS_SOP에 하드게이트/리니지/무결성/병렬격리 규칙 추가 | proof: `invest/docs/operations/OPERATIONS_SOP.md` 1/4-A/4-B/4-C/4-D 섹션, `invest/docs/architecture/GUARDRAIL_CHECKLIST_V1.md`

### P3-상시
- 2026-02-17 05:50 | 3522 | 주기적으로 할일 체크(정기 점검 루틴 상시 적용) | 상시 | IN_PROGRESS | first_action: 크론 `531714af-c1ee-4852-9966-2e9b62714449` 실행 상태 주기 확인 | proof: cron job active
- 2026-02-17 06:02 | 3542 | 10분 주기 점검 적용 + 본 사태 해결 브레인스토밍 수행 | 즉시 | DONE | first_action: 10분 점검 크론 등록 및 브레인스토밍 반영안 적용 | proof: cron job `531714af-c1ee-4852-9966-2e9b62714449` created, brainstorm 반영: DIRECTIVES.md P1/P2/P3+first_action

## Operating Checklist (경량 강제)
1) 새 지시 수신 → DIRECTIVES.md 즉시 기록
2) 약속/ETA/완료보고 전 P1/P2의 OPEN/IN_PROGRESS 재확인
3) 코드/전략/보고 완료 건은 DONE 전환 시 proof 1개 이상 첨부
4) 타이머(10분) 점검은 유지하되, 이상 징후 있을 때만 알림
- 2026-02-18 16:44 | 5900 | 단계 종료 즉시 다음 단계 자동 연속 실행(중단 금지) | 즉시 | IN_PROGRESS | first_action: 단계 완료 이벤트 직후 다음 단계 실행 트리거 적용 | proof: -
- 2026-02-19 04:49 | 6754 | 씽킹 설정은 컨텍스트 초기화 시 날아갈 수 있음을 메모리에 명시하고, 이후 실행마다 thinking=high를 명시 적용 | 즉시 | IN_PROGRESS | first_action: memory/2026-02-19.md에 운영 메모 추가 후 작업 실행 시 thinking 고정 명시 | proof: memory/2026-02-19.md
- 2026-02-19 07:XX | 6815 | 같은 설정/수치로 왔다갔다(핑퐁) 반복 금지 규칙 메모리 고정 | 즉시 | IN_PROGRESS | first_action: 라운드별 파라미터 변경 로그를 의무화하고 이전 2라운드와 중복 시 FAIL 처리 | proof: memory/2026-02-19.md
- 2026-03-03 22:20 | stage05-v4_6-single-source | Stage05 v4_6 KPI/차트/트레이드 단일 포트폴리오 소스 아키텍처 통합 + validator 하드FAIL 강화 | 즉시 | IN_PROGRESS | first_action: recompute/build_ui/validate 3개 스크립트 단일 소스 파이프라인 연결 및 메트릭 재계산 반영 | proof: -
- 2026-03-03 22:34 | stage05-v4_6-single-source | Stage05 v4_6 KPI/차트/트레이드 단일 포트폴리오 소스 아키텍처 통합 + validator 하드FAIL 강화 | 즉시 | DONE | first_action: 단일소스 JSON 생성 후 summary/UI/chart/trade_events/validator 연동 완료 | proof: archive legacy path(invest/scripts/stage05_full_recompute_v4_6_kr.py), archive legacy path(invest/scripts/stage05_build_ui_v4_6.py), archive legacy path(invest/scripts/stage05_validate_v4_6.py), invest/reports/stage_updates/stage05/v4_6/stage05_portfolio_single_source_v4_6_kr.json, invest/reports/stage_updates/stage05/v4_6/proof/stage05_v4_6_validation_verdict.json
- 2026-03-04 00:08 | stage05-v4_6-v4_7-v4_8-perfect-integrity | v4_6 완전무결(원신호 1:1/매매내역 포함) 고정 후 v4_7·v4_8을 v4_6 복사승계로 재생성, 1회 실행 자동화/하드검증/로컬뇌 검토 완료 | 즉시 | DONE | first_action: v4_6 스크립트 강화(승자신호 매트릭스+gate11+검증강화) 후 v4_7/v4_8 동형승계 및 v4_8 합의파라미터 적용, one-pass 실행증빙 생성 | proof: archive legacy path(invest/scripts/stage05_full_recompute_v4_6_kr.py), archive legacy path(invest/scripts/stage05_validate_v4_6.py), archive legacy path(invest/scripts/stage05_full_recompute_v4_7_kr.py), archive legacy path(invest/scripts/stage05_full_recompute_v4_8_kr.py), archive legacy path(invest/scripts/stage05_run_v4_6_7_8_onepass.py), invest/reports/stage_updates/stage05/v4_6/proof/stage05_v4_6_pipeline_run_proof.json, invest/reports/stage_updates/stage05/v4_7/proof/stage05_v4_7_pipeline_run_proof.json, invest/reports/stage_updates/stage05/v4_8/proof/stage05_v4_8_pipeline_run_proof.json, invest/reports/stage_updates/stage05/proof/stage05_v4_6_7_8_onepass_proof.json, invest/reports/stage_updates/stage05/proof/local_brain_review_v4_6_7_8.md
- 2026-03-04 07:XX | stage05-v4_6-universe-switch-validation | Stage05 v4_6 universe switch gate5를 실계산 기반으로 전환하고 validator 월교체/중복검증 강화 + recompute/build_ui/validate 재실행 | 즉시 | DONE | first_action: gate5 PASS 하드코딩 제거 후 single_source 파생 switch 진단 생성 및 validate 하드체크 추가 | proof: archive legacy path(invest/scripts/stage05_full_recompute_v4_6_kr.py), archive legacy path(invest/scripts/stage05_validate_v4_6.py), invest/reports/stage_updates/stage05/v4_6/summary.json, invest/reports/stage_updates/stage05/v4_6/proof/stage05_v4_6_pipeline_run_proof.json, invest/reports/stage_updates/stage05/v4_6/proof/stage05_v4_6_validation_verdict.json
- 2026-03-04 08:21 | 미확인 | Stage1~4를 코스피·코스닥 전종목 기준으로 완전 정비하고 재실행 후 커버리지 증빙 | 즉시 | IN_PROGRESS | first_action: 전종목 적용 코드 패치+체인 실행+단계별 처리수량 검증을 서브에이전트로 시작 | proof: subagent agent:main:subagent:3aaa3992-aa26-4b2b-a1b4-a2bd5cd91909
- 2026-03-04 08:23 | 미확인 | Stage1~4/Stage5 연결부의 동급 크리티컬 리스크(샘플링/게이트우회/중복오염/경로불일치/실시뮬혼동/fallback stale) 전수 감사 | 즉시 | IN_PROGRESS | first_action: 크리티컬 감사 병행 실행 및 TOP5 즉시차단 항목 도출 | proof: subagent agent:main:subagent:ceff51ab-7d19-44bb-a626-53d58bcfe48f
- 2026-03-04 08:43 | 미확인 | Stage2 파일명/참조를 full 의미로 정리(10pct 오해 제거) + 문서 동기화 | 즉시 | IN_PROGRESS | first_action: stage02_qc_cleaning_10pct.py -> full 명칭 전환 및 체인/문서 참조 업데이트 지시 | proof: sessions_send runId=5a1a25bc-9637-4bb5-8d86-813493952e2e
- 2026-03-04 08:57 | 미확인 | DIRECTIVES.md 토큰가드 문구 추가(리셋 직후 L1만 읽기 강제) | 즉시 | DONE | first_action: 파일 상단에 TOKEN GUARD 섹션 추가 | proof: DIRECTIVES.md 상단 TOKEN GUARD 블록
- 2026-03-04 10:07 | 미확인 | 서브에이전트도 백그라운드 실행 원칙으로 운영해 하트비트 응답 가능 상태 유지 | 즉시 | IN_PROGRESS | first_action: Stage1~4 재개 서브에이전트에 background 실행/저빈도 poll 강제 지시 반영 | proof: subagent runId=79d6d75c-3e0b-4baf-9dac-7f365551cbdd
- 2026-03-04 10:32 | 미확인 | 보고서 기반 남은 우선작업(C2 fail-close, C7 fallback TTL, 재검증, 문서동기화) 즉시 실행 | 즉시 | IN_PROGRESS | first_action: 실행 전용 서브에이전트로 패치+검증 작업 시작 | proof: subagent runId=f25fe247-98a7-4872-8414-901e4dde419c
- 2026-03-04 11:24 | 미확인 | Stage1~4 재실행검증(E2E) 수행 및 패치(A안/C2/C7) 운영경로 확인 | 즉시 | IN_PROGRESS | first_action: run_stage1234_chain 중심 재실행검증 서브에이전트 실행 | proof: subagent runId=a807be0b-c456-4017-8aee-d3401dd5eef7
- 2026-03-04 12:21 | 미확인 | 정성 언급 rolling 30일 threshold(특히 5)의 적정성 백테스트 및 대세상승종목 탈락 여부 분석 | 즉시 | IN_PROGRESS | first_action: 정성 mention 기반 민감도/포착률 분석 서브에이전트 실행 | proof: subagent runId=7805afc8-9978-4467-ac5a-12f94065c8c2
- 2026-03-04 13:44 | 미확인 | Stage2.5 신설(로컬뇌 강제) + Stage1~4(+2.5) in/out 명세 완전화 | 즉시 | IN_PROGRESS | first_action: Stage2.5 스크립트/문서/체크리스트 반영 서브에이전트 실행 | proof: subagent runId=4fab167f-e390-4ade-a9ae-ee1b02acb00c
- 2026-03-04 13:49 | 미확인 | 기존 경로 유지 없이 Stage1~5 구조를 전면 재편(싹 갈아엎기)하고 Stage2.5 로컬뇌 강제 체계로 재구성 | 즉시 | IN_PROGRESS | first_action: 진행중 Stage2.5 작업을 전면 구조이관 작업으로 확장 지시 | proof: TASKS.md JB-20260304-005
- 2026-03-04 13:58 | 미확인 | 레거시/미사용 파일·스크립트·문장 전면 정리 및 구조화 미준수 항목 정렬 + 정합성 보고 | 즉시 | IN_PROGRESS | first_action: cleanup/audit 전용 서브에이전트 실행(스냅샷->정리->검증->보고) | proof: subagent runId=adc0d4f0-c9fe-4d2c-a295-120388a9a420
- 2026-03-04 14:00 | 미확인 | 로컬뇌를 항상 적극 활용해 토큰 절약 우선 운영 | 즉시 | IN_PROGRESS | first_action: 진행중 서브에이전트에 로컬뇌 우선/장문최소화 지시 전송 | proof: sessions_send runId=60a9eeb5-fb3d-4333-93ed-d841ced67975
- 2026-03-04 14:02 | 미확인 | 문서 토큰 절감 구조화(L0/L1/L2 계층 + TOKEN GUARD + 단계문서 상단 요약블록) 적용 | 즉시 | IN_PROGRESS | first_action: 진행중 cleanup 서브에이전트에 문서 계층화 추가 지시 반영 | proof: sessions_send runId=163a2939-1e1f-409e-abc6-885b88a2016e
- 2026-03-04 14:30 | 미확인 | invest/docs 및 stage docs/scripts 정합성 확인 + Stage2.5 설계 문서화 + Stage1~4 실행 검증 | 즉시 | IN_PROGRESS | first_action: 전수 검증/설계/실행 통합 서브에이전트 실행 | proof: subagent runId=0a7b3b61-ffec-426b-9cb1-951b6c782c24
- 2026-03-04 14:49 | 미확인 | docs/scripts 정합성 FAIL 항목(M-01~M-10) 실제 수정 후 PASS 재검증 | 즉시 | IN_PROGRESS | first_action: FAIL 수정 전용 서브에이전트 실행 | proof: subagent runId=575234e7-99c2-41e5-9a93-9ed7a5192922
- 2026-03-04 15:25 | 미확인 | LaunchAgents openclaw plist 구경로(invest/scripts) 교정 + reload + 검증 | 즉시 | IN_PROGRESS | first_action: plist 백업 후 ProgramArguments stage 경로로 일괄 수정/재적재 수행 | proof: subagent runId=622d9564-8312-4b87-9f1f-0ed1b044f37b
- 2026-03-04 15:31 | 미확인 | Stage1부터 순차 실행(1→2→2.5→3→4) 후 문제 여부 검증 보고 | 즉시 | IN_PROGRESS | first_action: 전 단계 실런+검증 전용 서브에이전트 실행 | proof: subagent runId=53fddbca-192e-438b-b3db-39e2a21f8d6f
- 2026-03-04 15:44 | 미확인 | Stage2.5 로컬뇌 기준을 llama_local로 정리하고 뉴스 정성분석을 2.5에서 실질 반영 | 즉시 | DONE | first_action: stage2_5 코드/문서(backend 정책+뉴스신호 반영) 수정 전용 서브에이전트 실행 | proof: reports/stage_updates/STAGE2_5_LLAMA_AND_NEWS_SENTIMENT_FIX_20260304_1551.md, invest/stages/stage2_5_local_brain_attention/scripts/stage02_5_attention_gate_local_brain.py, invest/stages/stage2_5_local_brain_attention/scripts/stage02_5_build_input_jsonl.py
- 2026-03-04 15:50 | 미확인 | Stage2.5에 정성 레이어 확장(telegram/blog/premium 본문, 이벤트태깅, 소스가중치, 중복제거, 매크로감성) 반영 + 재현가능 문서화 | 즉시 | IN_PROGRESS | first_action: 진행중 Stage2.5 개선 서브에이전트에 5항목/문서화/검증 요구 추가 전달 | proof: sessions_send runId=79b5ea69-f118-4e7a-baf6-2ea534fb766f
- 2026-03-04 16:09 | 미확인 | Stage5 입력데이터 정합성(누락/중복/구경로/스키마/신선도) 전수 감사 | 즉시 | DONE | first_action: Stage5 input lineage 감사 서브에이전트 실행 | proof: reports/stage_updates/STAGE5_INPUT_DATA_AUDIT_20260304_1617.md
- 2026-03-04 16:23 | 미확인 | Stage5 감사 FAIL 후속수정(2.5 데이터 우선 생성 후 위 문제 수정) 수행 | 즉시 | DONE | first_action: Stage5 remediation 서브에이전트 실행(2.5→3→5 재연계/게이트/검증) | proof: reports/stage_updates/STAGE5_INPUT_REMEDIATION_20260304_1640.md, subagent runId=f8a1aec4-6c57-45c1-a986-efe049d4404c
- 2026-03-04 16:45 | 미확인 | 굳이 필요없는 수치 논외로 두고 Stage1~5 실제 풀런(1→2→2.5→3→4→5) 후 문제 여부 검증 | 즉시 | IN_PROGRESS | first_action: 전 단계 실제 실행+검증 서브에이전트 실행 | proof: subagent runId=e8a19caf-02ad-41ba-be61-37b1549325fe
- 2026-03-04 16:45 | 미확인 | Stage1~5 풀런에서 Stage5는 baseline_fixed가 아니라 v4_6 baseline 체인(full_recompute/build_ui/validate)으로 검증 | 즉시 | IN_PROGRESS | first_action: 진행중 풀런 서브에이전트에 Stage5 실행대상 v4_6 체인으로 변경 지시 | proof: sessions_send runId=61526555-01cd-44c1-ad66-c9bffa91ee27
- 2026-03-04 16:55 | 미확인 | Stage3/5 임시 가중치(튜닝) 로직 제거 및 튜닝 책임 Stage6 분리 반영 | 즉시 | IN_PROGRESS | first_action: Stage3 COMPOSITE/Stage5 blend 제거 및 문서 동기화 서브에이전트 실행 | proof: subagent runId=b517b28a-141d-4086-a1c5-ece11c962ef2
- 2026-03-04 17:16 | 미확인 | 모델 산출과 종목 매수/매도 데이터 매칭 정합성 검증(Stage5 v4_6 우선) | 즉시 | IN_PROGRESS | first_action: 모델-트레이드 정합 감사 서브에이전트 실행 | proof: subagent runId=4044e447-bc8d-4382-b954-d1f3c67630fe
- 2026-03-04 17:17 | 미확인 | Stage5 입력 스냅샷 존재/신선도 점검 후 stale면 해제 또는 최신화 적용 | 즉시 | IN_PROGRESS | first_action: 진행중 모델-트레이드 정합 감사에 스냅샷 점검/조치 항목 추가 전달 | proof: sessions_send runId=cce86c64-d8aa-4107-81b1-667f98ca223b
- 2026-03-04 17:38 | 미확인 | v4_6 모델-트레이드 정합 FAIL(누락 12건) 즉시 수정 후 재검증 | 즉시 | IN_PROGRESS | first_action: trade event 누락 원인 수정 전용 서브에이전트 실행 | proof: subagent runId=ebb5c91a-f66e-4290-b93e-5515e2f7934a
- 2026-03-04 18:08 | 미확인 | v4_6 매수/매도내역대로 실행 시 알고리즘 수익률 완전동일성(parity) 검증 | 즉시 | DONE | first_action: trade-log vs algo equity parity 감사 서브에이전트 실행 | proof: reports/stage_updates/TRADE_LOG_VS_ALGO_RETURN_PARITY_20260304_1816.md, invest/reports/stage_updates/stage05/v4_6/proof/trade_log_vs_algo_parity_v4_6_20260304_1816.json
- 2026-03-04 18:16 | 미확인 | Stage5 selection_formula를 signal_only에서 COMPOSITE_SCORE 기준으로 전환(튜닝은 Stage6 책임 유지) | 즉시 | IN_PROGRESS | first_action: Stage5 baseline selection 로직 및 문서 수정 서브에이전트 실행 | proof: subagent runId=a83b135d-736b-40f7-984c-be127c184b82
- 2026-03-04 18:38 | 미확인 | Stage5 v4_6 기존 알고리즘 파일로 복구하고 UI 자동갱신 + parity PASS까지 반복 수정 | 즉시 | IN_PROGRESS | first_action: v4_6 복구/자동UI/패리티루프 전용 서브에이전트 실행 | proof: subagent runId=076b5c99-764f-479f-91fb-dc729d90a8e7
- 2026-03-04 18:48 | 미확인 | Core 방식 정성게이트만 적용해 대세상승 종목 생존/탈락 구분 리포트 수행 | 즉시 | IN_PROGRESS | first_action: 기존 합의 기준(Core gate)으로 survivor/drop 분류 작업을 할일로 등록 | proof: TASKS.md JB-20260304-023
- 2026-03-04 19:35 | 미확인 | 실거래체결 일치 보장 모드 적용(원장 강제, 불일치 시 FAIL-CLOSE) | 즉시 | IN_PROGRESS | first_action: execution-ledger strict parity 게이트 구현 작업 시작 | proof: subagent runId=446008a6-3827-4517-b057-b8f59f2ddd38
- 2026-03-04 19:36 | 미확인 | UI winner 그래프와 baseline 동일성 이탈(divergence) 원인 수정 | 즉시 | DONE | first_action: v4_6 UI 데이터소스/계산식 점검 및 수정 서브에이전트 실행 | proof: reports/stage_updates/UI_WINNER_BASELINE_DIVERGENCE_FIX_20260304_1943.md, invest/stages/stage5/scripts/stage05_full_recompute_v4_6_kr.py
- 2026-03-04 19:47 | 미확인 | 폴더구조 이관 미완 잔여분 전면 정리 및 참조 정합화 | 즉시 | IN_PROGRESS | first_action: 잔여 이관 전용 서브에이전트 실행 | proof: subagent runId=603ef30d-92eb-4c3a-935c-cf6801a71b17
- 2026-03-04 20:07 | 미확인 | invest 루트 5개 폴더(data/features/logs/reports/results) 물리 제거 수준으로 완전 이관 | 즉시 | IN_PROGRESS | first_action: top-level 디렉터리 제거 전용 서브에이전트 실행 | proof: subagent runId=743bb1f9-6864-4ca7-8254-07a3fb3c17d3
- 2026-03-04 20:49 | 미확인 | common 임시 적재를 중단하고 data/logs/reports/results를 각 스테이지 제자리로 재배치 | 즉시 | IN_PROGRESS | first_action: common 분해 이관 전용 서브에이전트 실행 | proof: subagent runId=8660db9f-0746-4c95-b7b7-0bf35b054aa5
- 2026-03-04 20:15 | 미확인 | invest 루트 5폴더(data/features/logs/reports/results) 잔존 정정 및 재생성 방지까지 최종 마감 | 즉시 | IN_PROGRESS | first_action: 재생성 원인 스크립트 식별 후 경로 수정/물리 제거/재생성 검증 서브에이전트 실행 | proof: subagent runId=8a4ea9de-05b8-4001-8c5d-291de1e1a04d
- 2026-03-04 23:52 | 미확인 | 불필요 문서 삭제 지시: CHANNEL_SPLIT_RUNBOOK/PROMISE_WATCHDOG 정리 | 즉시 | DONE | first_action: 단독 삭제 가능성 검토 후 참조 동기 정리 포함 삭제 수행 | proof: docs/openclaw/CHANNEL_SPLIT_RUNBOOK.md(removed), docs/openclaw/PROMISE_WATCHDOG.md(removed), docs/openclaw/CONTEXT_RESET_READLIST.md, docs/openclaw/CONTEXT_MANIFEST.json
- 2026-03-04 23:53 | 미확인 | 불필요 문서 슬림화 추가: DOC_TEMPLATES 제거 | 즉시 | DONE | first_action: manifest 참조 제거 후 문서 삭제 수행 | proof: docs/openclaw/DOC_TEMPLATES.md(removed), docs/openclaw/CONTEXT_MANIFEST.json
- 2026-03-04 23:55 | 미확인 | 불필요 문서 슬림화 추가: MODEL_FAILOVER_POLICY 제거 | 즉시 | DONE | first_action: rules_index/manifest 참조 제거 후 문서 삭제 수행 | proof: docs/openclaw/MODEL_FAILOVER_POLICY.md(removed), docs/openclaw/RULES_INDEX.md, docs/openclaw/CONTEXT_MANIFEST.json
- 2026-03-04 23:56 | 미확인 | 불필요 문서 슬림화 추가: DOCS_MAINTENANCE_PLAYBOOK 제거 | 즉시 | DONE | first_action: manifest 참조 제거 후 문서 삭제 수행 | proof: docs/openclaw/DOCS_MAINTENANCE_PLAYBOOK.md(removed), docs/openclaw/CONTEXT_MANIFEST.json
- 2026-03-04 23:57 | 미확인 | docs/openclaw 폴더 불필요 문서 삭제/통합/이동 정리 | 즉시 | IN_PROGRESS | first_action: 문서 슬림화 전용 서브에이전트 실행 | proof: subagent runId=f8b682dc-c5ba-4ff8-b3da-ac24f569db93
- 2026-03-04 23:59 | 미확인 | invest/docs도 동일 슬림화 적용 + git push 정책 문서 위치 교정(contributing/docs/openclaw로 통합) | 즉시 | IN_PROGRESS | first_action: 진행중 문서 슬림화 서브에이전트에 범위확장/정책 재배치 지시 전달 | proof: sessions_send runId=5f104fe5-d3b6-4e4e-875f-b43c45c6eb8c
- 2026-03-05 00:03 | 미확인 | invest archive/assets/automation/report/script 계열 폴더 불필요 여부 전수진단 및 정리안 수립 | 즉시 | IN_PROGRESS | first_action: 진행중 문서정리 서브에이전트에 폴더진단 범위 확장(삭제는 보류, 제안만) | proof: sessions_send runId=465e98bc-4379-4616-971b-3f9d3cdb849f
- 2026-03-05 00:12 | 미확인 | workspace/docs/openclaw/archive 및 workspace/reports 불필요 여부 확인 후 삭제 | 즉시 | DONE | first_action: 대상 폴더 참조/규모 확인 후 삭제 수행, runtime 경로 1건(stage2 REPORT_DIR)을 stage 경로로 보정 | proof: docs/openclaw/archive(MISSING), reports(MISSING), invest/stages/stage2/scripts/stage02_onepass_refine_full.py
- 2026-03-05 00:30 | 미확인 | invest 루트 `assets/automation/archive` 정리 + scripts 레거시 잔존 점검 | 즉시 | DONE | first_action: 3개 폴더 삭제 후 scripts/stage scripts legacy 문자열/경로 참조 스캔 | proof: invest/assets(MISSING), invest/automation(MISSING), invest/archive(MISSING), legacy scan output(특히 stage5 blocked legacy wrappers)
- 2026-03-05 00:30 | 미확인 | `invest/assets`, `invest/automation`, `invest/archive` 삭제 및 scripts 레거시 잔존 제거 | 즉시 | DONE | first_action: 3개 폴더 삭제 후 stage5 blocked legacy wrapper 일괄 삭제/잔존 스캔 | proof: invest/assets(MISSING), invest/automation(MISSING), invest/archive(MISSING), invest/stages/stage5/scripts blocked wrapper 35개 삭제
- 2026-03-05 00:43 | 미확인 | invest/docs archive 삭제 및 불필요/비투자 문서 정리(외부 통합 포함) | 즉시 | DONE | first_action: invest/docs 정리 전용 서브에이전트 실행 | proof: invest/docs/archive(removed), invest/docs/governance/{ENGINEERING_RULES.md,SECURITY_RUNBOOK.md}(removed), invest/docs/INVEST_STRUCTURE_CANONICAL.md(removed), invest/docs/memory(removed)
- 2026-03-05 00:46 | 미확인 | `invest/reports` 불필요 판정 후 삭제 | 즉시 | DONE | first_action: 런타임 참조 0 확인 후 폴더 삭제 실행 | proof: invest/reports(MISSING)
- 2026-03-05 01:01 | 미확인 | invest/docs 하위 폴더 제거를 위한 문서 평탄화(flatten) 수행 | 즉시 | DONE | first_action: invest/docs flatten 전용 서브에이전트 실행 | proof: invest/docs/{BOOTSTRAP_REPRODUCTION.md,STAGE_EXECUTION_SPEC.md,RESULT_GOVERNANCE.md}, invest/stages/docs(MISSING), invest/stages/stage_updates(MISSING)
- 2026-03-05 01:15 | 미확인 | invest/stages/common 의존 치환 후 폴더 제거 | 즉시 | DONE | first_action: run_manifest import/경로 참조를 common→stages 루트로 치환 후 common 삭제 | proof: invest/stages/common(MISSING), invest/stages/run_manifest.py, common 참조 0
- 2026-03-05 01:25 | 미확인 | Stage1~4 정합성 감사 및 실행 검증(같은 stage inputs 참조 원칙 강제) | 즉시 | DONE | first_action: Stage1~4 경로구조 교정+실행 검증 전용 서브에이전트 실행 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE1_TO_4_INTEGRITY_AND_RUN_20260305_0150.md
- 2026-03-05 01:32 | 미확인 | 문서 구조 원칙 교정: stage 상세룰은 stage/docs, invest/docs는 공통문서만 유지 | 즉시 | DONE | first_action: 실행중 Stage1~4 서브에이전트에 문서 재정렬 요구 병합 지시 전달 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE1_TO_4_INTEGRITY_AND_RUN_20260305_0150.md
- 2026-03-05 01:56 | 미확인 | 전문서 정합성 보강: 구경로 stale 참조 전면 정리 | 즉시 | DONE | first_action: docs stale-path cleanup 전용 서브에이전트 실행 | proof: invest/stages/stage1/outputs/reports/stage_updates/DOCS_STALE_PATH_CLEANUP_20260305_0159.md
- 2026-03-05 02:05 | 미확인 | 전 스크립트 및 launchd(openclaw) 정합성 전수 확인 | 즉시 | DONE | first_action: 스크립트+launchd 정합성 전용 서브에이전트 실행 | proof: invest/stages/stage1/outputs/reports/stage_updates/FULL_SCRIPTS_AND_LAUNCHD_INTEGRITY_20260305_0209.md
- 2026-03-05 06:16 | 미확인 | Stage1~4 순차 실행 지시 수행 | 즉시 | DONE | first_action: Stage1→2→2.5→3→4 실행 전용 서브에이전트 실행 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE1_TO_4_RUN_20260305_0632.md
- 2026-03-05 08:09 | 미확인 | Stage1 `data/` 런타임 잔재를 `outputs/runtime`로 통합하고 data 폴더 제거 | 즉시 | DONE | first_action: stage01_post_collection_validate 출력경로를 outputs/runtime으로 변경 후 stage1/data/runtime 파일 이동 및 폴더 제거 | proof: invest/stages/stage1/data(MISSING), invest/stages/stage1/outputs/runtime/post_collection_validate.json, invest/stages/stage1/docs/{README.md,STAGE1_RULEBOOK_AND_REPRO.md}
- 2026-03-05 08:13 | 미확인 | Stage1 docs의 stage_updates 폴더 정리(규칙문서/리포트 분리) | 즉시 | DONE | first_action: stage docs stage_updates cleanup 서브에이전트 실행 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE_DOCS_STAGE_UPDATES_CLEANUP_20260305_0818.md
- 2026-03-05 08:16 | 미확인 | 로그 정리 1회 실행(불필요 로그 정리, 운영 로그 최소셋 유지) | 즉시 | DONE | first_action: logs cleanup 전용 서브에이전트 실행 | proof: invest/stages/stage1/outputs/reports/stage_updates/LOGS_CLEANUP_20260305_0826.md
- 2026-03-05 08:16 | 미확인 | Stage1에서 검역 제거, Stage2 단일 검역 책임으로 일원화 | 즉시 | DONE | first_action: Stage1 quarantine 제거 전용 서브에이전트 실행 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE1_QUARANTINE_REMOVAL_20260305_0821.md
- 2026-03-05 08:32 | 미확인 | Stage1 레거시 전면 정리 + raw 수집경로 검증 + 문서 연동 정합화 | 즉시 | DONE | first_action: Stage1 legacy/raw/docs cleanup 전용 서브에이전트 실행 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE1_LEGACY_RAW_DOCS_CLEANUP_20260305_0839.md
- 2026-03-05 08:39 | 미확인 | Stage2~6 구조 정합/레거시 정리/문서 1:1 매치 및 일관성 점검 | 즉시 | IN_PROGRESS | first_action: Stage2~6 전수 audit+cleanup 서브에이전트 실행 | proof: subagent runId=fa3078ce-d6a9-424d-9c9f-01009d07d430
- 2026-03-05 08:43 | 미확인 | Stage2~6 레거시 표식 문서/파일을 실제 삭제로 하드 정리 | 즉시 | IN_PROGRESS | first_action: stage2~6 legacy hard-cleanup 서브에이전트 실행 | proof: subagent runId=25713430-d64d-4d0f-8191-8cfb88d6c803
- 2026-03-05 08:53 | 미확인 | Stage2.5를 Stage3으로 승격하고 이후 단계 번호를 +1 시프트(전면 경로/문서 정합화) | 즉시 | IN_PROGRESS | first_action: 실행중 stage2~6 legacy 하드정리 서브에이전트에 번호재정렬 지시 병합 | proof: sessions_send runId=29a4c97c-dcdd-4b56-ba3f-d07bde2f000c
- 2026-03-05 08:54 | 미확인 | Stage 재번호 적용 후 신규 Stage1~6 실제 실행 및 in/out 경로 정합 검증 | 즉시 | IN_PROGRESS | first_action: 진행중 번호재정렬 서브에이전트에 실행검증 요구 병합 전달 | proof: sessions_send runId=c8b35932-2b1c-4884-a78c-6e29692951a8
- 2026-03-05 09:07 | 미확인 | 파일명/스테이지 번호/inputs-outputs 경로 최종 정합 마감 | 즉시 | IN_PROGRESS | first_action: 재번호+in/out 정합 전용 서브에이전트 실행 | proof: subagent runId=209ce04f-d804-470c-b9ae-d34edafe0a08
- 2026-03-05 09:15 | 미확인 | Stage2 입력 정제 범위에 dart/news/text 포함 보장(체인 엔트리 이원화 해소) | 즉시 | IN_PROGRESS | first_action: 진행중 재번호/정합 런에 Stage2 full refine 보장 요구 병합 | proof: sessions_send runId=9b7398b4-1c78-4d76-a9bd-19d231740f5a
- 2026-03-05 09:18 | 미확인 | 모든 스테이지(stage1~12) input/output 경로를 코드-문서 1:1 매트릭스로 검증(단순 실행PASS 금지) | 즉시 | IN_PROGRESS | first_action: 진행중 재번호/정합 런에 전스테이지 I/O 매트릭스 요구 병합 | proof: sessions_send runId=3ba2d0a8-d32b-40e0-a41c-e9e83e4a78ce
- 2026-03-05 09:20 | 미확인 | 작업 분담 기준 변경: 코드 공백/핵심 구현은 메인 직접 수행, 단순 반복/정리/검증은 서브에이전트 위임 | 즉시 | DONE | first_action: 분담 기준을 이후 작업 계획에 즉시 반영 | proof: 사용자 지시 메시지(2026-03-05 09:20 KST)
- 2026-03-05 10:17 | 미확인 | outputs 내 legacy 폴더 전면 정리(legacy_top_level 포함) 및 로그 경로 runtime 단일화 | 즉시 | DONE | first_action: source/plist 경로를 outputs/logs/runtime으로 치환 후 legacy 디렉토리 파일 이동/삭제 및 launchd 재적용 | proof: outputs legacy dirs 0, legacy_top_level refs 0, launchagents_reloaded
- 2026-03-05 10:47 | 미확인 | Stage3 채널 가중치 무가중(1.0) 전환 + 필터 우선 원칙 반영 | 즉시 | DONE | first_action: stage03 attention 코드/문서 가중치 정의를 1.0으로 변경하고 실행 검증 | proof: invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py, invest/stages/stage3/docs/STAGE3_DESIGN.md, stage3 RUN_OK(20260305_104921)
- 2026-03-05 10:51 | 미확인 | Stage3 변경 후 틀어진 데이터 삭제 + Stage3~6 재생성 + Stage3 항목 전면 점검 | 즉시 | IN_PROGRESS | first_action: rebuild/feature-audit 전용 서브에이전트 실행 | proof: subagent runId=f64e0ef4-20b8-454b-8401-ce36b3b3f174
- 2026-03-05 11:15 | 미확인 | Stage1 raw를 signal/qualitative로 분리하고 부족 지표(버핏/신용오실레이터) 추가 수집 | 즉시 | IN_PROGRESS | first_action: raw split + signal expansion 전용 서브에이전트 실행 | proof: subagent runId=f932947a-ccff-4b15-8fc8-e20263ec2336
- 2026-03-05 11:27 | 미확인 | Stage1 raw split(signal/qualitative) + macro indicator 확장(Buffett/Credit) + Stage2~6/문서 정합화 | 즉시 | DONE | first_action: Stage1 writer 경로 및 Stage2~6 reader fallback 경로를 동시 정렬하고 Stage1~3 스모크 검증 수행 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE1_RAW_SPLIT_AND_SIGNAL_EXPANSION_20260305_1127.md
- 2026-03-05 11:31 | 미확인 | Stage1 raw split 마감 + telegram/blog 수집 복구 + 지표 확장(버핏/신용오실레이터) | 즉시 | IN_PROGRESS | first_action: 수집 경로/launchd 복구 포함 전용 서브에이전트 재실행 | proof: subagent runId=b8b320ae-7e69-4830-b090-60a064214cc1
- 2026-03-05 11:39 | 미확인 | 중복연산 방지 규칙(축대표/상관제거/기여도캡) 코드·문서 반영 | 즉시 | IN_PROGRESS | first_action: 진행중 raw split 복구 런에 중복연산 방지 요구 병합 | proof: sessions_send runId=fc56b50a-f4b7-4d41-a39c-ebcfddfb8640
- 2026-03-05 12:09 | 미확인 | 중복연산 방지 4규칙(축대표1/축내합성1/|rho|>0.7 제거/축기여cap25%)을 Stage3~6 설계/코드에 반영, Stage3 신호결합부+Stage6 결합/검증부 guard 추가 | 즉시 | DONE | first_action: Stage3/Stage6 핵심 스크립트에 duplication_guard 로직 및 문서 동기화 반영 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE1_RAW_SPLIT_SIGNAL_QUAL_AND_COLLECTORS_FIX_20260305_1153.md (섹션 9)
- 2026-03-05 12:54 | 미확인 | Stage1 fail-close 강화: post-collection 10 core source 검증 확장 + Stage1 게이트 체인 삽입 + collector 최소성공 exit-code 하드닝 + 문서동기화 | 즉시 | OPEN | first_action: 대상 6파일 최소 수정 후 py_compile/bash -n/standalone validate/static gate evidence 검증 수행 | proof: -
- 2026-03-05 12:55 | 미확인 | Stage1 fail-close 강화: post-collection 10 core source 검증 확장 + Stage1 게이트 체인 삽입 + collector 최소성공 exit-code 하드닝 + 문서동기화 | 즉시 | IN_PROGRESS | first_action: 코드 패치 및 검증 커맨드 실행, 결과 리포트 작성 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE1_FAIL_CLOSE_GATE_HARDENING_20260305_125437.md
- 2026-03-05 12:56 | 미확인 | Stage1 fail-close 강화: post-collection 10 core source 검증 확장 + Stage1 게이트 체인 삽입 + collector 최소성공 exit-code 하드닝 + 문서동기화 | 즉시 | DONE | first_action: 필수 검증 4종 완료 및 리포트/메모리 동기화 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE1_FAIL_CLOSE_GATE_HARDENING_20260305_125437.md, memory/2026-03-05.md
- 2026-03-05 13:04 | 미확인 | 할일은 TASKS에 즉시 등록·가시화, 현재 우선은 Trends 제외+데이터 정리 | 즉시 | DONE | first_action: TASKS ACTIVE NOW에 JB-20260305-024/025 등록 | proof: TASKS.md
- 2026-03-05 13:07 | 미확인 | 기존 지시 누락분(TASKS) 보강: Stage1 10년 커버리지 감사/백필 작업 가시화 등록 | 즉시 | IN_PROGRESS | first_action: TASKS ACTIVE NOW에 JB-20260305-026/027 추가 | proof: TASKS.md
- 2026-03-05 15:02 | 미확인 | 최우선 지시 변경: Google Trends 운영 코드/데이터/참조 완전 제거 및 Stage1→3 검증 | 즉시 | DONE | first_action: stage01_fetch_trends.py/raw google_trends/runtime status 삭제 후 stage1~6 운영 스크립트 참조 0 스캔/검증 실행 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE_GOOGLE_TRENDS_FULL_REMOVAL_20260305_150206.md, invest/stages/stage1/outputs/reports/stage_updates/STAGE_GOOGLE_TRENDS_FULL_REMOVAL_20260305_150206.json
- 2026-03-05 15:50 | 미확인 | JB-024 재검증: 운영코드 기준 google_trends 참조 0 + 제거 산출물/스모크 근거 재확인 및 TASKS DONE 동기화 | 즉시 | DONE | first_action: stage1~6 scripts/stage1·3 docs 재스캔 + 삭제대상 존재검사 + 스모크 status 재확인 후 TASKS DONE 반영 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE_TASK_024_025_STATUS_SYNC_20260305_155043.md
- 2026-03-05 15:50 | 미확인 | JB-025 재검증: premium 링크메타 차단 + telegram·blog + DART/뉴스 커버리지 상태 확인, 미해결 외부의존 blocked 확정 | 즉시 | BLOCKED | first_action: score path/coverage 재검증 수치 산출 후 TELEGRAM 인증정보 부재를 blocked 사유로 고정 | proof: invest/stages/stage1/outputs/reports/stage_updates/STAGE_TASK_024_025_STATUS_SYNC_20260305_155043.md
- 2026-03-05 16:08 | 미확인 | 티켓 운영 문서 통합: TASKS를 SSOT로 유지, WORKFLOW_TICKET_SYSTEM 중복 제거, readlist/manifest 정리 | 즉시 | DONE | first_action: docs/openclaw/WORKFLOW_TICKET_SYSTEM.md 삭제 + CONTEXT_RESET_READLIST/CONTEXT_MANIFEST 참조 정리 | proof: TASKS.md, docs/openclaw/CONTEXT_RESET_READLIST.md, docs/openclaw/CONTEXT_MANIFEST.json
- 2026-03-05 16:25 | 미확인 | WORKFLOW_AUTO 통합 후 문서 삭제(중복 규정 제거) | 즉시 | DONE | first_action: AGENTS에 Workflow/Skill 규칙 통합, readlist/manifest/rules_index/workspace_structure 참조 정리 | proof: AGENTS.md, docs/openclaw/{RULES_INDEX.md,CONTEXT_RESET_READLIST.md,CONTEXT_MANIFEST.json,WORKSPACE_STRUCTURE.md}, WORKFLOW_AUTO.md(removed)
- 2026-03-05 18:05 | 미확인 | signal/market/news 폴더 정리 | 즉시 | DONE | first_action: 대상 경로 확인 후 legacy 빈 폴더 제거 수행 | proof: invest/stages/stage1/outputs/raw/signal/market/news(MISSING)
- 2026-03-05 18:09 | 미확인 | Stage1 백필 부진 개선: 텔레/뉴스/다트/블로그 등 10년치 최대 수집 가능하도록 코드 수정 후 실제 실행 검증 | 즉시 | IN_PROGRESS | first_action: JB-20260305-027 재가동(collector 수정+백필 실행+coverage 증빙) 서브에이전트 실행 | proof: subagent runId=a8904967-6f29-4d3d-8aa3-aa1821ed6b56
- 2026-03-05 21:17 | 미확인 | Stage2 폴더구조(signal/qualitative) 유지 + 정제규칙 강화 적용 | 즉시 | IN_PROGRESS | first_action: TASKS JB-20260305-032 등록 후 stage2 onepass 경로/정제로직 수정 전용 서브에이전트 실행 | proof: TASKS.md JB-20260305-032
- 2026-03-05 21:30 | 미확인 | Stage3 재설계 직접 수행(감성/주목도 제거, upside/downside_risk/bm/persistence 4축, 이중카운팅 방지, qualitative 전원천 입력, dart 분석 signal 분리) | 즉시 | IN_PROGRESS | first_action: TASKS JB-20260305-033 등록 후 stage3 build/gate/docs 및 stage4 연계 경로 직접 수정 | proof: TASKS.md JB-20260305-033
- 2026-03-05 21:46 | 주인님 | Stage3 재설계 직접 수행(감성/주목도 제거, 4축, 이중카운팅 가드, qualitative 전원천, dart signal 분리) | 즉시 | DONE | proof: invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py; invest/stages/stage3/scripts/stage03_build_input_jsonl.py; invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv; invest/stages/stage3/outputs/signal/dart_event_signal.csv
- 2026-03-05 21:58 | 주인님 | Stage2 dual-write 금지, legacy 데이터/스크립트 삭제 후 signal/qualitative 전용으로 재생성(서브에이전트 실행) | 즉시 | IN_PROGRESS | first_action: TASKS JB-20260305-034 등록 후 stage2 strict rebuild 서브 실행 | proof: TASKS.md JB-20260305-034
- 2026-03-05 22:34 | 주인님 | Stage2 텍스트 정제에서 링크본문 확장수집 + 중복링크 제거 반영 | 즉시 | IN_PROGRESS | first_action: TASKS JB-20260305-036 등록 후 링크확장/중복제거 구현 서브 실행 | proof: TASKS.md JB-20260305-036
- 2026-03-05 23:37 | 미확인 | TASKS 규칙/작업 분리로 토큰 절감 | 즉시 | DONE | first_action: TASKS.md 내용을 규칙/작업으로 분리 이관 | proof: TASKS.md, TASKS_RULES.md, TASKS_ACTIVE.md

- 2026-03-05 23:44 | 미확인 | TASKS 프로그램 전환(SQLite) + 티켓 강제 게이트 도입 | 즉시 | IN_PROGRESS | first_action: TASKS_ACTIVE JB-20260305-037 등록 후 프로그램 전환/강제화 구현 착수 | proof: TASKS_ACTIVE.md
- 2026-03-05 23:49 | 주인님 | TASKS 문서기반→프로그램(SQLite) 전환 + fail-close 티켓 게이트 도입 + TASKS 문서 3종 역할분리 정리 | 즉시 | DONE | proof: scripts/tasks/db.py, scripts/tasks/gate.py, TASKS.md, TASKS_RULES.md, TASKS_ACTIVE.md, runtime/tasks/README.md
2026-03-05 23:57 | 미확인 | TASKS 문서 최소화(프로그램 SSOT만 유지) | 즉시 | DONE | first_action: TASKS_ACTIVE.md/TASKS_RULES.md 삭제 후 TASKS.md 3줄 최소화 | proof: TASKS.md, TASKS_ACTIVE.md(removed), TASKS_RULES.md(removed)

- 2026-03-06 00:00 | 미확인 | DIRECTIVES 프로그램 전환(SQLite) + 티켓 강제 게이트 도입 | 즉시 | IN_PROGRESS | first_action: taskdb에 JB-20260306-001 등록 후 전환 작업 착수 | proof: runtime/tasks/tasks.db, scripts/tasks/db.py
