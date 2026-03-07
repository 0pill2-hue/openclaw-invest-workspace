# STAGE1 TODO

역할: Stage1 운영상 미해결 이슈와 추가 점검 항목의 tracked 목록.

## 현재 미해결 이슈
- KR supply latest stale
  - 현상: `2026-02-26` 이후 최신 거래일 공백
  - 영향: `post_collection_validate` 실패
- US OHLCV latest stale
  - 현상: `2026-02-26` 이후 최신부 정지, 일부 종목은 `2026-02-13`에서 멈춤
- RSS coverage 해석 보강 필요
  - 현상: 파일 수 대비 published_date unique date 수가 매우 적음
  - 과제: collected_run_dates vs published_dates 분리 카탈로그 필요
- Telegram coverage completeness 자동점검 보강
  - 현상: allowlist 대비 public fallback 파일 기준 미수집 엔트리 존재 가능
  - 과제: full/fallback/title 기반 매핑을 더 정확히 연결
- Blog coverage completeness 자동점검 보강
  - 현상: 현재는 discovered subdirectory 기준만 있음
  - 과제: blogId registry 또는 seed/source 기준 completeness 필요

## 카탈로그 개선 과제
- 모든 주요 source별 coverage summary 산출 여부 검토
- raw_tree 기반으로 새 폴더 생성/비어 있는 폴더 변화 감지
- runtime_health에 daily/post-collection 실패 상세 누적 보강
- 시장 데이터 cross-source diff 자동 경보 추가
