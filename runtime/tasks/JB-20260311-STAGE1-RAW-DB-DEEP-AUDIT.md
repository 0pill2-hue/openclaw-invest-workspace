# JB-20260311-STAGE1-RAW-DB-DEEP-AUDIT

- audit verdict: **DONE** (초기 read-only audit은 REWORK였고, 이후 runtime/code repair까지 완료)
- audit mode: read-only inspection → repair + revalidation 완료
- audited target DB: `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- raw root: `invest/stages/stage1/outputs/raw`
- stage2 mirror root: `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror`

## 0) audit precondition / snapshot quality
- 본 audit 중 `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json` 에서 raw DB writer가 연속으로 `RUNNING` 이었다.
  - 관측 1: `stage1_profile=blog_fast`, lock pid `71373`
  - 관측 2: `stage1_profile=dart_fast`, lock pid `71598`
- 따라서 **완전 정지(quiescent) 스냅샷 기준의 전수 동등성 증명은 이번 턴에 불가**했다.
- 대신 아래처럼 해석했다.
  1. 대표 prefix별 count/bytes 비교
  2. deterministic sample hash/content 검증
  3. Stage2 handoff currentness/staleness 확인
- 불확실한 원인 추정은 하지 않는다. freeze 없는 상태의 drift 원인은 **미확인**으로 둔다.

---

## 1) Stage1 raw tree ↔ raw DB reconciliation
증거 경로
- `invest/stages/common/stage_raw_db.py` (`stage2_default_prefixes`, `_should_track_path`, `_resolve_stage1_or_raw_path`)
- `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`
- `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- raw root representative paths listed below

### 1-1. 관측 시점 대표 prefix reconciliation
동일 count/bytes로 맞은 prefix:
- `signal/kr/ohlcv` → `2882 files / 1,419,678,765 bytes`
- `signal/kr/supply` → `2882 files / 338,542,518 bytes`
- `signal/us/ohlcv` → `509 files / 137,956,772 bytes`
- `signal/market/macro` → `24 files / 1,937,490 bytes`
- `signal/market/google_trends` → `0 / 0`
- `qualitative/market/news/selected_articles` → `4 files / 235,943 bytes`
- `qualitative/text/blog` → `40,996 files / 155,690,675 bytes`
- `qualitative/text/telegram` → `73 files / 209,512,006 bytes`
- `qualitative/text/premium/startale` → `972 files / 3,184,378 bytes`

writer running window에서 disk가 DB보다 앞선 prefix:
- `qualitative/kr/dart` → disk `718 / 600,189,316` vs db `717 / 599,690,649`
  - disk-only 대표: `invest/stages/stage1/outputs/raw/qualitative/kr/dart/dart_list_20260311_164015.csv` (`498,622 bytes`)
- `qualitative/market/rss` → disk `304 / 32,073,622` vs db `303 / 31,838,852`
  - disk-only 대표: `invest/stages/stage1/outputs/raw/qualitative/market/rss/rss_20260311-073645.json` (`234,770 bytes`)
- `qualitative/link_enrichment` → disk `42,037 / 59,445,613` vs db `42,028 / 59,439,684`
  - disk-only 9건 전부 blog link-enrichment 신규 `.md.json`
  - 대표: `invest/stages/stage1/outputs/raw/qualitative/link_enrichment/text/blog/james_lee_advisors/224212332883.md.json`
- `qualitative/attachments/telegram`
  - count는 동일(`182,990`)
  - running window 중 size drift 60건 관측됐으나, post-spot-recheck sample bundle은 DB/disk 일치로 돌아옴
  - 대표 재검증 PASS:
    - `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/Stock_Trip_stocktrip/bucket_060/msg_700__bundle.zip`
    - `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/김찰저의_관심과_생각_저장소_kimcharger/bucket_017/msg_12561__bundle.zip`

### 1-2. 전체 판정
- 관측 window 기준 `db_only_count=0`
- `disk_only_count=11` 이었고 전부 **live-mutating prefix** (`dart`, `rss`, `link_enrichment`)에 집중됐다.
- 즉, 이번 audit에서 본 큰 그림은 **DB 고아(row only) 문제는 못 봤고, drift는 active writer 동안 disk 선행 쪽으로만 관측**됐다.
- 따라서 raw DB archive 자체를 즉시 손상으로 판정할 근거는 부족하다.
- 단, **authoritative reconciliation은 writer 정지 상태에서 다시 1회 freeze-audit 필요**.

