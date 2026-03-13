# STAGE6_KPI_RUNTIME_SPEC

status: CANONICAL (Stage6 KPI runtime/rendering/current-values spec)

역할:
- `KPI_MASTER.md`의 Stage6 threshold를 실제 실행 결과에 매핑하는 구현 상세를 정의한다.
- 현재값/버전별 게이트/UI 산출물 계약처럼 변동 가능성이 높은 내용을 관리한다.

## Threshold Source
- threshold SSOT: `docs/invest/KPI_MASTER.md`
- result grade/path SSOT: `docs/invest/RESULT_GOVERNANCE.md`

## Current Snapshot (v4_0)
| KPI | Threshold | Current |
| --- | --- | --- |
| Replacement Edge | `>= 15%` | `0.69%` |
| MDD_2021+ | `>= -70%` | `-41.12%` |
| CAGR_core (2023~2025) | `>= 20%` | `37.78%` |

## UI / 결과 산출 게이트 (v4_0)
| 항목 | 기준 |
| --- | --- |
| `ui/index.html` 존재 | `invest/stages/stage6/outputs/reports/stage_updates/vX/ui/index.html` |
| 템플릿 패리티 | `KPI 섹션`, `gate 요약`, `교체 판단`, `최근 변동`, `차트 2종` 노출 |
| 그래프 링크 방식 | `<img src="charts/...png">` (Base64 금지) |

## 기타 게이트 (v4_0)
| Gate | 기준 |
| --- | --- |
| gate1 | 36개 모델 정상 실행 |
| gate2 | 가중 선발 내부 일관성 PASS |
| gate3 | numeric 최종 승자 금지 |
| gate5 | 월교체 상한/쿨다운/소프트단계 준수 PASS |
| gate6 | MDD 구간 분리(full/2021+/core) PASS |
| gate7 | UI 템플릿 필수 필드 일치 |
| gate8 | readable 필수 필드 포함 PASS |
| gate9 | UI 템플릿 산출물 일관성 PASS |

## KPI Rendering Contract
- `KPI` 판정은 수치 기반이며 `ui/index.html`은 시각화 산출물이다.
- `ui/index.html` 필수 노출 항목
  - Stage6 핵심 KPI 카드(총수익률/CAGR/MDD/판정)
  - Gate 요약(PASS/FAIL)
  - 교체 판단 상세(Edge/Persistence/Confidence)
  - 최근 포트폴리오 변경 이력
  - 차트 2종(연도별 리셋/연속 누적)
