# 거버넌스/Lineage/등급분리 전수조사 보고서

> **문서 등급:** INTERNAL AUDIT  
> **감사 일시:** 2026-02-18 01:05 KST  
> **감사 범위:** `invest/**/*.py`, `invest/scripts/**/*.py`, `invest/reports/stage_updates/*.md`  
> **총 점검 파일:** Python 62개, Markdown 10개  

---

## 📋 총평 요약

| 분류 | 건수 |
|------|------|
| 🔴 즉시조치 (P1~P4) | **4건** |
| 🟠 48시간조치 (P5~P7) | **3건** |
| 🟡 후순위 (P8~P10) | **3건** |
| **합계** | **10건** |

**핵심 결론:**  
- `backtest_compare.py`가 **raw 데이터 직접 읽기** → 정제/검증 게이트 완전 우회 (P1)  
- manifest(run_id/input_hash/output_hash) 생성은 `backtest_compare.py`에만 존재, **핵심 파이프라인 9개 스크립트 누락** (P2)  
- **5단계에서 10단계 역할(운영 지정) 수행** — 7단계 게이트 미통과 상태 (P3)  
- `generate_chart.py` 결과물이 **등급 없이 results/ 루트에 저장** (P4)  

---

## 🔴 위험 리스트 (우선순위 1~10)

### P1 — 백테스트가 raw 데이터 직접 읽음 【즉시조치】

**파일:** `invest/backtest_compare.py` (→ `invest/scripts/stage5_baseline_fixed_run_20260218.py`도 동일 경로 상속)

```python
OHLCV_DIR  = os.path.join(BASE_DIR, 'data/raw/kr/ohlcv')   # 위반
SUPPLY_DIR = os.path.join(BASE_DIR, 'data/raw/kr/supply')  # 위반
```

**위험:** 정제(onepass_refine_full.py)·검증(validate_refine_independent.py) 게이트를 **완전히 우회**한 raw 데이터로 백테스트 수행. 결과물의 입력 품질 보증 없음. stage5도 `from invest.backtest_compare import`로 동일 경로 상속.

**조치:** 
```python
OHLCV_DIR  = os.path.join(BASE_DIR, 'data/clean/production/kr/ohlcv')
SUPPLY_DIR = os.path.join(BASE_DIR, 'data/clean/production/kr/supply')
```

---

### P2 — 핵심 파이프라인 스크립트 manifest 생성 전면 누락 【즉시조치】

**manifest 생성 현황:**

| 스크립트 | run_id | input_hash | output_hash | 강제 검증 |
|----------|:------:|:----------:|:-----------:|:---------:|
| `backtest_compare.py` | ✅ | ✅ | ✅ | ✅ (RuntimeError) |
| `onepass_refine_full.py` | ❌ | ❌ | ❌ | ❌ |
| `validate_refine_independent.py` | ❌ | ❌ | ❌ | ❌ |
| `calculate_stage3_values.py` | ❌ | ❌ | ❌ | ❌ |
| `stage4_hardening_3items.py` | ❌ | ❌ | ❌ | ❌ |
| `stage5_baseline_fixed_run_20260218.py` | ❌ | ❌ | ❌ | ❌ |
| `daily_update.py` | ❌ | ❌ | ❌ | ❌ |
| `run_full_collection.py` | ❌ | ❌ | ❌ | ❌ |
| `refine_quant_data.py` | ❌ | ❌ | ❌ | ❌ |
| `compute_money_flow_sector_score.py` | ❌ | ❌ | ❌ | ❌ |

`run_manifest.py`의 `write_run_manifest()` 함수는 구현되어 있으나 `structure_md_corpus.py`, `organize_existing_data.py` 2개에만 호출됨. 핵심 단계(1~5단계) 스크립트에 전무.

**위험:** 단계 간 데이터 계보 추적 불가. 어떤 입력이 어떤 출력을 만들었는지 검증할 방법 없음. 재현성 보증 불가.

