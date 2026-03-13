# STAGE3_BRAIN_SCORING_DESIGN

status: DRAFT
updated_at: 2026-03-12 KST
change_type: Strategy
scope: Stage3 direct-brain scoring redesign for macro / industry / sector / stock qualitative analysis

## 1) 문서 목적
- 본 문서는 Stage3를 **문서별 / 아이템별 direct-brain scoring 구조**로 확장하기 위한 설계안이다.
- 현재 canonical 구현 계약은 여전히 `STAGE3_RULEBOOK_AND_REPRO.md`가 우선이며, 본 문서는 다음 Strategy 변경안을 정의한다.
- 핵심 목표는 단순 keyword/숫자 필터링이 아니라, 각 문서가 실제로 무엇을 주장하고 어떤 근거와 리스크를 갖는지까지 구조화해 Stage3 품질을 끌어올리는 것이다.
- 이번 개정의 초점은 **레벨별 분류 체계와 최종 산출결과를 first-principles로 재설계**하는 것이다. 즉, 공통 evidence/confidence 껍데기는 유지하되, 최종 측정 항목은 `macro / industry / sector / stock`마다 달라야 한다.

## 2) 이번 변경의 핵심 결정
1. 본 변경은 **Strategy change**다.
2. Stage3 점수화 기본 단위는 `document_or_item_id × focus_entity_or_context`다.
   - long-form 문서는 내부 section/card를 만들 수 있어도 최종 판정은 문서/아이템 단위로 남긴다.
3. 아래 source는 **direct-brain 필수 대상**이다.
   - `blog`
   - `telegram`
   - `premium`
   - `pdf_analyst_report`
4. 아래 source는 **expanded direct-brain candidate**로 포함한다.
   - `report`
   - `ir`
   - `earnings_call`
   - `conference_call`
   - `trade_publication`
   - `field_signal`
5. 아래 source는 **deterministic-first + auxiliary-brain**을 유지한다.
   - `dart`
   - `rss`
   - `macro`
6. 분석 구조는 `macro / industry / sector / stock` 4레벨을 지원한다.
7. **최종 final score measurement item은 레벨별로 다르다.**
   - stock은 `upside / downside risk / catalyst path / thesis confidence` 같은 종목 전용 축을 쓴다.
   - industry는 `구조적 매력 / 사이클 우위 / 가격결정력·수급 / 정책·기술 tailwind / 구조적 취약성` 같은 산업 전용 축을 쓴다.
   - sector는 `sector attractiveness / rotation strength / earnings breadth / flow-positioning / leadership quality / fragility` 같은 섹터 전용 축을 쓴다.
   - macro는 `regime support / liquidity stress / policy directionality / transmission clarity / macro confidence` 같은 거시 전용 축을 쓴다.
   - 따라서 industry/sector/macro는 stock의 upside/downside/risk 축을 복붙하지 않는다.
8. 추후 benchmark는 최소 `local_brain / main_brain / subagent_brain / external_review` 비교를 지원한다.

## 3) 왜 direct-brain scoring이 필요한가
기존 Stage3는 claim-card와 4축 score 구조를 이미 갖고 있으나, source family별로 실제 문서 의미를 깊게 반영하는 데 한계가 있다.
특히 blog/telegram/premium/report류는 아래 문제가 크다.
- 문서 길이와 구조가 비정형적이다.
- 숫자 유무만으로 가치가 갈리지 않는다.
- 종목 직접 언급보다 산업/섹터 힌트가 더 중요한 경우가 많다.
- 동일 문서 안에 bullish/bearish 근거가 함께 존재한다.
- 요약보다 `근거-반론-리스크-전달경로` 분리가 성능을 좌우한다.

따라서 Stage3는 단순 filtering stage가 아니라, **문서 하나하나를 읽고 투자판단에 필요한 분류항목, 중간 분석 카드, 최종 결과축을 함께 생산하는 scoring stage**로 설계하는 것이 맞다.

## 4) Stage3 scoring operating model

### 4.1 두 층 구조 유지
- **Layer A: deterministic ingest / normalize layer**
  - Stage2 clean 입력을 받는다.
  - entity linking, source normalization, fingerprint, published_at normalization을 수행한다.
- **Layer B: direct-brain scoring layer**
  - 문서별 / 아이템별 claim, evidence, risk, counterpoint, transmission path를 추출한다.
  - macro / industry / sector / stock row로 분기한다.
  - 공통 evidence/confidence skeleton과 레벨별 final result를 생성한다.

