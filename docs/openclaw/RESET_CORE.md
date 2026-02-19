# RESET_CORE.md

Last updated: 2026-02-18 KST
Purpose: 컨텍스트 리셋 직후 항상 읽는 최소 핵심팩(L1)

## MUST (항상 고정)
1. 안전/권한 원칙 준수 (파괴적 작업 사전 확인)
2. 문서 우선순위: RULEBOOK > stage 문서 > 실행 스크립트
3. 단계/운영 기준 확정 답변 전 필수 문서 재로딩
4. 코드/전략/데이터 변경 완료 전 3체크
   - instruction-check
   - record-check (memory 기록)
   - verify-check (실행/테스트 검증)
5. 모델 규칙
   - Gemini는 3.x만 사용
   - Gemini 1.5/2.5 금지

## 현재 고정 역할분담
- 수집/파이프라인: `google-antigravity/gemini-3-flash` (OAuth)
- 브레인스토밍/설계: Antigravity Pro + Sonnet/Opus 교차
- 기본 코드 구현: `openai-codex/gpt-5.3-codex`
- 검증/코드리뷰: 비-Codex 계열(Sonnet/Opus/Antigravity)

## 리셋 후 최소 확인 순서
1) 이 파일
2) `docs/openclaw/CONTEXT_RESET_READLIST.md` (L1만)
3) `DIRECTIVES.md` 상단 QUICK RESUME SNAPSHOT
4) 작업 유형별 L2 온디맨드 로드
