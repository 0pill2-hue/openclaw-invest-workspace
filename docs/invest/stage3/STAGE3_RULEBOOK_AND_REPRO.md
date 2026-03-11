# Stage3 Rulebook & Repro

status: CANONICAL (reproducible Stage3 implementation contract)  
updated_at: 2026-03-11 KST

## 문서 역할
- 이 문서는 **문서만 보고 현재 Stage3를 재구현할 수 있도록** 입력 JSONL 스키마, builder 규칙, claim-card 스키마, 점수 산식, dedup/cluster/feature/output schema를 고정한다.
- 배경 설명은 `STAGE3_DESIGN.md`를 보되, 구현 계약 충돌 시 본 문서가 우선한다.

---

## 1) 범위
- 역할: Stage2 clean 정성/비정형 입력을 로컬 브레인 친화적인 claim-card로 바꾼 뒤 4축 정성 feature로 집계
- 4축:
  - `upside_score`
  - `downside_risk_score`
  - `bm_sector_fit_score`
  - `persistence_score`
- 비범위:
  - sentiment/attention 축 직접 사용
  - cloud/remote 모델 사용
  - Stage4 이상의 운영 판단

---

## 2) Stage3 두 단계 구조

### 2.1 Step A — input builder
- script: `invest/stages/stage3/scripts/stage03_build_input_jsonl.py`
- 역할: Stage2 clean artifacts를 읽어 canonical intermediate corpus `stage2_text_meta_records.jsonl` 생성
- 추가 계약: DART/RSS/macro/blog/telegram/premium/selected_articles 모든 row에 동일한 deterministic semantic contract를 부여한다.

### 2.2 Step B — qualitative axes gate
- script: `invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py`
- 역할:
  - input JSONL row를 읽어 chunk 분할
  - `(record_id, chunk_id, focus_symbol)` claim-card 생성
  - issue cluster 및 `(symbol,date)` feature 집계
  - `dart_event_signal.csv` 생성
  - 날짜 단위 standalone `stage3_macro_forecast.csv` 생성

---

## 3) 입력 (Inputs)
- Stage2 clean roots 우선순위
  1. `invest/stages/stage3/inputs/upstream_stage2_clean/production/`
  2. `invest/stages/stage3/inputs/upstream_stage2_clean/`
  3. `invest/stages/stage2/outputs/clean/production/`
- 구체 입력
  - DART: `qualitative/kr/dart/*.json`
  - RSS: `qualitative/market/rss/*.json`
  - macro summary: `signal/market/macro/macro_summary.json`
  - text: `qualitative/text/{telegram,blog,premium}`
  - selected articles: `qualitative/market/news/selected_articles/*.jsonl`
  - reference: `invest/stages/stage3/inputs/reference/kr_stock_list.csv`
- fallback path
  - text/market는 legacy flat 경로도 허용 (`text/*`, `market/*`)

원칙:
- Stage3는 Stage1 raw를 직접 읽지 않는다.
- Telegram PDF는 Stage2 clean telegram 본문에 inline 승격된 결과만 읽는다.

---

## 4) canonical intermediate corpus schema
출력 파일: `invest/stages/stage3/inputs/stage2_text_meta_records.jsonl`

각 row 최소 schema:
```json
{
  "record_id": "string",
  "published_at": "ISO-8601 datetime",
  "symbols": ["000000", "__MACRO__", "__NOSYMBOL__"],
  "text": "string",
  "source": "string",
  "source_family": "canonical string",
  "content_fingerprint": "sha1(normalized_text)",
  "semantic_version": "stage-semantic-20260311-r1",
  "target_levels": ["macro", "industry", "stock"],
  "macro_tags": ["risk_off", "rates"],
  "industry_tags": ["반도체"],
  "stock_tags": ["005930"],
  "event_tags": ["guidance"],
  "impact_direction": "positive|negative|mixed|neutral",
  "horizon": "short_term|medium_term|long_term|unknown",
  "region_tags": ["kr", "us", "global"]
}
```

