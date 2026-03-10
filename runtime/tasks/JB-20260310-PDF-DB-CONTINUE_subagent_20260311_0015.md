# JB-20260310 PDF/DB continue subagent report (2026-03-11 00:15 KST)

- scope: JB-20260310-RAW-DB-PIPELINE / JB-20260310-STAGE1-DB-IMPLEMENT / JB-20260310-STAGE1-DB-CLEANUP 연속선에서 **PDF 수집·분해·DB 저장 축만** read-only 중심으로 점검
- destructive action: 없음
- delete/deploy/external-send/payment/live-trade: 없음
- important user update reflected: **stage01_sync_raw_to_db.py 기존 writer 실행 중이므로 duplicate writer 금지**

## 1) 현재 어디까지 진행됐는지

### A. 선행 관찰된 Stage1/Raw→DB 상태
이 턴 초반 점검에서 아래를 확인했다.

- canonical pipeline 문서/증빙은 이미 존재
  - `runtime/tasks/JB-20260310-RAW-DB-PIPELINE.md`
  - `runtime/tasks/JB-20260310-RAW-DB-PIPELINE_blocker_audit.md`
  - `runtime/tasks/proofs/JB-20260310-RAW-DB-PIPELINE_quiescent_audit.json`
  - `runtime/tasks/proofs/JB-20260310-STAGE1-DB-IMPLEMENT_verify.txt`
- 코드상 Stage1 raw→DB archive sync 엔트리포인트는 `invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
- DB archive 경로는 `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- Stage2 mirror/materialize helper는 `invest/stages/common/stage_raw_db.py`
- telegram attachment PDF artifact backfill 경로는 `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`

### B. 이번 턴에서 확인한 PDF 관련 실상(duplicate writer 인지 전 관찰 snapshot)
관찰 snapshot 기준:
- raw disk file count: `232474`
- telegram PDF meta rows on disk: `127467`
- telegram PDF meta 중 original file exists: `1213`
- telegram PDF meta 중 non-empty extract exists: `635`
- telegram PDF meta 중 manifest exists: `83941`
- telegram PDF meta 중 bundle exists: `600`
- DB active raw_artifacts: `232384`
- DB pdf_documents rows: `63735`
- DB pdf_pages rows: `9469`
- DB sync_meta.last_sync_id: `20260310T150528Z`
- runtime/raw_db_sync_status.json sync_id: `20260310T144702Z`

추가 해석:
- telegram PDF meta `127467`은 legacy/bucketed 이중 layout이 같이 남아 있어 **unique doc_key 기준 DB row(63735)** 보다 크다.
- `status.json`은 관찰 시점 기준 `sync_meta.last_sync_id`보다 뒤처져 있었다.
- 이미 active writer가 있는 동안에는 이 수치들이 중간값일 수 있으므로, **지금은 최종 확정값으로 닫지 않는다.**

### C. user update 이후 read-only writer audit
2026-03-11 00:15 KST snapshot:
- active `stage01_sync_raw_to_db.py` writer가 **2개** 관측됨
  - PID `5344` / parent `4951` (`stage01_daily_update.py --profile blog_fast`)
  - PID `5479` / parent `4952` (`stage01_daily_update.py --profile rss_fast`)
- concurrent daily_update parents:
  - PID `846` `--profile news_backfill`
  - PID `1417` `--profile telegram_fast`
  - PID `4951` `--profile blog_fast`
  - PID `4952` `--profile rss_fast`
- DB open-handle evidence:
  - both PID `5344`, `5479` hold `.sqlite3`, `-wal`, `-shm`
- file evidence at same moment:
  - DB main file mtime: `2026-03-11 00:14:35 +0900`
  - WAL file size: `18,882,083,632 bytes`
  - WAL mtime: `2026-03-11 00:15:07 +0900`
  - status json mtime: `2026-03-10 23:55:58 +0900`

