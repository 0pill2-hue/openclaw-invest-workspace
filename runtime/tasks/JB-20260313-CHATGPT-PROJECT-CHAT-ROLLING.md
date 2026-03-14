# JB-20260313-CHATGPT-PROJECT-CHAT-ROLLING

## landed
- `skills/web-review/scripts/send_chatgpt_project_prompt.py` 에 프로젝트 내부 채팅 롤링 유지 로직을 추가했다.
  - 기본 프로젝트를 `시스템트레이딩 모델개발` + `/project` URL 로 고정.
  - 프로젝트 본문/URL 가드(`project_name_visible`, `loaded_url_matches_prefix`)를 선행 확인.
  - 프로젝트 페이지에서만 보이는 내부 채팅 카드 DOM을 수집하도록 구현:
    - 절대 URL 기준 `https://chatgpt.com/g/.../c/<conversation_id>` prefix 매칭
    - `li` row + `button[data-conversation-options-trigger]` 존재를 함께 요구
    - 따라서 일반 좌측 히스토리(`/c/...`)와 분리해서 프로젝트 내부 채팅만 대상으로 함.
- 새 프롬프트 전송 전에 현재 프로젝트 내부 채팅 목록을 읽고, `max_keep=5` 기준으로 `overflow_if_send = max(0, existing + 1 - 5)` 를 계산한다.
  - 전송 성공 후에는 미리 계산된 가장 오래된 overflow 대상만 삭제하도록 구성했다.
  - 즉 정책은 `newest 5 keep / overflow delete` 이다.
- 삭제는 fail-closed 로 묶었다.
  - 전송 후 URL 이 프로젝트 내부 채팅(`.../g/.../c/<id>`)으로 확인되지 않으면 삭제하지 않음.
  - 삭제 직전에도 다시 프로젝트 `/project` 로 돌아가 guard 재검증 실패 시 삭제하지 않음.
  - 삭제 대상은 pre-plan 된 `conversation_id` 집합만 허용.
- 비파괴 검증 경로를 추가했다.
  - `--verify-only`: 전송/삭제 없이 프로젝트 채팅 DOM 탐지와 롤링 계획만 검증
  - `--cleanup-dry-run`: 전송 이후 삭제 계획만 수행하고 실제 confirm 삭제는 하지 않음
  - `--max-project-chats`: 기본 5, 필요 시 조정 가능
  - `--post-send-wait-seconds`: 전송 확인 대기값 조정 가능
- 전송 확인도 보강했다.
  - Enter / Meta+Enter / send-button fallback 순으로 시도
  - 최종 URL 이 프로젝트 내부 채팅 regex 와 prefix 를 만족해야 성공 처리

## remaining
- 실제 라이브 계정에서 confirm 삭제까지 눌러보는 실삭제 검증은 미실행.
  - 사유: destructive 동작이라 이 턴에서는 verify/dry-run 까지만 수행.
- ChatGPT 프로젝트 카드 DOM 이 크게 바뀌면 selector 재조정이 필요할 수 있다.
  - 현재는 실페이지 검증 기준으로 `project card anchor + conversation-options-trigger` 경로가 확인됨.

## proof
- 코드 변경 파일
  - `skills/web-review/scripts/send_chatgpt_project_prompt.py`
- 문법 검증
  - 명령: `.venv/bin/python -m py_compile skills/web-review/scripts/send_chatgpt_project_prompt.py`
- 프로젝트 DOM/롤링 계획 검증 (비파괴)
  - JSON: `runtime/tmp/chatgpt-project-rolling-verify.json`
  - Screenshot: `runtime/tmp/chatgpt-project-rolling-verify.png`
  - 핵심 결과:
    - `project_guard_before_send.ok = true`
    - `project_chat_count_before_send = 5`
    - `project_chat_cleanup_plan.overflow_if_send = 1`
    - 삭제 예정 후보: `69b3ebef-4d04-83a7-96dc-580de63b5bff` / `안녕하세요 인사`
- cleanup 함수 dry-run 검증 (비파괴)
  - JSON: `runtime/tmp/chatgpt-project-rolling-cleanup-dry-run.json`
  - 핵심 결과:
    - `status = "dry_run"`
    - `matched_targets[0].conversation_id = 69b3ebef-4d04-83a7-96dc-580de63b5bff`
    - `missing_target_ids = []`
- 프로젝트 카드 옵션 메뉴 확인 (비파괴)
  - JSON: `runtime/tmp/chatgpt-project-menu-proof.json`
  - 핵심 결과:
    - `opened = true`
    - `menu_items` 에 `삭제` 포함
    - 따라서 프로젝트 내부 카드에서 삭제 메뉴 진입 selector 가 유효함

## 2026-03-13 21:27 KST — status hold
- verify/dry-run/menu proof까지 완료
- 실제 confirm delete 클릭은 미실행
- 따라서 이 티켓은 DONE으로 닫지 않고 IN_PROGRESS로 유지
- next: project_internal guard 통과 상태에서 overflow 실제 삭제를 활성화/검증한 뒤 마감

## 2026-03-13 21:47 KST — actual delete verified
- headless 1차 실행은 Cloudflare 사람확인 화면에 걸려 `project_not_visible` 로 fail-closed 되었다.
  - proof: `runtime/tmp/chatgpt-project-rolling-delete-test.json`, `runtime/tmp/chatgpt-project-rolling-delete-test.png`
- headful verify 재실행에서 프로젝트 guard 와 프로젝트 내부 채팅 5개 상태를 재확인했다.
  - proof: `runtime/tmp/chatgpt-project-rolling-verify-headful.json`, `runtime/tmp/chatgpt-project-rolling-verify-headful.png`
- headful 실전송/실삭제 실행 결과:
  - 새 프로젝트 내부 채팅 생성 성공: `conversation_id = 69b406d7-3c40-83a3-bb72-c074fde96200`
  - overflow 대상 사전계획: `69b3ee28-70c0-83a3-808a-643d38e14c44` (`인사 및 도움 요청`)
  - 삭제 confirm 성공, 최종 프로젝트 내부 채팅 수 `5` 유지 확인
- 최종 newest 5 keep 목록:
  - `69b406d7-3c40-83a3-bb72-c074fde96200` `롤링 삭제 테스트`
  - `69b40580-0890-83a3-b789-8b0b8713727f` `롤링 삭제 테스트`
  - `69b3f899-9ffc-83a7-84d7-77bfa997f4b0` `Stage3 external review`
  - `69b3f489-c164-83a8-b9c4-1176d307373b` `Stage3 External Review`
  - `69b3f02a-d4bc-83a4-9303-447de95b13ef` `Batch scoring review`
- decisive proof:
  - `runtime/tmp/chatgpt-project-rolling-delete-test-headful.json`
  - `runtime/tmp/chatgpt-project-rolling-delete-test-headful.png`
- next: 주인님 보고 후 티켓/디렉티브 마감
