# stage05_density_adaptive_brainstorm_v3_16_kr

## inputs
- `invest/results/validated/stage05_baselines_v3_12_kr.json`
- `invest/results/validated/stage05_baselines_v3_14_kr.json`
- `scripts/stage05_rerun_v3_15_kr.py`
- `invest/config/stage05_auto_capture_v3_15_kr.yaml`
- 사용자 추가 하드조건 (high-density advantage gate 강화: +0.25, MDD, turnover)

## run_command(or process)
- 브레인스토밍/정책 설계 문서화 (코드 실행 없음)

## outputs
- `reports/stage_updates/stage05/stage05_density_adaptive_brainstorm_v3_16_kr.md`
- (후속 적용) `scripts/stage05_rerun_v3_16_kr.py`, `invest/config/stage05_auto_capture_v3_16_kr.yaml`

## quality_gates
- density band 3단계 이상 제안: PASS (`low/mid/high`)
- band별 qualitative/hybrid 평가 방식 포함: PASS
- 옵션 3개 비교 + 채택안 1개: PASS
- RULEBOOK 하드룰(보유1~6/20일/+15%/월30) 변경 없음: PASS

## failure_policy
- band 정의가 3단계 미만이면 `FAIL_STOP`
- high-density gate 조건(+0.25/MDD/turnover) 누락 시 `FAIL_STOP`
- KRX only / external_proxy 비교군 전용 위반 시 `FAIL_STOP`

## proof
- 본 문서 `A/B/C/D/E` 섹션
- 후속 반영 코드: `scripts/stage05_rerun_v3_16_kr.py`

---

## A) 옵션 3개

### 옵션 1) Density-Scaled Qual Only
- 아이디어: density가 낮을수록 qualitative 점수만 스케일 다운, high에서만 스케일 업
- qualitative:
  - low: `qual_scale↓`, `noise_penalty↑`, `lag+`
  - high: `qual_scale↑`, `noise_penalty↓`
- hybrid:
  - 기존 비율 고정(밴드별 변경 없음)
- 장점: 구현 단순, 기존 로직 침습 적음
- 단점: hybrid 결합 자체가 density 반응하지 않아 개선폭 제한

### 옵션 2) Band-specific Hybrid Mix Gate Only
- 아이디어: low/mid/high별 `hybrid_qual_mix_ratio` 허용구간을 다르게 적용
- qualitative:
  - 기존 수식 유지
- hybrid:
  - low: qual mix 하단 허용
  - high: qual mix 상단 강제
- 장점: 정책 설명 명확
- 단점: 점수 생성 단계(qual 신호 품질/노이즈/시차)가 그대로라 근본 개선 약함

### 옵션 3) **Band-adaptive Scoring + Band-adaptive Hybrid + High-density OOS Advantage Gate**
- 아이디어: 점수 생성과 결합, 최종 채택게이트를 모두 밀도 밴드 기준으로 일관 적용
- qualitative (밴드별):
  - low: `lag 추가`, `buzz/ret/up multiplier 감소`, `anchor 소폭 증가`, `qual_scale↓`, `noise_mult↑`
  - mid: 중립(1.0)
  - high: `lag 축소`, `buzz/ret/up multiplier 증가`, `qual_scale↑`, `noise_mult↓`
- hybrid (밴드별):
  - low: `quant_mult↑`, `qual/agree_mult↓`
  - mid: 중립
  - high: `quant_mult↓`, `qual/agree_mult↑`
- 게이트:
  - high-density OOS에서 `(qual or hybrid)`가 `numeric + 0.25` 이상 + `MDD(abs) <= numeric` + `turnover <= numeric*1.05`
- 장점: 신호 생성/결합/최종판정이 같은 철학으로 정렬
- 단점: 구현 복잡도 상승, 서브기간 안정성 미통과 가능성 증가

---

## B) chosen / rejected

### chosen
- **옵션 3 채택**

### rejected
1. 옵션1 reject
   - 이유: hybrid 결합이 band 반응을 못해 non-numeric 선발 개선이 제한적
2. 옵션2 reject
   - 이유: 게이트만 강화하면 실제 신호 품질(시차/노이즈/밀도 불균형) 개선이 부족

---

## C) density_bands
- low: `density < 0.35`
- mid: `0.35 <= density < 0.65`
- high: `density >= 0.65`

---

## D) eval_policy_by_band

### low band
- qualitative:
  - `qual_lag_extra_days=+2`
  - `qual_buzz/ret/up_mult` 하향
  - `qual_anchor_mult` 상향
  - `qual_scale` 하향
  - `noise_mult` 상향
- hybrid:
  - `hybrid_quant_mult` 상향
  - `hybrid_qual/agree_mult` 하향
  - 추천 mix 하한은 낮게 허용

### mid band
- qualitative/hybrid 모두 중립 (multiplier 1.0)

### high band
- qualitative:
  - `qual_lag_extra_days=0`
  - `qual_buzz/ret/up_mult` 상향
  - `qual_scale` 상향
  - `noise_mult` 하향
- hybrid:
  - `hybrid_qual/agree_mult` 상향
  - `hybrid_quant_mult` 하향
  - 추천 mix 하한 상향
- **추가 하드 게이트**:
  - OOS high-density에서 `(qual or hybrid)`가 아래 모두 충족해야 PASS
    - `return >= numeric + 0.25`
    - `abs(mdd) <= abs(numeric_mdd)`
    - `turnover_proxy <= numeric_turnover_proxy * 1.05`

---

## E) risks
- low band 과억제로 초반 기회손실 가능
- high band 강화 시 특정 구간 과최적화 위험
- 게이트 강화(+0.25)로 ADOPT 문턱이 높아져 `HOLD/REDESIGN` 빈도 증가 가능

## expected_effect
- 정성 신호의 밀도 편향(저밀도 과신/고밀도 저활용) 완화
- high-density 구간에서 non-numeric 우위의 실질성(수익+리스크+회전) 검증 강화
- tie/형식적 우위가 아닌 구조적 우위만 채택하도록 품질 상향