### 4.2 문서별 / 아이템별 평가 원칙
- scoring unit은 단순 숫자 threshold가 아니라 **한 개 파일 또는 한 개 feed item**이다.
- 각 unit은 반드시 아래를 남긴다.
  - 무엇을 주장하는가 (`primary_claim`)
  - 어떤 근거를 제시하는가 (`evidence`)
  - 무엇이 깨질 수 있는가 (`risk`)
  - 반대 해석은 무엇인가 (`counterpoint`)
  - 어떤 level/entity/context에 연결되는가 (`macro|industry|sector|stock`)
  - 그 주장이 어떤 경로로 실적/밸류/수급/레짐에 번역되는가 (`transmission_path`)
- 점수는 evidence 없는 경우 낮아져야 하며, 숫자나 source tier가 높아도 근거 구조가 빈약하면 높은 점수를 줄 수 없다.

## 5) source routing policy

### 5.1 route matrix
| source_family | 기본 lane | 비고 |
| --- | --- | --- |
| blog | direct-brain | 필수 |
| telegram | direct-brain | 필수 |
| premium | direct-brain | 필수 |
| pdf_analyst_report | direct-brain | 필수 |
| report | direct-brain | 확장 후보 |
| ir | direct-brain | 확장 후보 |
| earnings_call | direct-brain | 확장 후보 |
| conference_call | direct-brain | 확장 후보 |
| trade_publication | direct-brain | 확장 후보 |
| field_signal | direct-brain | 확장 후보, 단독 승격 제한 |
| dart | deterministic-first | brain은 auxiliary note만 가능 |
| rss | deterministic-first | brain은 selective assist |
| macro | deterministic-first | brain은 scenario/support note |

### 5.2 deterministic-first contract
#### DART
- event extraction, filing type, date, issuer, explicit numbers는 deterministic parser가 우선한다.
- brain lane은 아래만 보조한다.
  - filing의 의미 해석 보조
  - 기존 thesis와의 연결 메모
  - ambiguity flag
- brain lane은 DART의 사실값을 덮어쓰지 않는다.

#### RSS
- item flatten, entity linking, macro/industry/sector/stock tag 부여는 deterministic이 우선한다.
- brain lane은 아래 조건에서만 개입한다.
  - item이 장문 summary를 포함할 때
  - 해석 충돌이 있을 때
  - benchmark 샘플링 대상일 때

#### macro
- macro regime, risk-on/off, rates/fx/liquidity 태그는 deterministic-first다.
- brain lane은 scenario note, transmission path, affected sectors를 보조 기록할 수 있다.
- brain 단독으로 macro regime label을 뒤집지 않는다.
- 다만 macro row가 생성될 경우에도 **최종 산출 축은 stock 축을 쓰지 않고 macro 전용 결과축**을 사용한다.

## 6) analysis levels and separation

### 6.1 level separation 원칙
한 문서에서 4레벨이 동시에 추출될 수 있지만 row는 분리한다.
- `macro_context_row`
- `industry_analysis_row`
- `sector_analysis_row`
- `stock_analysis_row`

### 6.2 가장 중요한 원칙: common skeleton, different final scorecards
- 공통으로 유지할 것은 `evidence / risk / counterpoint / source reliability / confidence / escalation` 골격이다.
- **분리해야 하는 것은 최종 점수항목, 최종 판단 결과, rollup 방식**이다.
- Stage3는 더 이상 “모든 레벨을 같은 4축에 억지로 넣는 구조”를 primary output으로 삼지 않는다.
- 즉, stock/industry/sector/macro는 같은 문서를 읽더라도 서로 다른 질문과 서로 다른 최종 산출물을 갖는다.

### 6.3 level별 핵심 질문
#### macro
- 지금의 거시 레짐은 risk asset에 순풍인가 역풍인가?
- 유동성/금리/환율/정책 변화가 어떤 전달경로로 industry/sector/stock에 전이되는가?
- 충격이 광범위한가, 특정 구간에만 제한되는가?

#### industry
- 산업 전체의 구조 변화가 있는가?
- 수요/공급/가격/규제/기술 사이클이 어떻게 변하는가?
- 어느 비즈니스 모델이 가치 포착(value capture) 우위를 갖는가?

#### sector
- 투자 분류상 같은 sector 바스켓 내부에서 어떤 하위 구도가 생기는가?
- 해당 sector의 대표 KPI 또는 earnings breadth / flow / rotation이 개선되는가?
- benchmark / relative strength / positioning 관점에서 이 섹터는 쓸모 있는가?