---

## 2) `raw_artifacts` sample path/hash existence integrity
증거 경로
- DB sample source: `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- raw sample files: 아래 rel_path들

### 2-1. sample method
- 각 Stage2 tracked prefix별 first/last row + PDF 관련 추가 sample(`meta.json`, `__pdf_manifest.json`, `__page_001.png`, selected_articles latest`)를 deterministic하게 점검
- 총 sample: **27개**

### 2-2. 결과
- **25/27 full pass**
  - 존재 / size / mtime / sha1 / DB blob content 모두 일치
- 대표 PASS
  - `signal/kr/ohlcv/000020.csv`
  - `signal/us/ohlcv/A.csv`
  - `qualitative/market/news/selected_articles/selected_articles_20260311-010827.jsonl`
  - `qualitative/attachments/telegram/Nihil_s_view_of_data_information_viewofdata/bucket_064/msg_3008__pdf_manifest.json`
  - `qualitative/attachments/telegram/Nihil_s_view_of_data_information_viewofdata/bucket_064/msg_3008__page_001.png`
  - `qualitative/attachments/telegram/Nihil_s_view_of_data_information_viewofdata/msg_3008/meta.json`

### 2-3. FAIL sample 2건
둘 다 canonical raw payload가 아니라 **live summary sidecar** 였다.
- `invest/stages/stage1/outputs/raw/qualitative/kr/dart/coverage_summary.json`
- `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_merged_summary.json`

관측 내용:
- disk size는 DB row size와 같았지만, `mtime/sha1/content` 가 달랐다.
- 해석: 이 2개는 sync 이후 재생성/갱신된 derived summary일 가능성이 높다. 정확한 갱신 주체는 **미확인**.

### 2-4. sample integrity 판정
- **primary payload는 정상**으로 보인다.
- 다만 `coverage_summary.json`, `selected_articles_merged_summary.json` 같은 derived summary를 raw DB exact-hash invariant에 섞으면 false-positive가 난다.

---

## 3) `pdf_documents` / `pdf_pages` / manifest consistency
증거 경로
- `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- resolver contract: `invest/stages/common/stage_raw_db.py` 의 `_resolve_stage1_or_raw_path`
- representative manifest:
  - `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/Nihil_s_view_of_data_information_viewofdata/bucket_064/msg_3008__pdf_manifest.json`
  - corresponding meta: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/Nihil_s_view_of_data_information_viewofdata/msg_3008/meta.json`

### 3-1. corrected path-resolution check
`outputs/raw/...` prefix를 `_resolve_stage1_or_raw_path` 규칙으로 해석하면:
- `manifest_rel_path` missing on disk: **0**
- `manifest_rel_path` missing in raw_artifacts: **0**
- `extract_rel_path` missing on disk: **0 / 59,672**
- `extract_rel_path` missing in raw_artifacts: **0 / 59,672**
- `bundle_rel_path` missing on disk: **0 / 608**
- `bundle_rel_path` missing in raw_artifacts: **0 / 608**
- `pdf_pages.text_rel_path` missing on disk/DB: **0 / 5,665**
- `pdf_pages.render_rel_path` missing on disk/DB: **0 / 5,840**

즉, **경로 해석을 바로 잡으면 경로 참조 자체는 정합**이다.

### 3-2. table-level consistency
- `pdf_documents`: **63,735**
- `pdf_pages`: **9,632**
- `docs_with_manifest`: **608**
- `docs_with_extract`: **59,672**
- `docs_with_bundle`: **608**
- `doc.page_count != pdf_pages row_count`: **0**
- `doc.text_pages != non-empty text rows`: **0**
- `doc.rendered_pages != non-empty render rows`: **0**
- manifest JSON parse error: **0**
- `pdf_documents.page_count != manifest.page_count`: **0**

### 3-3. important contract divergence: 73 docs
- `manifest.pages[] length != pdf_pages row_count` 문서: **73건**
- representative proofs:
  - `telegram:Nihil_s_view_of_data_information_viewofdata:3013`
  - `telegram:Nihil_s_view_of_data_information_viewofdata:3014`
  - `telegram:Stock_Trip_stocktrip:1018`
