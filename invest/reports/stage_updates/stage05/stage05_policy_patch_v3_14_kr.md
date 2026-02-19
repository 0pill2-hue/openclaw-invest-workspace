# stage05_policy_patch_v3_14_kr

## inputs
- 사용자 정책 업데이트(10:10): 기존 "정성 50% 하드고정" 폐기, **B + C 채택**
- 기존 Stage05 정책: `reports/stage_updates/stage05/stage05_policy_decision_v3_13_kr.md`
- 구현 대상 스크립트: `invest/scripts/stage05_rerun_v3_14_kr.py`

## outputs
- `invest/scripts/stage05_rerun_v3_14_kr.py` (정책 반영 실행기)
- `invest/results/validated/stage05_baselines_v3_14_kr.json`
- `reports/stage_updates/stage05/stage05_result_v3_14_kr.md`

## quality_gates
- Gate1/2 정책이 코드 및 결과 JSON에 모두 기록됨: PASS
- hybrid_qual_mix_ratio, regime band, gate1/gate2 필드 보고서 반영: PASS
- repeat_counter 이어서 기록 + stop_reason 필수: PASS

## failure_policy
- `hybrid_qual_mix_ratio < 0.35` 또는 `> 0.60`: FAIL 라운드
- `hybrid_qual_w < 0.10` 또는 `hybrid_agree_w < 0.05`: FAIL 라운드
- Gate2 미충족 시 non-numeric ADOPT 금지

## proof
- code: `invest/scripts/stage05_rerun_v3_14_kr.py`
- json: `invest/results/validated/stage05_baselines_v3_14_kr.json`
- report: `reports/stage_updates/stage05/stage05_result_v3_14_kr.md`

---

## 정책 변경 요약

### (교체 전) 폐기 규칙
- "hybrid 정성비중 50% 하드고정" (`hybrid_qual_w + hybrid_agree_w >= 0.50`, `hybrid_quant_w <= 0.50`)

### (교체 후) 채택안 = B + C

## B) Gate1: hybrid 정성비중 동적밴드
- base band: `hybrid_qual_w + hybrid_agree_w in [0.35, 0.60]`
- 저밀도/고노이즈 구간: 하단(>=0.35) 허용
- 고밀도/저노이즈 구간: 상단(>=0.50) 권장
- 하드금지: `mix_ratio < 0.35` => FAIL

구현 보강(기존 지시 유지):
- `hybrid_qual_w >= 0.10`
- `hybrid_agree_w >= 0.05`

## C) Gate2: non-numeric 채택 2계층 조건
아래 중 하나를 만족해야 ADOPT 가능:
1. (i) `non_numeric_return >= numeric_return + epsilon(0.005)`
2. (ii) `|non_numeric_return - numeric_return| <= 0.005` 이면서 `MDD/turnover 동시 우위`

---

## 구현 포인트
- Gate1 계산 필드:
  - `hybrid_qual_mix_ratio`
  - `regime` / `regime_band(min,max,recommended_min)`
  - `gate1_pass`, `gate1_recommended_pass`, `gate1_fail_reason`
- Gate2 계산 필드:
  - `gate2_pass`, `gate2_reason`
  - `gate2_condition_i`, `gate2_condition_ii`
  - `non_numeric_candidate`, `non_numeric_return`
- 안전 필드:
  - `tie_detected`, `clone_detected`, `non_numeric_top_valid`

---

## 최종 반영 상태
- v3_14 실행에서 Gate1은 통과했으나 Gate2 불충족으로 `final_decision=REDESIGN`
- 정책 문서/결과 필수 필드 반영 완료
