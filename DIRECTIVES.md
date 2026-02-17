# DIRECTIVES.md

주인님 지시 원문/요약을 누락 없이 기록하는 고정 로그.

## 기록 규칙
- 모든 지시를 수신 즉시 1줄로 추가
- 필드: `time | message_id | directive | due | status | first_action | proof`
- 상태: `OPEN | IN_PROGRESS | DONE | BLOCKED`
- 완료 시 반드시 proof(파일/리포트 경로) 기입

## Priority Buckets (WIP=1)

### P1-오늘 (정확히 1개)
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
- 2026-02-17 11:32 | 3825 | 알고리즘 보고 시 1단계부터 전체 나열 + 단계별 진행바(예: ■■■□□□50%), 단계 완료마다 별도 업데이트 보고서 생성(예: 내지표 vs 이웃지표 표) | 상시 | IN_PROGRESS | first_action: 시간별/일일 보고 포맷과 단계완료 리포트 규칙을 크론 프롬프트/보고 폴더에 반영 | proof: -
- 2026-02-17 11:33 | 3826 | 단계완료 보고는 GitHub 업데이트 + 보고채널 전송을 동시에 수행 | 상시 | IN_PROGRESS | first_action: `reports/stage_updates/` 생성 후 단계완료 시 별도 파일 저장 및 채널 별도 보고 규칙 추가 | proof: -

### P3-상시
- 2026-02-17 05:50 | 3522 | 주기적으로 할일 체크(정기 점검 루틴 상시 적용) | 상시 | IN_PROGRESS | first_action: 크론 `531714af-c1ee-4852-9966-2e9b62714449` 실행 상태 주기 확인 | proof: cron job active
- 2026-02-17 06:02 | 3542 | 10분 주기 점검 적용 + 본 사태 해결 브레인스토밍 수행 | 즉시 | DONE | first_action: 10분 점검 크론 등록 및 브레인스토밍 반영안 적용 | proof: cron job `531714af-c1ee-4852-9966-2e9b62714449` created, brainstorm 반영: DIRECTIVES.md P1/P2/P3+first_action

## Operating Checklist (경량 강제)
1) 새 지시 수신 → DIRECTIVES.md 즉시 기록
2) 약속/ETA/완료보고 전 P1/P2의 OPEN/IN_PROGRESS 재확인
3) 코드/전략/보고 완료 건은 DONE 전환 시 proof 1개 이상 첨부
4) 타이머(10분) 점검은 유지하되, 이상 징후 있을 때만 알림
