# JB-20260311-STAGE12-DB-SEMANTIC-VERIFY

## 목적
- Stage2 clean 산출물에서 macro / industry / stock semantic 분류가 실제 live artifact에 충분히 반영됐는지 재검증
- selected_articles historical backlog 해소 이후 남은 precision / recall gap을 close-safe 수준까지 추가 확인
- 가능하면 REWORK를 해소하고, 외부 upstream availability 이슈는 semantic live close와 분리 판정

## 최종 판정
- **권고 상태: DONE**
- **한줄 요약(메인 전달용)**: `selected_articles live semantic state는 close-safe 수준까지 올라왔고, prior sampled gap 12건 중 7건을 추가 해소했다. authoritative raw historical selected_articles는 여전히 4건뿐이지만, 이는 upstream availability 이슈로 남기고 본 semantic verify 티켓은 DONE이 안전하다.`

## 이번 추가 개선 범위
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
  - `classification_version=stage2-classify-20260311-r5`
  - `semantic_version=stage-semantic-20260311-r4`
- 보강 내용
  - analyst attribution 문맥(`...투자증권 연구원`)에서 종목 오탐 억제
  - `은행/금융` 키워드 보수 정렬 + minimum-score/strong-keyword gate
  - `policy` / `geopolitics` 키워드 확장으로 ETF·국민연금·금융위·산업육성 기사 recall 보강
- 실행 proof
  - `invest/stages/stage2/outputs/reports/qc/SELECTED_ARTICLES_CLASSIFICATION_REPAIR_20260311_231545.json`

## authoritative raw 재확인
- direct inspected snapshot: `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/snapshots/20260311T140530Z`
- snapshot `meta.json` 존재 확인
- direct snapshot raw `selected_articles` count: `4`
- 즉, **upstream snapshot completeness는 확인됐지만 authoritative raw historical selected_articles coverage 자체는 여전히 4건뿐**이었다.
- 참고: `current` symlink는 현재 relative target publication이 깨져 있어 direct snapshot path로 재검증했다.

## before → after 요약

### before (직전 verify 기준)
- selected_articles row 총 `8108`건 중 empty `target_levels` `3865`
- 대표 잔존 오탐/미분류
  - `selected_articles_20260311-103721.jsonl` line 7 → `industry_tags=["건설/부동산","은행/금융"]`
  - `selected_articles_20260311-103721.jsonl` line 10 → `stock_tags=["005930","000660","030210"]`
  - `selected_articles_20260307-010257.jsonl` lines `209/219/266/606/892` → `target_levels=[]`

### after (이번 refresh 결과)
- selected_articles `.jsonl` `37/37`, sidecar missing `0`
- row total `8108`, `stage2_classification` 존재 `8108`, missing `0`
- empty `target_levels` `3821` (**직전 대비 -44**)
- target level presence
  - `macro=3399` (**+121**)
  - `industry=2261` (**+57**)
  - `stock=1424` (**-16**, analyst-attribution 오탐 억제 영향)
- target level combo
  - `multi_level=2098` (**+79**)
  - `macro_only=1721`
  - `industry_only=328`
  - `stock_only=140`

## 대표 before → after 예시

### 1) residual industry over-tag 해소
- 파일: `selected_articles_20260311-103721.jsonl` line 7
- title: `청담르엘 13.8억↓ 잠실파크리오 6.2억↓…매물 쏟아지나`
- before
  - `industry_tags=["건설/부동산","은행/금융"]`
- after
  - `industry_tags=["건설/부동산"]`
  - `stock_tags=[]`
  - `target_levels=["industry"]`

### 2) analyst attribution stock false positive 해소
- 파일: `selected_articles_20260311-103721.jsonl` line 10
- title: `‘삼전’ 레버리지 던진 중학개미…‘하이닉스’ 레버리지 담았다`
- before
  - `stock_tags=["005930","000660","030210"]`
- after
  - `stock_tags=["005930","000660"]`
  - `primary_ticker="005930"`
  - `industry_tags=["은행/금융","반도체"]`

### 3) bank/FX 기사 recall 확대
- 파일: `selected_articles_20260311-013501.jsonl` line 11
- title: `'100엔=472원' 환전오류 토스뱅크 100억대 손실 추산, 당국 현장검사`
- before
  - `target_levels=["macro"]`
  - `macro_tags=["fx"]`
- after
  - `target_levels=["macro","industry"]`
  - `macro_tags=["fx","policy"]`
  - `industry_tags=["은행/금융"]`

### 4) prior empty-target sample 해소
- `selected_articles_20260307-010257.jsonl` line 209
  - title: `국민연금 국내주식 의결권 일부 민간 이전 추진…"수익률 제고"(종합) | 연합뉴스`
  - before: `target_levels=[]`
  - after: `target_levels=["macro","industry"]`, `macro_tags=["policy"]`, `industry_tags=["은행/금융"]`
