# STAGE3 Deep Analysis Extraction Rubric

status: DRAFT
updated_at: 2026-03-10 KST
change_type: Rule
scope: Stage3-B 심층분석 문서 선정/추출 기준

## 1) 목적
- Stage3-B 심층분석에서 문서별로 무엇을 추출할지 기준을 고정한다.
- 결과는 최소 `stock_data`와 `industry_data` 두 축으로 나뉘어 저장 가능해야 한다.
- 서브에이전트는 본 rubric에 따라 초안을 만들고, 메인은 샘플 검수/최종 판정을 담당한다.

## 2) 적용 범위
심층분석 대상 source 예시:
- official: 공시, IR, investor presentation, 주주서한, earnings call transcript, conference/Q&A
- professional: sell-side/buy-side report, 업계 전문지, 전문 리서치
- independent: 블로그, 뉴스레터, premium article
- field_signal: 고객/개발자 커뮤니티, 리뷰, 채용, 파트너/현장 신호

비대상:
- 가격 등락만 반복하는 시황 메모
- 근거 없는 감상/홍보문
- entity 연결이 불가능한 텍스트
- 이미 같은 claim/evidence로 최근 1개월 내 충분히 커버된 중복 문서

## 3) 문서 선정 기준 (deep-analysis candidate gate)
문서별로 아래를 보고 심층분석 대상으로 채택한다.

### 필수 조건
1. `entity_linkable`
   - 최소 하나 이상의 종목 또는 산업에 연결 가능해야 한다.
2. `evidence_present`
   - 숫자, 인용, 이벤트, 비교, 발언, 규제/제품/수요 변화 등 확인 가능한 근거가 있어야 한다.
3. `incremental_value`
   - 최근 1개월 기준 이미 알려진 내용의 단순 반복이 아니라 새 시사점/새 근거/새 해석이 있어야 한다.

### 가점 조건
- official/professional source tier
- 향후 1~12개월에 영향을 줄 이벤트 언급
- 경쟁구도/산업구조 변화 설명
- 수익성/가격/수요/공급/점유율/규제 등 구조적 변수 포함
- 반대 근거나 리스크를 함께 담고 있음

### 제외 규칙
아래면 Stage3-B deep analysis에서 제외 또는 낮은 우선순위로 내린다.
- entity 연결이 약함
- 근거 없는 opinion only
- 제목만 자극적이고 본문 근거 빈약
- promotional boilerplate 비중 과다
- UI/noise/meta 텍스트가 대부분
- 사실관계보다 단순 가격 코멘트 위주

## 4) 심층분석 추출 단위
기본 단위:
- `document_id × focus_entity`

focus_entity 종류:
- `stock`
- `industry`

한 문서에서 둘 다 추출 가능하지만, 결과 row는 분리한다.
- stock 관련 claim은 `stock_data`
- industry 관련 claim은 `industry_data`

## 5) 공통 필수 추출 항목
모든 심층분석 row는 아래 항목을 우선 추출한다.

1. `primary_claim`
   - 문서가 말하는 핵심 주장 1개
2. `supporting_claims`
   - 보조 주장 1~3개
3. `evidence`
   - claim을 지지하는 문장/숫자/발언/사실
4. `risk`
   - 하방/실패 가능성/불확실성
5. `counterpoint`
   - 반대 해석 또는 claim 약화 요소
6. `time_horizon`
   - 단기(0~3m) / 중기(3~12m) / 장기(12m+)
7. `novelty`
   - 최근 1개월 corpus 대비 새로움 정도
8. `source_tier`
   - official / professional / independent / field_signal
9. `source_reliability_note`
   - 신뢰 또는 한계 한 줄 메모
10. `source_refs`
   - 인용 위치/문단/페이지/URL 등 역추적 정보

## 6) stock_data 필수 추출 기준
stock 분석일 때는 아래 중 실제 근거가 있는 항목만 뽑는다.

### 핵심 축
1. `stock_thesis_direction`
   - bullish / bearish / mixed / watch
2. `company_specific_catalyst`
   - 수주, 신제품, 가격인상, 승인, 계약, 고객확대, 생산능력 증설 등
3. `company_specific_risk`
   - 실적악화, 규제, 소송, dilution, 경쟁심화, 지연 등
