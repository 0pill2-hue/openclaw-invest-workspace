# KPI_MASTER

> canonical: 스테이지별 KPI 수치 기준 전용 문서  
> location: `docs/invest/`  
> paired_rulebook: `RULEBOOK_MASTER.md`  
> status: ACTIVE  
> created: 2026-02-22

---

## 목적

- 각 단계의 "통과 기준(KPI)"을 수치로 고정한다.
- RULEBOOK_MASTER(실행 하드룰)와 분리하여 **평가 합격 수치**만 여기서 정의한다.
- 신규 버전 출시 시 이 문서를 먼저 확인하고, 변경 시 날짜+사유를 기록한다.

---

## 공통 원칙

- KPI 수치는 주인님 승인 없이 임의 변경 금지
- 수치 미달 → 해당 단계 FAIL, 다음 단계 진입 금지 (`STRATEGY_MASTER.md` 단계 우회 금지 원칙)
- 결과 등급(`DRAFT / VALIDATED / PRODUCTION`)은 KPI 수치와 무관하게 별도 판정

---

## Stage1 — 데이터 수집 KPI

| KPI | 기준값 | 비고 |
| --- | --- | --- |
| 수집 성공률 | ≥ 98% | 전체 대상 종목(OHLCV/수급) 기준 일별 |
| 연속 누락 허용 | < 3일/심볼 | 3일 연속 시 DC-01 발동, 해당 심볼 차단 |
| 수집 완료 신선도 | 당일 06:00 이전 | 장 개시 전 완료 필수 |
| 격리(quarantine)율 | < 5% | Stage02 투입 전 기준 |
| Health State | ok=true, grade=VALIDATED | `memory/health-state.json` 기준 |
| Checkpoint Gate | ok=true | `stage01_checkpoint_gate.py` 결과 |

---

## Stage2 — 데이터 정제 KPI

| KPI | 기준값 | 비고 |
| --- | --- | --- |
| 보존법칙 (QG-02-01) | count(raw) == count(clean) + count(quarantine) | 위반 시 STOP_PIPELINE 필수 |
| Logical Invariant 위반 (QG-02-02) | 0건 | High≥Low, High≥Close, Low≤Close |
| 시간 단조성 위반 (QG-02-03) | 0건 | Date 인덱스 엄격 단조 증가 |
| 격리율 (QG-02-04) | < 15% | quarantine_count / total_count |
| STOP_PIPELINE 발생 | 0회 | 발생 시 Stage04 진입 금지 |

---

## Stage4 — 정제 검증 KPI

| KPI | 기준값 | 비고 |
| --- | --- | --- |
| 독립 FAIL 항목 수 (QG-03-01) | ≤ 3건 | `verdict_*.json` `summary.FAIL` 기준 |
| 스키마 준수율 (QG-03-02) | 100% | `schemas/*.json` 기준 |
| 이상치 미검증 (QG-03-03) | 0건 | 수익률 >20% 건은 모두 교차 확인 후 PASS |
| 샘플링 오류율 (QG-03-04) | < 1% | 랜덤 10% 샘플 기준 |
| BLOCK_STAGE_04 발생 | 0회 | CRITICAL 태그 발생 시 4단계 진입 금지 |

---

## Stage5 — VALIDATED 밸류 산출 KPI

| KPI | 기준값 | 비고 |
| --- | --- | --- |
| 결과 등급 | VALIDATED 이상 | DRAFT 상태로 Stage06 진입 금지 |
| NaN 비율 (QG-04-02) | < 0.5% | VALUE_SCORE 기준 (lead-in 구간 제외) |
| Z-Score 정규화 (QG-04-01) | ㅣMeanㅣ < 0.05, ㅣStd-1.0ㅣ < 0.1 | factor scores 기준 |
| 유동성 필터 준수 (QG-04-03) | 100% | 기준 이하 종목은 null score 필수 |
| 연속성 WARN 비율 (QG-04-04) | < 70% | 초과 시 ACCEPT_AS_DRAFT 처리 |

---

## Stage6 — 베이스라인 비교/선발 KPI

