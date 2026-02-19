# stage05_result_v3_24_kr

## inputs
- 전체 36개 baseline 처음부터 재실행: numeric10 / qualitative10 / hybrid10 / external6
- 정책 반영(브레인스토밍): over-switching 축소, hold 우선
- 교체 조건 강화: +15% edge + persistence(3개 중 2개) + confidence gate
- 교체 전 소프트 단계: 신규 편입 비중 패널티 후 전면교체
- 교체 후 쿨다운: 2개월
- 월 교체 상한: 20%
- numeric 최종승자 금지 유지

## run_command(or process)
- `python3 -m py_compile invest/scripts/stage05_full_recompute_v3_24_kr.py`
- `./venv/bin/python invest/scripts/stage05_full_recompute_v3_24_kr.py`

## outputs
- `invest/results/validated/stage05_baselines_v3_24_kr.json`
- `invest/reports/stage_updates/stage05/v3_24/summary.json`
- `invest/reports/stage_updates/stage05/v3_24/stage05_result_v3_24_kr.md`
- `invest/reports/stage_updates/stage05/v3_24/stage05_result_v3_24_kr_readable.md`
- `invest/reports/stage_updates/stage05/v3_24/stage05_trade_events_v3_24_kr.csv`
- `invest/reports/stage_updates/stage05/v3_24/stage05_portfolio_timeline_v3_24_kr.csv`
- `invest/reports/stage_updates/stage05/v3_24/stage05_portfolio_weights_v3_24_kr.csv`
- `invest/reports/stage_updates/stage05/v3_24/stage05_portfolio_weights_summary_v3_24_kr.json`
- `invest/reports/stage_updates/stage05/v3_24/charts/stage05_v3_24_yearly_continuous_2021plus.png`
- `invest/reports/stage_updates/stage05/v3_24/charts/stage05_v3_24_yearly_reset_2021plus.png`
- `invest/reports/stage_updates/stage05/v3_24/ui/index.html`

## quality_gates
- gate1(track 36개, 10/10/10/6): PASS
- gate2(weighted selection internal): PASS
- gate3(numeric 최종 승자 불가): PASS
- gate4(replacement composite gate): PASS
- gate5(monthly cap/cooldown/soft stage schema): PASS
- gate6(MDD split): PASS
- gate7(UI template parity): PASS

## winner
- model_id: hybrid_h10_fee_stress
- track: hybrid
- total_return: 8789.16%
- cagr: 50.37%
- mdd_full: -52.60%
- replacement_edge: 29.69%
- persistence_hits: 2/3
- confidence_score: 0.67

## final
- final_decision: ADOPT_HOLD_PRIORITY_V324
- stop_reason: ALL_POLICY_GATES_PASS
