# GUARDRAIL_CHECKLIST_V1

## 목적
선행 의존성 위반/오염 데이터 혼입/무증빙 100% 보고를 구조적으로 차단한다.

## Release Gate (모두 PASS 필요)
1. Dependency Gate PASS
   - [ ] 정제 실패 상태에서 검증/학습/밸류 미실행
2. Clean-only Gate PASS
   - [ ] feature/train/value 입력 경로가 `invest/data/clean/**` 만 사용
3. Lineage Gate PASS
   - [ ] run_id, rule_version, input_hash, output_hash 기록
4. Idempotency Gate PASS
   - [ ] 4~8회 반복 실행 간 상태 초기화/분산 허용치 이내
5. Reporting Gate PASS
   - [ ] 완료 100% 표기는 DONE+proof에 한정
   - [ ] 5항목 포맷 누락 없음

## 운영 기준
- 병렬도: 기본 3, 최대 4
- 충돌 발생 시 해당 스테이지 순차 강등
- FAIL 발생 시 하류 단계 즉시 중단
