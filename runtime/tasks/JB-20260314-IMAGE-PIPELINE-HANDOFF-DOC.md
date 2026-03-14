# JB-20260314-IMAGE-PIPELINE-HANDOFF-DOC

- ticket: JB-20260314-IMAGE-PIPELINE-HANDOFF-DOC
- status: DRAFT
- owner: owner
- purpose: 다른 에이전트가 Stage1/2 이미지 보존·삭제·DB 검증 작업을 안전하게 이어받도록 실행 순서, 산출물, 예외 대응을 고정한다.
- checked_at: 2026-03-14 10:43 KST

## 0. 한줄 결론
**실행 순서는 `용량 대안/추정(dry-run) → 삭제 후보 리스트 산출(실삭제 금지) → Stage1/2 DB 검증 → 소규모 시범 materialization` 이다.**
이미지/다운사이징 저장을 먼저 대량 수행하면 저장소 폭증 위험이 있으므로 금지한다.

## 0-1. 저성능 에이전트용 실행 계약 (5.3 spark / qwen3.5 기준)
이 문서는 **추론을 많이 못하는 에이전트도 그대로 따라 하도록** 쓴다. 아래 규칙을 우선한다.

1. 한 번에 한 단계만 한다.
2. **실삭제 금지**. owner 승인 전에는 어떤 파일도 지우지 않는다.
3. **실제 이미지 저장/다운사이징/OCR 금지**. 먼저 dry-run만 한다.
4. dry-run 결과가 없으면 다음 단계로 가지 않는다.
5. DB 검증 전에는 deletion list를 `후보`로만 쓴다. `확정`이라고 쓰지 않는다.
6. 디스크가 꽉 차면 자동 복구 시도하지 말고 즉시 중지 후 보고한다.
7. 모르면 추측하지 말고 `미확인`이라고 쓴다.
8. 출력은 항상 아래 4개 파일 또는 섹션으로 남긴다.
   - dry-run report
   - deletion candidate report
   - stage1/stage2 db verification report
   - go/no-go decision

### 저성능 에이전트 금지사항
- keep-all 방식으로 전부 저장 시작 금지
- owner 승인 없이 삭제 금지
- writer active 상태에서 authoritative DB 판정 금지
- 디스크 full 후 같은 배치 즉시 재시작 금지
- 문서에 없는 새 규칙 임의 추가 금지

### 저성능 에이전트용 최소 성공 조건
아래 4개를 만들면 1차 성공이다.
1. 현재 free space 기록
2. dry-run 예상 용량 기록
3. 삭제 후보 3버킷(`SAFE_CANDIDATE_NOW`, `VERIFY_AFTER_DB_CHECK`, `BLOCKED`) 기록
4. Stage1/2 DB 검증 PASS/REWORK/BLOCKED 중 하나 기록

## 1. 현재 확인된 사실
1. 현재 디스크 여유:
   - `df -h .` 기준 `/System/Volumes/Data` = `460Gi` total / `289Gi` used / `132Gi` avail / `69%` used.
   - 즉시 압박 상태는 아님.
2. 기존 이미지 자산 파이프라인 판단:
   - `runtime/tasks/JB-20260313-TELEGRAM-BLOG-IMAGE-ASSET-PIPELINE.md`
   - Telegram image는 현재 meta-only에 가깝고, blog image는 Stage1에서 유실된다.
   - naive keep-all은 수십~수백 GiB급 저장소 폭증 가능성이 높다.
3. 기존 삭제 효과가 확인된 범위:
   - `runtime/tasks/JB-20260313-PDF-ORIGINAL-RENDER-CLEANUP.md`
   - text 추출 완료 페이지 render 정리로 약 `52.387 GiB` 회수한 전례가 있다.
4. Stage1/2 DB authoritative 체크에 필요한 invariant 근거:
   - `runtime/tasks/JB-20260311-STAGE1-RAW-DB-DEEP-AUDIT.md`
   - no active writer, Stage2 mirror currentness parity, raw↔DB reconciliation, PDF/path resolve, sample hash 검증이 핵심이다.
5. 관련 directive:
   - `JB-20260313-IMAGE-RETENTION-1M-CLEANUP`
   - 1개월 초과 이미지/파생데이터 정리 의도는 있으나, dangling link와 Stage1/2/3 계약/DB 정합성 유지가 선행 조건이다.

## 2. 이 문서의 목표
다음 4가지를 다른 에이전트가 바로 수행 가능하게 만든다.

