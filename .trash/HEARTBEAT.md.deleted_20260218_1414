# HEARTBEAT.md
# 규칙 등급: MUST 항목만 체크. SHOULD/CAN은 침묵.
# 동일 경고 4h 이내 재경고 금지.

## ✅ MUST 체크 (경고 발송)
1. `TASKS.md`에 `[PENDING_REPORT]` 항목의 due 초과 여부
   - 초과 시만 알림. 진행중이면 `[계속중]` 1줄 요약.
   - **동일 항목 4h 내 재경고 금지.**
2. `memory/health-state.json` 존재 & 30분 이내 갱신 여부
   - 없거나 stale이면 즉시 경고.
3. pendingMessages > 20
   - (이전 기준 10 → 20으로 상향)

## 🚫 경고 안 함 (SHOULD/CAN — 침묵)
- memory 파일 미작성 (당일 22:00 전이면 패스)
- TASKS.md 미완료 항목 단순 존재
- git 미커밋 (24h 내 변경 없으면 무시)
- watchdog 수동체크 (실패 로그 없으면 침묵)
- 야간 22:00~09:00 비긴급 알림 전부

## 야간 침묵
- 22:00~09:00: MUST ①②③ 중 실제 장애만 경고
- 그 외: HEARTBEAT_OK

## 이상 없으면
→ `HEARTBEAT_OK`
