# Backtest Result Governance

## Grades
- DRAFT: exploratory/test-only (never official)
- VALIDATED: data/rule/verification conditions passed
- PRODUCTION: approved for official reporting/adoption

## Mandatory rules
1. Missing grade => DRAFT
2. DRAFT outputs must include `TEST ONLY` watermark/text.
3. Keep physical separation:
   - `invest/stages/stage6/outputs/results/test_history/`
   - `invest/stages/stage6/outputs/results/prod_history/`
4. Official report/adoption is allowed only for PRODUCTION.

## Minimal promotion checks
- DRAFT -> VALIDATED
  - Data range >= 3 years
  - Cost/slippage explicitly applied
  - OOS split >= 30%
  - Rule spec documented
- VALIDATED -> PRODUCTION
  - Walk-forward/paper verification completed
  - Reviewer approval recorded
