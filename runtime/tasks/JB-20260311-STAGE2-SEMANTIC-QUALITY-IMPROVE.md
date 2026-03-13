# JB-20260311-STAGE2-SEMANTIC-QUALITY-IMPROVE

- status: COMPLETED (subagent implementation)
- change_type: Tuning
- result_label: VALIDATED
- close_recommendation: DONE

## summary
- Stage2 semantic heuristic을 보수적으로 조정해 selected_articles 중심의 stock/macro/event 오탐을 줄였다.
- historical selected_articles clean backlog 37개 파일에 대해 row-level `stage2_classification` + `*.classification.json` sidecar를 clean 기반으로 재물질화했다.
- 현재 upstream raw historical selected_articles가 전량 남아 있지 않아 authoritative raw replay는 못 했지만, existing clean corpus backlog는 해소했다.

## what changed
### 1) Stage2 semantic heuristic tightening
파일:
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`

핵심 변경:
- stock name match에 token/postfix 경계를 넣어 substring 오탐 축소
  - 예: `대상`, `이닉스`, `CS` 같은 이름이 일반 단어/더 긴 단어 내부에 박혀 있을 때 매칭 억제
- 짧은 ASCII keyword는 boundary match로만 집계
  - event/macro/industry short token 오탐 축소
- macro keyword를 더 구체화
  - `fx`: generic `달러` 제거, `환전`/`엔화` 보강
  - `rates`: generic `수익률` 제거
  - `energy`: generic `유가` 제거, `국제유가/유가 상승/유가 하락`으로 축소
  - `risk_on`: 단독 `인하` 제거, `금리인하/금리 인하`만 허용
- selected_articles 분류 입력을 `title + body` 우선으로 바꾸고, body가 짧을 때만 `summary`를 보조 입력으로 사용
  - polluted summary snippet로 인한 unrelated stock/event 오탐 축소

### 2) selected_articles backlog materialization path added
파일:
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`

추가 경로:
- `--folders <folder1,folder2>`: Stage2 subset 실행 지원
- `--repair-selected-articles-clean`: upstream raw replay 없이 existing clean selected_articles JSONL에 대해
  - row-level `stage2_classification`
  - file-level `*.classification.json`
  를 재물질화
- incremental skip은 qualitative clean output의 classification sidecar/row payload가 이미 존재할 때만 허용하도록 조정

### 3) Stage2 doc sync
파일:
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`

반영 내용:
- classification sidecar skip 조건
- selected_articles body-priority classification rule
- `--folders`
- `--repair-selected-articles-clean`
- raw history 축약 시 clean 기반 backlog repair 경로

## verification
### A. syntax / import-level check
명령:
```bash
python3 -m py_compile invest/stages/stage2/scripts/stage02_onepass_refine_full.py
```
판정:
- PASS

### B. selected_articles clean backlog repair
명령:
```bash
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --repair-selected-articles-clean
```
증빙:
- `invest/stages/stage2/outputs/reports/qc/SELECTED_ARTICLES_CLASSIFICATION_REPAIR_20260311_212500.json`

핵심 결과:
- `files_seen=37`
- `files_updated=37`
- `rows_reclassified=8108`
- `sidecars_written=37`
- `files_with_parse_errors=0`

### C. sidecar backlog 해소 확인
증빙:
- `runtime/tasks/proofs/JB-20260311-STAGE2-SEMANTIC-QUALITY-IMPROVE.json`

핵심 결과:
- `selected_articles_jsonl_total=37`
- `selected_articles_missing_sidecar=0`

### D. representative false-positive reduction proof
증빙 파일:
- `runtime/tasks/proofs/JB-20260311-STAGE2-SEMANTIC-QUALITY-IMPROVE.json`
- `invest/stages/stage2/outputs/clean/production/qualitative/market/news/selected_articles/selected_articles_20260311-103721.jsonl`
- `invest/stages/stage2/outputs/clean/production/qualitative/market/news/selected_articles/selected_articles_20260311-013501.jsonl`

대표 개선:
1. `selected_articles_20260311-103721.jsonl` line 7
   - title: `청담르엘 13.8억↓ 잠실파크리오 6.2억↓…매물 쏟아지나`
   - 이전 이슈: `stock_tags=["001680"]` (`대상`) 오탐
   - 현재: `stock_tags=[]`, `macro_tags=[]`, `target_levels=["industry"]`

2. `selected_articles_20260311-103721.jsonl` line 10
   - title: `‘삼전’ 레버리지 던진 중학개미…‘하이닉스’ 레버리지 담았다`
   - 이전 이슈: polluted summary 때문에 `primary_ticker=452400(이닉스)`, `event_tags=["rights_issue"]`, 과다 macro tag
   - 현재: `primary_ticker=005930`, `stock_tags=["005930","000660","030210"]`, `event_tags=[]`, `macro_tags=["geopolitics"]`
   - 비고: major false positive는 줄었지만 analyst firm mention(`030210`)은 아직 남음

3. `selected_articles_20260311-013501.jsonl` line 11
   - title: `'100엔=472원' 환전오류 토스뱅크 100억대 손실 추산, 당국 현장검사`
   - 이전 이슈: `macro_tags=["fx","energy","risk_on"]`
   - 현재: `macro_tags=["fx"]`

4. `selected_articles_20260311-013501.jsonl` line 12
   - title: `남동산단을 '문화선도산단'으로…인천시, 정부 공모사업 응모`
   - 이전 이슈: `stock_tags=["025560"]` (`미래산업`) 오탐
   - 현재: `stock_tags=[]`, `macro_tags=["policy"]`

## remaining gaps / honest caveats
1. **authoritative raw historical replay는 미완료**
   - 현재 selected_articles historical raw는 full corpus가 upstream에 남아 있지 않다.
   - 증빙:
     - `runtime/tasks/proofs/JB-20260311-STAGE2-SEMANTIC-RAW-AVAILABILITY.json`
     - `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_20260311_211926.md`
   - 현재 상태:
     - `stage1_raw_selected_articles_count=4`
     - `stage2_inputs_upstream_selected_articles_count=4`
     - `stage2_db_mirror_selected_articles_exists=false`
   - 따라서 이번 작업은 clean backlog repair로 해결했고, historical raw authoritative rerun까지는 못 했다.

2. **잔여 semantic noise는 일부 남음**
   - 예: analyst/quote context에서 증권사명이 stock으로 남는 경우(`030210`)
   - 일부 industry over-tag도 더 남아 있을 수 있음
   - 이건 token/keyword tightening만으로는 한계가 있어, 더 깊은 quote/context-aware entity pass가 필요하다.

## conclusion
- 사용자 요구 범위 내 최소 수정으로
  - selected_articles semantic backlog materialization 경로를 추가했고
  - existing clean backlog 37개 파일/8108개 row를 실제로 backfill 했으며
  - 대표 false-positive 사례(stock/event/macro)를 줄였다.
- residual precision issue는 남지만, 이번 티켓 범위의 implementation follow-up은 완료로 보는 것이 타당하다.

## close recommendation
- DONE
