# stage05_brainstorm_decision_v3_7_kr

## inputs
- prior baseline: `invest/results/validated/stage05_baselines_v3_6_kr_r03.json`
- fixed constraints: Rulebook hold 1~6 / min_hold 20d / replace +15% / monthly_replace_cap 30%
- scope: KRX only, `external_proxy` comparison-only
- user update: `numeric freeze`, `numeric guard(-5%)`, `qual/hybrid only tuning`

## run_command(or process)
- `python3 invest/scripts/stage05_tuning_loop_v3_7_kr.py`

## outputs
- `invest/results/validated/stage05_baselines_v3_7_kr.json`
- `reports/stage_updates/stage05/stage05_brainstorm_decision_v3_7_kr.md`

## quality_gates
- numeric_locked=true: PASS
- numeric_guard(current >= locked*0.95): PASS
- KRX only hard guard: PASS
- external_proxy 비교군 전용: PASS
- changed_params non-empty (ping-pong 방지): PASS

## failure_policy
- numeric_guard FAIL 시 해당 라운드 즉시 FAIL
- changed_params 비어있으면 해당 라운드 FAIL
- 내부 3000% 게이트 FAIL 시 Stage06 진입 금지

## proof
- `invest/results/validated/stage05_baselines_v3_7_kr.json`
- `invest/scripts/stage05_tuning_loop_v3_7_kr.py`
- `invest/docs/strategy/RULEBOOK_V3.md`

---

## 1) 브레인스토밍 (관점 분리 3개)

### A. 안정성 관점 (리스크/턴오버)
- 아이디어: numeric는 잠그고, qualitative의 과민 반응(buzz 과가중)을 완화해 hybrid의 변동을 줄인다.
- 파라미터 방향:
  - `qual_buzz_w` 소폭 하향
  - `qual_ret_w` 소폭 상향
  - hybrid는 50:50 유지(구조 안정)
- 기대효과: numeric 훼손 없이 hybrid 하방 완화, 분포 쏠림 완화.

### B. 수익 극대화 관점 (3000% 목표)
- 아이디어: qual 반응도 강화(`qual_buzz_w`↑)로 급등 포착률을 높인다.
- 파라미터 방향:
  - `qual_buzz_w` 상향, `qual_ret_w` 하향
- 기대효과: qualitative 단독 수익 상향 가능.
- 리스크: hybrid 품질 저하 가능성(실측에서 확인됨).

### C. 정성결합 관점 (qual signal 게이트/융합)
- 아이디어: qual 신호의 노이즈를 줄이고 hybrid의 안정성을 우선한다.
- 파라미터 방향:
  - `qual_buzz_w` 0.80→0.78
  - `qual_ret_w` 0.20→0.21
  - hybrid 50:50 고정
- 기대효과: qualitative 성과 유지 + hybrid 개선.

---

## 2) 의사결정

### 채택안 (Adopted)
- `r02_qh_tune`
- 이유:
  - numeric_guard PASS 유지
  - qualitative 성과 유지(잠금기준 대비 보전)
  - hybrid 성과 상승(잠금기준 대비 +0.2159)
  - 극단적 단일 numeric 쏠림 지표 일부 완화(best/second 8.91 → 6.64)

### 백업안 (Backup)
- `r03_qh_tune`
- 이유:
  - numeric_guard PASS
  - qualitative 유지, hybrid도 잠금기준 대비 +0.1533로 개선
  - 채택안 대비 개선 폭이 작아 2순위

---

## 3) changed_params (직전 대비 / 직전2라운드 대비)

### (a) v3_6_kr_r03 -> v3_7_kr adopted
- 고정(LOCK):
  - `universe_limit=180, max_pos=5, min_hold_days=20, replace_edge=0.15, monthly_replace_cap=0.30`
  - `trend_span_fast=8, trend_span_slow=36, ret_short=10, ret_mid=40, flow_scale=1.2e8, fee=0.003`
- 변경(qual/hybrid only):
  - `qual_buzz_w: 0.80 -> 0.78`
  - `qual_ret_w: 0.20 -> 0.21`

### (b) ping-pong 금지 관점(직전 2라운드와의 실질 차별)
- v3_6 r02/r03은 글로벌 파라미터(유니버스/모멘텀/max_pos) 중심 조정
- v3_7은 **numeric freeze + q/h 전용 조정**으로 탐색 축 자체를 변경
- 즉, 동일 축 왕복이 아니라 운영 체계를 전환한 변경

### (c) v3_7 내부 라운드 변경
- r01 -> r02
  - `qual_buzz_w: 0.82 -> 0.78`
  - `qual_ret_w: 0.18 -> 0.21`
- r02 -> r03
  - `qual_buzz_w: 0.78 -> 0.76`
  - `qual_ret_w: 0.21 -> 0.20`

---

## 4) why
- numeric는 이미 3000% 초과 성능(4008.66%)을 확보했으므로 훼손 금지가 최우선.
- 따라서 numeric를 고정하고 qualitative/hybrid만 조정해 내부 3종 품질 일관성 개선을 시도.
- 결과적으로 numeric 보전 + hybrid 개선이라는 목표를 충족.

## 5) next
- Stage06 진입 가능(내부 3000% gate PASS 유지).
- 다만 분포 쏠림(one_sided_skew_flag=true)은 잔존하므로,
  - Stage06에서는 `qual/hybrid seed` 확장 비중을 높여 분포 균형 추가 검증 권장.
