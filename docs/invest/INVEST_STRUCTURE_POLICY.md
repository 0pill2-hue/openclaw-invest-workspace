# INVEST_STRUCTURE_POLICY

## 목적
- invest 파이프라인의 문서/코드/산출물 위치 정책을 고정한다.
- 상위 문서와 stage 상세 문서의 책임 경계를 분리한다.
- outputs 추적 정책을 실제 Git tracked 상태와 맞춘다.

## 1. Stage canonical 디렉토리 구조
기본안:
- `invest/stages/stageN/docs/`
- `invest/stages/stageN/inputs/`
- `invest/stages/stageN/outputs/`
- `invest/stages/stageN/scripts/`

설명:
- `docs/`는 stage 상세 운영 기준의 canonical 위치다.
- `inputs/`는 stage 실행 입력/설정/시드 위치다.
- `outputs/`는 생성 산출물 위치다.
- `scripts/`는 실행 코드 위치다.

현재 적용 상태:
- **Stage1은 이 canonical 구조를 적용한다.**
- Stage2 이상은 이번 작업 범위 밖이므로, 현재 존재하는 문서 경로를 유지하되 이후 점진적으로 같은 구조로 맞춘다.

## 2. 상위 문서와 stage 문서의 역할 분리
### 상위 문서
- `docs/invest/README.md`
  - 공통 SSOT와 stage 진입 인덱스 안내
- `docs/invest/INVEST_STRUCTURE_POLICY.md`
  - 구조/경로/outputs 정책
- `docs/invest/STAGE_EXECUTION_SPEC.md`
  - stage 상세 문서 링크 허브
- `docs/invest/OPERATIONS_SOP.md`
  - 공통 실행 절차/실패 정책/보고 기준

### stage 상세 문서
- canonical: `invest/stages/stageN/docs/STAGE{N}_RULEBOOK_AND_REPRO.md`
- 역할:
  - 해당 stage의 책임 범위
  - 실제 디렉토리 구조
  - 입력/출력/스크립트
  - 실행 순서와 재실행 규칙
  - 실패 기준과 검증 방법
  - 다음 stage로 넘기는 조건

원칙:
- 상위 문서는 공통 정책과 링크 허브만 담당한다.
- stage 운영 상세는 stage RULEBOOK만 담당한다.
- 동일 내용을 상위 문서에 복제하지 않는다.

## 3. Stage RULEBOOK 템플릿
canonical 파일명:
- `invest/stages/stageN/docs/STAGE{N}_RULEBOOK_AND_REPRO.md`

필수 섹션:
1. 목적
   - 이 stage가 왜 존재하는지 한두 문장으로 설명한다.
2. 책임 범위
   - stage가 반드시 수행해야 하는 일만 적는다.
3. 비책임 범위
   - 다음 stage 또는 상위 거버넌스로 넘기는 일을 명시한다.
4. 실제 디렉토리 구조
   - `docs/`, `inputs/`, `outputs/`, `scripts/`의 실제 경로를 적는다.
5. 입력물
   - 설정 파일, 외부 원천, upstream 산출물 등 실제 입력 경로를 적는다.
6. 출력물
   - master/raw/runtime/reports/checkpoints 등 실제 생성 경로를 적는다.
7. 스크립트 목록
   - 메인 진입점과 보조 스크립트를 실제 파일명으로 정리한다.
8. 표준 실행 순서
   - 일상 실행 시 어떤 순서로 돌리는지 적는다.
9. 일일 실행 규칙
   - 일일 오케스트레이션, 부분 실패 처리, 상태 파일 기록 규칙을 적는다.
10. 재실행 규칙
   - load existing → fetch new → merge → dedup → sort → temp write → atomic replace 원칙을 적는다.
11. 실패 기준
   - 어떤 경우 non-zero exit / fail-close 인지 적는다.
12. 검증 방법
   - checkpoint, validate, coverage catalog 등 확인 순서를 적는다.
13. 다음 stage로 넘기는 조건
   - 어떤 상태가 충족되어야 다음 stage 입력으로 승격되는지 적는다.
14. 변경 이력(optional)
   - 필요 시 중요한 변경만 짧게 적는다.

## 4. outputs 추적 정책
실제 Git tracked 상태 기준:
- `invest/stages/stage*/outputs/**`는 기본적으로 high-churn generated artifact로 본다.
- 따라서 raw/status/checkpoints/reports는 **기본 비추적**이다.

예외:
- 공개 repo의 canonical 보조 산출물은 예외적으로 tracked 가능
- 현재 Stage1 tracked 예외:
  - `invest/stages/stage1/outputs/raw/source_coverage_index.json`
  - `invest/stages/stage1/outputs/raw/qualitative/kr/dart/coverage_summary.json`

표현 원칙:
- "outputs는 모두 비추적" 같은 단정 문구는 금지
- 대신 아래처럼 적는다:
  - "outputs는 기본 비추적이다. 다만 canonical coverage/catalog 산출물은 예외적으로 tracked될 수 있다."

구분 기준:
- `raw/`
  - 원천 보존 성격 데이터. 기본 비추적.
- `reports/`
  - 점검/이상치/업데이트 리포트. 기본 비추적.
- `runtime/`
  - 상태 파일/락/실행 로그. 기본 비추적.
- `checkpoints/`
  - 게이트용 산출물. 기본 비추적.
- `sample outputs / canonical coverage catalogs`
  - 외부 검토와 구조 설명에 필요한 최소 산출물만 tracked 예외 허용.
