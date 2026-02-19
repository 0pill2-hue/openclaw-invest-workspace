# DIRECTIVES.md

주인님 지시 원문/요약을 누락 없이 기록하는 고정 로그.

## 기록 규칙
- 모든 지시를 수신 즉시 1줄로 추가
- 필드: `time | message_id | directive | due | status | first_action | proof`
- 상태: `OPEN | IN_PROGRESS | DONE | BLOCKED`
- 완료 시 반드시 proof(파일/리포트 경로) 기입
- 임의 룰 추가 시 코드 폐기 (주인님 명령/Rulebook 미근거 규칙 삽입 금지)

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
- 2026-02-18 15:19 | 5775 | 8단계 브레인스토밍 기반 설계 문서화(재현필드 완비) + 다른 계열 검증 | 즉시 | DONE | first_action: Stage08(Purged CV/OOS) 설계 브레인스토밍 3모델 후 canonical 문서 작성 및 비-Codex 교차검증 수행 | proof: reports/stage_updates/stage08/stage08_purged_cv_oos.md, scripts/stage08_purged_cv_oos.py, scripts/stage08_purged_cv_oos_qc.py, invest/results/validated/stage08_purged_cv_oos.json
- 2026-02-18 15:13 | 5761 | 7단계 브레인스토밍 후 설계 문서 작성 + 자체검증 필요 시 포함 설계 | 즉시 | DONE | first_action: Stage07 컷 기준 브레인스토밍 3모델 실행 후 canonical 문서/자체검증 스크립트 설계 반영 | proof: reports/stage_updates/stage07/stage07_candidate_stage_cut.md, scripts/stage07_candidate_stage_cut.py, scripts/stage07_candidate_cut_qc.py, invest/results/validated/stage07_candidates_cut.json
- 2026-02-18 14:04 | 5658 | 5단계 문서 참조 기반으로 6단계 설계 브레인스토밍 후 문서 업데이트 | 즉시 | DONE | first_action: stage05 baseline/pass 문서를 입력으로 stage06 canonical 문서를 템플릿 필드 포함 형태로 재작성 | proof: reports/stage_updates/stage06/stage06_candidate_gen_v1.md, reports/stage_updates/STAGE06_ENTRY_PREP_20260218.md
- 2026-02-18 14:11 | 5671 | heartbeat가 메인작업을 멈추지 않도록 복귀루틴을 문서가 아닌 강제 절차로 수정 | 즉시 | OPEN | first_action: foreground anchor/heartbeat 분리/3분 복귀 타임박스 규칙을 SOP+readlist에 강제 반영 | proof: invest/docs/operations/OPERATIONS_SOP.md, docs/openclaw/CONTEXT_RESET_READLIST.md, runtime/foreground_anchor.json
- 2026-02-18 14:52 | 5705 | Stage06 설계 기준으로 실제 실행 진행 | 즉시 | DONE | first_action: stage06 생성 스크립트/검증 스크립트 준비 후 실행 | proof: invest/scripts/stage06_candidate_gen_v1.py, scripts/stage06_candidate_qc.py, invest/results/validated/stage06_candidates.json
- 2026-02-18 13:42 | 5637 | 리팩토링 명목으로 미뤄진 지시(함수별 입출력/기능 주석 명시, 문서 리팩토링) 즉시 재개 및 누락 없이 처리 | 즉시 | OPEN | first_action: 미이행 항목 인벤토리 작성 후 코드 주석 반영 범위/문서 리팩토링 범위 확정 | proof: -
- 2026-02-18 05:45 | 4947 | 지시/합의사항(특히 11단계·운영선정 규칙) 즉시 문서화하고 동일 혼선 재발 금지 | 상시 | IN_PROGRESS | first_action: memory/2026-02-18.md에 합의 규칙(택1 운영, 4→5 반복, 예외 시 2→3 재진입) 고정 기록 | proof: memory/2026-02-18.md
- 2026-02-18 05:52 | 4969 | 1번 단계를 수집으로 고정하고 단계 문서 전체를 재정렬/업데이트 | 즉시 | DONE | first_action: stage 문서 번호/명칭을 11단계 canonical에 맞게 재작성 | proof: reports/stage_updates/README.md, stage01_data_collection.md ~ stage11_adopt_hold_promote.md, invest/strategy/RULEBOOK_V1_20260218.md
- 2026-02-18 05:53 | 4970 | 컨텍스트 비운 뒤 먼저 읽을 문서 목록을 메모리에 고정 | 즉시 | DONE | first_action: memory/2026-02-18.md에 재로딩 체크리스트 추가 | proof: memory/2026-02-18.md
- 2026-02-18 06:03 | 4996 | stage01~04 명시 게이트 브레인스토밍 후 문서 반영, 실제 동작 점검 1회 실행 | 즉시 | DONE | first_action: stage02~04 gate 설계/반영 후 gate-check 스모크 실행 | proof: reports/stage_updates/stage02/stage02_data_cleaning.md, stage03_cleaning_validation.md, stage04_validated_value.md, scripts/stage_gate_check_1to4.py 실행결과(SUMMARY:FAIL, stage04:grade_present:FAIL)
- 2026-02-18 06:05 | 5001 | RULEBOOK/Stage 문서 추가·수정 필요점 브레인스토밍 후 적용 | 즉시 | DONE | first_action: RULEBOOK의 운영선정/충돌룰 모순 제거 + stage gate 연결 섹션 추가 + README 동기화 + gate-check 재실행 | proof: invest/strategy/RULEBOOK_V1_20260218.md, reports/stage_updates/README.md, scripts/stage_gate_check_1to4.py 실행결과(SUMMARY:FAIL, stage04:grade_present:FAIL)
- 2026-02-18 06:13 | 5009 | OpenClaw 시스템/폴더/설정 문서를 invest 밖에 작성하고 컨텍스트 초기화 시 강제 재로딩 규칙 추가 | 즉시 | DONE | first_action: 시스템 브레인스토밍 후 baseline 문서 2종 작성 + AGENTS/메모리 체크리스트 반영 | proof: docs/openclaw/OPENCLAW_SYSTEM_BASELINE.md, docs/openclaw/WORKSPACE_STRUCTURE.md, docs/openclaw/CONTEXT_RESET_READLIST.md, AGENTS.md
- 2026-02-18 06:17 | 5017 | 시스템/알고리즘 변경 시 문서 업데이트 강제 | 상시 | DONE | first_action: AGENTS.md에 Documentation Sync Gate 추가 | proof: AGENTS.md
- 2026-02-18 06:20 | 5027 | 문서는 전부 재현 가능한 수준으로 작성 | 상시 | DONE | first_action: stage/rulebook/openclaw 문서에 실행·입력·출력·게이트·증빙 필드 점검 및 누락 보강 | proof: AGENTS.md Documentation Sync Gate(재현 필드 최소요건 명시), memory/2026-02-18.md
- 2026-02-18 06:22 | 5033 | 시스템 불필요 파일 브레인스토밍 후 제거 | 즉시 | DONE | first_action: 안전 대상(캐시/컴파일 산출물) 선별 후 trash 이동 | proof: workspace 전체 __pycache__/pyc/.DS_Store 제거 확인(find 결과 없음)
- 2026-02-18 06:24 | 5037 | 폴더구조 적합성 브레인스토밍 후 문제 없이 수정 | 즉시 | DONE | first_action: 실제 디렉터리 트리와 문서 기준 비교 후 불일치 문서만 수정 | proof: docs/openclaw/WORKSPACE_STRUCTURE.md
- 2026-02-18 06:25 | 5038 | 문서 추가/보강 필요점 브레인스토밍 후 점검 | 즉시 | DONE | first_action: docs/openclaw + stage/rulebook 대상 갭 분석 후 추가/보강안 반영 | proof: docs/openclaw/DOCS_MAINTENANCE_PLAYBOOK.md, docs/openclaw/CONTEXT_RESET_READLIST.md, reports/stage_updates/stage02/stage02_data_cleaning.md, stage03_cleaning_validation.md, stage04_validated_value.md
- 2026-02-18 06:30 | 5051 | 메모리 파일 보강 필요점 브레인스토밍 및 반영 | 즉시 | DONE | first_action: MEMORY/memory/*.md 갭 점검 후 최소 보강안 적용 | proof: MEMORY.md(2026-02-18 섹션 추가), memory/INDEX.md(2026-02-17/18 인덱스 보강)
- 2026-02-18 06:31 | 5053 | 4/5 게이트 통과 후 Git 업데이트 선행, 그 다음 리팩토링 진행 | 상시 | IN_PROGRESS | first_action: 4/5 게이트 통과 확인 전에는 리팩토링 제안/실행 보류, 통과 즉시 git 업데이트부터 수행 | proof: -
- 2026-02-18 07:09 | 5132 | 리팩토링 시 input/output path 안정성 보장 | 리팩토링 시점 | DONE | first_action: 경로 변경 시 alias/호환레이어 유지 + run/gate/manfiest 경로 회귀검증 포함 | proof: reports/stage_updates/REFACTOR_FINAL_REPORT_20260218_FLASH.md
- 2026-02-18 07:11 | 5138 | 리팩토링 누락 파일 전수 탐색/검증 | 리팩토링 종료 전 | DONE | first_action: 네이밍 룰 기준 전체 파일 스캔 후 미반영 목록/수정 목록 리포트 생성 | proof: reports/stage_updates/REFACTOR_FINAL_REPORT_20260218_FLASH.md
- 2026-02-18 07:36 | 5157 | 미완료 작업 종료 시 남은 할일+다음 제안 자동 포함 규칙 고정 | 즉시 | DONE | first_action: SOP에 종료보고 제안 규칙 추가 | proof: invest/docs/operations/OPERATIONS_SOP.md 섹션 8
- 2026-02-18 07:42 | 5165 | 검수코드/중요작업은 다른 계열 고성능 모델에 교차 배정 규칙 추가 | 즉시 | DONE | first_action: SOP에 교차모델 배정 규칙 신설 | proof: invest/docs/operations/OPERATIONS_SOP.md 섹션 9
- 2026-02-18 07:43 | 5167 | 구버전 지시 잔존/충돌 재발 방지 규칙 문서화 | 즉시 | DONE | first_action: SOP에 지시 충돌 정리 절차(상태전환+해소메모+proof보강) 추가 | proof: invest/docs/operations/OPERATIONS_SOP.md 섹션 10
- 2026-02-18 07:52 | 5185 | 정시/예약 보고의 REPORT_QUEUE 선등록 누락 재발 방지 | 즉시 | DONE | first_action: SOP에 선등록 규칙 추가 + 08:00 pending 즉시 등록 | proof: invest/docs/operations/OPERATIONS_SOP.md 섹션 11, TASKS.md REPORT_QUEUE
- 2026-02-18 08:01 | 5199 | 문서별 포맷 표준 확정 | 즉시 | DONE | first_action: 문서 유형별 템플릿(단계/운영/리포트) 표준 문서 신설 및 readlist 연동 | proof: docs/openclaw/DOC_TEMPLATES.md, docs/openclaw/CONTEXT_RESET_READLIST.md
- 2026-02-18 08:11 | 5221 | 정시 보고 완료 후 PENDING 잔존 경고 재발 방지 | 즉시 | DONE | first_action: TASKS REPORT_QUEUE 즉시 종료 반영 + 점검 크론에 자동정리/재알림 억제 규칙 추가 | proof: TASKS.md 08:00 DONE_REPORT, cron job 531714af payload update
- 2026-02-18 08:22 | 5234 | US OHLCV freshness 오탐 재발 방지 | 즉시 | DONE | first_action: post_collection_validate의 US freshness 룰에 KST 장중/비장중 분기 임계치 적용 | proof: invest/scripts/post_collection_validate.py, 실행검증 ok=true (08:22)
- 2026-02-18 08:54 | 5256 | 리팩토링 우선, 기타 4개 블록 처리 후 본작업 집중 | 즉시 | DONE | first_action: 추가 대응은 4개 블록으로 제한하고 리팩토링 본작업 시간 블록 고정 | proof: reports/stage_updates/REFACTOR_FINAL_REPORT_20260218_FLASH.md
- 2026-02-18 07:47 | 5173 | 특갤 참고사항 중 적용가능 항목 선별·반영 | 즉시 | DONE | first_action: 우회팁 제외, 운영원칙(작업성격별 모델모드 선택/임시복구 핸들링)만 문서 반영 | proof: docs/openclaw/OPERATING_GOVERNANCE.md
- 2026-02-18 06:43 | 5079 | 네이밍 룰 우선 수립 | 즉시 | DONE | first_action: 파일/함수/리포트/매니페스트 네이밍 초안 제시 후 승인받기 | proof: docs/openclaw/NAMING_STRATEGY.md, docs/openclaw/CONTEXT_RESET_READLIST.md
- 2026-02-18 06:47 | 5089 | 코딩 룰 브레인스토밍 후 고정 | 즉시 | DONE | first_action: 운영/재현/게이트 중심 코딩 룰 초안 작성 | proof: docs/openclaw/CODING_RULES.md, docs/openclaw/CONTEXT_RESET_READLIST.md
- 2026-02-18 06:49 | 5093 | 운영전략(게이트/SOP/SLA/Git) 브레인스토밍 후 문서 고정 | 즉시 | DONE | first_action: 상위 운영 문서에 4개 기준을 canonical로 추가 | proof: docs/openclaw/OPERATING_GOVERNANCE.md, docs/openclaw/CONTEXT_RESET_READLIST.md, invest/docs/operations/OPERATIONS_SOP.md
- 2026-02-17 10:34 | 3737 | 작업 순서를 순차 처리로 고정(꼬임 방지) | due 해제(주인님 지시) | IN_PROGRESS | first_action: 1) 데이터 정제 완료 2) 정제 검증 3) VALIDATED 밸류 산출 4) 비교표/후속 작업 순서로 진행 | proof: -

### P2-이번주
- 2026-02-17 05:57 | 3530 | 제출물에 피처 비교표 3종(내vs이웃 점수/기여도·방향성/clean 전후 차이열) 필수 포함 | due 해제(주인님 지시) | IN_PROGRESS | first_action: `invest/results/validated|test`에서 내지표/이웃지표 결과 파일 경로 확정 후 표 템플릿 생성 | proof: -
- 2026-02-17 05:42 | 3500 | 완료 최우선 + 남는 시간 자동 검증/로그 안정화 보강 | due 해제(주인님 지시) | IN_PROGRESS | first_action: `invest/scripts/` 자동검증 스크립트 실행 로그 경로 1차 수집 | proof: -
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
- 2026-02-17 11:33 | 3826 | 단계완료 보고는 GitHub 업데이트 + 보고채널 전송을 동시에 수행 | 상시 | DONE | first_action: `reports/stage_updates/` 생성 후 단계완료 시 별도 파일 저장 및 채널 별도 보고 규칙 추가 | proof: `reports/stage_updates/README.md`, cron `86edd049` 단계완료 별도 메시지 규칙 반영
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