#### stock
- 개별 기업 thesis에 직접 연결되는 catalyst/risk가 있는가?
- 실적, 마진, 수주, 가격, 점유율, execution, 자본조달에 어떤 영향을 주는가?
- 산업 변화가 이 종목의 숫자와 멀티플로 어떻게 번역되는가?

### 6.4 level row 생성 규칙
- 하나의 문서가 여러 종목을 언급해도 `focus_entity_or_context`가 다르면 row를 분리한다.
- entity 연결 신뢰도가 낮으면 row를 만들지 않고 `entity_link_weak`로 드롭 또는 review queue로 보낸다.
- field signal은 `industry/sector`에는 기여 가능하나 `stock` 단독 확정 근거로는 낮은 prior를 둔다.
- macro는 entity가 아닌 context row일 수 있으며, 이후 industry/sector/stock row에 영향을 주는 상위 입력으로만 사용될 수 있다.

## 7) 공통 evidence/confidence skeleton
각 문서/아이템은 먼저 아래 공통 envelope를 만든다.

```json
{
  "document_or_item_id": "string",
  "source_family": "blog|telegram|premium|pdf_analyst_report|report|ir|earnings_call|conference_call|trade_publication|field_signal|dart|rss|macro",
  "focus_level": "macro|industry|sector|stock",
  "focus_entity_or_context_id": "string",
  "primary_claim": "string",
  "supporting_claims": ["string"],
  "evidence": [{"text": "string", "locator": "string", "kind": "quote|number|observation|cross-check"}],
  "risk": ["string"],
  "counterpoint": ["string"],
  "transmission_path": ["string"],
  "time_horizon": "short|medium|long",
  "novelty": "low|medium|high",
  "source_tier": "official|professional|independent|field_signal",
  "source_reliability_note": "string",
  "entity_link_confidence": 0.0,
  "analysis_confidence": 0.0,
  "needs_escalation": false
}
```

### 7.1 공통 sub-score
모든 direct-brain row는 최소 아래 공통 sub-score를 갖는다.
- `evidence_quality_score` (근거 명확성)
- `novelty_score` (최근 corpus 대비 새로움)
- `materiality_score` (실적/산업구조/멀티플/레짐에 미칠 중요도)
- `linkage_score` (macro→industry→sector→stock 전달 연결 강도)
- `source_reliability_score` (source tier + corroboration)
- `counterbalance_score` (반론/리스크를 함께 반영했는지)
- `timing_clarity_score` (언제 작동하는지 명확한지)

### 7.2 공통 skeleton의 역할
- 이 공통 점수들은 **신뢰도와 근거 품질**을 표현한다.
- 그러나 이것만으로 최종 투자판단을 표현하지 않는다.
- 실제 final scorecard는 아래 8장처럼 **레벨별 taxonomy/card/output**으로 별도 생성한다.

## 8) level-specific deep taxonomy and intermediate cards

### 8.1 macro level
#### (1) 무엇을 분류해야 하는가
- `regime_state`: 성장/인플레/유동성/정책 조합이 어떤 레짐인가
- `shock_source`: rates / fx / credit / commodity / fiscal / geopolitics 중 무엇이 원인인가
- `transmission_channel`: 할인율, 자금조달, 소비, CAPEX, 재고, 가격, 환산손익 중 어떤 경로로 전이되는가
- `breadth_scope`: 광범위한가, 특정 지역/산업에 국한되는가
- `persistence_type`: 일시 이벤트인가, 정책/사이클 지속형인가
- `beneficiary_harmed_map`: 어느 산업/섹터가 수혜/피해를 받는가

#### (2) 어떤 중간 분석 카드가 있어야 하는가
- `macro_regime_card`
  - current regime
  - dominant driver
  - confirming evidence
  - invalidation signal
- `policy_path_card`
  - policy stance
  - expected next move
  - policy uncertainty
- `transmission_matrix_card`
  - channel
  - affected levels
  - lag estimate
  - confidence
- `macro_scenario_card`
  - bull/base/bear macro scenario
  - trigger set
  - timing window

#### (3) 최종적으로 어떤 판단 결과가 나와야 하는가
- `regime_support_score`: risk asset 및 실물 수요에 대한 순풍/역풍 정도
- `liquidity_stress_score`: 자금조달/밸류에이션 압박 정도
- `policy_directionality_score`: 정책이 우호적인지 긴축적인지
- `transmission_clarity_score`: 실제 하위 레벨로 얼마나 명확히 전이되는지
- `macro_confidence_score`: 레짐 해석에 대한 확신도
- `macro_regime_label`: easing / reflation / tightening / stagflation / uncertainty spike 등
- `affected_priority_map`: 우선 영향받는 industry/sector 목록