필드 의미:
- `record_id`: Stage3 storage unit 식별자
- `published_at`: KST로 해석 가능한 시각
- `symbols`:
  - 실제 종목코드(6자리)
  - `__MACRO__`: 종목 없는 macro-only 문서
  - `__NOSYMBOL__`: 종목 미추출 텍스트(기본 builder는 포함 가능)
- `source`: lineage string
- `source_family`: builder가 canonical family로 normalize한 값
- `content_fingerprint`: Stage3 builder의 1차 dedup key
- `semantic_version`: semantic contract version
- `target_levels`: 문서가 겨냥하는 분석 레벨 집합 (`macro|industry|stock`)
- `macro_tags`, `industry_tags`, `stock_tags`, `event_tags`, `region_tags`: deterministic rule-based tag list
- `impact_direction`: `positive|negative|mixed|neutral`
- `horizon`: `short_term|medium_term|long_term|unknown`

---

## 5) input builder exact behavior

### 5.1 공통 normalize
- `published_at`은 KST timezone-aware ISO string으로 normalize
- `content_fingerprint = sha1(lowercase + whitespace-normalized + non-alnum-stripped text)`
- 종목 추출은
  1. `kr_stock_list.csv`의 이름 매칭
  2. 6자리 코드 regex 매칭
  순으로 수행
- `include_nosymbol=true`가 기본이며, symbol 미검출 텍스트는 `__NOSYMBOL__`로 포함 가능
- semantic contract는 builder 마지막 공통 단계에서 모든 source row에 동일하게 부여한다.
  - `target_levels`: `macro_tags` 존재 또는 `__MACRO__/news_rss_macro`면 `macro`, industry tag 존재면 `industry`, 실제 stock code 존재면 `stock`
  - `macro_tags`: risk-on/off, rates, inflation, fx, liquidity, policy, energy, recession_growth, geopolitics 키워드 기반
  - `industry_tags`: Stage2와 같은 industry keyword table 기반
  - `stock_tags`: placeholder 제외 실제 stock code list
  - `event_tags`: `order|rights_issue|lawsuit|guidance` keyword 기반
  - `impact_direction`: positive/negative keyword count + event bias 기반
  - `horizon`: short/medium/long keyword 우선, macro row fallback=`short_term`, 없으면 `unknown`
  - `region_tags`: kr/us/cn/jp/eu/global keyword + source-family fallback 기반

### 5.2 source별 record 생성 규칙

#### DART
- 입력: latest `dart/*.json`
- row source: `dart`
- `record_id`: `dart:<rcept_no>`
- `symbols`: `[stock_code]`
- `text`: `corp_name + report_nm`
- published_at:
  - `rcept_dt=YYYYMMDD`면 `YYYY-MM-DDT15:30:00+09:00`

#### RSS
- 입력: latest `rss/*.json`
- flatten 대상: feed → items
- `text`: `title + summary`
- symbol이 없고 macro word만 있으면 `symbols=["__MACRO__"]`, `source="rss_macro:<feed>"`
- symbol이 있으면 `source="rss:<feed>"`
- symbol도 macro signal도 없으면 drop

#### macro summary
- 입력: `macro_summary.json`
- `latest` dict를 읽어
  - risk-on set: `SPY, QQQ, SOX`
  - risk-off set: `VIX, DXY, TNX, IRX`
- `change_1d` 부호를 카운트해 risk word(`risk-on|risk-off|neutral`)를 만들고
- `symbols=["__MACRO__"]`
- `source="rss_macro:market_macro"`

#### telegram
- 입력: `text/telegram/*.md`
- message split 기준: `\n---\s*\nDate:\s*([^\n]+)\n`
- 각 message body가 길이 `< 20`이면 skip
- symbol 미검출 시
  - 기본: `symbols=["__NOSYMBOL__"]`, `source_family=text_telegram_nosymbol`
  - `--exclude-nosymbol`이면 skip