판정:
- **현재는 write가 진행 중인 live state** 이므로, 추가 sync/backfill writer를 붙이면 lock/경합 위험이 높다.
- 따라서 이 서브에이전트는 여기서 **read-only audit + 증거 기록까지만** 수행하고 멈춘다.

## 2) 실제로 계속 돌린 명령/스크립트

### 문맥/기존 증빙 확인
```bash
python3 scripts/tasks/db.py summary --top 10 --recent 10
python3 scripts/directives/db.py summary --top 10 --recent 10
find runtime ...
find invest ...
find scripts ...
read runtime/tasks/JB-20260310-RAW-DB-PIPELINE.md
read runtime/tasks/JB-20260310-RAW-DB-PIPELINE_blocker_audit.md
read runtime/tasks/JB-20260310-STAGE1-DB-CLEANUP_report.md
read runtime/tasks/proofs/JB-20260310-STAGE1-DB-IMPLEMENT_verify.txt
read runtime/tasks/proofs/JB-20260310-RAW-DB-PIPELINE_blocker_audit_current.json
read runtime/tasks/proofs/JB-20260310-RAW-DB-PIPELINE_quiescent_audit.json
read invest/stages/common/stage_raw_db.py
read invest/stages/common/stage_pdf_artifacts.py
read invest/stages/stage1/scripts/stage01_sync_raw_to_db.py
read invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py
```

### live state observation (writer 실행 사실 인지 전)
```bash
python3 - <<'PY'
# raw/pdf/meta/extract/manifest/db/status snapshot audit
PY
```

### user update 반영 후 read-only writer audit만 수행
```bash
pgrep -fal 'stage01_sync_raw_to_db.py|stage01_daily_update.py|telegram_attachment_extract_backfill|python3'
ps -axo pid,ppid,lstart,etime,stat,command | egrep 'stage01_sync_raw_to_db.py|stage01_daily_update.py|telegram_attachment_extract_backfill'
lsof -n stage1_raw_archive.sqlite3 stage1_raw_archive.sqlite3-wal stage1_raw_archive.sqlite3-shm
ls -lT invest/stages/stage1/outputs/runtime/raw_db_sync_status.json
ls -lhT invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3*
```

## 3) 남은 블로커 또는 다음 액션

### immediate blocker
- **중복 writer 실행 중** (`stage01_sync_raw_to_db.py` 2개 동시 관측)
- live DB WAL이 매우 큼 (`~18.9 GB`) and still moving
- status json은 latest DB write completion을 아직 반영하지 못함

### next action after quiescence
1. `stage01_sync_raw_to_db.py` writer가 **1개 이하/종료 + WAL/DB mtime 안정화** 되는 시점 확인
2. 그 다음에만 read-only quiescent audit 재실행
3. quiescent가 확인되면 telegram PDF 기준으로
   - missing extract 재보강 대상 추림
   - missing/invalid manifest 재보강 대상 추림
   - duplicate legacy/bucketed meta 정합성 확인
4. **single writer only** 원칙으로 후속 DB sync 1회 연결
5. 최종 proof에 `status.json`, `sync_meta`, `pdf_documents/pdf_pages`, sample rel_path를 같이 묶어 남김

## 4) 증거 파일 경로

### 기존 canonical proof
- `runtime/tasks/JB-20260310-RAW-DB-PIPELINE.md`
- `runtime/tasks/JB-20260310-RAW-DB-PIPELINE_blocker_audit.md`
- `runtime/tasks/proofs/JB-20260310-RAW-DB-PIPELINE_quiescent_audit.json`
- `runtime/tasks/proofs/JB-20260310-STAGE1-DB-IMPLEMENT_verify.txt`

### 이번 턴 추가 proof
- `runtime/tasks/proofs/JB-20260310-RAW-DB-PIPELINE_writer_readonly_audit.json`
- `runtime/tasks/proofs/JB-20260310-RAW-DB-PIPELINE_writer_readonly_audit.txt`
- `runtime/tasks/JB-20260310-PDF-DB-CONTINUE_subagent_20260311_0015.md`
