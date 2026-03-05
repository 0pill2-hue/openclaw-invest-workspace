# Workspace README

이 저장소는 투자 파이프라인(Stage1~Stage9) 운영 워크스페이스입니다.

## 핵심 원칙
- 코드/문서/규칙 파일은 Git 추적
- 고변동 산출물(실행 중 계속 바뀌는 대용량 데이터)은 Git 추적 제외

## 현재 추적 제외 정책
- `runtime/**/*.db`
- `invest/stages/stage1/outputs/**`
- `invest/stages/stage1/outputs/runtime/telegram_scrape_*.json`
- `invest/stages/stage1/outputs/runtime/telegram_attach_tmp/**`
- `invest/stages/stage2/outputs/clean/production/`
- `invest/stages/stage2/outputs/quarantine/production/`
- `invest/stages/stage3/outputs/**`
- `invest/stages/stage3/inputs/stage2_text_meta_records.jsonl`
- `invest/stages/stage1/outputs/runtime/*.lock`
- `*.session-journal`

## 운영 메모
- Stage2 정제 결과는 `reports`와 검증 리포트로 관리하고,
  `clean/quarantine production` 원파일은 로컬 산출물로 취급합니다.
- 필요 시 재생성(onepass + qc) 기준으로 운영합니다.
