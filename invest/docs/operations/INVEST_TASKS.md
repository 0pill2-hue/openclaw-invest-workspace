# INVEST_TASKS.md

Last updated: 2026-02-19 17:34 KST
Purpose: 투자 도메인 전용 실행 백로그

## NOW (우선 실행)
- [ ] 오염 데이터 clean/quarantine 재분리 배치 실행 (기존 적재분 소급 정리)
- [ ] 정제 전/후 백테스트 비교 리포트 생성 (내지표 vs 이웃지표)
- [ ] 알고리즘 신호 로직 전수점검 (부호/진입/청산/포지션 규칙)
- [ ] 교차리뷰(설계/구현/결과) 반영본 제출

## IN PROGRESS
- [ ] 미국 OHLCV 수집 정체 구간 보강 (`invest/scripts/stage01_fetch_us_ohlcv.py`)
- [ ] 수집 단계 오염 즉시 분리 운영 검증 (`invest/scripts/stage01_fetch_ohlcv.py`, `invest/scripts/stage01_fetch_supply.py`)
- [ ] 블로그 fallback 경로 보강 후 관찰 (신규 URL/날짜 추출/요청지연)

## ALWAYS-ON (상시 운영)
- [ ] 텔레그램/블로그 수집 파이프라인 헬스 모니터링
- [ ] health-state / pendingMessages / 연속 실패 감시

## BLOCKED / PENDING
- [ ] DART 공시 연동 (OpenAPI 키 필요)
- [ ] 필요 시 한국어 OCR 추가 설치(tesseract-lang)
