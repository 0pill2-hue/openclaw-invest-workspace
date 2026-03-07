# Stage1 Docs

Stage1 문서는 이 디렉터리의 두 파일만 유지한다.
상세 실행·재현 SSOT는 반드시 `RUNBOOK.md`를 본다.

- 역할: 외부 원천 수집과 raw/master/runtime 기준선 생성
- 범위: Stage2 정제 이전의 데이터 수집과 1차 게이트
- 메인 진입점: `invest/stages/stage1/scripts/stage01_daily_update.py`
- 체인 진입점: `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
- 필수 검증: checkpoint gate, post-collection validate
- 핵심 출력: `outputs/master`, `outputs/raw`, `outputs/runtime`, `outputs/logs`
- Telegram 인증/폴백, DART, RSS, 뉴스, OCR 수집 규칙은 RUNBOOK에 통합했다.
- 백필 명령과 운영 재현 명령도 RUNBOOK에만 남긴다.
- 새 문서를 추가하지 말고 Stage1 운영 변경은 RUNBOOK 갱신으로 반영한다.
- 공통 전략/단계 개요는 `docs/invest/STRATEGY_MASTER.md`, `docs/invest/STAGES_OVERVIEW.md`를 따른다.

## 바로가기
- [RUNBOOK.md](./RUNBOOK.md)
