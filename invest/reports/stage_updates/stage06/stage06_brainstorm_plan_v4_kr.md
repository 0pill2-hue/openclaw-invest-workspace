# stage06_brainstorm_plan_v4_kr

## inputs
- Stage05 3x3 결과(JSON): `/Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`
- Stage05 설계 리포트: `/Users/jobiseu/.openclaw/workspace/reports/stage_updates/stage05/stage05_3x3_design_v3_9_kr.md`
- Stage05 결과 리포트: `/Users/jobiseu/.openclaw/workspace/reports/stage_updates/stage05/stage05_3x3_result_v3_9_kr.md`
- RULEBOOK 기준: 보유 1~6, 최소보유 20일, 교체 +15%, 월교체 30%, KRX only, external_proxy 선발 제외

---

## A) 브레인스토밍 1 — Stage06 모델 확장 전략

### 관찰 근거 (Stage05 파일 기반)
- Stage05 내부 9개 모델의 total_return 범위: **1.7605 ~ 45.3883**
- track별 최고값:
  - numeric: **25.2883** (`numeric_n2_flow_tilt`)
  - qualitative: **17.5563** (`qual_q3_fee_stress`)
  - hybrid: **45.3883** (`hybrid_h2_consensus_tilt`)
- 입력 스케일: universe_size=120, rebalance_points=122

### 후보안 비교 (3x3 seed 확장)
| plan_id | 후보 수 | 트랙 분배 | 계산비용 proxy (후보수×120×122) | 비용배수(vs 최소안) | 성능개선 기대 | 판단 |
|---|---:|---|---:|---:|---|---|
| minimal_9 | 9 | 3/3/3 | 131,760 | 1.00x | 낮음~중간 (seed 주변 좁은 탐색) | 기각 |
| **medium_12** | **12** | **4/4/4** | **175,680** | **1.33x** | **중간~높음 (seed 유지 + 외부아이디어 이식 폭 확보)** | **채택** |
| extended_18 | 18 | 6/6/6 | 263,520 | 2.00x | 높음(탐색폭 큼) | 기각 |

### chosen_plan
- **plan_id:** `medium_12`
- **선택 이유:**
  1) 최소안 대비 탐색 폭을 늘리되(12), 비용 증가를 1.33x로 제한
  2) numeric/qualitative/hybrid를 4개씩 대칭 확장해 한쪽 과최적화 위험 완화
  3) external 아이디어(시계열/앙상블/리스크) 이식 실험을 각 트랙에 최소 1개 이상 배치 가능

### rejected_plan
- `minimal_9` 기각 사유:
  - Stage05 변동폭(1.7605~45.3883)이 큰데 9개는 탐색이 너무 협소
  - 외부 아이디어 이식 슬롯이 제한돼 후보 다양성 부족
- `extended_18` 기각 사유:
  - 비용 2.0x 증가 대비 Stage06 1차 라운드에서 과탐색 위험
  - 검증/리포팅 반복 시간 증가로 의사결정 지연 가능

---

## B) 브레인스토밍 2 — 외부 상위권 계열 아이디어 도입 목록

## external_ideas
| 아이디어 | 계열 | direct model 사용 | 아이디어 이식(운용 레이어) | Stage06 반영 | 비고 |
|---|---|---|---|---|---|
| Time-series momentum lookback tuning | 시계열 | N/A | O | O | ret_short/ret_mid/trend span 조정 |
| Flow tilt + cross-sectional balancing | 앙상블/시계열 | N/A | O | O | quant_trend_w vs quant_flow_w 재가중 |
| Rank/consensus ensemble weighting | 앙상블 | N/A | O | O | hybrid_agree_w 중심 합의항 보강 |
| Sentiment smoothing (buzz window 확장) | 리스크관리/정성 | N/A | O | O | buzz_window 확장으로 노이즈 완화 |
| Cost-aware execution proxy | 리스크관리 | N/A | O | O | fee stress/relief로 회전비용 민감도 반영 |

- direct model 사용을 N/A로 둔 이유:
  - 이번 Stage06의 목적은 **외부 모델 “직접 도입”이 아니라 아이디어 이식형 후보 확장**
  - RULEBOOK 고정 제약(보유/교체/최소보유/월교체)과 충돌 없이 운영 레이어만 조정하기 위함

## compatibility
| 항목 | KRX 호환 | RULEBOOK V3.4 호환 | external_proxy 규칙 호환 | 판정 |
|---|---|---|---|---|
| 시계열 lookback 조정 | O | O (하드 규칙 미변경) | O | PASS |
| flow 가중 재조정 | O | O | O | PASS |
| hybrid 합의항 조정 | O | O | O | PASS |
| sentiment smoothing | O | O | O | PASS |
| cost-aware proxy(fee 파라미터) | O | O | O | PASS |

---

## changed_params_policy
1) Stage06 후보는 모두 `changed_params`를 **명시**한다(빈 값 금지).
2) RULEBOOK 하드 파라미터(`max_pos=6`, `min_hold_days=20`, `replace_edge=0.15`, `monthly_replace_cap=0.30`, `trailing_stop_pct=-0.20`)는 **변경 금지**.
3) 트랙별 후보는 동일 축 ping-pong(되돌리기) 반복을 피하도록, 각 후보의 변경 목적을 `why`에 명시한다.
4) `external_proxy`는 비교군 전용이며 Stage06 후보 선발 목록에 포함하지 않는다.
5) 재실행 시 버전을 올리고(`v4 -> v4.x or v5`) 변경 축/사유를 문서에 누적 기록한다.

---

## run_command(or process)
- `python3 invest/scripts/stage06_candidates_v4_kr.py`

## outputs
- `/Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v4_kr.json`
- `/Users/jobiseu/.openclaw/workspace/reports/stage_updates/stage06/stage06_candidates_v4_kr.md`

## proof
- `/Users/jobiseu/.openclaw/workspace/invest/scripts/stage06_candidates_v4_kr.py`
- `/Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v4_kr.json`
