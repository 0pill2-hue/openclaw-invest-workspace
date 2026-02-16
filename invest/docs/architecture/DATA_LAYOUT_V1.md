# DATA_LAYOUT_V1

## 목표
- raw/clean/quarantine/audit/reports 계층 분리
- 코드/데이터/MD 모두 lineage 추적 가능화
- 오염 데이터 즉시 분리 + 근거(audit) 저장

## 표준 폴더
```
invest/data/
  raw/
    kr/{ohlcv,supply}/
    text/{blog,telegram}/
  clean/
    kr/{ohlcv,supply}/
    text/{blog,telegram}/
  quarantine/
    kr/{ohlcv,supply}/
    text/{blog,telegram}/
  audit/
    kr/{ohlcv,supply}/
    text/{blog,telegram}/
  reports/
    data_quality/
```

## 운영 규칙
1. raw는 불변(append-only)
2. clean은 검수 통과본만 저장
3. quarantine는 제외가 아니라 증거 보존
4. audit에는 rule_version, reason, source_path 반드시 기록
5. 저장 UTC / 보고 KST

## MD 구조화
- 원문: raw/text/*/*.md
- 구조화본: clean/text/*/*.jsonl
- 격리본: quarantine/text/*/*.jsonl
- audit: audit/text/*/*.jsonl (왜 격리됐는지)

## 단계 적용
1) 수집기 raw 저장
2) 정제기 clean/quarantine 분리
3) 백테스트는 clean만 사용
4) 보고는 clean+audit 요약