- 공통 패턴:
  - manifest `max_pages_applied=25`
  - manifest `pages[]` 길이 = `25`
  - DB `page_count` = 실제 전체 페이지 수(예: 70, 100, 43)
  - `pdf_pages` row도 전체 페이지 수까지 채워져 있음
  - **manifest에 없는 extra page rows는 전부 blank placeholder** (`text_rel_path=''`, `render_rel_path=''`)였다.

판정:
- 파일 손상은 아님
- 하지만 `runtime/tasks/JB-20260310-RAW-DB-PIPELINE_stage2_handoff.md` 에 적힌 “`pdf_pages row count / manifest pages[] len = cap applied actual stored pages 수`” 계약과는 **현재 DB가 다르다**.
- 즉, 현행 구현은 “전체 page_count까지 placeholder row를 채우는 방식”이고, 문서/운영 계약은 그에 맞춰 다시 정렬돼야 한다.

### 3-4. manifest inventory asymmetry
- disk manifest inventory: **41,980 files** (`*__pdf_manifest.json`)
- 그런데 `meta.json` 중 `pdf_manifest_path` 를 가진 건 **608건**뿐이었다.
- attachment `meta.json` 총량: **64,140**
- 따라서 `pdf_documents` 가 manifest-bearing doc로 인식하는 범위는 현재 **608건**으로 좁다.

판정:
- 이것을 즉시 corruption으로 단정할 근거는 없다. indexer는 `meta.json` 의 `pdf_manifest_path` contract를 SSOT로 사용한다.
- 다만 disk manifest inventory와 DB-indexed manifest doc 범위의 괴리가 매우 크므로, **운영상 후속 설명/정책 명시가 필요**하다.

---

## 4) `selected_articles` source/domain contamination
증거 경로
- live dir: `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles`
- summary: `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_merged_summary.json`
- runtime status: `invest/stages/stage1/outputs/runtime/news_selected_articles_status.json`
- live files:
  - `.../selected_articles_20260311-010827.jsonl`
  - `.../selected_articles_20260311-013501.jsonl`
  - `.../selected_articles_20260311-072254.jsonl`

결과:
- live files: **3개**
- live rows: **64**
- `source_domains`: `{"n.news.naver.com": 64}`
- `source_kinds`: `{"naver_finance_list": 64}`
- parsed URL origin domains: `{"n.news.naver.com": 64}`
- contamination rows(non-Naver domain): **0**
- contamination rows(non-`naver_finance_list` kind): **0**
- runtime status도 `merge_all_indexes=false`, `index_file_count=1`, Naver index 1개로 맞다.

판정:
- **현재 live selected_articles corpus는 contamination 미발견 (PASS)**
- summary/status/live file set도 현재는 서로 정렬돼 있다.

---

