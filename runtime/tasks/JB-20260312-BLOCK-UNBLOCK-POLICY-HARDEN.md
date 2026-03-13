# JB-20260312-BLOCK-UNBLOCK-POLICY-HARDEN

- ticket: JB-20260312-BLOCK-UNBLOCK-POLICY-HARDEN
- status: DONE
- checked_at: 2026-03-12 06:13 KST

## Goal
장기 작업을 단순 시간 경과로 BLOCK하지 않고, 담당자/프로세스 liveness 확인 후 실제 미동작일 때만 BLOCK 처리하며, 선행조건 해소 시 즉시 UNBLOCK/재진행하는 운영정책을 강화한다.

## Adopted rule
1. 오래 걸린다는 이유만으로 BLOCK 금지
2. stale 감지 시 먼저 담당자 진행 여부 확인 시도
3. 단, 담당자 응답 부재를 기본 시나리오로 가정하고 응답 유무 하나에 의존하지 않음
4. 동시에 아래 liveness를 확인
   - 프로세스/session 생존 여부
   - 최근 로그/출력 갱신 여부
   - 산출물/파일 변화 여부
   - completion/wake/callback 신호 여부
5. 응답이 없어도 liveness가 살아 있으면 IN_PROGRESS 유지 + 재지시/리마인드
6. 응답도 없고 liveness/산출도 멈춰 있으면 그때 BLOCK 또는 재배정
7. 선행조건 해소 즉시 UNBLOCK/재진행
8. BLOCK 시 반드시 아래를 남김
   - blocked_reason
   - prereq_tickets
   - unblock_condition
   - next_action

## Immediate application
- 이후 stale/blocked 판단은 `응답 + process liveness + output movement` 3축으로 판정한다.
- 단순 경과시간 기반 BLOCK은 운영상 잘못된 신호로 간주한다.

## Next action
- 이후 모든 BLOCK/UNBLOCK 운영에 이 규칙을 우선 적용한다.