### 8.2 industry level
#### (1) 무엇을 분류해야 하는가
- `demand_regime`: 최종수요가 확장/정체/축소 중 무엇인가
- `supply_discipline`: 공급 증가/감산/재고/가동률 상태가 어떤가
- `value_capture_map`: value chain 어디가 이익을 가져가는가
- `pricing_power_state`: 가격인상력, 계약구조, pass-through 가능성이 어떤가
- `cycle_position`: early/mid/late/downturn/recovery 중 어디인가
- `policy_tech_change`: 정책/규제/기술 변화가 구조적 추세를 만드는가
- `entry_barrier_shift`: 진입장벽/교체비용/규모경제가 강화되는가 약화되는가
- `winner_traits`: 앞으로 유리할 기업 속성이 무엇인가

#### (2) 어떤 중간 분석 카드가 있어야 하는가
- `industry_structure_card`
  - market structure
  - concentration
  - barrier trend
  - substitute threat
- `demand_supply_balance_card`
  - demand trend
  - supply trend
  - inventory/capacity
  - imbalance direction
- `value_capture_card`
  - profit pool location
  - margin transfer path
  - bargaining power owner
- `policy_technology_change_card`
  - regulatory change
  - technology inflection
  - adoption lag
- `winner_profile_card`
  - advantaged attributes
  - disadvantaged attributes
  - evidence basis

#### (3) 최종적으로 어떤 판단 결과가 나와야 하는가
- `structural_attractiveness_score`: 산업 자체의 장기 구조적 매력
- `cycle_advantage_score`: 현재 사이클 구간이 산업에 우호적인 정도
- `pricing_power_supply_score`: 가격결정력·수급·가동률 측면의 우위
- `policy_technology_tailwind_score`: 정책/기술 변화의 순풍 강도
- `disruption_fragility_score`: 구조적 붕괴/대체/규제 충격 취약성
- `industry_attractiveness_score`: 위 축을 종합한 산업 매력도
- `industry_regime_label`: expansion / tightening / oversupply / restructuring / secular winner 등
- `winner_traits_output`: 어떤 기업 유형이 유리한지에 대한 결과 요약

### 8.3 sector level
#### (1) 무엇을 분류해야 하는가
- `benchmark_role`: 시장에서 공격/방어/중립 섹터로 어떤 역할을 하는가
- `rotation_state`: 자금 로테이션이 유입/유출/혼조 중 무엇인가
- `earnings_revision_breadth`: 상향/하향 조정이 sector 전반에 넓게 퍼지는가
- `leadership_breadth`: 소수 리더 집중인지, broad participation인지
- `positioning_crowding`: 포지셔닝 과밀 여부
- `style_sensitivity`: 금리/성장/가치/퀄리티 등 스타일 변화에 대한 민감도
- `internal_dispersion`: 같은 sector 내부 winner/loser 분산도가 큰가
- `benchmark_utility`: 섹터 신호가 실제 basket construction에 유용한가

#### (2) 어떤 중간 분석 카드가 있어야 하는가
- `sector_rotation_card`
  - flow direction
  - relative strength
  - rotation persistence
- `earnings_breadth_card`
  - revision breadth
  - estimate trend
  - breadth confidence
- `leadership_dispersion_card`
  - leaders vs laggards
  - concentration risk
  - breadth of participation
- `positioning_crowding_card`
  - crowdedness
  - unwind risk
  - ownership imbalance
- `benchmark_fit_card`
  - signal usefulness
  - basket coherence
  - implementation caveat

#### (3) 최종적으로 어떤 판단 결과가 나와야 하는가
- `sector_attractiveness_score`: 섹터 자체의 투자 매력도
- `rotation_strength_score`: 상대강도/로테이션 강도
- `earnings_breadth_score`: 실적/추정치 개선이 sector 전반으로 확산되는 정도
- `flow_positioning_score`: 자금흐름과 포지셔닝의 우호성
- `leadership_quality_score`: 리더십이 건강하고 확산형인지 여부
- `fragility_dispersion_score`: crowding, 내부 분산, unwind 취약성
- `sector_state_label`: leadership / accumulation / crowded / deteriorating / defensive bid 등
- `sector_usage_output`: benchmark/reference sector로 쓸지, 선별형 접근이 필요한지