1. **용량 대안 설계**
   - 이미지를 실제로 모으기 전에 얼마나 늘어날지 추정하는 dry-run 설계
2. **삭제 후보 리스트 산출 설계**
   - Stage1/2 raw 및 파생데이터 중 삭제 가능 후보를 실삭제 없이 목록화
3. **Stage1/2 DB 검증 설계**
   - 이미지 보존/삭제 전후로 DB와 raw tree가 깨지지 않았는지 확인하는 절차 정의
4. **예외 대응 설계**
   - 수집/다운사이징/OCR 중 디스크 full이 나면 어떻게 멈추고 복구할지 결정

## 3. 다른 에이전트가 따라야 할 작업 순서 (고정)
### Phase A. Preflight
1. `df -h .`
2. `openclaw status --deep`
3. authoritative 검사 전에는 writer 상태 확인
   - `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json.status != RUNNING`
4. 현재 관련 문서 3개 읽기
   - `runtime/tasks/JB-20260313-TELEGRAM-BLOG-IMAGE-ASSET-PIPELINE.md`
   - `runtime/tasks/JB-20260311-STAGE1-RAW-DB-DEEP-AUDIT.md`
   - `runtime/tasks/JB-20260313-PDF-ORIGINAL-RENDER-CLEANUP.md`

### Phase B. Dry-run 용량 추정 (실제 binary 저장 금지)
1. Telegram/blog/PDF image 자산을 표본 또는 전체 메타 기준으로 스캔
2. 다음 class별 예상량을 계산
   - `drop`
   - `preview_only`
   - `keep_for_analysis`
   - `keep_and_ocr`
3. 실제 파일 저장 없이 다음만 산출
   - 총 대상 수
   - 원본 총 bytes
   - class별 예상 파일 수/bytes
   - preview 예상 bytes
   - OCR 예상 bytes
   - hot/cold retention 적용 시 잔존량
4. 결과 보고서를 남긴다.

### Phase C. 삭제 후보 리스트 산출 (실삭제 금지)
1. Stage1 raw / Stage2 mirror / 파생 preview / OCR / legacy image_map 계열을 분리한다.
2. 각 항목을 다음 셋으로 분류한다.
   - `SAFE_CANDIDATE_NOW`: lineage와 대체본이 이미 확인된 항목
   - `VERIFY_AFTER_DB_CHECK`: DB/path 검증 후 삭제 가능 여부가 갈리는 항목
   - `BLOCKED`: 계약 미정, 대체본 미확인, 현재 writer 사용중, 참조 끊김 위험
3. owner 승인 전에는 실제 삭제 금지.
4. 삭제 리스트는 경로 glob가 아니라 **구체 파일/폴더/row 기준**으로 남긴다.

### Phase D. Stage1/2 DB 검증
1. writer quiescent 확인
2. Stage2 mirror current/meta sync_id가 Stage1 DB latest sync_id와 일치하는지 확인
3. raw↔DB reconciliation
   - disk_only_count
   - db_only_count
   - representative sample hash/path resolve
4. image/PDF lineage 검증
   - DB rel_path가 실제 파일로 resolve 되는지
   - manifest/meta/preview/original/OCR 경로가 일관적인지
5. Stage2 clean/sidecar 기대계약 검증
   - 본문 lean 유지
   - 필요한 asset lineage는 sidecar 또는 ref로 남는지
6. 보고서를 남긴다.

### Phase E. 소규모 시범 materialization
1. 위 A~D가 통과한 뒤에만 수행
2. 전체가 아니라 소규모 샘플로 진행
3. 실행 중에도 disk guard를 둔다.
4. guard hit 시 즉시 중단하고 예외 절차로 이동

## 4. Dry-run 설계 상세
## 4-1. 목적
- 실제 이미지/preview/OCR 파일을 만들지 않고도 저장소 증가량을 미리 추정한다.
- keep-all을 금지하고 selective retention이 실제로 어느 정도 공간을 쓰는지 수치화한다.

## 4-2. 입력 단위
다음 family를 분리 집계한다.
1. Telegram image attachment
2. Telegram PDF page/render 계열
3. Blog inline image / attachment 후보
4. 기존 image_map / images_ocr / preview 파생물

## 4-3. class 정의
- `drop`: metadata/hash만 유지, binary 저장 없음
- `preview_only`: 작은 preview만 유지
- `keep_for_analysis`: 분석용 1본 유지, OCR는 선택
- `keep_and_ocr`: 분석용 1본 + OCR text + 선택 tile/page 유지

