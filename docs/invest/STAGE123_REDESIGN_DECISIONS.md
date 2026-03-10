# STAGE123_REDESIGN_DECISIONS

status: DRAFT
updated_at: 2026-03-10 KST
purpose: 세션 유실/막힘 시에도 유지해야 하는 Stage1/2/3 재설계 결정사항 고정

## 공통 원칙
- DB 중심 구조로 재설계한다.
- 기존 소스를 직접 수정하는 것을 원칙으로 하며 레거시 파일/호환 래퍼/중복 경로는 남기지 않는다.
- 단순작업·반복작업·노가다성 작업은 서브에이전트에 위임하고 메인은 구조 설계·판단·검증·최종 정리에 집중한다.
- 중요 설계 변경은 memory와 directive에 함께 남긴다.

## Stage1
- 원천 수집 DB 단계로 운영한다.
- 원천 식별키를 고정한다:
  - `source_type`
  - `channel`
  - `message_id`
  - `attachment_id`
  - `doc_hash`
  - `fetched_at`
- ingest 상태를 둔다:
  - `NEW`, `FETCHED`, `PARSED`, `FAILED`, `SKIPPED`
- 보관은 `ingested_at` 기준 1개월 rolling 방식으로 운영한다.
- 불량/충돌 데이터는 quarantine로 격리한다.

## Stage2
- Stage1 DB를 입력으로 정제/정규화 DB를 생성한다.
- 최근 1개월은 중복을 보존한다.
- 로컬 작업 특성상 데이터가 꼬일 위험이 크면 전체 초기화 후 재적재를 허용한다.
- `canonical_doc_id`를 두어 대표본을 분리한다.
- lineage를 남긴다:
  - `stage1_ids`
  - `dedupe_group_id`
  - `normalized_from`
- rebuild 모드:
  - `full rebuild`
  - `recent 1month rebuild`
  - `single-source rebuild`
- 정규화 축:
  - `stock`
  - `industry`
  - `doc`
  - `source`
  - 시계열 관련 일자 필드

## Stage3
- 두 레이어로 분리한다.
  - Stage3-A: 최근 1개월 corpus를 직접 읽고 텍스트 문구를 작성하는 텍스트 기반 집계 분석
  - Stage3-B: 문서 단건 심층분석
- Stage3-B source 범위:
  - report
  - blog
  - premium
  - filing / IR
  - earnings call transcript
  - conference / Q&A
  - trade publication
  - field signal
- source tier taxonomy:
  - `official`
  - `professional`
  - `independent`
  - `field_signal`
- 결과는 최소 두 축으로 산출한다.
  - `stock_data`
  - `industry_data`
- stock↔industry 연결키를 유지한다:
  - `primary_industry`
  - `secondary_industries`
  - `theme_links`
- 심층분석 출력 계약은 점수보다 아래 중심으로 설계한다.
  - `claim`
  - `evidence`
  - `risk`
  - `counterpoint`
  - `source_refs`
- source 충돌 시 사실관계는 `official` 우선이다.

## 심층분석 운영 규칙
- 문서별로 무엇을 뽑을지는 `docs/invest/stage3/STAGE3_DEEP_ANALYSIS_EXTRACTION_RUBRIC.md`를 따른다.
- 대량 결과(수만 건)는 전건 수동 승인하지 않는다.
- 품질 운영은 아래 3단 구조로 간다.
  - `auto-pass`
  - `escalate`
  - `sample audit`

## 운영 메모
- 세션이 날아가거나 막혀도 본 문서 + memory + directives를 기준으로 재개한다.
- 세션 watchdog은 주인님 재개 지시 전까지 중지 상태로 유지한다.