### 8.4 stock level
#### (1) 무엇을 분류해야 하는가
- `thesis_driver_map`: volume / price / mix / cost / capacity / share / capital allocation / valuation 재평가 중 무엇이 핵심 driver인가
- `catalyst_type`: 실적, 제품, 수주, 정책 수혜, M&A, 정상화, 턴어라운드 등 어떤 catalyst인가
- `catalyst_path`: catalyst가 실제 숫자와 멀티플로 번역되는 경로가 명확한가
- `company_specific_edge`: 경쟁우위, execution, 고객구성, 원가구조, 밸런스시트가 차별화 포인트인가
- `failure_mode`: 무엇이 thesis를 깨는가
- `timing_window`: catalyst 시차와 유효기간이 언제인가
- `valuation_bridge`: 좋은 스토리가 실제 valuation re-rate를 만들 수 있는가

#### (2) 어떤 중간 분석 카드가 있어야 하는가
- `stock_thesis_translation_card`
  - primary thesis
  - P&L / cashflow translation
  - key assumption
  - evidence backing
- `catalyst_path_card`
  - catalyst event
  - expected timing
  - market recognition path
  - gating factor
- `execution_fragility_card`
  - operational risk
  - balance sheet risk
  - management credibility
  - dependency concentration
- `valuation_bridge_card`
  - current expectation
  - re-rate/de-rate trigger
  - sensitivity
- `thesis_falsification_card`
  - disconfirming indicators
  - stop condition
  - monitoring items

#### (3) 최종적으로 어떤 판단 결과가 나와야 하는가
- `upside_capture_score`: 문서가 제시하는 upside 실현 잠재력
- `downside_risk_score`: 실적/멀티플/자금조달/실행 측면의 하방 리스크
- `catalyst_path_score`: catalyst가 실제로 작동할 가능성과 경로의 명확성
- `thesis_confidence_score`: evidence, 반론 처리, 연결 논리까지 포함한 확신도
- `execution_resilience_score`: 회사가 thesis를 실행할 체력과 복원력
- `stock_view_label`: asymmetric long / watchlist / mixed / avoid / short-risk-check 등
- `falsification_output`: 무엇이 나오면 thesis를 버려야 하는지

## 9) final score production design

### 9.1 primary principle
- **Stage3의 primary final output은 레벨별 scorecard다.**
- 공통 skeleton은 shared envelope이고, 최종 판단은 `level_specific_taxonomy + level_specific_cards + level_specific_result_axes`로 표현한다.
- 같은 문서라도 macro/industry/sector/stock row는 서로 다른 result axis를 가진다.

### 9.2 level-specific result payload example
```json
{
  "focus_level": "industry",
  "classification": {
    "demand_regime": "expanding",
    "supply_discipline": "tight",
    "cycle_position": "mid-cycle",
    "pricing_power_state": "improving"
  },
  "analysis_cards": {
    "industry_structure_card": {},
    "demand_supply_balance_card": {},
    "value_capture_card": {},
    "policy_technology_change_card": {}
  },
  "final_result": {
    "structural_attractiveness_score": 82,
    "cycle_advantage_score": 74,
    "pricing_power_supply_score": 79,
    "policy_technology_tailwind_score": 68,
    "disruption_fragility_score": 29,
    "industry_attractiveness_score": 80,
    "industry_regime_label": "secular winner"
  }
}
```

### 9.3 optional legacy compatibility view
- downstream 호환이 꼭 필요하면 **secondary projection**으로만 아래를 계산할 수 있다.
  - `legacy_upside_proxy`
  - `legacy_downside_proxy`
  - `legacy_bm_fit_proxy`
  - `legacy_persistence_proxy`
- 단, 이것은 level-specific 결과를 압축한 파생치일 뿐이며 primary truth가 아니다.
- industry/sector/macro를 legacy 4축으로 투영할 때 정보 손실이 크므로, canonical decision/reporting은 level-specific output을 기준으로 한다.

## 10) score production logic

### 10.1 direct-brain row 생성 순서
1. entity/context link
2. level split (`macro|industry|sector|stock`)
3. `primary_claim`와 `transmission_path` 추출
4. 공통 evidence/risk/counterpoint skeleton 생성
5. level-specific taxonomy 분류
6. level-specific intermediate analysis card 생성
7. level-specific final result axis 산출
8. common confidence / escalation flag 결정
9. 필요 시 only-secondary legacy projection 생성

