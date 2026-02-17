# OPENCLAW_SYSTEM_BASELINE.md

Last updated: 2026-02-18 06:13 KST
Purpose: 컨텍스트 초기화 후에도 OpenClaw 운영 상태/점검 기준을 빠르게 복구하기 위한 기준 문서

## 1) 현재 시스템 베이스라인
- Dashboard: `http://127.0.0.1:18789/`
- OS/Node: `macos 26.2 (arm64) / node 25.6.0`
- Gateway: `ws://127.0.0.1:18789` (local loopback)
- Gateway service: LaunchAgent 설치/로드/실행 중
- Node service: LaunchAgent 미설치
- Channel: Telegram ON/OK
- Update 상태: update available (`openclaw update` 표시됨)

## 2) 필수 점검 명령(우선순위)
1. `openclaw status`
2. `openclaw security audit`
3. `openclaw logs --follow` (이상 징후 시)

## 3) 운영 제약
- 업데이트/설정 변경은 주인님 명시 지시 있을 때만 수행
- 통신/채널 이상 시 먼저 status->logs 순으로 원인 확인

## 4) 장애 시 최소 복구 순서
1. `openclaw status`로 Gateway/Channel 상태 확인
2. 필요 시 `openclaw gateway restart`
3. heartbeat/health-state 갱신 여부 확인
4. 재발 시 로그 첨부 후 원인 보고
