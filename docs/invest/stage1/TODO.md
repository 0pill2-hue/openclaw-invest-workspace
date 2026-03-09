# STAGE1 TODO

역할: Stage1 운영상 미해결 이슈와 추가 점검 항목의 tracked 목록.

## 현재 미해결 이슈
- RSS coverage 해석 보강 필요
  - 현상: `source_coverage_index.json`의 RSS 카탈로그는 아직 `unique_dates_count` 중심이라, 수집 실행일(`collected_run_dates`)과 기사 발행일(`published_dates`)을 분리해 해석하기 어렵다.
  - 과제: collected_run_dates vs published_dates 분리 카탈로그를 추가해 coverage 해석을 명확히 한다.
- Blog coverage SSOT 불일치 정리 필요
  - 현상: `post_collection_validate.json`의 `runtime/blog_full_coverage`는 terminal registry 반영 기준 `all_buddies_satisfied=true`지만, `source_coverage_index.json`의 blog scope는 아직 `all_buddies_satisfied=false`, `missing_buddy_count=6`으로 남아 있다.
  - 과제: blog coverage 판정 SSOT를 하나로 정리하고, 남은 6개 buddy를 terminal 정상종결로 볼지 추가 원문 확보 대상으로 둘지 기준을 고정한다.

## 최근 확인으로 해소된 항목 (2026-03-09 확인)
- KR supply latest stale
  - 현재 상태: `post_collection_validate.json` 기준 `raw/signal/kr/supply ok=true`, `failed_count=0`
  - 메모: 기존 stale 이슈는 현재 TODO 잔여로 보지 않음
- Telegram 실제 coverage 미수집 후속 처리
  - 현재 상태: `source_coverage_index.json` 기준 telegram `all_channels_satisfied=true`
  - 메모: terminal registry 반영 기준으로 현재 TODO 잔여로 보지 않음

## 카탈로그 개선 과제
- 모든 주요 source별 coverage summary 산출 여부 검토
- raw_tree 기반으로 새 폴더 생성/비어 있는 폴더 변화 감지
- runtime_health에 daily/post-collection 실패 상세 누적 보강
- 시장 데이터 cross-source diff 자동 경보 추가
