# stage06_brainstorm_plan_v5_kr

## inputs
- Stage05 3x3 결과(JSON): `/Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`
- Stage06 v4 계획/결과: 
  - `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage06/stage06_brainstorm_plan_v4_kr.md`
  - `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage06/stage06_candidates_v4_kr.md`
- RULEBOOK V3.5/V3.4 하드 규칙 고정:
  - 보유 1~6, 최소보유 20일, 교체 +15%, 월교체 30%, trailing_stop=-20%
- 고정 운영 제약:
  - KRX only
  - external_proxy 선발 제외
  - 임의 규칙 추가 금지
  - changed_params 의무 기록 + ping-pong 금지

---

## A) 왜 72(24/24/24)인가

### 목적 재정의
- v4(12개)는 **탐색 시동용**으로는 충분했으나, 변수 영향(lookback/flow/qual/hybrid/fee)의 상호작용 분석에는 표본이 부족함.
- v5는 Stage06에서 바로 **확장 탐색 + 변수 민감도 강화**를 동시에 수행하기 위해 72로 확대.

### 후보안 비교 (비용-성능 tradeoff)
- 비용 proxy = `후보 수 × universe_size(120) × rebalance_points(122)`

| plan_id | 후보 수 | 트랙 분배 | 비용 proxy | 비용배수(vs 12안) | 탐색폭 | 판정 |
|---|---:|---|---:|---:|---|---|
| compact_12 | 12 | 4/4/4 | 175,680 | 1.0x | 낮음 (축간 상호작용 표본 부족) | **기각** |
| **expanded_72** | **72** | **24/24/24** | **1,054,080** | **6.0x** | **중~고 (축별 grid + 교차조합 확보)** | **채택** |
| max_180 | 180 | 60/60/60 | 2,635,200 | 15.0x | 매우 높음 | **기각** |

### 채택 근거 (72)
1) **통계적 탐색폭 확보:** 3개 트랙 각각 24개로 구성하면 단일 축 튜닝이 아닌 교차축(예: momentum×flow×fee, weight×window×fee) 비교가 가능
2) **비용 관리 가능 구간:** 12 대비 6배 증가지만, 180 대비 40% 수준의 연산량으로 품질/속도 균형 유지
3) **후속 단계 연결성:** Stage07 컷오프 시 충분한 후보 다양성을 제공하여 과조기 탈락 리스크 완화

### 기각안 사유
- **12안 기각:**
  - v4에서 이미 확인한 한계(탐색밀도 부족)
  - 변수 영향도(corr, 민감도) 해석 시 표본 수 제약 큼
- **180안 기각:**
  - Stage06 라운드에서 계산비용 및 검증 리드타임 과다
  - 과탐색으로 인한 노이즈 적합 위험 증가

---

## B) 트랙별 설계 원칙 (24/24/24)

### numeric 24
- 6개 momentum profile × 4개 flow profile = 24
- fee cycle 동시 부여로 비용 스트레스/완화 국면까지 포함
- 핵심 축: `ret_short/ret_mid/trend_fast/trend_slow/flow_scale/quant_*_w/fee`

### qualitative 24
- 6개 weight mix × 4개 window profile = 24
- 이벤트 반응(buzz)과 지속성(up_ratio) 균형 점검
- 핵심 축: `qual_*_w/buzz_window/up_window/fee`

### hybrid 24
- 6개 blend profile × 4개 support profile = 24
- hybrid 가중 + quant/qual 보조신호 동시 조정
- 핵심 축: `hybrid_*_w/quant_*_w/qual_up_w/fee`

---

## C) 규칙/게이트 설계

### 하드 규칙 고정 (변경 금지)
- `max_pos=6`
- `min_hold_days=20`
- `replace_edge=0.15`
- `monthly_replace_cap=0.30`
- `trailing_stop_pct=-0.20`

### quality gates
1) 후보 수 정확성: 총 72개
2) 트랙 분배 정확성: 24/24/24
3) changed_params 비어있음 금지
4) changed_params duplicate/ping-pong 패턴 금지
5) external_proxy 선발 제외
6) RULEBOOK V3.5/V3.4 하드 제약 전량 통과
7) `new_selection_gate` 명시(= numeric 단독 1등 즉시 채택 금지)

### new_selection_gate (연계 규칙)
- policy_id: `anti_numeric_monopoly_gate_v1`
- 최종 채택 허용:
  - (a) hybrid/qualitative가 numeric total_return 추월
  - (b) 수익률 근접 + MDD 우위 + turnover 우위 동시 충족
- Stage06 보고서에는 정책을 선언하고, Stage07/09에서 실제 채택 판정으로 강제

---

## run_command(or process)
- `python3 invest/scripts/stage06_candidates_v5_kr.py`

## outputs
- `/Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v5_kr.json`
- `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage06/stage06_candidates_v5_kr.md`
- `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage06/stage06_crosscheck_v5_kr.md`

## failure_policy
- Stage05 seed 누락/비검증(VALIDATED 아님) 시 FAIL_STOP
- 72개/24-24-24 불일치 시 FAIL_STOP
- 하드 규칙 파라미터 위반 시 FAIL_STOP
- changed_params 중복 또는 ping-pong 탐지 시 FAIL_STOP
- external_proxy가 선발 후보로 유입되면 FAIL_STOP

## proof
- `/Users/jobiseu/.openclaw/workspace/invest/scripts/stage06_candidates_v5_kr.py`
- `/Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v5_kr.json`