**조치:**  
1단계(`onepass_refine_full.py`) → 2단계(`validate_refine_independent.py`) → 3단계(`calculate_stage3_values.py`) → 4단계(`stage4_hardening_3items.py`) 각각에 manifest 필수 생성 코드 추가.  
`run_manifest.py`의 `write_run_manifest()` 호출 + 생성 실패 시 `raise RuntimeError` 강제화.

---

### P3 — 5단계에서 10단계 역할(운영 지정) 수행 — 게이트 우회 【즉시조치】

**관련 파일:**
- `invest/reports/stage_updates/STAGE05_BASELINE_FIXED_RUN_20260218.md`  
- `invest/reports/stage_updates/stage07/stage07_purged_cv_oos.md` (`status: REQUIRED_NEXT_GATE`)

**위반 내용:**  
`STAGE05_BASELINE_FIXED_RUN_20260218.md`에서 이미 **운영1: Hybrid, 감시2: Quant·Text** 지정 완료.  
그러나 `stage07_purged_cv_oos.md`의 상태는 `REQUIRED_NEXT_GATE` — 즉 **7단계 Purged CV/OOS 검증이 미완료**인 상태에서 10단계 역할이 결정된 것.

```yaml
# stage07_purged_cv_oos.md (미완료)
status: REQUIRED_NEXT_GATE
must_check:
  - TimeSeries OOS + Calibration 검증 통과 전 채택 금지

# STAGE05 (이미 지정)
roles:
  operate: Hybrid      ← 7단계 전 채택 금지인데 이미 운영 지정
  monitor: [Quant, Text]
```

**drop_criteria_v1** 자체에 `governance violation (DRAFT 운영투입 / 7단계 미통과 채택 / 등급위반 보고)`를 hard_drop으로 명시하고 있음에도 이를 위반.

**위험:** 7~9단계 검증을 우회하고 운영 역할이 사실상 확정된 상태로 관리됨. 문서 상으로는 DRAFT/금지라고 표기되어 있으나 실무 의사결정에 활용될 위험.

**조치:**  
`stage05` 문서에서 운영/감시 지정 표현을 **"잠정 후보 (7단계 통과 전 확정 불가)"**로 변경. 10단계 문서(`stage10_adopt_hold_promote.md`)를 7단계 완료 전 작성 금지 명시.

---

### P4 — generate_chart.py: 등급 없이 results/ 루트에 저장 【즉시조치】

**파일:** `invest/results/generate_chart.py`

```python
OUTPUT_DIR = '/Users/jobiseu/.openclaw/workspace/invest/results'  # 루트 직접
png_path = f'{OUTPUT_DIR}/annual_returns_comparison_v2.png'       # 등급 없음
```

**위반 내용:**
- `RESULT_GOVERNANCE.md`의 물리 분리 규칙(`results/test/` 사용) 위반
- `results/annual_returns_comparison_v2.png` 파일에 DRAFT 워터마크 없음
- 등급(DRAFT/VALIDATED/PRODUCTION) 표기 없음
- hardcoded 수익률 데이터(2016-2024)를 비고정 경로에 저장

**위험:** `results/` 루트의 파일이 공식 결과로 오인될 수 있음. AGENTS.md의 "DRAFT 결과는 TEST ONLY 워터마크 필수" 규칙 위반.

**조치:**
```python
OUTPUT_DIR = '.../invest/results/test'  # 변경
# 파일명에 _DRAFT_TESTONLY 접미어 추가
# DRAFT/TEST ONLY 워터마크 matplotlib 텍스트 추가
```

---

### P5 — invest/scripts/refine_quant_data.py, validate_quant_data.py, refine_text_data.py → clean/ 직접 사용 【48시간】

**파일들:**

| 파일 | 위반 경로 |
|------|-----------|
| `invest/scripts/refine_quant_data.py` | `clean/kr/ohlcv`, `clean/us/ohlcv`, `clean/kr/supply` 직접 저장 |
| `invest/scripts/validate_quant_data.py` | `clean/kr/ohlcv`, `clean/us/ohlcv`, `clean/kr/supply` 직접 읽기 |
| `invest/scripts/refine_text_data.py` | `clean/text/` 직접 저장 |
| `invest/scripts/qc_cleaning_10pct.py` | `clean/kr_ohlcv`, `clean/us_ohlcv` 직접 저장 |