- `record_id`: `text_telegram:<sha1(file_name:d_raw:text_prefix:source_family)[:20]>`
- `source`: `text/telegram:<file_stem>`

#### blog
- 입력: `text/blog/**/*.md`
- title 추출 우선순위
  1. `# ...`
  2. `Title:`
  3. fallback `fp.stem`
- date 추출 우선순위
  1. `Date|PublishedDate|PublishedAt`
  2. inline date regex
- body cleaning:
  - `Source:` 이후 body 기준
  - UI/noise/meta line 제거
- `record_id`: `text_blog:<sha1(path:source_family)[:20]>`
- `source`: `text/blog:<parent_dir_name>`

#### premium
- 입력: `text/premium/**/*.md`
- `# STARTALE PREMIUM LINK` 문서는 linkmeta로 보고 skip
- title/date/body 정제 방식은 blog와 유사하되 premium boilerplate 제거 사용
- `record_id`: `text_premium:<sha1(path:source_family)[:20]>`
- `source`: `text/premium:<parent_dir_name>`

#### selected_articles
- 입력: `market/news/selected_articles/**/*.jsonl`
- row must be object
- `text = title + summary + body`
- `record_id`: `market_selected_articles:<sha1(file:line_no:url:source_family)[:20]>`
- `source`: `market/selected_articles:<source_domain|unknown>`

### 5.3 builder dedup
builder는 source 전체를 합친 뒤 아래 순서로 dedup한다.
1. duplicate `record_id` drop
2. duplicate `content_fingerprint` drop

summary에 남는 key:
- `rows_from_*`
- `rows_before_dedup`
- `rows_output`
- `dropped_duplicate_record_id`
- `dropped_duplicate_fingerprint`
- `telegram_stats`, `blog_stats`, `premium_stats`, `selected_articles_stats`
- `caps_effective`
- `ingestion_validation`

---

## 6) source family canonical mapping
| source/source_family hint | canonical source_family |
| --- | --- |
| `dart*` | `dart` |
| `rss_macro:*` | `news_rss_macro` |
| `rss:*` | `news_rss` |
| `market/selected_articles:*` | `market_selected_articles` |
| `text/telegram:*` | `text_telegram` |
| `text/blog:*` | `text_blog` |
| `text/premium:*` | `text_premium` |
| `text/image_map:*` | `text_image_map` |
| `text/images_ocr:*` | `text_images_ocr` |
| 기타 | `other` |

`*_nosymbol` source_family는 canonicalization 시 suffix를 제거한다.

---

## 7) local-only policy / fail-close
- 허용 backend: `keyword_local`, `llama_local`
- local endpoint만 허용
  - `local://...`
  - `http(s)://localhost|127.0.0.1|::1|0.0.0.0`
- 금지 model ref substring
  - `openai`, `anthropic`, `gemini`, `bedrock`, `claude`, `gpt-`
- `llama_local`은 실제 socket connection 가능해야 함

fail-close exit code:
- policy/runtime 위반: `41`
- input validation error: `43`
- no_valid_records_after_validation: `44`

---

## 8) evaluation units
- storage unit: `stage2_text_meta_records.jsonl`의 1 row
- model evaluation unit: `(record_id, chunk_id, focus_symbol)`
- aggregation unit: `(symbol, date, issue_cluster_id)` → `(symbol, date)`

---

## 9) chunk policy
| source_family | target_chars | max_chunks |
| --- | ---: | ---: |
| `dart` | 220 | 1 |
| `news_rss` | 420 | 2 |
| `news_rss_macro` | 420 | 2 |
| `market_selected_articles` | 650 | 4 |
| `text_telegram` | 700 | 4 |
| `text_blog` | 750 | 5 |
| `text_premium` | 750 | 5 |
| `text_image_map` | 550 | 3 |
| `text_images_ocr` | 500 | 3 |
| `other` | 650 | 4 |

