# CONTRIBUTING

## 1) 브랜치/머지 정책
- `main` 직접 푸시 금지
- 작업은 기능 브랜치에서 진행
  - 예: `feat/data-layout-v1`, `fix/rss-parser`, `hotfix/fetch-timeout`
- `main` 반영은 Pull Request(PR)만 허용

## 2) 커밋 룰 (필수)
- 형식: `type: summary`
  - `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `hotfix`
- 커밋 전 체크:
  1. 민감정보 포함 여부(.env, token, key, session)
  2. 실행/문법 검증 통과(py_compile 또는 스모크)
  3. TASKS/메모리 업데이트 필요 항목 반영

## 2-1) Push 타이밍 정책 (Canonical)
- SSOT: 이 섹션
- 원칙:
  1. 커밋 직후 지체 없이 원격에 push한다.
  2. push 대상은 현재 작업 브랜치이며, `main` 직접 push는 금지한다.
  3. 동일 작업에서 커밋이 2개 이상 누적되면 마지막 커밋 직후 즉시 push한다.
- 예외(2개만 허용):
  - 민감정보 누출 점검 미완료
  - 대용량 산출물 정리/ignore 정합성 미완료

## 3) 코드 적용 프로세스
1. 이슈/작업 정의
2. 기능 브랜치 생성
3. 구현 + 로컬 검증
4. PR 생성
5. 중요 변경에 한해 AI 교차리뷰 1회
6. CI 통과
7. 승인 후 merge
8. 배포/운영 반영

> 중요 변경 = 전략/게이트/운영크론/데이터오염 위험/외부 영향이 있는 변경

## 4) 리뷰 기준
- 데이터 오염/누수/룩어헤드 가능성
- raw/clean/quarantine/audit 규칙 준수
- 결과 등급(DRAFT/VALIDATED/PRODUCTION) 준수
- 재현성(run_id, manifest, 입력/출력 추적)
- 코드 가독성(핵심 로직/예외처리/입출력 경로 주석 명확성)

## 5) 금지 사항
- 민감정보 커밋
- 검증 없이 운영 크론/백테스트 반영
- 중요 변경 무검토 반영