**올바른 경로:** `clean/production/` 하위 사용 필수  
`onepass_refine_full.py`, `feature_engineer.py`, `validate_refine_independent.py` 등 메인 스크립트들은 `clean/production/` 올바르게 사용.

**위험:**  
`invest/scripts/` 의 구형 스크립트들이 `clean/` 루트에 쓰면 `clean/production/`과 다른 정제 기준의 파일이 공존. 어떤 것이 공식 정제 데이터인지 혼동 발생. 특히 `validate_quant_data.py`가 `clean/` 루트를 읽으면 production 외 파일을 검증 통과로 처리할 수 있음.

**조치:** 경로를 `clean/production/` 하위로 통일. 기존 `clean/kr/`, `clean/us/`, `clean/text/` 디렉토리를 `clean/production/` 내부로 마이그레이션 또는 deprecated 표시.

---

### P6 — Stage 상태 등급 표기 혼재 (비표준 status 사용) 【48시간】

**현황:**

| 파일 | 현재 status | 표준 여부 |
|------|-------------|-----------|
| `stage01_data_cleaning.md` | `DRAFT` | ✅ |
| `stage02_cleaning_validation.md` | `DRAFT` | ✅ |
| `stage03_validated_value.md` | `IN_PROGRESS` | ❌ 비표준 |
| `stage04_baseline_3track.md` | `FIXED` | ❌ 비표준 |
| `stage05_candidate_gen_v1.md` | `DRAFT` | ✅ |
| `stage06_candidate_stage_cut.md` | `DRAFT` | ✅ |
| `stage07_purged_cv_oos.md` | `REQUIRED_NEXT_GATE` | ❌ 비표준 |
| `stage08_cost_turnover_risk.md` | `DRAFT` | ✅ |
| `stage09_cross_review.md` | `DRAFT` | ✅ |
| `stage10_adopt_hold_promote.md` | `DRAFT` | ✅ |

**위험:** `FIXED`, `IN_PROGRESS`, `REQUIRED_NEXT_GATE` 등 비표준 상태가 자동화 스크립트나 `check_reports.py`에서 파싱 오류 또는 오분류로 이어질 수 있음. 게이트 통과 여부 판단이 불명확해짐.

**조치:** 표준 `status` 값을 `DRAFT | VALIDATED | PRODUCTION | BLOCKED | DEPRECATED`로 제한. `stage03` → `DRAFT`, `stage04` → `DRAFT`, `stage07` → `BLOCKED` 로 수정.

---

### P7 — daily_update.py: 수집 실패 시 계속 진행 (게이트 없음) 【48시간】

**파일:** `invest/scripts/daily_update.py`

```python
failures = []
for script in scripts:
    ok, err = run_script(script)
    if not ok:
        failures.append({"script": script, "error": err})   # 기록만
    time.sleep(2)                                           # 계속 진행
# ← 실패 시 중단 없음, 이후 단계도 그대로 실행
```

**위험:**  
필수 데이터(kr/ohlcv, kr/supply 등) 수집 실패 시에도 파이프라인이 계속 진행. 불완전 데이터가 정제→검증→밸류 단계로 흘러들어 결과 오염 가능. `status.json`만 기록하고 실패 알림이나 차단이 없음.

**조치:**
```python
# 필수 스크립트 구분 (critical vs optional)
CRITICAL_SCRIPTS = ['fetch_stock_list.py', 'fetch_ohlcv.py', 'fetch_supply.py']
for script in CRITICAL_SCRIPTS:
    ok, err = run_script(script)
    if not ok:
        raise RuntimeError(f"Critical script failed: {script} — {err}")
```

---

### P8 — compute_money_flow_sector_score.py → clean/ 직접 읽기 【후순위】

**파일:** `invest/scripts/compute_money_flow_sector_score.py`

```python
IN_PATH = '.../data/clean/market/sector_flow_input.csv'   # production 없이
```

