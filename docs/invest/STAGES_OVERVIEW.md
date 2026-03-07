# STAGES_OVERVIEW

## Active stages

### Stage1 — ACTIVE
목적: 외부 시장/기업/정성 원천을 수집해 파이프라인의 raw 기준선을 만든다.
입력: 외부 API, 피드, 수집 설정, 인증이 필요한 런타임 환경변수.
출력: master, raw signal/qualitative, runtime 상태, 수집 로그.
게이트: 핵심 수집 성공, checkpoint/post-collection 검증 통과 시에만 다음 단계로 넘긴다.

### Stage2 — ACTIVE
목적: Stage1 raw를 정제하고 quarantine 분리를 통해 downstream 신뢰도를 확보한다.
입력: Stage1 raw 및 stage2 입력 동기화 결과.
출력: clean 데이터셋, quarantine, 정제 리포트, 자동실행 상태.
게이트: 보존법칙·논리 invariant·신선도 기준을 만족해야 Stage3/4 입력으로 승격된다.

### Stage3 — ACTIVE
목적: 정성/비정형 입력을 attention gate로 요약해 구조화 가능한 특징으로 바꾼다.
입력: Stage1 정성 원천과 Stage2 clean 메타 입력.
출력: JSONL 중간 입력, attention/sentiment feature, 실행 요약.
게이트: 로컬 브레인 처리와 최소 입력 조건이 충족되어야 Stage4로 전달된다.

### Stage4 — ACTIVE
목적: 상위 입력을 결합해 가치 계산과 핵심 검증 산출물을 생성한다.
입력: Stage1 master, Stage2 clean, Stage3 출력.
출력: value 산출물, 검증 리포트, 다음 feature engineering 입력.
게이트: 계산 완료와 품질 검증 기준 충족 시에만 Stage5로 승격된다.

### Stage5 — ACTIVE
목적: 모델/선발에 필요한 validated feature set을 일관된 형식으로 만든다.
입력: Stage1 master, Stage2 clean, Stage4 value 결과.
출력: feature 테이블, 엔지니어링 리포트, 평가용 입력 자산.
게이트: NaN/정규화/유동성 등 품질 기준을 통과해야 Stage6 후보로 사용된다.

### Stage6 — ACTIVE
목적: 베이스라인 비교와 선발 판단을 수행해 운영 채택 직전 결과를 정리한다.
입력: Stage1~5에서 검증된 누적 산출물.
출력: 비교 결과, 선발 결과, 결과 등급별 보고 자산.
게이트: 검증·승인·증빙이 충족된 결과만 VALIDATED 또는 PRODUCTION으로 승격된다.

### Stage7 — ACTIVE
목적: Stage4 출력에서 튜닝 입력 인터페이스를 생성한다.
입력: `invest/stages/stage7/inputs/upstream_stage4_outputs/`
출력: `invest/stages/stage7/inputs/stage7_tuning_input_from_stage4_latest.json`, `invest/stages/stage7/outputs/results/stage7_interface_build_latest.json`
게이트: stage7 입력 계약과 source.stage4_* 경로 검증을 통과해야 한다.

## Reserved / historical / governance stages

### Stage8 — RESERVED / HISTORICAL_ONLY
현재 stage8 전용 실행 스크립트는 없다. 상세 문서는 historical reference다.

### Stage9 — RESERVED / HISTORICAL_ONLY
현재 stage9 전용 실행 스크립트는 없다. 상세 문서는 historical reference다.

### Stage10 — RESERVED / HISTORICAL_ONLY
현재 stage10 전용 실행 스크립트는 없다. 상세 문서는 historical reference다.

### Stage11 — RESERVED / DRAFT_PLACEHOLDER
구조 슬롯만 존재하며 실행 기준은 아직 없다.

### Stage12 — RESERVED / GOVERNANCE_STAGE
채택/보류/승격 거버넌스 문서 중심 단계이며 실행 기준은 아직 없다.