## 5) Stage2 mirror / handoff materialization + smoke
증거 경로
- mirror root: `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror`
- current symlink: `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/current`
- current meta: `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/snapshots/20260310T224733Z/meta.json`
- incomplete snapshot example: `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/snapshots/20260311T064150Z`
- DB sync meta: `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3` (`sync_meta.last_sync_id`)
- stage2 code path:
  - `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
  - `invest/stages/stage2/scripts/stage02_qc_cleaning_full.py`

### 5-1. materialization state
- `current` 는 symlink이며 target은:
  - `.../snapshots/20260310T224733Z`
- 그러나 DB latest completed sync는:
  - `last_sync_id = 20260311T074250Z`
- 따라서 **current mirror sync_id != DB last_sync_id**

### 5-2. incomplete snapshots
`raw/` 는 있는데 `meta.json` 이 없는 snapshot 디렉터리 관측:
- `20260310T120528Z`
- `20260310T124536Z`
- `20260310T215202Z`
- `20260311T064150Z`

이들은 완성 snapshot으로 보기 어렵다.

### 5-3. representative smoke verification
대표 smoke 대상으로 current day live file을 잡아 확인했다.
- target rel_path:
  - `qualitative/market/news/selected_articles/selected_articles_20260311-072254.jsonl`
- raw disk: **exists**
- DB active row: **exists** (`size=77,981`, sha1=`6483c961883525bde95bf3bbb212d9d8ec5c3328`)
- Stage2 current mirror: **missing**

추가 smoke:
- `signal/kr/ohlcv/000020.csv`
  - current mirror file exists는 하나, DB current sha1 와 불일치
  - 즉 current mirror 전체가 **stale snapshot** 이다.

판정:
- **Stage2 handoff current materialization은 현재 FAIL**
- mirror가 존재한다는 사실만으로는 충분하지 않고, `current/meta.json.sync_id == sync_meta.last_sync_id` 가 맞아야 authoritative handoff로 볼 수 있다.

---

## 6) lightweight invariants + fail-close 기준

### 6-1. routine lightweight invariant set
1. **No active writer for authoritative checks**
   - `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json.status != RUNNING`
2. **Stage2 currentness parity**
   - `stage1 DB sync_meta.last_sync_id == stage2 mirror current/meta.json.sync_id`
3. **Snapshot completeness**
   - `snapshots/<sync_id>/raw/` 가 있으면 `snapshots/<sync_id>/meta.json` 도 반드시 있어야 함
4. **raw↔DB post-sync reconciliation**
   - quiescent 상태에서 `db_only_count == 0`
   - quiescent 상태에서 `disk_only_count == 0`
   - derived summary sidecar는 exact-hash invariant에서 제외하거나 sync 직후 재생성 규칙을 별도로 둔다
5. **sample hash set**
   - prefix별 deterministic sample(예: first/last + targeted PDF assets) sha1/content equality 유지
6. **PDF integrity**
   - `pdf_documents.page_count == manifest.page_count`
   - `_resolve_stage1_or_raw_path` 기준으로 manifest/extract/bundle/page refs 전부 resolve 가능
   - `text_pages == non-empty text rows`, `rendered_pages == non-empty render rows`
7. **selected_articles clean lane**
   - live corpus `source_domains == {n.news.naver.com}`
   - `source_kinds == {naver_finance_list}`
   - runtime status `merge_all_indexes=false`, `index_file_count=1`

### 6-2. fail-close conditions
아래는 **즉시 fail-close** 권장:
- `raw_db_sync_status.status == RUNNING` 인데 authoritative handoff / full reconciliation / Stage2 rebuild를 시작하려는 경우
- `current/meta.json.sync_id != sync_meta.last_sync_id`
- `snapshots/<sync_id>/raw` 는 있으나 `meta.json` 이 없는 경우
- quiescent 상태인데 `db_only_count > 0` 또는 `disk_only_count > 0`
- selected_articles live corpus에서 non-Naver domain/kind 1건이라도 검출되는 경우
- PDF에서 `pdf_documents.page_count != manifest.page_count`
- PDF capped docs에서 manifest에 없는 extra `pdf_pages` row가 **blank placeholder가 아닌 실제 path를 가질 경우**

### 6-3. doc/contract alignment follow-up
- 현재 73건 capped PDF는 “placeholder `pdf_pages` row를 전체 page_count까지 채우는 구현”이다.
- 운영 문서가 “`pdf_pages row count == manifest pages[] len`” 을 전제로 하면 오판정이 난다.
- 따라서 둘 중 하나로 정렬 필요:
  1. 구현을 manifest pages[] 길이에 맞추기
  2. 아니면 문서를 “extra blank placeholder rows 허용” 계약으로 수정하기

---

## 7) initial read-only conclusion
- Stage1 raw DB 자체는 **대체로 건강**해 보인다. 대표 prefix 다수가 exact match였고, `db_only` 고아는 못 봤다.
- raw_artifacts sample hash/content도 **primary payload 기준 양호**하다. 다만 derived summary sidecar는 volatile하다.
- PDF 경로/파일 참조는 resolver 기준으로 정합하지만, **73건 capped PDF contract divergence** 는 남아 있다.
- selected_articles contamination은 **현재 PASS** 다.
- 당시에는 **Stage2 current mirror가 DB latest sync를 따라오지 못해 authoritative handoff는 FAIL** 이었다.
- 그래서 초기 read-only 판정은 **REWORK** 였다.

## 8) repair closure / before-after
### 8-1. root cause
- `invest/stages/common/stage_raw_db.py`의 `prepare_stage2_raw_input_root(...)`가 **snapshot 디렉터리 존재 여부만 확인**하고 `current` symlink를 갱신했다.
- 동시에 `materialize_snapshot_from_db(...)`는 snapshot 디렉터리/`raw/`를 먼저 만들고 **마지막에만 `meta.json`을 기록**했다.
- 그래서 **동시 호출 또는 중도 종료 시 partial snapshot이 남고, 다음 호출이 그것을 완성본으로 오인**해 `current`를 incomplete snapshot으로 바꾸는 구조였다.

### 8-2. before state
- current pointer:
  - `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/current -> .../snapshots/20260311T121049Z`
- target completeness:
  - `20260311T121049Z/meta.json` 없음
  - 사실상 `qualitative/attachments/telegram` 위주 partial 상태
- missing key paths in old current:
  - `raw/signal/kr/ohlcv/000020.csv`
  - `raw/signal/market/macro/DGS10.csv`
  - `raw/qualitative/kr/dart/dart_list_20260311_194017.csv`
  - `raw/qualitative/market/rss/rss_20260311-110505.json`
  - `raw/qualitative/market/news/selected_articles/selected_articles_20260311-103721.jsonl`

### 8-3. applied repair
- 파일 수정: `invest/stages/common/stage_raw_db.py`
- 반영 내용:
  1. `.prepare.lock` advisory lock 추가
  2. `meta.json`/`raw/`/`sync_id`/`prefixes` 기반 snapshot completeness 검증 추가
  3. `.<sync_id>__building__...` staging 위치에 먼저 materialize 후 완료 시 rename하는 **atomic publish** 적용
  4. invalid snapshot은 삭제하지 않고 preserve rename 후 교체하도록 보강
- 실행 조치:
  - repaired `prepare_stage2_raw_input_root(...)`를 직접 호출해 최신 completed sync 기준 snapshot을 재생성하고 `current`를 갱신했다.

### 8-4. after state
- Stage1 raw DB runtime status now:
  - `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json.status = PASS`
  - `stage1_profile = rss_fast`, `lock_pid = null`
- Stage1 DB latest completed sync:
  - `last_sync_id = 20260311T140530Z`
  - `last_sync_finished_at = 2026-03-11T14:05:30.144726+00:00`
- current pointer:
  - `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/current -> .../snapshots/20260311T140530Z`
- current meta:
  - `sync_id = 20260311T140530Z`
  - `file_count = 274591`
  - `total_bytes = 8795953989`
- revalidated key paths in new current:
  - `raw/signal/kr/ohlcv/000020.csv` → PASS
  - `raw/signal/market/macro/DGS10.csv` → PASS
  - `raw/qualitative/kr/dart/dart_list_20260311_194017.csv` → PASS
  - `raw/qualitative/market/rss/rss_20260311-110505.json` → PASS
  - `raw/qualitative/market/news/selected_articles/selected_articles_20260311-103721.jsonl` → PASS
  - `raw/qualitative/attachments/telegram/Nihil_s_view_of_data_information_viewofdata/msg_3008/meta.json` → PASS
- idempotence smoke:
  - repaired `prepare_stage2_raw_input_root(...)` 재호출 elapsed ≈ `5.015s`
  - `current` 유지: `.../snapshots/20260311T140530Z`

### 8-5. preserved evidence
- old incomplete current target remains preserved as evidence:
  - `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/snapshots/20260311T121049Z`
- additional incomplete remnants observed (non-current):
  - `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/snapshots/20260311T135155Z`
  - `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/snapshots/.20260311T135155Z__building__20260311T141115Z__pid294`

## 9) final conclusion after repair
- Stage1 raw DB 정합성 audit 핵심 결론은 유지된다: **raw DB 본체는 대체로 건강**하다.
- 기존 blocker였던 **Stage2 upstream mirror/current incomplete snapshot 문제는 실제로 수리 완료**됐다.
- 현재는 `current/meta.json.sync_id == Stage1 DB sync_meta.last_sync_id` 가 성립하고, Stage2 rerun에 필요한 핵심 prefix 경로들도 PASS다.
- 별도 후속 이슈로 남는 것은 capped PDF 73건의 계약 정렬이며, 이것은 본 mirror/current blocker와는 분리된 후속 work item이다.
- 따라서 본 티켓의 현재 운영 판정은 **DONE** 이다.