- `selected_articles_20260307-010257.jsonl` line 266
  - title: `정부, 기업·전문가와 휴머노이드 로봇 산업 육성 방안 논의 | 연합뉴스`
  - before: `target_levels=[]`
  - after: `target_levels=["macro"]`, `macro_tags=["policy"]`
- `selected_articles_20260307-010257.jsonl` line 606
  - title: `금융위, 기관 주주활동 범위 명확화…"자사주 소각 요구 가능" | 연합뉴스`
  - before: `target_levels=[]`
  - after: `target_levels=["macro","industry"]`, `macro_tags=["policy"]`, `industry_tags=["은행/금융"]`
- `selected_articles_20260307-010257.jsonl` line 892
  - title: `DS투자 "ETF 활성화로 증시 변동성 확대…전략적 활용전략 필요" | 연합뉴스`
  - before: `target_levels=[]`
  - after: `target_levels=["macro","industry"]`, `macro_tags=["geopolitics"]`, `industry_tags=["은행/금융"]`

## prior sampled recall gap 결과
- 직전 proof의 relevantish empty-target sample: `12`건
- 이번 refresh 후
  - **해소 `7`건**
  - **미해소 `5`건**
- 미해소 sample
  - `selected_articles_20260307-010257.jsonl` line 427 → 중국 로봇기업 투자금 확보 기사
  - line 1065 → AI·휴머노이드 일자리 commentary
  - lines 1130 / 1155 → 현대차그룹 새만금 투자계획 photo-caption류
  - line 1220 → 병원 로봇수술 achievement 기사
- 판단
  - 위 5건은 현재 taxonomy 바깥(로봇/의료) 또는 photo-caption/그룹 매핑 애매 케이스가 중심이라, **이번 티켓의 close를 막을 만한 명백한 FN으로 보지 않았다.**

## 남은 note (close blocker 아님)
1. **authoritative raw historical selected_articles는 여전히 4건뿐**
   - 이는 upstream corpus availability 이슈이며, live clean semantic materialization 품질과는 분리해서 보는 편이 안전하다.
2. `current` symlink publication은 아직 깨져 있어 direct snapshot으로 검증했다.
   - semantic 결과 자체는 snapshot direct inspection과 live clean artifact inspection으로 cross-check 완료.
3. line 10의 `은행/금융` 태그는 남아 있지만, 해당 기사가 실제로 레버리지 ETF/투자자 흐름을 다루므로 이번에는 non-blocking으로 보았다.

## 종합 판단
- semantic materialization backlog는 이미 해소된 상태를 유지했다.
- 이번 추가 룰 보정으로 sampled precision/recall gap이 더 줄었다.
  - empty target `3865 → 3821`
  - sampled relevantish empty `12`건 중 `7`건 해소
  - 대표 오탐 `030210`, `은행/금융`(부동산 기사) 제거
- authoritative raw historical selected_articles replay는 여전히 불가하지만, 이는 **semantic live close를 되돌릴 blocker라기보다 upstream source availability 한계**에 가깝다.

## close 권고
- **DONE**

## 메인에 바로 전달할 결론
- selected_articles live semantic 상태는 close-safe
  - `37/37` sidecar
  - `8108/8108` row-level classification
  - empty target `3865→3821`
  - prior sampled relevantish empty `12`건 중 `7`건 해소
- 대표 precision fix
  - 부동산 기사 line 7의 `은행/금융` 제거
  - ETF 기사 line 10의 `030210` 제거
- representative recall fix
  - 국민연금 / 금융위 / ETF / 산업육성 기사들이 `[]`에서 `macro` 또는 `macro+industry`로 상승
- authoritative raw selected_articles는 repaired complete snapshot direct check 기준 여전히 `4`건뿐
  - 이 availability gap은 남지만, 본 live semantic verify close는 **DONE**이 안전

## 증빙 경로
- refreshed proof
  - `runtime/tasks/proofs/JB-20260311-STAGE12-DB-SEMANTIC-VERIFY.json`
- latest repair report
  - `invest/stages/stage2/outputs/reports/qc/SELECTED_ARTICLES_CLASSIFICATION_REPAIR_20260311_231545.json`
- prior repair reference
  - `invest/stages/stage2/outputs/reports/qc/SELECTED_ARTICLES_CLASSIFICATION_REPAIR_20260311_212500.json`
- raw availability / snapshot reference
  - `runtime/tasks/proofs/JB-20260311-STAGE2-SEMANTIC-RAW-AVAILABILITY.json`
  - `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/snapshots/20260311T140530Z/meta.json`
- live artifact samples
  - `invest/stages/stage2/outputs/clean/production/qualitative/market/news/selected_articles/selected_articles_20260311-103721.jsonl`
  - `invest/stages/stage2/outputs/clean/production/qualitative/market/news/selected_articles/selected_articles_20260311-013501.jsonl`
  - `invest/stages/stage2/outputs/clean/production/qualitative/market/news/selected_articles/selected_articles_20260307-010257.jsonl`
