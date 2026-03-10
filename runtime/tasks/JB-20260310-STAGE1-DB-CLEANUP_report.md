# JB-20260310-STAGE1-DB-CLEANUP report

- 작성 시각: 2026-03-10 07:27 KST
- 범위: **Stage1 DB/raw/archive 비파괴 정리만** 수행
- 파괴적 조치: **없음**
- 삭제/이동/리네임 실집행: **없음**
- 작업 기준 경로: `/Users/jobiseu/.openclaw/workspace`

## 1) 수행 범위
주인님 최신 지시에 따라 Stage1부터 순서대로 구현 원칙을 유지하며, 이번 턴에서는 아래만 수행했습니다.

1. Stage1 raw/db/archive 현황 inventory
2. `stage1_raw_archive.sqlite3` + raw/runtime/status 기준 정합성 점검
3. 삭제 대신 **비파괴 정리 후보 분류**
4. 안전한 후속 조치 초안 작성

실제 삭제/파괴적 정리는 하지 않았습니다.

---

## 2) 확인된 주요 경로

### 핵심 저장소
- DB: `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- raw root: `invest/stages/stage1/outputs/raw`
- runtime root: `invest/stages/stage1/outputs/runtime`

### archive 성격 경로
- 확인된 DB archive 산출물: `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- 확인된 raw archive 디렉터리: `invest/stages/stage1/outputs/raw/qualitative/text/premium/startale/_stale_blocked_archive_20260305`
- 별도 `outputs/archive/` 트리는 **미확인**

---

## 3) Inventory 결과

### raw snapshot
증거: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_proof.json`

- raw 파일 수: **206,231**
- raw 디렉터리 수: **65,206**
- raw 총 용량: **32,757,371,397 bytes**
- 상위 비중
  - `qualitative`: 199,932 files / 30,840,498,826 bytes
  - `signal`: 6,297 files / 1,897,771,248 bytes
- 확장자 상위
  - `.json`: 144,437
  - `.md`: 41,639
  - `.csv`: 6,769
  - `.txt`: 6,212
  - `.png`: 5,751

### runtime snapshot
- runtime 파일 수: **888**
- runtime 디렉터리 수: **1**
- temp 디렉터리: `telegram_attach_tmp`
- lock 파일: `telegram_scrape.lock` (5 bytes)

### DB snapshot
증거: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_commands.txt`

- `raw_artifacts`: **205,767**
- `pdf_documents`: **63,735**
- `pdf_pages`: **5,751**
- `sync_meta`: **5**

### PDF 인덱스 개요
- `docs_with_manifest_rel_path`: **15,081**
- `docs_with_original_rel_path`: **608**
- `docs_with_extract_rel_path`: **30**
- `docs_with_bundle_rel_path`: **3**
- `page_count_mismatch_docs`: **72**

