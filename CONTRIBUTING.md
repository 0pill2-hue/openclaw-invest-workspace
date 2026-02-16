# CONTRIBUTING

## 1) 브랜치/머지 정책
- `main` 직접 푸시 금지
- 작업은 반드시 기능 브랜치에서 진행
  - 예: `feat/data-layout-v1`, `fix/rss-parser`, `hotfix/fetch-timeout`
- `main` 반영은 Pull Request(PR)만 허용

## 2) 커밋 룰 (필수)
- 형식: `type: summary`
  - `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `hotfix`
- 예시:
  - `feat: add run manifest for data jobs`
  - `hotfix: prevent rss post id parsing failure`
- 커밋 전 체크:
  1. 민감정보 포함 여부(.env, token, key, session)
  2. 실행/문법 검증 통과(py_compile 또는 스모크)
  3. TASKS/메모리 업데이트 필요 항목 반영

## 3) 코드 적용 프로세스 (자동승인 모드)
1. 이슈/작업 정의
2. 기능 브랜치 생성
3. 구현 + 로컬 검증
4. PR 생성 (템플릿 체크리스트 필수)
5. AI 교차리뷰 수행(다른 뇌/서브에이전트 최소 1회)
6. CI 통과
7. 자동승인 후 Squash merge
8. 배포/운영 반영

> 주인님 지시로 현재는 `AUTO_APPROVE` 모드 사용 (수동 클릭 승인 생략)

## 4) 리뷰 기준
- 데이터 오염/누수/룩어헤드 가능성
- raw/clean/quarantine/audit 규칙 준수
- 결과 등급(DRAFT/VALIDATED/PRODUCTION) 준수
- 재현성(run_id, manifest, 입력/출력 추적)
- 코드 가독성(핵심 로직/예외처리/입출력 경로 주석 명확성)

## 4-1) 주석 규칙 (필수)
- 함수/핵심 블록마다 "무엇(what) / 왜(why)"를 짧게 주석으로 남긴다.
- 하드코딩 상수는 의미/근거를 주석으로 명시한다.
- 예외 처리 구간은 실패 시 영향과 복구 의도를 주석으로 남긴다.
- 경로 전환(raw/clean/quarantine/audit), 룰 버전(rule_version), 결과 등급 판단 로직은 반드시 주석 처리한다.
- 불필요한 잡담성 주석은 금지하고, 유지보수에 필요한 정보만 남긴다.

## 5) 금지 사항
- 민감정보 커밋
- 검증 없이 운영 크론/백테스트 반영
- AI 교차리뷰 없이 중요 산출물 반영
