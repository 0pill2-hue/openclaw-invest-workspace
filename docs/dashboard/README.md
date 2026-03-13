# Local Operations Dashboard

검은 배경 탭형 운영 대시보드입니다.

## 실행

```bash
python3 scripts/dashboard/server.py
```

기본 주소: `http://127.0.0.1:8717`

옵션:

```bash
python3 scripts/dashboard/server.py --host 127.0.0.1 --port 8717
```

## 탭

1. 운영보고서
2. Stage1
3. Stage2
4. Stage3 (준비중)

## API

- `GET /api/ops/overview`
- `GET /api/tasks/{ticket_id}`
- `GET /api/stage1/summary`
- `GET /api/stage2/summary`

## 데이터 소스 원칙

- 모델 호출 없음
- 로컬 파일/DB만 사용
- 브라우저 4초 polling 기반 자동반영

주요 소스:

- `runtime/tasks/tasks.db`
- `runtime/current-task.md`
- `runtime/tasks/watchdog_notify_state.json`
- `runtime/tasks/auto_dispatch_status.json`
- `runtime/tasks/watchdog.launchd.log`
- `runtime/heartbeat/local_brain_guard.launchd.log`
- `runtime/dashboard/provider_usage_cache.json`
- `invest/stages/stage1/outputs/runtime/*.json`
- `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- `invest/stages/stage2/outputs/**/*`
- `invest/stages/stage2/inputs/config/*.json`

Stage2는 `invest/stages/stage2/outputs/runtime/stage2_status.json`를 대시보드 요약 소스로 생성/갱신합니다.