분할 규칙:
- DART는 앞 220자 1개 chunk 고정
- 그 외는 paragraph split 우선, 없으면 sentence split
- chunk는 `target_chars + 120` 범위까지만 유지
- `max_chunks` 초과분은 버린다

---

## 10) keyword tables (exact current sets)

### 10.1 upside words
`성장, 개선, 확대, 수주, 계약, 흑자, 상향, 반등, 증가, 회복, 신제품, 점유율, 가이던스, 성공, 강세, growth, improve, expand, order, beat, upgrade, strong, recovery, guidance, share gain, launch`

### 10.2 downside words
`감소, 부진, 하락, 적자, 둔화, 악화, 소송, 분쟁, 유상증자, 리스크, 규제, 지연, 차질, 정정, 우려, decline, weak, drop, loss, lawsuit, dispute, dilution, downgrade, risk, regulation, delay, concern`

### 10.3 persistence positive words
`지속, 장기, 반복, 연속, 누적, 중장기, pipeline, recurring, long-term, backlog, 구조적, 계속`

### 10.4 persistence negative words
`일회성, 단기, 일시, 변동성, 불확실, temporary, one-off, volatile, uncertain, 반짝, 소멸`

### 10.5 event keywords
- `order`: `수주, 공급계약, 단일판매, 계약체결, 수주계약, 판매계약`
- `rights_issue`: `유상증자, 증자, 전환사채, cb, bw, 신주발행, 희석`
- `lawsuit`: `소송, 피소, 판결, 항소, 가처분, 분쟁`
- `guidance`: `가이던스, 실적전망, 전망치, 컨센서스, 잠정실적, 실적발표`

### 10.6 macro keywords
- risk-on: `완화, 인하, 랠리, 상승, 회복, risk-on, risk on, soft landing, stimulus, easing`
- risk-off: `긴축, 인상, 침체, 전쟁, 관세, 하락, 위기, 리스크오프, risk-off, risk off, recession, conflict, sanction`

---

## 11) source weights / priors

### 11.1 source reliability
| source_family | value |
| --- | ---: |
| `dart` | 1.00 |
| `news_rss` | 0.94 |
| `news_rss_macro` | 0.94 |
| `market_selected_articles` | 0.91 |
| `text_premium` | 0.84 |
| `text_blog` | 0.72 |
| `text_telegram` | 0.68 |
| `text_image_map` | 0.58 |
| `text_images_ocr` | 0.55 |
| `other` | 0.55 |

### 11.2 source BM base
| source_family | value |
| --- | ---: |
| `dart` | 0.92 |
| `market_selected_articles` | 0.80 |
| `text_premium` | 0.82 |
| `news_rss` | 0.76 |
| `text_blog` | 0.68 |
| `news_rss_macro` | 0.66 |
| `text_telegram` | 0.62 |
| `text_image_map` | 0.58 |
| `text_images_ocr` | 0.56 |
| `other` | 0.55 |

---

## 12) claim-card generation

### 12.1 pre-validation
각 input row는 아래를 만족해야 한다.
- `record_id` 존재
- `published_at` 존재 및 KST date 파싱 가능
- `symbols`는 non-empty list
- `text` 존재

### 12.2 placeholder 처리
- 실제 symbol이 없고 `__MACRO__` 또는 `news_rss_macro`면 macro_docs로 간다.
- 실제 symbol이 없고 `__NOSYMBOL__`뿐이면 Stage3 feature 집계에서는 제외하고 `records_skipped_nosymbol`로 집계한다.

### 12.3 record-level dedup
- gate는 input row를 다시 한 번 `content_fingerprint` 기준 dedup한다.

### 12.4 evidence snippet
- keyword/event sentence가 있으면 그 첫 sentence (max 260자)
- 없으면 첫 sentence / text prefix 사용

