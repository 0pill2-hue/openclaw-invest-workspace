status: CANONICAL
updated_at: 2026-02-18 06:00 KST
stage: 05
name: baseline_3track
description: Quant/Text/Hybrid 동일 조건 비교(3검증 1운영 전제)
rule:
  - 운영은 택1(통과 모델 1개만)
  - 미통과 시 4->5 반복

gate_fail_protocol:
  classify:
    - data_failure: 누락/정합성/지연 이슈
    - model_failure: MDD/Sharpe/초과수익 등 성능 미달
    - governance_failure: 등급/리뷰/절차 위반

  actions_by_type:
    data_failure:
      - 2->3 재진입(정제/검증 복구)
      - 복구 후 4->5 재실행
    model_failure:
      - 4->5 집중 반복
      - 1차: MDD 절단(포지션 캡/하드스탑/레짐 게이트)
      - 2차: Sharpe 개선(신호 합의/과매매 억제/회전율 컷)
      - 3차: 비용/턴오버 재점검
    governance_failure:
      - 실행 즉시 중지
      - 문서/리뷰/등급 요건 충족 후 재개

  loop_stop_rules:
    - 동일 처방 2회 연속 개선 없음 -> 처방 축 교체
    - 3회 연속 미통과 -> 관망모드 + 파라미터 재설계
    - Hard Drop 재발 -> 즉시 중지 + 원인 리포트 선행

  report_format:
    - 실패유형(데이터/모델/거버넌스)
    - 막힌 게이트(MDD/Sharpe 등)
    - 이번 처방(최대 3줄)
    - 결과(통과/미통과) + 다음 액션 1줄

next: stage06_candidate_gen_v1.md