### 10.2 hard guardrails
- evidence가 비어 있으면 high-confidence/high-score 금지
- counterpoint/risk가 전혀 없으면 confidence cap 적용
- source tier가 낮아도 corroboration이 있으면 살릴 수 있다
- source tier가 높아도 boilerplate면 점수 상한 적용
- price-action only 문서는 low-value로 보낸다
- level mismatch 문서는 해당 level result 생성을 금지한다
  - 예: macro note를 stock upside/downside score로 바로 변환 금지
  - 예: industry note를 stock catalyst score로 바로 복붙 금지

### 10.3 aggregation
최종 Stage3 집계는 기존처럼 `(date, focus_level, focus_entity_or_context)` rollup을 갖되, **레벨별 개별 rollup 파일과 개별 axis 집계**를 유지한다.
- stock rollup key: `(date, symbol)`
- sector rollup key: `(date, sector_id)`
- industry rollup key: `(date, industry_id)`
- macro rollup key: `(date, macro_context_id)`
- long-form 동일 문서의 중복 section은 `document_or_item_id` 기준 중복 가드를 둔다.

## 11) lane architecture

### 11.1 lanes 정의
1. `local_brain`
   - 로컬 모델/로컬 규칙 기반 자동 lane
   - 대량 처리 기본선
2. `main_brain`
   - 메인 세션이 직접 판단하는 고품질 lane
   - 복잡/중요 샘플, adjudication 용도
3. `subagent_brain`
   - 서브에이전트가 동일 계약으로 처리하는 lane
   - 장문/대량/비교 실험 용도
4. `external_review`
   - 외부 수동 평가 보조 lane
   - 첨부 파일 기반 소배치 평가 전용

### 11.2 lane 역할 분리
- production default는 `local_brain + deterministic-first` 조합이다.
- `main_brain`과 `subagent_brain`은 benchmark, high-impact review, disagreement resolution에서 주로 사용한다.
- `external_review`는 최종 writer가 아니라 **독립 비교군**이다.

## 12) external-review lane 설계

### 12.1 목적
- web-review 스타일의 독립 평가 lane을 제공하되, 코드리뷰 스킬을 그대로 재사용하지 않는다.
- 대상은 repository diff가 아니라 **데이터 파일 직접 첨부 기반 평가**다.
- 용도는 production 대체가 아니라 아래 두 가지다.
  - benchmark 독립 비교군 확보
  - 내부 lane disagreement adjudication 보조

### 12.2 배치 크기 제한
- 한 번의 external-review batch는 **100개 이하 문서/아이템**만 허용한다.
- 권장 크기: 20~50개
- 너무 큰 묶음은 금지한다. 이유는 첨부 품질, 응답 일관성, 회수 가능성을 유지하기 위해서다.

### 12.3 입력 패키지
external-review 입력은 최소 아래 파일로 구성한다.
- `batch_manifest.json`
- `documents.jsonl` 또는 문서 원문/발췌 파일 묶음
- `entity_reference.csv`
- `scoring_contract.md`
- 필요 시 `taxonomy_reference.csv`

### 12.4 external-review contract
- reviewer는 각 파일을 문서/아이템 단위로 평가한다.
- 각 row에 대해 아래만 반환하도록 제한한다.
  - 공통 evidence/confidence skeleton
  - level-specific classification 요약
  - level-specific final result axis
  - 처리 불가/애매 flag
- reviewer에게 전체 투자판단이나 포트폴리오 추천은 요구하지 않는다.
- reviewer 응답은 반드시 작은 구조화 포맷(JSON/CSV)으로 회수한다.

### 12.5 external-review 주의사항
- 외부 review는 reference input일 뿐 자동 채택하지 않는다.
- 민감 데이터나 비공개 원문은 사전 승인 없이 보내지 않는다.
- 외부 review 결과는 내부 lane과 같은 schema로 normalize 후 비교한다.

## 13) proposed output schema

### 13.1 raw per-lane scorecards
파일 예시:
- `invest/stages/stage3/outputs/features/stage3_brain_doc_scorecards.jsonl`