### 12.5 claim-card exact score formula
토큰화 후:
- `up_hits = count(token in UPSIDE_WORDS)`
- `down_hits = count(token in DOWNSIDE_WORDS)`
- `pers_pos = count(token in PERSIST_POS_WORDS)`
- `pers_neg = count(token in PERSIST_NEG_WORDS)`
- `event_hits = sum(event flags)`
- `has_number = regex('\d')`
- `polarity = (up_hits - down_hits) / max(up_hits + down_hits, 1)`
- `pers_balance = (pers_pos - pers_neg) / max(pers_pos + pers_neg, 1)`
- `evidence_density = min(n_toks, 120) / 120`

기본식:
- `upside = 50 + 22*polarity + 8*min(up_hits,6)/6`
- `downside = 50 - 20*polarity + 10*min(down_hits,6)/6`
- `bm_sector_fit = 100 * SOURCE_BM_BASE[source_family]`
- `persistence = 38 + 18*pers_balance + 18*evidence_density`

이벤트 보정:
- `order`: `upside += 8`, `persistence += 4`, `bm += 4`
- `guidance`: `upside += 4`, `persistence += 3`
- `rights_issue`: `downside += 12`, `bm -= 5`, `persistence -= 4`
- `lawsuit`: `downside += 10`, `bm -= 6`, `persistence -= 5`

추가 보정:
- `has_number`: `bm += 3`, `persistence += 2`
- `source_family == dart`: `bm += 7`
- `source_family == market_selected_articles`: `bm += 2`
- 모든 card score는 `[0,100]` clip

dominant axis:
- `abs(score-50)`가 가장 큰 축

claim confidence:
- `clip(0.32 + 0.08*min(total_keyword_hits,5) + 0.10*event_hits + (0.06 if has_number else 0), 0.15, 0.98)`

claim weight:
- `clip(source_reliability * (0.85 + 0.18*min(event_hits,2) + 0.16*min(evidence_density,1) + 0.08*(1 if has_number else 0)), 0.20, 2.00)`

### 12.6 issue cluster rule
cluster key 우선순위:
1. event flag가 있으면 `event:<sorted_event_names_joined>`
2. 없으면 text token에서
   - 길이 `<2` 제외
   - 숫자 제외
   - stopword 제외
   - 앞 3개 unique token 사용
   - `topic:<source_family>:tok1-tok2-tok3`
3. 아무 토큰도 없으면 `topic:<source_family>:generic`

issue_cluster_id:
- `sha1("<date_kst>:<symbol>:<cluster_key>")[:16]`

claim_card_id:
- `sha1("<record_id>:<symbol>:<chunk_idx>:<issue_cluster_id>")[:20]`

### 12.7 claim-card JSONL schema
출력: `invest/stages/stage3/outputs/features/stage3_claim_cards.jsonl`

각 row key:
- `date`
- `symbol`
- `record_id`
- `chunk_id`
- `focus_symbol`
- `claim_card_id`
- `issue_cluster_id`
- `source`
- `source_family`
- `source_reliability`
- `chunk_text`
- `evidence_text`
- `upside_score_card`
- `downside_risk_score_card`
- `bm_sector_fit_score_card`
- `persistence_score_card`
- `dominant_axis`
- `claim_confidence`
- `claim_weight`
- `event_order`
- `event_rights_issue`
- `event_lawsuit`
- `event_guidance`
- `event_tagged`

---

## 13) macro docs
- macro-only row는 claim-card로 가지 않고 `macro_docs`로 간다.
- per chunk 산식:
  - `macro_score = clip((risk_on_count - risk_off_count)/max(total_macro_hits,1), -1, 1)`
- summary field:
  - `date`, `record_id`, `chunk_id`, `macro_score`, `risk_on_cnt`, `risk_off_cnt`, `source_family`