### PDF 상태 요약
증거: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_proof.json`

- extraction_status
  - `failed`: 63,128
  - `ok`: 568
  - `partial`: 38
  - 빈값: 1
- render_status
  - 빈값: 48,654
  - `failed`: 14,481
  - `ok`: 600
- quality_grade
  - `F`: 63,135
  - `A`: 553
  - `B`: 47

---

## 4) 정합성 점검 결과

## 4-1. raw vs DB 정합성
- raw disk file count: **206,231**
- DB active raw_artifacts count: **205,767**
- disk only 후보: **464**
- db only 후보: **0**
- size mismatch 후보: **268**

### disk only 후보 분포
- `qualitative/attachments`: 415
- `qualitative/market`: 45
- 기타: `.DS_Store`, `qualitative/text`, `source_coverage_index.json`

### disk only 후보 대표 샘플
- `.DS_Store`
- `qualitative/attachments/telegram/Stock_Trip_stocktrip/msg_577/pdf`
- `qualitative/attachments/telegram/Stock_Trip_stocktrip/msg_700/pdf`
- `qualitative/attachments/telegram/TNBfolio_TNBfolio/msg_11208/pdf`
- `qualitative/attachments/telegram/TNBfolio_TNBfolio/msg_11345/pdf`
- `qualitative/attachments/telegram/간절한_투자스터디카페_Desperatestudycafe/msg_52131/digital-pratik-buy-the-dip.mp4`
- `qualitative/market/news/url_index/...jsonl` 계열
- `qualitative/attachments/telegram/선진짱_주식공부방_1378197756/bucket_***/msg_*__pdf_manifest.json` 계열

### size mismatch 후보 분포
- 전부 `qualitative/attachments` 하위로 관측
- 확장자: 전부 `.json`
- 대표 샘플
  - `qualitative/attachments/telegram/선진짱_주식공부방_1378197756/msg_34441/meta.json` → disk 1435 / db 842
  - `qualitative/attachments/telegram/선진짱_주식공부방_1378197756/msg_34444/meta.json` → disk 1434 / db 841
  - 유사 패턴 다수

판정:
- `db_only_count=0` 이므로 DB에만 남은 고아 경로는 이번 snapshot 기준 **미발견**
- 반대로 disk 쪽이 더 많아 **후속 수집 또는 인덱스 미반영 후보**가 존재
- 원인(동시 실행 중 생성/재색인 누락/메타 갱신 순서 문제)은 **미확인**

## 4-2. sync/status 정합성
증거: `raw_db_sync_status.json`, `sync_meta`, proof json

- `runtime_status_sync_id`: `20260309T220503Z`
- `sync_meta_last_sync_id`: `20260309T221643Z`
- `runtime_status_scanned_files`: **204,926**
- `sync_meta_last_sync_summary_scanned_files`: **205,767**
- 현재 raw disk file count(snapshot): **206,231**

판정:
- `runtime/raw_db_sync_status.json` 과 DB `sync_meta` 가 **같은 sync snapshot을 가리키지 않음**
- status 파일 수치 < sync_meta 수치 < 현재 raw disk 수치 순으로 증가
- 따라서 **status lag / 후속 수집 반영 / sync 순서 차이 후보**는 있으나 정확한 원인은 **미확인**

## 4-3. manifest vs pdf_documents
- disk manifest count: **16,092**
- pdf_documents 내 manifest path count: **15,081**
- disk에는 있으나 pdf_documents에 없는 manifest: **1,011**
- pdf_documents에는 있으나 disk에 없는 manifest: **0**

대표 샘플:
- `qualitative/attachments/telegram/선진짱_주식공부방_1378197756/bucket_000/msg_33280__pdf_manifest.json`
- `.../bucket_000/msg_33536__pdf_manifest.json`
- `.../bucket_001/msg_34433__pdf_manifest.json`
- `.../bucket_002/msg_33666__pdf_manifest.json`

판정:
- manifest 파일이 disk에는 있으나 `pdf_documents` 인덱스가 뒤따르지 못한 후보가 **1,011건**
- 삭제 대상이 아니라 **인덱스 보강 우선** 대상입니다.

## 4-4. pdf_documents / pdf_pages 정합성
- `page_count_vs_rows`: **72**
- `text_pages_vs_rows`: **0**
- `rendered_pages_vs_rows`: **0**
- page text/render path missing on disk: **없음**
- page text/render path missing in DB: **없음**

판정:
- page row 누락/과다 후보는 72건
- 그러나 text/render 파일 참조 자체는 이번 snapshot 기준 정합함
- 따라서 우선순위는 **page_count 재산정/재색인** 이고, 파일 삭제가 아님

## 4-5. pdf_documents 경로 참조 이상
- `pdf_documents`가 참조하지만 raw_artifacts에 없는 original 경로: **4건**
  - `qualitative/attachments/telegram/Stock_Trip_stocktrip/msg_577/pdf`
  - `qualitative/attachments/telegram/Stock_Trip_stocktrip/msg_700/pdf`
  - `qualitative/attachments/telegram/TNBfolio_TNBfolio/msg_11208/pdf`
  - `qualitative/attachments/telegram/TNBfolio_TNBfolio/msg_11345/pdf`

판정:
- 파일 자체 missing 이 아니라 **경로 표기/인덱스 기준 불일치 후보**로 보는 것이 안전함
- 즉시 삭제/이동 대상 아님

## 4-6. 중복 후보
### 메시지 좌표 중복(정규화 slug 기준)
검증된 중복군: **3건**

동일 normalized slug `nihilsviewofdatainformationviewofdata` 에서 아래 `message_id` 가 중복 관측됨.
- 3008
- 3013
- 3014

실제 slug 쌍:
- `Nihil_s_view_of_data_information_viewofdata`
- `Nihils_view_of_data__information_viewofdata`

판정:
- 경로/인덱스 alias 정리 후보
- 실리네임보다 **alias map / rename manifest**를 먼저 만드는 것이 안전

### 동일 SHA1 중복 파일군
proof snapshot에서 적어도 아래 1개 중복군 확인:
- SHA1 `17702dfe5f84a6310e28383d2cf4e4ff34751b6c`
- size 1,090,617 bytes
- count 44
- 예시: `qualitative/kr/dart/dart_list_20260301_*.json`

전체 중복군 상위 전수 재산출은 이번 live tree에서 장시간 쿼리로 지연되어 **미확인**. 다만 **중복 후보가 실제 존재함은 확인**했습니다.

---

## 5) 비파괴 정리 조치 초안
증거: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_action_plan.json`

