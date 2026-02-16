# TASKS.md

## REPORT_QUEUE (Mandatory)
- format: `- [ ] [PENDING_REPORT] HH:MM | task | due | channel`
- close rule: mark `[x] [DONE_REPORT]` only after actual report message sent

- [x] [DONE_REPORT] 12:59 | 피처 점수 정규화 비교표 재보고 | 보고완료 15:44 | telegram
- [x] [DONE_REPORT] 13:22 | 추가 규칙(MUST 3개) 적용 완료 보고 | 보고완료 15:40 | telegram
- [x] [DONE_REPORT] 13:30 | 2/11~현재 텔레/블로그 정성분석 보고 | 보고완료 15:32 | telegram

---

## NOW (우선 실행)
- [ ] 데이터 오염 리포트(11238건) 유형별 검수표 확정 (정상/오염 판정기준 문서화)
- [ ] 오염 데이터 clean/quarantine 재분리 배치 실행 (기존 적재분 소급 정리)
- [ ] 정제 전/후 백테스트 비교 리포트 생성 (내지표 vs 이웃지표)
- [ ] 알고리즘 신호 로직 전수점검 (부호/진입/청산/포지션 규칙)
- [ ] 교차리뷰(설계/구현/결과) 반영본 제출

## IN PROGRESS
- [ ] 미국 OHLCV 수집 정체 구간 보강 (`fetch_us_ohlcv.py` yfinance 타임아웃/재시도/로그)
- [ ] 수집 단계 오염 즉시 분리 운영 검증 (`fetch_ohlcv.py`, `fetch_supply.py`)
- [ ] 블로그 fallback 경로 보강 후 관찰 (신규 URL/날짜 추출/요청지연)

## ALWAYS-ON (상시 운영)
- [ ] 텔레그램/블로그 수집 파이프라인 헬스 모니터링
- [ ] health-state / pendingMessages / 연속 실패 감시
- [ ] 시간별/정시 보고 운영

## BLOCKED / PENDING
- [ ] DART 공시 연동 (OpenAPI 키 필요)
- [ ] 필요 시 한국어 OCR 추가 설치(tesseract-lang)

---

## DONE (최근 핵심)
- [x] 블로그 최신 누락 원인 수정 (RSS 신형 URL 패턴 반영)
- [x] 블로그 전구간 재수집 완료 (633/633)
- [x] 텔레그램 수집 정상 완료 (`ALL_CHANNELS_FINISHED`)
- [x] 결과 거버넌스(DRAFT/VALIDATED/PRODUCTION, 경로 분리) 반영
- [x] fallback 보강(HTTP/browser 신형 URL 대응, RSS 실패 로그 추가)
- [x] 오염 전수조사 리포트 생성
  - `invest/reports/data_quality/contamination_scan_20260216_2033.csv`
  - `invest/reports/data_quality/contamination_scan_summary_20260216_2033.json`

## ARCHIVE (이전 백로그)
- [ ] 전체 스크립트 코드 리뷰 (나머지 수집/유틸)
- [ ] QUERY_MAX_CODES 운영값 확정(600/800/1200 A/B)
- [ ] 텔레그램 allowlist 엔트리 주기 검수
- [ ] 보안 P0/P1 항목 (수집 안정화 이후 순차)