---

## 14) feature aggregation

### 14.1 issue cluster aggregation
groupby: `(date, symbol, issue_cluster_id)`
- `cluster_weight = max(sum(claim_weight), 1.0)`
- `cluster_claim_count = len(group)`
- `cluster_doc_count = nunique(record_id)`
- each cluster axis score = weighted mean by `claim_weight`

### 14.2 `(date, symbol)` counts
주요 count column:
- `doc_count`
- `mention_count`
- `claim_card_count`
- `issue_cluster_count`
- `source_diversity_ratio = clip(unique_source_families / 7, 0, 1)`
- `source_reliability_mean`
- `dart_doc_count`
- `news_doc_count`
- `rss_doc_count`
- `selected_articles_doc_count`
- `news_mention_count`
- `telegram_doc_count`
- `blog_doc_count`
- `premium_doc_count`
- `image_map_doc_count`
- `images_ocr_doc_count`
- event count columns

### 14.3 base score aggregation
cluster weighted mean:
- `upside_score`
- `downside_risk_score`
- `bm_sector_fit_score`
- `persistence_score_cluster_mean`

### 14.4 macro context + standalone forecast
macro summary를 날짜별로 합쳐 아래를 만든다.
- `macro_news_doc_count`
- `macro_risk_signal = mean(macro_score)`
- `macro_risk_on_ratio = mean(macro_score > 0)`
- `macro_risk_off_ratio = mean(macro_score < 0)`
- `macro_regime_label ∈ {risk_on, risk_off, neutral, mixed}`
- `macro_forecast_score = clip(50 + 35*macro_risk_signal + 10*(macro_risk_on_ratio - macro_risk_off_ratio), 0, 100)`
- `macro_confidence = clip(0.35 + 0.12*min(macro_doc_count,4)/4 + 0.20*max(abs(macro_risk_signal), abs(macro_risk_on_ratio-macro_risk_off_ratio)) + 0.08*min(unique_source_family_count,3)/3, 0.20, 0.97)`
- `macro_horizon = "1-5d"`
- `macro_evidence_summary = top unique macro evidence snippets joined by " | " (max 3)`
- `macro_source_mix = "<source_family>:<ratio>" csv string`

stock axis 반영 정책:
- 기본 실행 플래그: `--apply-macro-to-stock-axes on` (backward-compat)
- `off`이면 macro context 컬럼만 남기고 stock axis(`upside/downside/bm`)는 직접 mutate하지 않는다.

`--apply-macro-to-stock-axes on`일 때만 아래 보정식을 적용한다.
- `upside_score = clip(upside_score + 7*macro_risk_on_ratio - 6*macro_risk_off_ratio, 0, 100)`
- `downside_risk_score = clip(downside_risk_score + 11*macro_risk_off_ratio - 5*macro_risk_on_ratio, 0, 100)`
- `bm_sector_fit_score = clip(0.74*bm_sector_fit_score + 22*source_diversity_ratio + 6*(dart_doc_count>0) + 3*(premium_doc_count>0) + 3*(selected_articles_doc_count>0) - 7*macro_risk_off_ratio, 0, 100)`

### 14.5 persistence formula
rolling window는 symbol별 20일
- `doc_presence = 1 if doc_count > 0 else 0`
- `presence_roll_20 = rolling_mean(doc_presence, 20)`
- `cluster_roll_20 = rolling_mean(issue_cluster_count, 20)`
- `persistence_score = clip(0.55*persistence_score_cluster_mean + 25*presence_roll_20 + 20*(clip(cluster_roll_20,0,6)/6), 0, 100)`

### 14.6 derived scores
- `risk_score = downside_risk_score`
- `net_edge_score = clip(upside_score - downside_risk_score, -100, 100)`

---

## 15) duplication guard / final qualitative signal