### Hard Gate (gate4) — 교체 판단 합격 기준

모든 항목 통과 시 gate4 PASS. 하나라도 미달 시 FAIL.

| KPI | 기준값 | 현재값(v4_0) |
| --- | --- | --- |
| Replacement Edge | ≥ 15% | 0.69% ❌ |
| MDD_2021+ | ≥ -70% | -41.12% ✅ |
| CAGR_core (2023~2025) | ≥ 20% | 37.78% ✅ |

### Soft Gate (교체 판단 보조)

| KPI | 기준값 | 비고 |
| --- | --- | --- |
| Persistence | 3구간 중 ≥ 2 통과 | 2021-22 / 2023-24 / 2025+ 구간 |
| Confidence Score | ≥ 0.7 | 0.7 미만 시 교체 보류 |

### 전략 목표 KPI (장기)

> 교체 합격 기준과 별개로 전략 성과를 평가하는 기준

| KPI | 목표값 | 비고 |
| --- | --- | --- |
| CAGR (long-term) | ≥ 70% | 연평균 기준, 공식 KPI |
| CAGR (2025 스트레치) | ≥ 300% | 별도 추적, 기본 KPI와 분리 |
| vs KOSPI 초과수익 | > 0% | 공식 평가 구간(2021~현재) 기준 |
| MDD_full 모니터링 구간 | -50% 초과 시 경고 | 필수 차단 기준 아님, 리뷰 트리거 |

### UI/결과 산출 게이트 (v4_0)

| 항목 | 기준 | 비고 |
| --- | --- | --- |
| `ui/index.html` 존재 | `invest/stages/stage6/outputs/reports/stage_updates/vX/ui/index.html` | stage06 결과와 동일한 필수 시각화 항목 포함 |
| 템플릿 패리티 | `KPI` 섹션/`gate 요약`/`교체 판단`/`최근 변동`/`차트 2종` 항목 노출 | v3 템플릿 기준 |
| 그래프 링크 방식 | `<img src="charts/...png">` | Base64 미사용 (토큰/유지보수성) |

### 기타 게이트 (v4_0 기준)

| Gate | 기준 | 비고 |
| --- | --- | --- |
| gate1 | 36개 모델 정상 실행 | 10/10/10/6 트랙 |
| gate2 | 가중 선발 내부 일관성 | PASS |
| gate3 | numeric 최종 승자 금지 | 고정 정책 |
| gate5 | 월교체 상한/쿨다운/소프트단계 준수 | PASS |
| gate6 | MDD 구간 분리(full/2021+/core) | PASS |
| gate7 | UI 템플릿 필수 필드 일치 | 별도 체크 |
| gate8 | readable 필수 필드 포함 | PASS |
| gate9 | UI 템플릿 산출물 일관성 | PASS (ui/index.html 기반, charts 링크 방식) |

### Stage6 KPI 산출 산출물 규칙(고정)

- `KPI` 판정은 수치 기반, `ui/index.html`은 판정 시각화 산출물이다.
- `ui/index.html`은 아래 항목을 반드시 노출해야 한다.
  - Stage6 핵심 KPI 카드(총수익률/CAGR/MDD/판정)
  - Gate 요약(PASS/FAIL)
  - 교체 판단 상세(Edge/Persistence/Confidence)
  - 최근 포트폴리오 변경 이력(최근 N건)
  - 차트 2종(연도별 리셋/연속 누적)

---

## 변경 이력

| 날짜 | 변경 내용 | 사유 |
| --- | --- | --- |
| 2026-02-22 | 최초 작성 (stage1~5 KPI 정의) | 룰북 분산 문제 해결, 수치 기준 공식화 |
| 2026-02-22 | `ui/index.html` 템플릿을 Stage6 KPI 출력 규범에 반영 | v4_0 링크형 대시보드 템플릿을 KPI 산출 산출물의 일관성 규칙으로 통합 |
| 2026-03-03 | 하단 작업로그성 섹션(what/why/next/중요 결정) 제거 후 변경 이력으로 통합 정리 | KPI 문서 오염 제거 및 canonical 형식 복구 |
