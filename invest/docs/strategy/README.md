# invest/docs/strategy 문서 운영 기준

## 1) 이 폴더에서 어디를 보면 되는가 (최우선)
항상 아래 3개만 **운영 기준(canonical)** 으로 사용합니다.

1. `RULEBOOK_MASTER.md`  
   - 하드룰/게이트/금지사항
2. `PIPELINE_11_STAGE_MASTER.md`  
   - 11단계 정의/순서/단계 의미
3. `STAGE_STRATEGY_MASTER.md`  
   - 단계별 실행 전략/산출물 요구사항

---

## 2) 나머지 문서의 역할
- `reference/` 하위 문서는 **참고/이력** 전용입니다.
- 운영 중 의사결정의 기준으로 직접 사용하지 않습니다.

---

## 3) 문서 관리 규칙 (중복 방지)
- 새 규칙 추가/변경: `RULEBOOK_MASTER.md`에만 반영
- 단계 정의 변경: `PIPELINE_11_STAGE_MASTER.md`에만 반영
- 단계 실행 전략 변경: `STAGE_STRATEGY_MASTER.md`에만 반영
- 동일 내용 2개 이상 파일에 복제 금지
- 참고 문서로 내릴 때는 `reference/`로 이동

---

## 4) 버전 관리 규칙 (Git 필수)
- 문서 변경은 반드시 Git 커밋
- 커밋 메시지 권장:
  - `docs(strategy): update rulebook ...`
  - `docs(strategy): update pipeline ...`
  - `docs(strategy): update stage strategy ...`
- 큰 변경은 파일별/주제별로 커밋 분리

---

## 5) 빠른 체크리스트
- [ ] 변경 대상이 3개 canonical 중 정확히 1개인가?
- [ ] 같은 내용을 다른 파일에 중복 기록하지 않았는가?
- [ ] reference 문서를 운영 기준으로 사용하지 않는가?
- [ ] Git 커밋 완료했는가?
