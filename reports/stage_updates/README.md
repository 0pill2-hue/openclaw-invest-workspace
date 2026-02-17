# 단계 문서 (11단계 기준, 01=수집)

기준 단계:
1. `stage01_data_collection.md` (데이터 수집)
2. `stage02_data_cleaning.md` (데이터 정제)
3. `stage03_cleaning_validation.md` (정제 검증)
4. `stage04_validated_value.md` (VALIDATED 밸류 산출)
5. `stage05_baseline_3track.md` (베이스라인 3트랙 비교)
6. `stage06_candidate_gen_v1.md` (후보군 1차 생성)
7. `stage07_candidate_stage_cut.md` (후보군 단계별 컷)
8. `stage08_purged_cv_oos.md` (Purged CV + OOS)
9. `stage09_cost_turnover_risk.md` (비용/턴오버/리스크)
10. `stage10_cross_review.md` (교차리뷰 반영)
11. `stage11_adopt_hold_promote.md` (채택/보류/승격)

운영 원칙:
- 단계 번호/의미는 위 목록을 canonical로 사용
- stage01~04: 각 문서의 `quality_gate(s)`/`failure_policy`를 통과해야 다음 단계 진입
- stage05: `gate_fail_protocol` 기준으로 분기(데이터형/모델형/거버넌스형)
- 5단계에서 미통과 시 기본적으로 4→5 반복
- 단계 정의 변경 시 README와 각 stage 문서를 동시에 갱신