## 4-4. 기본 cap 제안
- 일반 image preview: long edge `<= 768px`, 목표 `<= 200KB`
- PDF preview page: long edge `<= 1200px`, 목표 `<= 250KB`
- analysis-grade image: long edge `<= 2048px` 또는 원본이 더 작으면 원본 유지
- PDF page는 전 페이지 render 금지, dense page/tile만 선택 생성

## 4-5. dry-run 산출물 형식 (필수)
다음 필드를 가진 JSON + md 요약을 남긴다.
- `checked_at`
- `disk_free_before_bytes`
- `families[]`
  - `family`
  - `asset_count`
  - `source_bytes_total`
  - `predicted_preview_bytes`
  - `predicted_analysis_bytes`
  - `predicted_ocr_bytes`
  - `predicted_total_bytes`
  - `predicted_by_class`
- `worst_case_total_bytes`
- `recommended_total_bytes`
- `go_no_go`
- `blocking_reasons[]`

## 4-6. Go / No-Go 기준
다음 중 하나라도 만족하면 **NO_GO**.
- dry-run 예상 추가량이 owner가 허용한 임계치를 초과
- 남은 여유 공간 대비 worst-case 여유가 부족
- writer active 상태라 authoritative 기준점 확보 실패
- 어떤 class에서든 lineage path schema가 미정

## 5. 삭제 후보 리스트 설계
## 5-1. 삭제 후보를 먼저 뽑되, 실삭제는 나중
주인님 지시상 삭제 리스트는 필요하지만, **실삭제 판단은 반드시 DB/path 검증 뒤**에 한다.
따라서 산출물은 “후보 리스트”다.

## 5-2. 후보 버킷
### A. 즉시 검토 가능한 local/generated
- `runtime/tasks/proofs`
- `runtime/browser-profiles`
- `runtime/tmp*`
- `runtime/backups`
설명: 운영 원본이 아닌 local/generated 영역. 단, 역시 owner 승인 후 삭제.

### B. Stage1/2 derived image 계열
- text가 이미 확보된 render/preview
- selected page/tile 외 나머지 다중 preview
- old image_map/images_ocr 파생물
설명: lineage와 text 대체본이 확인되면 유력한 삭제 후보.

### C. raw/original 계열
- Stage1 original image/PDF
- Stage2 mirror 잔존본
설명: 가장 위험한 영역. 대체본/DB rel_path/consumer 계약 확인 전에는 `BLOCKED` 기본값.

## 5-3. 각 후보에 반드시 기록할 필드
- `bucket`
- `path`
- `family`
- `bytes`
- `why_candidate`
- `replacement_proof`
- `db_rows_affected`
- `stage2_or_stage3_consumer_risk`
- `deletion_gate` (`safe_now|after_db_check|blocked`)

## 5-4. 삭제 리스트 최소 산출물
1. `*_safe_candidates.json`
2. `*_verify_after_db_check.json`
3. `*_blocked.json`
4. md 요약표

## 6. Stage1/2 DB 검증 설계
## 6-1. Precondition
- authoritative 검증 전에 반드시 no active writer
- `raw_db_sync_status.status != RUNNING`

## 6-2. 필수 invariant
다음은 기존 deep audit에서 가져온 핵심 invariant다.
1. **No active writer**
2. **Stage2 currentness parity**
   - Stage1 DB latest sync_id == Stage2 mirror current/meta.json sync_id
3. **Snapshot completeness**
   - snapshot raw가 있으면 meta.json도 있어야 함
4. **raw↔DB reconciliation**
   - quiescent 상태에서 db_only_count == 0
   - quiescent 상태에서 disk_only_count == 0
5. **Sample hash / path resolve**
   - deterministic sample의 sha1/content/path resolve 일치
6. **PDF integrity**
   - manifest/page_count/path resolve consistency
7. **image lineage integrity**
   - preview/original/analysis/OCR 경로가 DB/meta/manifest와 상호 resolve 가능

## 6-3. 이미지 작업에 추가할 확인 항목
1. Telegram image가 meta-only에서 끝나는지 여부
2. Blog image가 Stage1에서 실제 manifest로 수집되는지 여부
3. Stage2 clean 본문은 lean하지만, sidecar/ref로 lineage가 남는지 여부
4. Stage3가 image를 직접 먹지 않더라도 ref/OCR 텍스트를 선택 소비할 준비가 되었는지 여부