### 15.1 axis representatives
- `dup_axis_upside_rep = clip((upside_score - 50)/50, -1, 1)`
- `dup_axis_downside_rep = clip((downside_risk_score - 50)/50, -1, 1)`
- `dup_axis_bm_rep = clip((bm_sector_fit_score - 50)/50, -1, 1)`
- `dup_axis_persistence_rep = clip((persistence_score - 50)/50, -1, 1)`

### 15.2 base weights / cap / threshold
- base weights: upside/downside/bm/persistence = `0.25` each
- correlation threshold: `|rho| > 0.70`
- single-axis weight cap: `0.25`
- priority:
  - downside = 4
  - bm = 3
  - persistence = 2
  - upside = 1

### 15.3 drop rule
- high-corr pair가 생기면 **priority가 낮은 축을 drop(weight=0)**
- 모든 축이 0이 되면 base weights로 롤백

### 15.4 final formula
`sum_w = sum(active_axis_weights)`

`qualitative_signal = (`
- `+ w_upside * dup_axis_upside_rep`
- `- w_downside * dup_axis_downside_rep`
- `+ w_bm * dup_axis_bm_rep`
- `+ w_persistence * dup_axis_persistence_rep`
`) / sum_w`

최종 `qualitative_signal`은 `[-1,1]` clip

### 15.5 Stage4 linkage fields
- `stage4_numeric_weight = 0.80`
- `stage3_qual_weight = 0.20`
- `stage4_link_formula = "COMPOSITE = 0.80*VALUE_SCORE + 0.20*QUALITATIVE_SIGNAL"`
- Stage4 macro contract(권장): `date` 기준으로 `stage3_macro_forecast.csv`를 별도 조인하고, stock row의 `QUALITATIVE_SIGNAL`과 독립적으로 regime overlay를 적용한다.

---

## 16) feature CSV schema
출력: `invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv`

컬럼:
- `date`, `symbol`
- `doc_count`, `mention_count`, `claim_card_count`, `issue_cluster_count`
- `upside_score`, `downside_risk_score`, `risk_score`, `bm_sector_fit_score`, `persistence_score`, `net_edge_score`
- `source_diversity_ratio`, `source_reliability_mean`
- `dart_doc_count`, `news_doc_count`, `rss_doc_count`, `selected_articles_doc_count`, `news_mention_count`
- `telegram_doc_count`, `blog_doc_count`, `premium_doc_count`, `image_map_doc_count`, `images_ocr_doc_count`
- `event_tagged_doc_count`, `event_order_count`, `event_rights_issue_count`, `event_lawsuit_count`, `event_guidance_count`
- `macro_news_doc_count`, `macro_risk_on_ratio`, `macro_risk_off_ratio`, `macro_risk_signal`
- `macro_to_stock_axes_applied`
- `qualitative_signal`
- duplication guard fields
  - `dup_guard_axis_weight_upside`
  - `dup_guard_axis_weight_downside`
  - `dup_guard_axis_weight_bm`
  - `dup_guard_axis_weight_persistence`
  - `dup_guard_corr_threshold`
  - `dup_guard_axis_cap`
  - `dup_guard_pre_high_corr_pair_count`
  - `dup_guard_post_high_corr_pair_count`
  - `dup_guard_actions`
  - `dup_guard_pre_pairs`
  - `dup_guard_post_pairs`
- Stage4 linkage fields
  - `stage4_numeric_weight`
  - `stage3_qual_weight`
  - `stage4_link_formula`
- `brain_backend`

---

## 17) macro forecast CSV
출력: `invest/stages/stage3/outputs/signal/stage3_macro_forecast.csv`

컬럼:
- `date`
- `macro_doc_count`
- `macro_risk_signal`
- `macro_risk_on_ratio`
- `macro_risk_off_ratio`
- `macro_regime_label`
- `macro_forecast_score`
- `macro_confidence`
- `macro_horizon`
- `macro_evidence_summary`
- `macro_source_mix`
- `brain_backend`

