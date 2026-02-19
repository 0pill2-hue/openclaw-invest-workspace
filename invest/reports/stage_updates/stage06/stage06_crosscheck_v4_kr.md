# stage06_crosscheck_v4_kr

## inputs
- `/Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v4_kr.json`
- `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage06/stage06_candidates_v4_kr.md`
- `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage06/stage06_brainstorm_plan_v4_kr.md`

## run_command(or process)
- `python3 invest/scripts/stage06_candidates_v4_kr.py`

## outputs
- `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage06/stage06_crosscheck_v4_kr.md`

## quality_gates
- Opus/Sonnet/AgPro 3관점 요약 포함
- 논리/데이터/리스크 관점 분리
- external_proxy 선발 제외 여부 재확인

## failure_policy
- 3관점 중 중대한 FAIL 발견 시 Stage06 결과를 `DRAFT`로 강등하고 재실행
- 데이터 경로 또는 RULEBOOK 고정값 위반 발견 시 즉시 FAIL_STOP

## proof
- `/Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v4_kr.json`
- `/Users/jobiseu/.openclaw/workspace/invest/scripts/stage06_candidates_v4_kr.py`

---

## Opus 관점 (논리)
- 판정: **PASS**
- 근거:
  1) Stage05 track-best seed 3개를 기준으로 Stage06 후보를 확장하는 구조가 일관됨
  2) chosen_plan(12개)와 실제 생성 수(12개)가 일치
  3) external 아이디어는 direct model 도입이 아니라 운용 레이어 이식으로 제한되어 요구사항과 부합

## Sonnet 관점 (데이터/정합성)
- 판정: **PASS**
- 근거:
  1) 입력 파일이 KRX 경로(`invest/data/raw/kr/ohlcv`, `.../supply`)로 고정
  2) 결과 JSON의 quality_gates에서 RULEBOOK 하드값(보유1~6, 최소20일, 교체+15%, 월30%, -20% trailing) 모두 true
  3) external_proxy는 선발 제외로 명시됨(`external_proxy_selection_excluded=true`)

## AgPro 관점 (리스크/실행성)
- 판정: **PASS (조건부 모니터링 권고)**
- 근거:
  1) 후보군의 일부 MDD가 큰 편(예: -0.66~-0.73 구간)으로 Stage07 컷에서 추가 리스크 절단 필요
  2) 비용 민감도 아이디어(fee 조정) 후보가 포함되어 실전 실행성 검증에 유리
  3) 현재 산출물은 후보 생성 단계이므로 최종 채택 전 Stage07/08 리스크 검증 전제가 필요

---

## 종합 결론
- 최종 판정: **PASS (Stage06 범위 내)**
- 다음 단계 권고:
  - Stage07에서 MDD/turnover 기준으로 추가 컷오프
  - Stage08에서 OOS/일관성 검증
  - Stage09에서 최종 교차감사 확정