`clean/market/` 경로가 `clean/production/market/`이 아님. 공식 정제 데이터 경로와 불일치.

**조치:** `clean/production/market/sector_flow_input.csv`로 변경.

---

### P9 — extract_coupling_signals.py → raw 직접 읽기 【후순위】

**파일:** `invest/scripts/extract_coupling_signals.py`

```python
posts_dir    = '.../data/raw/text/blog'       # raw 직접
premium_dir  = '.../data/raw/text/premium/startale'  # raw 직접
tg_dir       = '.../data/raw/text/telegram'   # raw 직접
```

정제된 `clean/production/text/` 대신 raw 데이터에서 커플링 시그널 추출. 잡음·오염 텍스트가 분석에 포함될 수 있음.

**조치:** `clean/production/text/` 경로로 변경.

---

### P10 — STAGE3_VALIDATION_SONNET: VALIDATED 판정 후 물리 폴더 미이동 【후순위】

**파일:** `invest/reports/stage_updates/STAGE3_VALIDATION_SONNET_20260218.md`

```
- **검증 등급:** VALIDATED
```

그러나 `invest/data/validated/` 폴더는 비어 있으며, `invest/data/value/stage3/`가 `validated/` 와 분리되지 않음.

AGENTS.md: `"Test/validated/production outputs must be physically separated"`

**위험:** VALIDATED 판정 받은 Stage3 산출물이 여전히 `value/stage3/` 에 위치하며 DRAFT 산출물과 물리적으로 동일 경로. 혼용 가능성.

**조치:** VALIDATED 판정 후 `invest/data/validated/value/stage3/` 로 복사 또는 심볼릭 링크. `value/stage3/`는 DRAFT/Working 취급으로 명시.

---

## 📊 분류별 조치 목록

### 🔴 즉시조치 (P1~P4)

| 우선순위 | 파일 | 위반 유형 | 조치 |
|----------|------|-----------|------|
| P1 | `invest/backtest_compare.py` | raw 직접 읽기 (게이트 우회) | 입력 경로 → `clean/production/` |
| P2 | `onepass_refine_full.py` 외 9개 | manifest 전면 누락 | `write_run_manifest()` 필수 추가 |
| P3 | `STAGE05_BASELINE_FIXED_RUN_20260218.md` | 7단계 미통과 운영 지정 | 지정 표현 "잠정 후보"로 정정 |
| P4 | `invest/results/generate_chart.py` | 등급 없이 results/ 루트 저장 | `results/test/` + DRAFT 워터마크 |

### 🟠 48시간조치 (P5~P7)

| 우선순위 | 파일 | 위반 유형 | 조치 |
|----------|------|-----------|------|
| P5 | `refine_quant_data.py`, `validate_quant_data.py`, `refine_text_data.py`, `qc_cleaning_10pct.py` | clean/ 직접 사용 | `clean/production/` 경로 통일 |
| P6 | `stage03,04,07` MD 파일들 | 비표준 status 표기 | DRAFT/BLOCKED 표준화 |
| P7 | `daily_update.py` | 수집 실패 시 계속 진행 | critical 스크립트 실패 시 중단 |

### 🟡 후순위 (P8~P10)

| 우선순위 | 파일 | 위반 유형 | 조치 |
|----------|------|-----------|------|
| P8 | `compute_money_flow_sector_score.py` | clean/ 직접 읽기 | `clean/production/` 변경 |
| P9 | `extract_coupling_signals.py` | raw 직접 읽기 | `clean/production/text/` 변경 |
| P10 | `STAGE3_VALIDATION_SONNET_20260218.md` | VALIDATED 판정 후 물리 미분리 | `validated/value/stage3/` 이동 |

---

## 🔍 점검 항목별 요약

### ① DRAFT/VALIDATED/PRODUCTION 분리 위반

