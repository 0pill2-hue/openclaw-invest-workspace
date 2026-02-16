# RUNBOOK_V1

## 목적
- 브레인스토밍 합의사항 즉시 운영 반영
- raw/clean/quarantine/audit/reports + run manifest 표준화

## 실행 순서
1. 기존 데이터 소급 정리
```bash
.venv/bin/python3 invest/scripts/organize_existing_data.py
```
2. MD 구조화
```bash
.venv/bin/python3 invest/scripts/structure_md_corpus.py
```
3. 수집기 실행 (raw 저장 + quarantine 분리)
```bash
python3 invest/scripts/fetch_ohlcv.py
python3 invest/scripts/fetch_supply.py
```

## 산출물 확인
- reports/data_quality/*summary*.json
- reports/data_quality/*manifest*.json
- data/clean/*
- data/quarantine/*

## 규칙
- raw는 overwrite 금지
- clean만 백테스트 입력 허용
- quarantine은 삭제 금지(근거 보존)
- 모든 배치 산출물은 manifest 생성 필수
