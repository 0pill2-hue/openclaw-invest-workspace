# stage05_qual_brainstorm_density_v3_12_kr

## inputs
- `invest/results/validated/stage05_baselines_v3_11_kr.json`
- `invest/data/raw/text/blog/**/*.md`
- `invest/data/raw/text/telegram/*.md`
- `invest/data/raw/kr/ohlcv/*.csv`
- `invest/data/raw/kr/supply/*_supply.csv`
- `invest/docs/strategy/RULEBOOK_V3.md` (V3.5 + v3_13 종료조건 반영)

## run_command(or process)
- `python3 invest/scripts/stage05_density_repeat_v3_12_kr.py | tee invest/reports/stage_updates/logs/stage05_density_repeat_v3_12_kr.log`

## outputs
- `invest/reports/stage_updates/stage05/stage05_qual_brainstorm_density_v3_12_kr.md`
- `invest/results/validated/stage05_baselines_v3_12_kr.json`
- `invest/reports/stage_updates/stage05/stage05_result_v3_12_kr.md`

## quality_gates
- RULEBOOK V3.5 하드룰 유지(보유1~6/20거래일/+15%/월30%): PASS
- KRX only: PASS
- external_proxy 비교군 전용: PASS
- numeric 단독 자동채택 금지 유지: PASS
- 반복 종료 조건 적용: `baseline_internal_best_id != numeric`
- round 보고에 `repeat_counter` 필수: PASS

## failure_policy
- `repeat_counter` 누락/역행 시 `FAIL_STOP`
- `baseline_internal_best_id == numeric`면 자동 다음 라운드 반복
- `changed_params/why/proof` 누락 라운드는 무효 처리

## proof
- `invest/scripts/stage05_density_repeat_v3_12_kr.py`
- `invest/reports/stage_updates/logs/stage05_density_repeat_v3_12_kr.log`
- `invest/results/validated/stage05_baselines_v3_12_kr.json`
- `invest/docs/strategy/RULEBOOK_V3.md`

---

## A) 브레인스토밍 옵션

### 옵션 1) 연도별 데이터 밀도 가중치 적용
- 핵심: `year_density = w_blog*blog_norm + w_tg*tg_norm`를 정성 점수 multiplier로 사용
- 기대효과: 텍스트 밀도 낮은 연도(초기 구간)에서 과신호 완화
- 부작용: 저밀도 구간에서 기회주 포착이 느려질 수 있음
- 검증방법:
  - 연도별 `density_coverage_summary` 생성
  - 저밀도 연도에서 qual turnover 감소/성과 안정성 확인

### 옵션 2) 블로그 우선 / 텔레 보조 재가중
- 핵심: 텍스트 출처 가중치를 `blog > telegram`으로 설정
- 기대효과: 표본 수가 많은 blog 기반으로 밀도 추정 분산 축소
- 부작용: 2026처럼 telegram 밀도 급증 구간의 민감도 저하 가능
- 검증방법:
  - `blog_weight` 변화에 따른 qual/hybrid 연도별 성과 비교
  - 2025~2026 구간 성과 드리프트 확인

### 옵션 3) 정성 신호 시차 정렬 + 노이즈 컷 강화
- 핵심: 신호를 `lag_days`만큼 지연 정렬하고, `noise_w`로 과민반응 감산
- 기대효과: 신호-가격 체결 시점 mismatch 완화, 스파이크 노이즈 억제
- 부작용: 급등 초입 진입 지연 가능
- 검증방법:
  - lag/noise 파라미터 라운드별 성과 비교
  - gap(qual-hybrid vs numeric) 축소 여부 확인

### 옵션 4) 저밀도 구간 정성 영향 제한
- 핵심: `low_density_threshold` 미만 연도에 `low_density_scale` 적용
- 기대효과: 데이터 공백기에서 정성 과적합 차단
- 부작용: 초기 구간 수익 탄력 둔화
- 검증방법:
  - 저밀도 연도 drawdown/turnover 변화 확인
  - 전체 CAGR 저하 여부 확인

---

## B) 최종 채택안 (chosen)

### chosen
**옵션 3 + 옵션 4 혼합안** (시차 정렬 + 노이즈 컷 + 저밀도 영향 제한)
- 보조로 옵션 2의 출처 재가중(blog 우선)을 적용
- 반복 종료 조건(사용자 확정): `baseline_internal_best_id != numeric`

### why
- 단순 가중치 조정(옵션1/2 단독)만으로는 numeric 대비 격차 축소 폭이 제한적
- 실제 약점 원인 가설(시차/노이즈)을 직접 제어하는 옵션3이 핵심
- 저밀도 연도 과신호를 차단하려면 옵션4가 반드시 필요

### rejected
1. **옵션1 단독**
   - 이유: 밀도만 반영하면 시차/노이즈 문제를 해결하지 못함
2. **옵션2 단독**
   - 이유: 소스 가중치 재배분만으로 성능 구조 개선이 작음
3. **옵션3 단독**
   - 이유: 저밀도 구간의 근본적 데이터 공백 리스크가 남음

### risks
- 시차 강화 시 급등 초기 missed-entry 리스크
- 저밀도 스케일 다운이 강하면 2016~2020 구간 기회손실 가능
- 반복 종료를 위해 hybrid가 numeric 동치로 수렴하는 경우, 해석 시 tie-break 사유를 명확히 기록해야 함

### next
- Stage06 진입 전, tie-break 기반 종료 라운드의 재현성(동일 입력/동일 결과) 1회 추가 확인
- Stage06 후보 확장에서 `density_pow / lag_days / noise_w` 축을 독립 실험으로 분리
