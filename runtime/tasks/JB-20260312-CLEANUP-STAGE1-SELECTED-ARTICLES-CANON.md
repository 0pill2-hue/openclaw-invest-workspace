# JB-20260312-CLEANUP-STAGE1-SELECTED-ARTICLES-CANON

- completed_at: 2026-03-12 KST
- scope: Stage1 selected_articles 문서 canonicalize only
- destructive action: 없음

## summary
- cleanup audit 1순위 권고대로 Stage1 selected_articles 문서 3종만 정렬했다.
- 핵심 정렬 내용은 다음 3가지다.
  1. live `selected_articles/` canonical writer를 generic collector가 아니라 `stage01_collect_selected_news_articles_naver.py`로 명시
  2. `daily_full`/`selected_articles_naver_only`는 live writer 포함, `news_backfill`은 RSS + URL-index backlog만 담당하도록 문서 계약 수정
  3. generic `stage01_collect_selected_news_articles.py`는 explicit `--input-index`가 필요한 manual/debug helper로 강등

## doc classification (Stage1 selected_articles-related)
| path | classification | decision |
| --- | --- | --- |
| `docs/invest/stage1/RUNBOOK.md` | canonical ops doc / stale selected_articles wording | canonicalized |
| `docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md` | canonical stage-contract doc / stale selected_articles profile table | canonicalized |
| `docs/invest/stage1/stage01_data_collection.md` | canonical collection appendix / internal self-conflict on selected_articles writer | canonicalized |
| `runtime/tasks/JB-20260311-SELECTED-ARTICLES-ALT-PATH.md` | proof / historical validation note | kept as evidence |
| `runtime/tasks/JB-20260312-LEGACY-CLEANUP-AUDIT.md` | audit / cleanup ordering source | kept as evidence |

## touched paths
- `docs/invest/stage1/RUNBOOK.md`
- `docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage1/stage01_data_collection.md`
- `runtime/tasks/JB-20260312-CLEANUP-STAGE1-SELECTED-ARTICLES-CANON.md`

## proof
- audit order source: `runtime/tasks/JB-20260312-LEGACY-CLEANUP-AUDIT.md`
  - recommended next cleanup order #1 = Stage1 selected_articles 문서 일괄 canonicalize
- code truth used for canonicalization:
  - `invest/stages/stage1/scripts/stage01_daily_update.py`
    - `PROFILE_CHOICES` includes `selected_articles_naver_only`
    - `daily_full` uses `stage01_collect_selected_news_articles_naver.py`
    - `news_backfill` no longer runs `stage01_collect_selected_news_articles.py`
  - `invest/stages/stage1/scripts/stage01_collect_selected_news_articles_naver.py`
    - verified Naver index 생성 후 generic collector를 explicit `--input-index`로 호출
    - live verified lane wrapper 역할 확인
- live-path validation source retained:
  - `runtime/tasks/JB-20260311-SELECTED-ARTICLES-ALT-PATH.md`
  - current live corpus = Naver-only, summary is derived-only

## concrete changes
### 1) `RUNBOOK.md`
- `selected_articles_naver_only` profile command 추가
- `news_backfill` 설명을 “selected_articles 2016 coverage용 RSS/URL-index 백필”로 수정
- helper commands에서 Naver-only wrapper를 canonical live lane으로 올리고, generic collector는 `--input-index` required manual/debug only로 표기
- 운영 주기 섹션에서 `news_backfill`이 live writer가 아님을 명시

### 2) `STAGE1_RULEBOOK_AND_REPRO.md`
- 지원 profile 목록에 `selected_articles_naver_only` 추가
- profile table에서
  - `daily_full` → `stage01_collect_selected_news_articles_naver.py`
  - `selected_articles_naver_only` row 추가
  - `news_backfill` → RSS + URL index + sync + coverage manifest only
- `news_backfill` env 계약에서 selected_articles writer env 블록 제거 후 note로 current live-lane contract 명시
- raw/path 및 selected_articles 핵심 원칙에 derived summary / manual-debug lane 경계 추가

### 3) `stage01_data_collection.md`
- 4.4 Selected articles의 canonical live writer를 `stage01_collect_selected_news_articles_naver.py`로 수정
- generic collector를 helper/manual-debug only로 분리
- wrapper → verified Naver index → explicit `--input-index` collector 호출 구조를 문서화
- current live corpus contamination 판단 기준(`n.news.naver.com`, `naver_finance_list`)을 운영 메모로 고정

## next step
- audit recommendation order상 다음 배치는 `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md` + `docs/invest/stage2/STAGE2_PDF_REFINEMENT_DESIGN.md`의 Telegram PDF path canonicalize다.
