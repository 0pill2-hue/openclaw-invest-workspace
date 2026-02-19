# stage05_result_v3_23_kr

## inputs
- 전체 36개 baseline 처음부터 재실행: numeric10 / qualitative10 / hybrid10 / external6
- 재사용 금지 강제: 이전 버전 결과 incremental reuse 미사용
- 공식 평가 윈도우: official(2021~현재), core(2023~2025), reference(2016~현재)
- 신규 규칙: numeric 최종 승자 불가, 동적 가중치 제어(상태 기반), 교체 +15% edge 유지

## run_command(or process)
- `python3 -m py_compile invest/scripts/stage05_full_recompute_v3_23_kr.py`
- `./venv/bin/python invest/scripts/stage05_full_recompute_v3_23_kr.py`

## outputs
- `invest/results/validated/stage05_baselines_v3_23_kr.json`
- `invest/reports/stage_updates/stage05/v3_23/summary.json`
- `invest/reports/stage_updates/stage05/v3_23/stage05_result_v3_23_kr.md`
- `invest/reports/stage_updates/stage05/v3_23/charts/stage05_v3_23_yearly_continuous_2021plus.png`
- `invest/reports/stage_updates/stage05/v3_23/charts/stage05_v3_23_yearly_reset_2021plus.png`
- `invest/reports/stage_updates/stage05/v3_23/ui/dashboard.html`

## recompute evidence (필수)
- full_recompute=true: true
- reused_models=0
- recomputed_models=36

## quality_gates
- gate1(track 36개, 10/10/10/6): PASS
- gate2(weighted selection internal): PASS
- gate3(numeric 최종 승자 불가): PASS
- gate4(교체 +15% edge): FAIL
- gate5(MDD 분할 full/2021+/core): PASS

## 1) 필수 구간 성과 요약 (승자 기준)
| 구간 | 수익률 | CAGR | MDD |
|---|---:|---:|---:|
| Full(2016~현재) | 4561.52% | 41.80% | -52.16% |
| Official(2021~현재) | - | - | -40.07% |
| Core(2023~2025) | - | - | -40.07% |

## 2) gate/final/repeat/stop 필수 필드
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: FAIL
- gate5: PASS
- final_decision: HOLD_V323_REVIEW_REQUIRED
- repeat_counter: 1
- stop_reason: GATE4_REPLACEMENT_EDGE_BELOW_THRESHOLD

## 3) 승자 상세
| 항목 | 값 |
|---|---|
| model_id | qual_q09_governance_score |
| track | qualitative |
| total_return | 4561.52% |
| CAGR | 41.80% |
| MDD (Full) | -52.16% |
| MDD (2021+) | -40.07% |
| MDD (Core) | -40.07% |
| 교체 Edge | 5.87% (기준 +15% 미달) |

## 4) 주요 변경점 (v3_22 → v3_23)
| 항목 | v3_22 | v3_23 |
|---|---|---|
| 모델 수 | 12 | 36 |
| 트랙 구성 | 3/3/3/3 | 10/10/10/6 |
| Numeric 최종 승자 | 허용 | 불가 |
| 가중치 제어 | 고정 | 동적(상태 기반) |
| 집중 트림 래더 | 적용 | 미적용 |
| MDD 분할 | 단일 | full/2021+/2023-2025 |

## 5) 차트 재현 스펙(형태 고정)
- 생성 스크립트: `invest/scripts/stage05_full_recompute_v3_23_kr.py`
- 실행 커맨드: `./venv/bin/python invest/scripts/stage05_full_recompute_v3_23_kr.py`
- 입력: `invest/results/validated/stage05_baselines_v3_23_kr.json`
- **평가 산출물 canonical 폴더:** `invest/reports/stage_updates/stage05/v3_23/`

### 차트 A (누적 평가용)
- 경로: `invest/reports/stage_updates/stage05/v3_23/charts/stage05_v3_23_yearly_continuous_2021plus.png`
- 기간: 2021+ (일간 축)
- 형태: 일간 연속 곡선

### 차트 B (연도별 리셋 평가용)
- 경로: `invest/reports/stage_updates/stage05/v3_23/charts/stage05_v3_23_yearly_reset_2021plus.png`
- 기간: 2021+ (일간 축)
- 형태: 연도 경계에서 리베이스

### 시각 규칙(색/스타일 고정)
- Top1: `#1f77b4` (blue)
- Top2: `#ff7f0e` (orange)
- Top3: `#2ca02c` (green)
- KOSPI: `#d62728` (red, dashed)
- KOSDAQ: `#9467bd` (purple, dotted)

## 6) UI 대시보드
- 경로: `invest/reports/stage_updates/stage05/v3_23/ui/dashboard.html`
- 포함 내용: 36개 모델 비교표, 승자 상세, MDD 분할, 차트 임베드

## 7) 연도 범위 표기 주의
- 코드에서 `range(..., 2027)`은 Python 상한 미포함 규칙으로 **2026년까지 계산**을 의미한다.
- 본 v3_23 산출물은 2027 데이터를 사용하지 않는다.