## 6-4. 검증 결과 분류
- `PASS`: 즉시 다음 단계 가능
- `REWORK`: 코드/경로/계약 교정 후 재검증
- `BLOCKED`: owner 승인, 외부 의존, 또는 설계 미정으로 진행 금지

## 7. 디스크 full 예외 대응 플레이북
## 7-1. 원칙
**디스크 full이 나면 자동으로 production data를 지우지 않는다.**
먼저 작업을 멈추고, partial state를 보존하고, 안전영역 또는 owner 승인 범위만 정리한다.

## 7-2. 즉시 수행 순서
1. 현재 실행중인 materialization/downsize/OCR 배치를 즉시 중지
2. 상태 증빙 확보
   - `df -h .`
   - `openclaw status --deep`
   - 관련 runtime status/json
3. writer가 active면 DB/WAL 정합성부터 확인
4. partial output 경로와 마지막 성공 단위를 기록
5. owner 승인 없는 production 삭제 금지

## 7-3. 우선 정리 가능한 영역
owner가 이미 승인했거나 재승인 가능한 **local/generated**부터 본다.
- `runtime/tasks/proofs`
- `runtime/browser-profiles`
- `runtime/tmp*`
- `runtime/backups`

## 7-4. full 직후 금지사항
- panic retry loop 금지
- 같은 배치를 즉시 재시작 금지
- Stage1 raw/original을 근거 없이 선삭제 금지
- DB sync가 RUNNING인데 mirror authoritative 검증 시작 금지

## 7-5. 재개 조건
아래가 모두 만족해야 재개한다.
1. 충분한 free space 확보
2. writer quiescent 또는 정상상태 확인
3. partial output 범위와 resume point 기록 완료
4. dry-run 예상량 재산출 완료

## 8. 다른 에이전트에게 요구되는 최종 산출물
다른 에이전트는 최소 아래 4개를 남겨야 한다.
1. `dry-run capacity report`
2. `deletion candidate report`
3. `stage1/stage2 db verification report`
4. `go/no-go + next batch plan`

## 9. 권장 파일/증빙 경로
- 메인 설계 문서: `runtime/tasks/JB-20260314-IMAGE-PIPELINE-HANDOFF-DOC.md`
- dry-run proof: `runtime/tasks/proofs/JB-20260314-IMAGE-PIPELINE-HANDOFF-DOC/`
- 삭제 후보 proof: `runtime/tasks/proofs/JB-20260314-IMAGE-PIPELINE-HANDOFF-DOC/delete_candidates/`
- DB 검증 proof: `runtime/tasks/proofs/JB-20260314-IMAGE-PIPELINE-HANDOFF-DOC/db_verify/`

## 10. 다른 에이전트용 짧은 시작 프롬프트
아래 문장을 그대로 넘겨도 된다.

> 이 문서 `runtime/tasks/JB-20260314-IMAGE-PIPELINE-HANDOFF-DOC.md` 만 기준으로 작업하라. 순서는 무조건 1) `df -h .` 와 상태 확인 2) dry-run 용량 추정 3) 삭제 후보 리스트 산출(실삭제 금지) 4) Stage1/2 DB 검증 5) 소규모 시범 materialization 검토 이다. owner 승인 전에는 삭제하지 말고, dry-run 없이 실제 이미지 저장/다운사이징/OCR를 시작하지 마라. 모르면 `미확인`이라고 쓰고 멈춰라. 디스크 full이면 자동삭제/자동재시작하지 말고 즉시 중지 후 증빙과 예외 보고를 남겨라.

### 10-1. 저성능 에이전트용 체크리스트
- [ ] `df -h .` 결과 기록
- [ ] writer active 여부 기록
- [ ] dry-run report 작성
- [ ] deletion candidates 3버킷 작성
- [ ] Stage1/2 DB verification 작성
- [ ] go/no-go 기록
- [ ] owner 승인 전 실삭제 안 했는지 확인

## 11. 미확인 / 후속 확인 필요
- 현재 Telegram/blog image의 실제 전체 건수
- class별 실제 평균 preview/OCR bytes
- image_map/images_ocr 레거시 경로별 실사용 잔존량
- Stage3 image/OCR row builder 구현 상태의 최신 코드 기준 상세

## 12. 다음 액션
1. 다른 에이전트가 이 문서 기준으로 dry-run부터 수행
2. dry-run 수치가 나오면 삭제 후보 우선순위 재정렬
3. DB 검증 PASS가 난 범위만 시범 materialization
4. owner 승인 후에만 실제 삭제 반영
