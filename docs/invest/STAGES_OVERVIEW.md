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
목적: Stage2 clean 기반 정성/비정형 입력을 로컬 브레인 claim-card 추출과 rule-engine 집계로 4축 정성신호로 압축한다.
입력: Stage2 clean qualitative/signal 입력, `stage2_text_meta_records.jsonl`, Stage3 reference.
출력: JSONL 중간 입력, 4축 정성 feature, claim-card 증거, DART event signal, 실행 요약.
게이트: 로컬 브레인 처리, 최소 입력 조건, 중복가드 검증이 충족되어야 Stage4로 전달된다.

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
목적: Stage4 산출을 튜닝 입력 인터페이스 JSON으로 고정해 후속 실험/조정 입력 계약을 만든다.
입력: Stage4 value 출력, Stage4 report, Stage4 manifest.
출력: stage7 tuning input JSON, interface build 결과 JSON.
게이트: Stage4 source 경로와 required_columns 계약이 확인되어야 유효 산출물로 인정된다.

## Reserved stages

### Stage8 — RESERVED
목적: 향후 컷오프/분기 관리 또는 중간 승인 절차를 담당할 수 있는 예약 단계다.
입력: 미확인. 기존 validated 입력을 이어받는 위치로만 정의한다.
출력: 미확인. 현시점에서는 생성 책임이 없다.
게이트: 운영 목적과 승격 규칙이 확정되기 전까지 RESERVED 유지.

### Stage9 — RESERVED
목적: 향후 추가 가치평가 또는 심화 scoring 로직을 배치할 수 있는 예약 단계다.
입력: 미확인. 기존 핵심 산출물의 후속 평가 입력을 받을 가능성만 정의한다.
출력: 미확인. 현재는 산출 의무가 없다.
게이트: 평가 의미와 KPI가 확정되기 전까지 사용 금지.

### Stage10 — RESERVED
목적: 향후 교차검토나 독립 검증 체계를 배치할 수 있는 예약 단계다.
입력: 미확인. 이전 단계 결과를 재검증하는 확장 슬롯으로 본다.
출력: 미확인. 현행 파이프라인에서는 비활성이다.
게이트: 검증 주체와 판정 규칙이 고정되기 전까지 RESERVED 유지.

### Stage11 — RESERVED
목적: 향후 최종 승인 준비, 배포 전 점검, 보고 집계를 맡을 수 있는 예약 단계다.
입력: 미확인. 승인 직전 결과 묶음을 받는 용도로만 가정한다.
출력: 미확인. 현재는 활성 산출물이 없다.
게이트: 승인 프로세스와 책임 경계가 문서화되기 전까지 사용하지 않는다.

### Stage12 — RESERVED
목적: 향후 채택/보류/승격 최종 결정을 기록하는 종착 단계로 예약한다.
입력: 미확인. 직전 승인 준비 산출물을 이어받는 구조만 상정한다.
출력: 미확인. 현시점 운영 결과는 Stage6까지를 기준으로 본다.
게이트: 공식 채택 모델이 확정되기 전까지 RESERVED 상태를 유지한다.
