# openclaw-invest-workspace

투자 데이터 수집/정제/검증/백테스트를 위한 OpenClaw 워크스페이스입니다.

## 핵심 목표
- 데이터 오염 방지 (raw / clean / quarantine / audit 분리)
- 재현 가능한 백테스트 (run manifest + 결과 등급)
- 운영 안정화 (수집 파이프라인 + 헬스체크 + 보고 체계)

## 디렉토리 개요
- `invest/data/raw/` : 원본 데이터(불변)
- `invest/data/clean/` : 검수 통과 데이터
- `invest/data/quarantine/` : 오염/의심 데이터 격리
- `invest/data/audit/` : 감사/추적 로그
- `invest/reports/data_quality/` : 오염/정리 리포트
- `invest/results/test|validated|prod/` : 결과 등급 분리

## 빠른 시작
```bash
# 1) 기존 데이터 정리 (clean/quarantine 분리)
.venv/bin/python3 invest/scripts/organize_existing_data.py

# 2) MD 코퍼스 구조화(JSONL)
.venv/bin/python3 invest/scripts/structure_md_corpus.py

# 3) 블로그 수집
python3 invest/scripts/scrape_all_posts_v2.py

# 4) 텔레그램 수집
python3 invest/scripts/scrape_telegram_highspeed.py

# 5) 백테스트 (DRAFT)
.venv/bin/python3 invest/backtest_compare.py
```

## 운영 규칙(요약)
- raw는 overwrite 금지(append-only)
- 분석/백테스트 입력은 clean 우선
- quarantine 데이터는 삭제 금지(근거 보존)
- 결과는 `DRAFT | VALIDATED | PRODUCTION` 등급 준수

## 관련 문서
- `invest/docs/architecture/DATA_LAYOUT_V1.md`
- `invest/docs/architecture/RUNBOOK_V1.md`
- `invest/results/RESULT_GOVERNANCE.md`

---
필요한 항목이 있으면 이 README를 계속 확장합니다.