```json
{
  "batch_id": "string",
  "date": "YYYY-MM-DD",
  "document_or_item_id": "string",
  "source_family": "string",
  "focus_level": "macro|industry|sector|stock",
  "focus_entity_or_context_id": "string",
  "lane": "local_brain|main_brain|subagent_brain|external_review",
  "primary_claim": "string",
  "evidence_summary": "string",
  "evidence_refs": ["string"],
  "risk_summary": ["string"],
  "counterpoint_summary": ["string"],
  "transmission_path": ["string"],
  "evidence_quality_score": 0,
  "novelty_score": 0,
  "materiality_score": 0,
  "linkage_score": 0,
  "source_reliability_score": 0,
  "counterbalance_score": 0,
  "timing_clarity_score": 0,
  "classification": {},
  "analysis_cards": {},
  "final_result_axes": {},
  "final_result_label": "string",
  "analysis_confidence": 0.0,
  "processing_seconds": 0.0,
  "estimated_cost_usd": 0.0,
  "human_effort_minutes": 0.0,
  "needs_escalation": false,
  "legacy_projection": {
    "legacy_upside_proxy": 0,
    "legacy_downside_proxy": 0,
    "legacy_bm_fit_proxy": 0,
    "legacy_persistence_proxy": 0
  },
  "error_flag": "none"
}
```

### 13.2 level-specific rollup outputs
레벨별 final axis가 다르므로 rollup도 분리한다.
- `invest/stages/stage3/outputs/features/stage3_brain_macro_rollup.csv`
- `invest/stages/stage3/outputs/features/stage3_brain_industry_rollup.csv`
- `invest/stages/stage3/outputs/features/stage3_brain_sector_rollup.csv`
- `invest/stages/stage3/outputs/features/stage3_brain_stock_rollup.csv`

핵심 원칙:
- 각 rollup은 그 레벨의 axis만 wide column으로 가진다.
- cross-level 통합 리포트가 필요하면 JSON/long-form으로 합치되, **axis name을 보존**한다.

예시 컬럼:
#### macro rollup
- `date`
- `macro_context_id`
- `regime_support_score`
- `liquidity_stress_score`
- `policy_directionality_score`
- `transmission_clarity_score`
- `macro_confidence_score`
- `macro_regime_label`

#### industry rollup
- `date`
- `industry_id`
- `structural_attractiveness_score`
- `cycle_advantage_score`
- `pricing_power_supply_score`
- `policy_technology_tailwind_score`
- `disruption_fragility_score`
- `industry_attractiveness_score`
- `industry_regime_label`

#### sector rollup
- `date`
- `sector_id`
- `sector_attractiveness_score`
- `rotation_strength_score`
- `earnings_breadth_score`
- `flow_positioning_score`
- `leadership_quality_score`
- `fragility_dispersion_score`
- `sector_state_label`

#### stock rollup
- `date`
- `symbol`
- `upside_capture_score`
- `downside_risk_score`
- `catalyst_path_score`
- `thesis_confidence_score`
- `execution_resilience_score`
- `stock_view_label`

### 13.3 evidence index
파일 예시:
- `invest/stages/stage3/outputs/features/stage3_brain_evidence_index.jsonl`

목적:
- scorecard의 evidence locator를 원문/페이지/문단/메시지 위치와 역추적 가능하게 남긴다.
- level-specific card와 evidence 연결도 추적할 수 있게 한다.

### 13.4 benchmark comparison output
파일 예시:
- `invest/stages/stage3/outputs/benchmark/stage3_brain_lane_comparison.jsonl`
- `invest/stages/stage3/outputs/benchmark/stage3_brain_lane_comparison_summary.json`

핵심 비교 원칙:
- **같은 level끼리만 비교한다.**
- 비교 단위는 고정 4축이 아니라 `focus_level + axis_name`이다.
- long-form 비교를 사용한다.

핵심 비교 필드:
- `batch_id`
- `document_or_item_id`
- `focus_level`
- `focus_entity_or_context_id`
- `source_family`
- `axis_name`
- `local_brain_axis_score`
- `main_brain_axis_score`
- `subagent_brain_axis_score`
- `external_review_axis_score`
- `axis_score_spread_max`
- `evidence_overlap_bucket`
- `processing_seconds_by_lane`
- `estimated_cost_usd_by_lane`
- `human_effort_minutes_by_lane`
- `agreement_bucket`
- `winner_for_traceability`
- `winner_for_speed`
- `winner_for_cost`
- `review_note`

## 14) benchmark design: main vs subagent 중심

### 14.1 benchmark 목적
후속 benchmark는 최소 아래 질문에 답해야 한다.
- 메인과 서브에이전트가 같은 문서를 비슷하게 읽는가?
- 어느 lane이 근거 추적성이 더 좋은가?
- 어느 lane이 속도/비용/수고 대비 효율이 높은가?
- source family별로 lane 우열이 달라지는가?
- level별 taxonomy/card/output을 얼마나 일관되게 생성하는가?