### A1. manifest gap 인덱스 보강
- 대상: disk manifest 1,011건
- 조치: manifest path 목록을 기준으로 **PDF index 재보강 dry-run** 또는 audit 모드 실행
- 금지: manifest 삭제 금지

### A2. slug alias 정리 초안
- 대상: 중복 message_id 3건
- 조치: channel slug alias map 작성, rename/mapping manifest만 생성
- 금지: 실제 rename / doc_key rewrite 금지

### A3. disk-only 후보 검토 manifest
- 대상: 464건
- 세부 버킷
  - `.DS_Store`
  - `.mp4`
  - `<no_ext>`
  - `url_index/*.jsonl`
  - orphan manifest 후보
- 조치: **quarantine 후보 목록만** 작성
- 금지: 실제 이동/삭제 금지

### A4. meta.json 재동기화 우선
- 대상: size mismatch 268건
- 조치: `meta.json` 재스캔 후 DB delta 보고서 생성
- 금지: raw 파일을 DB 값으로 덮어쓰기 금지

### A5. runtime hygiene 정책 문서화
- 대상: `telegram_attach_tmp`, `telegram_scrape.lock`
- 조치: 보관/flush 기준만 문서화
- 금지: live holder 확인 없이 삭제 금지

---

## 6) 재현 가능한 실행/검증 명령과 결과
상세 파일: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_commands.txt`

핵심 검증 명령 5종을 남겼습니다.
1. raw tree inventory
2. runtime temp/lock 확인
3. sqlite table count
4. pdf index health summary
5. proof snapshot cross-check

이 파일에는 **실행 명령 + 이번 실행의 observed_result** 를 함께 기록했습니다.

---

## 7) 생성/갱신 산출물

### 최종 보고서
- `runtime/tasks/JB-20260310-STAGE1-DB-CLEANUP_report.md`

### 증거/보조 산출물
- `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_proof.json`
- `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_commands.txt`
- `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_action_plan.json`

### 보조 스크립트 초안
- `runtime/tasks/JB-20260310_STAGE1_DB_CLEANUP_proof.py`
- `runtime/tasks/JB-20260310_STAGE1_DB_CLEANUP_audit.py`

보조 스크립트는 후속 보강용 초안이며, 이번 보고의 공식 증거 경로는 위 proof/report 파일입니다.

---

## 8) 결론
이번 턴에서 확인된 핵심은 아래입니다.

1. **삭제가 아니라 인덱스 보강이 먼저**입니다.
2. raw disk > raw_artifacts > runtime status 순으로 snapshot 차이가 있어 **sync/status 불일치**가 존재합니다.
3. disk manifest 1,011건이 `pdf_documents` 에 미반영 상태입니다.
4. `page_count` 불일치 문서가 72건 있습니다.
5. slug alias 중복 3건이 확인되었습니다.
6. disk-only 464건, size mismatch 268건은 모두 **비파괴 후보 목록**으로만 유지해야 합니다.

즉시 삭제/정리보다,
**(a) sync/status 기준 정렬 → (b) manifest/pdf index 보강 → (c) alias map 설계 → (d) move/rename dry-run manifest 작성** 순서가 안전합니다.

원인 미확정 항목은 모두 **미확인**으로 유지했습니다.
