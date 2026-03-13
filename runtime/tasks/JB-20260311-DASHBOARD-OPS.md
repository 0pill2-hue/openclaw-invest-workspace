# JB-20260311-DASHBOARD-OPS

## goal
- 주인님 지시 기준으로 로컬 파일/DB 기반의 검은 배경 탭형 운영 대시보드를 구현한다.
- 모델 호출 없이 runtime/ 및 invest/stages 산출물만 읽는 경량 로컬 API + 정적 프론트 구조로 만든다.

## scope
- docs/dashboard/index.html
- docs/dashboard/app.css
- docs/dashboard/app.js
- scripts/dashboard/server.py
- scripts/dashboard/read_tasks.py
- scripts/dashboard/read_ops.py
- scripts/dashboard/read_stage1.py
- scripts/dashboard/read_stage2.py
- runtime/dashboard/provider_usage_cache.json
- 필요 시 stage2_status.json 및 간단한 사용 문서

## constraints
- 대시보드 갱신 때문에 토큰/모델 호출 금지
- localhost 전용 경량 구현
- 폴링 기반 자동반영 허용
- 파일/DB 부재 시 degraded/unavailable로 견고하게 표시

## initial_plan
1. 현재 데이터 소스/파일 구조 조사
2. Python API 구현
3. 다크 테마 탭형 UI 구현
4. Stage1/Stage2 summary 연결
5. 실행 방법 문서화

## proof_log
- task created: runtime/tasks/JB-20260311-DASHBOARD-OPS.md

## implementation
- 로컬 대시보드 정적 프론트 + Python API 서버 구현 완료
- 탭 구성: 운영보고서 / Stage1 / Stage2 / Stage3(준비중)
- 자동반영: 프론트 polling(4초), 서버는 로컬 파일/DB만 조회
- 모델/LLM 호출 경로 없음

### changed_files
- docs/dashboard/index.html
- docs/dashboard/app.css
- docs/dashboard/app.js
- docs/dashboard/README.md
- scripts/dashboard/server.py
- scripts/dashboard/read_tasks.py
- scripts/dashboard/read_ops.py
- scripts/dashboard/read_stage1.py
- scripts/dashboard/read_stage2.py
- runtime/dashboard/provider_usage_cache.json
- invest/stages/stage2/outputs/runtime/stage2_status.json

### verification
- python3 -m py_compile scripts/dashboard/*.py
- node --check docs/dashboard/app.js
- python3 scripts/dashboard/server.py --host 127.0.0.1 --port 8765 (기동 후 API 응답 확인)
  - /api/ops/overview OK
  - /api/stage1/summary OK
  - /api/stage2/summary OK
  - /api/tasks/JB-20260311-DASHBOARD-OPS OK

### run
- python3 scripts/dashboard/server.py
- 브라우저: http://127.0.0.1:8765/