### 14.2 benchmark batch 구성
- source family별로 균형 샘플을 잡는다.
- 우선순위:
  - blog
  - telegram
  - premium
  - pdf_analyst_report
  - report / ir / earnings_call / conference_call / trade_publication / field_signal
- deterministic-first family는 보조 샘플만 넣는다.
- batch는 `same documents, same entity mapping, same scoring contract`를 메인/서브/외부에 공통 적용한다.

### 14.3 비교 방식
- 문서별 taxonomy classification 일치율
- intermediate analysis card completeness
- level-specific final axis absolute diff
- evidence locator 일치율
- escalation 필요 판단 일치율
- 처리시간
- 비용/수고
- source family별 승률

### 14.4 승부 판정 기준 예시
- `traceability_winner`: evidence locator와 card linkage가 더 명확한 lane
- `taxonomy_winner`: level-specific 분류 정확성이 더 높은 lane
- `stability_winner`: 동일 family/level에서 score variance가 더 낮은 lane
- `speed_winner`: processing_seconds가 더 낮은 lane
- `efficiency_winner`: 비용/수고 대비 품질이 좋은 lane
- `final_reference_lane`: 메인 검수 후 이번 배치에서 reference로 삼을 lane

## 15) disagreement and escalation rules
- 메인/서브/외부 중 axis spread가 임계치 이상이면 `disagreement_flag=true`
- 아래면 escalation한다.
  - entity/context mapping 충돌
  - primary claim 충돌
  - transmission path 충돌
  - taxonomy classification 충돌
  - intermediate card 핵심 항목 누락 차이 큼
  - 같은 level final axis 중 2개 이상에서 큰 편차
- escalation 후에는 main_brain adjudication 또는 별도 human review를 둔다.

## 16) practical rollout sequence
1. direct-brain 필수 family부터 도입
   - blog / telegram / premium / pdf_analyst_report
2. 공통 skeleton schema 고정
3. macro / industry / sector / stock level split 구현
4. level-specific taxonomy/card/result schema 구현
5. 레벨별 rollup 파일 분리
6. benchmark용 main vs subagent 공통 배치 작성
7. external-review 소배치 lane 추가
8. source family별 default route / escalation threshold 튜닝
9. 이후 canonical Stage3 rulebook 반영 여부 결정

## 17) non-goals
- Stage3에서 최종 포트폴리오 판단을 내리지 않는다.
- external-review를 production 단일 truth source로 쓰지 않는다.
- DART/RSS/macro를 전면 brain-first로 바꾸지 않는다.
- 단순 감성/주목도 점수만으로 종목 선호를 결정하지 않는다.
- 레벨별로 다른 현실을 하나의 얕은 공통 taxonomy로 뭉개지 않는다.

## 18) final design summary
- Stage3는 앞으로 **문서별 / 아이템별 direct-brain scoring**을 중심에 둔다.
- 필수 대상은 `blog / telegram / premium / pdf analyst reports`다.
- 확장 대상은 `report / IR / earnings call / conference call / trade publication / field signal`이다.
- `DART / RSS / macro`는 계속 deterministic-first이며 brain은 auxiliary support만 한다.
- 분석 레벨은 `macro / industry / sector / stock` 4개를 지원한다.
- 공통 skeleton은 evidence/confidence만 공유하고, **최종 final result axis는 레벨별로 분리**한다.
- industry/sector에는 attractiveness를 넣되, stock의 upside/downside/risk를 복붙하지 않는다.
- stock은 `upside_capture / downside_risk / catalyst_path / thesis_confidence / execution_resilience` 중심으로 본다.
- industry는 `structural_attractiveness / cycle_advantage / pricing_power_supply / policy_technology_tailwind / disruption_fragility` 중심으로 본다.
- sector는 `sector_attractiveness / rotation_strength / earnings_breadth / flow_positioning / leadership_quality / fragility_dispersion` 중심으로 본다.
- macro는 `regime_support / liquidity_stress / policy_directionality / transmission_clarity / macro_confidence` 중심으로 본다.
- output은 공통 scorecard envelope + level-specific taxonomy/card/result + evidence index + level별 rollup + benchmark comparison을 남긴다.
- benchmark는 `local_brain / main_brain / subagent_brain / external_review`를 같은 파일 단위로 비교하되, 비교 축도 level-specific axis 기준으로 수행한다.
