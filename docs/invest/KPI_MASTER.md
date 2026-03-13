# KPI_MASTER

status: ACTIVE  
role: stage별 KPI threshold(합격 수치) 전용 SSOT

원칙:
- 이 문서는 threshold만 정의한다.
- 현재값, UI 렌더링, 버전별 구현 세부는 stage별 구현 spec로 분리한다.
  - Stage6: `docs/invest/stage6/STAGE6_KPI_RUNTIME_SPEC.md`

## 공통 원칙
- KPI 수치는 승인 없이 임의 변경 금지
- 수치 미달 시 해당 단계 FAIL, 다음 단계 진입 금지
- 결과 등급(`DRAFT|VALIDATED|PRODUCTION`) 판정은 `RESULT_GOVERNANCE.md` 기준

## Stage1 KPI
| KPI | Threshold |
| --- | --- |
| 수집 성공률 | `>= 98%` |
| 연속 누락 허용 | `< 3일/심볼` |
| 수집 완료 신선도 | `당일 06:00 이전` |
| 격리율 | `< 5%` |
| Health State | `ok=true`, `grade=VALIDATED` |
| Checkpoint Gate | `ok=true` |

## Stage2 KPI
| KPI | Threshold |
| --- | --- |
| 보존법칙(QG-02-01) | `count(raw) == count(clean) + count(quarantine)` |
| Logical Invariant 위반(QG-02-02) | `0건` |
| 시간 단조성 위반(QG-02-03) | `0건` |
| 격리율(QG-02-04) | `< 15%` |
| STOP_PIPELINE 발생 | `0회` |

## Stage4 KPI
| KPI | Threshold |
| --- | --- |
| 독립 FAIL 항목 수(QG-03-01) | `<= 3건` |
| 스키마 준수율(QG-03-02) | `100%` |
| 이상치 미검증(QG-03-03) | `0건` |
| 샘플링 오류율(QG-03-04) | `< 1%` |
| BLOCK_STAGE_04 발생 | `0회` |

## Stage5 KPI
| KPI | Threshold |
| --- | --- |
| 결과 등급 | `VALIDATED 이상` |
| NaN 비율(QG-04-02) | `< 0.5%` |
| Z-Score 정규화(QG-04-01) | `|Mean| < 0.05`, `|Std-1.0| < 0.1` |
| 유동성 필터 준수(QG-04-03) | `100%` |
| 연속성 WARN 비율(QG-04-04) | `< 70%` |

## Stage6 KPI
### Hard Gate (gate4)
| KPI | Threshold |
| --- | --- |
| Replacement Edge | `>= 15%` |
| MDD_2021+ | `>= -70%` |
| CAGR_core (2023~2025) | `>= 20%` |

### Soft Gate
| KPI | Threshold |
| --- | --- |
| Persistence | `3구간 중 >= 2 통과` |
| Confidence Score | `>= 0.7` |

### 전략 목표 KPI (장기)
| KPI | Threshold |
| --- | --- |
| CAGR (long-term) | `>= 70%` |
| CAGR (2025 stretch) | `>= 300%` |
| vs KOSPI 초과수익 | `> 0%` |
| MDD_full 모니터링 경고선 | `-50% 초과 시 경고` |