| 구분 | 위반 파일 | 설명 |
|------|-----------|------|
| 경로 혼재 | `refine_quant_data.py`, `validate_quant_data.py`, `refine_text_data.py`, `qc_cleaning_10pct.py` | `clean/` 직접 → `clean/production/` 미사용 |
| 결과 루트 저장 | `generate_chart.py` | `results/` 루트 → `results/test/` 미사용 |
| VALIDATED 미이동 | `data/value/stage3/` | 물리 validated/ 폴더 비어있음 |
| 올바른 사례 ✅ | `feature_engineer.py`, `onepass_refine_full.py`, `backtest_compare.py`(등급) | production 경로 또는 등급 표기 준수 |

### ② Manifest (run_id/input_hash/output_hash) 누락

`write_run_manifest()` 호출 현황:
- ✅ 구현됨: `run_manifest.py`
- ✅ 호출됨: `backtest_compare.py`, `structure_md_corpus.py`, `organize_existing_data.py`
- ❌ **누락**: 나머지 주요 파이프라인 스크립트 전부

### ③ 10단계/11단계 혼선 포인트

```
현재 단계 상태:
1단계  DRAFT   → (정제)
2단계  DRAFT   → (검증)
3단계  IN_PROG → (밸류)   VALIDATED 판정(Sonnet) 있으나 미반영
4단계  FIXED   → (Baseline)
5단계  DRAFT   → (Candidate Gen) ← 여기서 이미 운영1/감시2 지정 완료 ⚠️
6단계  DRAFT   →
7단계  REQUIRED_NEXT_GATE → ← 미완료인데 5단계에서 채택 결정됨 ⚠️
8단계  DRAFT   →
9단계  DRAFT   →
10단계 DRAFT   → (Adopt/Hold/Promote)
```

**혼선:** 5단계 문서가 10단계 역할(운영/감시 지정)을 수행함. 7→8→9→10단계 게이트가 사실상 형식화될 위험.

### ④ 단계 게이트 우회 가능 코드

| 코드 위치 | 우회 방식 | 위험도 |
|-----------|-----------|--------|
| `backtest_compare.py:46-47` | raw 직접 읽기 | 🔴 높음 |
| `daily_update.py:40-50` | 실패 기록 후 계속 | 🟠 중간 |
| `run_full_collection.py` | 후처리 실패 시에만 중단, 수집 실패는 통과 | 🟠 중간 |
| `onepass_refine_full.py:~210` | 예외 발생 시 quarantine 저장 후 계속 진행 | 🟡 낮음 |

---

## ✅ 양호 항목 (참고)

- `backtest_compare.py`: DRAFT 등급, `results/test/` 저장, manifest RuntimeError 강제 ✅
- `feature_engineer.py`: `_guard_no_raw_path()` raw 경로 접근 차단 ✅
- `validate_refine_independent.py`: GR-1 보존법칙, GR-2 Blind-review 분리, GR-3 L3캡 구현 ✅
- `walk_forward_validator.py`: OOS 분리 검증 구조 양호 ✅
- `stage05_baseline_fixed_run_20260218.py`: grade/watermark JSON 내 명시 ✅
- `RESULT_GOVERNANCE.md`: 등급 체계 문서화 완료 ✅
- `onepass_refine_full.py`: 증분 처리 인덱스, quarantine 보존 ✅

---

## 📅 조치 일정

| 우선순위 | 마감 | 담당 |
|----------|------|------|
| P1 — raw→clean/production 경로 수정 | **즉시** | invest/backtest_compare.py |
| P2 — 핵심 스크립트 manifest 추가 | **즉시** | 1~4단계 스크립트 전체 |
| P3 — 5단계 운영 지정 표현 정정 | **즉시** | STAGE05 MD 파일 |
| P4 — generate_chart.py 경로+등급 수정 | **즉시** | results/generate_chart.py |
| P5 — invest/scripts/ 경로 clean/production 통일 | 48h | 4개 파일 |
| P6 — stage MD status 표준화 | 48h | 3개 파일 |
| P7 — daily_update.py critical 게이트 | 48h | daily_update.py |
| P8~P10 | 후순위 | 각 해당 파일 |

---

*생성: 2026-02-18 01:05 KST | 감사자: Subagent (full-audit-governance-lineage) | 검토 대상: 메인 에이전트 + 주인님*
