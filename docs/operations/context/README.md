# context

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

역할: **세션 복구 / 로딩 / handoff 관련 문서 묶음**.

이 폴더는 사람이 context 운영 문서를 빠르게 찾도록 돕는 카테고리 인덱스다.
규칙의 canonical source는 기존 상위 문서에 남고,
여기서는 역할별 연결만 제공한다.

## 문서 map
- `docs/operations/context/CONTEXT_POLICY.md`
  - 컨텍스트 운용 기준, token threshold 대응, reset/cutover 판단
- `docs/operations/context/CONTEXT_LOAD_POLICY.md`
  - 무엇을 언제 읽는지, 기본/옵션 로드 정책
- `docs/operations/context/CONTEXT_RESET_READLIST.md`
  - reset 직후 최소 재로딩 목록
- `docs/operations/context/CONTEXT_HANDOFF_FORMAT.md`
  - handoff 카드 형식
- `docs/operations/context/CONTEXT_MANIFEST.json`
  - context 관련 참조 manifest

## 추천 진입 순서
1. `CONTEXT_LOAD_POLICY.md`
2. `CONTEXT_POLICY.md`
3. 필요 시 `CONTEXT_RESET_READLIST.md` / `CONTEXT_HANDOFF_FORMAT.md`

## 메모
- 이 문서는 human-facing category index다.
- 기본 세션 로드에서는 자동으로 읽지 않는다.
