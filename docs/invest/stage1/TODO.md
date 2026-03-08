# STAGE1 TODO

역할: Stage1 운영상 미해결 이슈와 추가 점검 항목의 tracked 목록.

## 현재 미해결 이슈
- KR supply latest stale
  - 현상: `2026-02-26` 이후 최신 거래일 공백
  - 영향: `post_collection_validate` 실패
- RSS coverage 해석 보강 필요
  - 현상: 파일 수 대비 published_date unique date 수가 매우 적음
  - 과제: collected_run_dates vs published_dates 분리 카탈로그 필요
- Blog/Telegram 실제 coverage 미수집 후속 처리
  - 현상: 검증 기준은 `all_buddies_satisfied` / `all_channels_satisfied`까지 반영됐고, 현재 raw 기준으로 일부 blog buddy 및 telegram channel 누락이 남아 있다.
  - 과제: source-side 미수집 원인을 개별 확인하고 실제 raw를 채운 뒤 재검증한다.

## 카탈로그 개선 과제
- 모든 주요 source별 coverage summary 산출 여부 검토
- raw_tree 기반으로 새 폴더 생성/비어 있는 폴더 변화 감지
- runtime_health에 daily/post-collection 실패 상세 누적 보강
- 시장 데이터 cross-source diff 자동 경보 추가