4. `financial_impact_hint`
   - 매출/마진/현금흐름/비용 구조에 미치는 방향성
5. `management_signal`
   - 경영진 톤, 가이던스 변화, 우선순위 변화
6. `competitive_position`
   - 점유율, moat, 고객 락인, 제품력, execution quality
7. `stock_industry_link`
   - 이 종목이 어떤 산업 구조 변화의 수혜/피해인지

### 있으면 추가
- `valuation_frame_mentioned`
- `customer_or_channel_signal`
- `supply_chain_position`
- `geography_specific_issue`

## 7) industry_data 필수 추출 기준
industry 분석일 때는 아래 중 실제 근거가 있는 항목만 뽑는다.

### 핵심 축
1. `industry_primary_theme`
   - 산업의 핵심 변화 1개
2. `demand_state`
   - 수요 확대/둔화/재고조정/주문흐름
3. `supply_state`
   - 공급 부족/과잉/증설/병목
4. `pricing_power`
   - 가격 인상/할인 압력/마진 구조 변화
5. `industry_structure_shift`
   - 경쟁구도, value chain, winner/loser 이동
6. `regulatory_or_policy_effect`
   - 허가/제재/규제/보조금/관세 등
7. `technology_or_cycle_phase`
   - 채택 초입/확산/피크/둔화/교체 주기
8. `industry_stock_links`
   - 수혜 종목군/피해 종목군 연결

### 있으면 추가
- `channel_inventory_signal`
- `customer_budget_signal`
- `capex_cycle_signal`
- `global_vs_local_split`

## 8) source tier별 추출 우선순위
### official
- 사실관계, 일정, 수치, 경영진 발언, 가이던스 변경을 최우선 추출
- 해석보다 확인 가능한 statement 우선

### professional
- 산업 구조 해석, 경쟁 비교, 추정치 변화, variant view를 우선 추출
- 단, 근거 없는 narrative는 축소

### independent
- 독창적 해석, 현장감 있는 variant view를 추출
- official/professional corroboration 여부를 함께 기록

### field_signal
- 고객/사용자/채널/개발자 반응을 보조 증거로 추출
- 단독 채택 금지, 가능하면 상위 tier와 연결

## 9) source 충돌 처리 규칙
- 사실 충돌: `official` 우선
- 해석 충돌: `professional`과 `independent` 병기 가능
- field_signal은 단독 결론 근거로 승격하지 않는다
- 충돌이 남으면 `unresolved_conflict=true`로 표시하고 메인 검수 대상으로 올린다

## 10) 금지 추출
아래는 추출하지 않거나 low-value로 버린다.
- 단순 주가 반응 요약
- 출처 없는 과장 표현
- 반복 boilerplate
- 문서 전체 요약만 있고 actionable claim 없는 경우
- entity/industry 연결 없는 일반론
- Stage4/Stage6 성격의 최종 투자판단 문구

## 11) 최소 출력 계약 (draft)
```json
{
  "document_id": "string",
  "focus_entity_type": "stock|industry",
  "focus_entity_id": "string",
  "source_type": "report|blog|premium|filing|ir|transcript|conference|trade_pub|field_signal",
  "source_tier": "official|professional|independent|field_signal",
  "primary_claim": "string",
  "supporting_claims": ["string"],
  "evidence": [{"text": "string", "locator": "string"}],
  "risk": ["string"],
  "counterpoint": ["string"],
  "time_horizon": "short|medium|long",
  "novelty": "low|medium|high",
  "stock_industry_link": ["string"],
  "source_reliability_note": "string",
  "source_refs": ["string"],
  "unresolved_conflict": false
}
```

## 12) 운영 원칙
- 서브에이전트는 문서를 읽고 본 rubric대로 초안을 생성한다.
- 메인은 샘플 검수, source 충돌 판정, rubric 수정만 담당한다.
- 단순 적재/정리/재실행은 서브에이전트에 위임한다.
- 기존 소스를 직접 수정하고 legacy path/compat wrapper는 만들지 않는다.

## 13) 다음 단계
1. 본 DRAFT를 Stage3 canonical rulebook에 반영할 최소 필드셋 확정
2. Stage3-B DB schema 초안 작성
3. 서브에이전트용 prompt/template 작성
4. 샘플 문서 20~30건으로 extraction 품질 검수