---

## 18) DART event signal
출력: `invest/stages/stage3/outputs/signal/dart_event_signal.csv`

생성 대상:
- `dart_doc_count > 0`인 `(date,symbol)` row만

산식:
- `dart_event_signal = (event_order_count - event_rights_issue_count - event_lawsuit_count + 0.5*event_guidance_count) / max(doc_count, 1)`
- clip to `[-1,1]`

컬럼:
- `date`
- `symbol`
- `dart_doc_count`
- `event_order_count`
- `event_rights_issue_count`
- `event_lawsuit_count`
- `event_guidance_count`
- `dart_event_signal`

---

## 19) summary JSON schema
출력: `invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json`

top-level key:
- `stage`
- `local_brain_enforced`
- `backend`
- `local_endpoint`
- `input_jsonl`
- `claim_card_jsonl`
- `output_csv`
- `dart_signal_csv`
- `macro_forecast_csv`
- `canonical_intermediate_corpus`
- `units`
- `records_loaded`
- `records_scanned`
- `records_dedup_dropped`
- `records_macro_only`
- `records_skipped_nosymbol`
- `source_docs`
- `claim_cards_generated`
- `issue_clusters_generated`
- `mentions_loaded`
- source별 loaded docs count
- `macro_news_docs_loaded`
- `symbols_output`
- `rows_output`
- `dart_signal_rows`
- `macro_forecast_rows`
- `apply_macro_to_stock_axes`
- `axes`
- `duplication_guard`
- `bootstrap_empty_ok`

검증 포인트:
- `rows_output > 0`, `claim_cards_generated > 0` (bootstrap-empty 제외)
- `records_skipped_nosymbol`가 집계되는지
- `duplication_guard` 섹션 존재

---

## 20) 실행 커맨드
```bash
# input build
python3 invest/stages/stage3/scripts/stage03_build_input_jsonl.py

# local qualitative axes
python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py \
  --input-jsonl invest/stages/stage3/inputs/stage2_text_meta_records.jsonl \
  --output-csv invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv \
  --claim-card-jsonl invest/stages/stage3/outputs/features/stage3_claim_cards.jsonl \
  --dart-signal-csv invest/stages/stage3/outputs/signal/dart_event_signal.csv \
  --macro-forecast-csv invest/stages/stage3/outputs/signal/stage3_macro_forecast.csv \
  --summary-json invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json

# bootstrap mode
python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py --bootstrap-empty-ok
```

builder optional caps:
- `--text-lookback-days`
- `--telegram-max-files`
- `--telegram-max-messages-per-file`
- `--blog-max-files`
- `--premium-max-files`
- `--selected-articles-max-files`
- `--include-nosymbol` / `--exclude-nosymbol`

gate optional args:
- `--backend keyword_local|llama_local`
- `--local-endpoint`
- `--local-model`
- `--macro-forecast-csv`
- `--apply-macro-to-stock-axes on|off`
- `--bootstrap-empty-ok`

---

## 21) PASS / FAIL 기준
- builder는 출력 0건이어도 JSONL 파일은 만든다.
- gate는 아래면 실패
  - local-only policy 위반
  - input row validation error 존재
  - `bootstrap_empty_ok`가 아닌데 최종 feature가 empty
- 최종 산출물
  - `stage3_qualitative_axes_features.csv`
  - `stage3_claim_cards.jsonl`
  - `dart_event_signal.csv`
  - `STAGE3_LOCAL_BRAIN_RUN_latest.json`

---

## 22) 재현 구현 요약
Stage3를 문서만 보고 재현하려면 아래를 동일하게 맞추면 된다.
1. builder의 source별 record 생성 규칙과 intermediate JSONL schema
2. chunk policy / keyword table / source prior
3. claim-card score formula / cluster rule / duplication guard
4. feature CSV / macro forecast / dart signal / summary JSON schema
