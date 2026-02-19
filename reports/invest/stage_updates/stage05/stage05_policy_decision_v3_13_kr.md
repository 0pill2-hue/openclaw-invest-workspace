# stage05_policy_decision_v3_13_kr

## inputs
- 정책 기준 문서: `docs/invest/strategy/RULEBOOK_V3.md`
- 기존 Stage05 운영 결과: `reports/stage_updates/stage05/stage05_result_v3_7_kr.md`
- 고정 제약:
  - RULEBOOK 기존 하드룰 유지(보유 1~6 / 최소보유 20일 / 교체 +15% / 월교체 30% / trailing -20% 등)
  - KRX only
  - `external_proxy` 비교군 전용
  - 임의규칙 금지

## run_command(or process)
- 정책 결정/문서화 작업 (코드 실행 없음)

## outputs
- `reports/stage_updates/stage05/stage05_policy_decision_v3_13_kr.md`
- `(수정) docs/invest/strategy/RULEBOOK_V3.md`

## quality_gates
- numeric 1위 최종 채택 금지 하드게이트 문서 반영: PASS
- Stage05 종료조건(운영 stop rule) 명문화: PASS
- `repeat_counter` 유지 규칙 반영: PASS
- `stage05_result` 보고서 `stop_reason` 필수화 반영: PASS
- KRX only / external_proxy 비교군 전용 유지: PASS

## failure_policy
- numeric 1위 결과를 ADOPT로 표기 시 즉시 `FAIL_STOP`
- `stop_reason` 누락 시 결과 등급 `DRAFT` 강등
- `repeat_counter` 역행/누락 또는 max_repeat 우회 시 `FAIL_STOP`

## proof
- `docs/invest/strategy/RULEBOOK_V3.md` (Rule 6-3, Rule 6-4)
- `reports/stage_updates/stage05/stage05_policy_decision_v3_13_kr.md`

---

## 1) 옵션 3개 브레인스토밍

### A. strict
- 규칙: `numeric` 1위 금지 + 무기한 반복
- 개념: non-numeric(qual/hybrid) 1위가 나올 때까지 반복 실행

### B. balanced
- 규칙: `numeric` 1위 금지 + 개선 정체 시 중단
- 개념: non-numeric 개선폭(예: best_non_numeric delta) 정체가 누적되면 중단

### C. pragmatic
- 규칙: `numeric` 1위 금지 + 최대 라운드 도달 시 종료 + 재설계 전환
- 개념: 반복 상한을 명시하고, 미달성 시 무한 튜닝 대신 파라미터 축/설계 자체를 재구성

---

## 2) 옵션 비교 (과적합/시간/재현성/성능)

| 옵션 | 과적합 리스크 | 시간 비용 | 재현성 | 성능 잠재력 | 총평 |
|---|---|---|---|---|---|
| A. strict | 높음 (무기한 반복으로 탐색 과열) | 매우 큼/무한 | 낮음 (종료시점 비결정적) | 이론상 높음 | 운영 리스크 과다 |
| B. balanced | 중간 (정체 감지로 과열 완화) | 중간 | 중간~높음 (정체 기준 정의 필요) | 높음 | 합리적이나 경계값 민감 |
| C. pragmatic | 낮음~중간 (반복 상한으로 과열 억제) | 예측 가능/제한적 | 높음 (repeat_counter로 결정적 종료) | 중간~높음 (재설계로 다음 사이클 품질 확보) | 운영/거버넌스 최적 |

핵심 해석:
- A는 성능 극대화 가능성이 있어도 운영 통제 실패 가능성이 큼.
- B는 좋은 절충안이지만, 정체 임계치 정의에 따라 논쟁/재현성 이슈가 남음.
- C는 종료 조건이 명확하고 감사가능성이 높아, 현재 “numeric 1위 강제 차단” 정책과 가장 일관됨.

---

## 3) 최종 채택안

## 채택: **C. pragmatic**

채택 근거:
1. **거버넌스 일치성**: numeric 1위 결과를 최종 채택 금지하는 하드게이트와 충돌 없이 동작.
2. **운영 통제성**: `repeat_counter` + `max_repeat`로 종료 시점이 명확.
3. **재현성/감사성**: 동일 입력에서 동일 종료 조건 재현 가능 (`stop_reason` 강제 기록).
4. **품질 유지 전략**: 무의미 반복 대신 재설계 전환으로 탐색 축을 바꿔 과적합 위험 완화.

확정 운영 파라미터:
- `max_repeat = 3` (Stage05 표준 3라운드 운용과 정합)
- 종료 사유(`stop_reason`)는 아래 2개만 허용:
  - `NON_NUMERIC_TOP_CONFIRMED`
  - `MAX_REPEAT_REACHED_REDESIGN`

---

## 4) 실행 규칙 반영(확정)

1. `repeat_counter`는 라운드마다 +1, 누락/역행 금지.
2. `stage05_result*.md`에는 `stop_reason` 필수(공백 금지).
3. `baseline_internal_best_id == numeric`이면 `final_decision`은 `HOLD` 또는 `REDESIGN`만 허용(`ADOPT` 금지).
4. `external_proxy`는 계속 비교군 전용(선발/게이트 제외).
5. KRX only 범위 유지.

---

## 5) next
- Stage05 후속 실행 결과 보고서 템플릿에 `repeat_counter`, `stop_reason`, `final_decision` 필드 고정.
- max_repeat 도달 시 Stage06 강행이 아니라, 먼저 Stage05 재설계 문서(`why/changed_axis/expected_risk`) 생성 후 다음 사이클로 진입.