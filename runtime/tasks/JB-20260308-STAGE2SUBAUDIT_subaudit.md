# JB-20260308-STAGE2SUBAUDIT — Stage2 최근 1개월 실데이터 정밀검증

## 결론
**RESULT: FAIL**

검증 기준 기간: **2026-02-08 ~ 2026-03-08**

핵심 실패 사유는 아래 3개입니다.
1. **Stage2 canonical live output 경로가 사실상 비어 있음**
   - `invest/stages/stage2/outputs/clean/production` 파일 수: **0**
   - `invest/stages/stage2/outputs/quarantine/production` 파일 수: **0**
   - 실제로 `find -L invest/stages/stage2/outputs -type f` 결과는 로그 2개만 확인됨.
2. **검증용 full snapshot(`runtime/tmp/stage2_validation_20260308_1635/...`) 기준으로도 최근 1개월 데이터 일부가 Stage2 산출물로 전혀 반영되지 않음**
   - `qualitative/text/telegram`: 최근 활성 56개 raw 파일, clean/quarantine **0**
   - `qualitative/text/premium/startale`: 최근 raw 64개(그중 `Status: SUCCESS` 37개), clean/quarantine **0**
3. **일부 signal / dart raw 파일도 snapshot 기준 clean·quarantine 어디에도 매핑되지 않음**
   - `signal/kr/ohlcv`: 최근 raw 파일 2,882개 중 **112개 미매핑**
   - `signal/kr/supply`: 최근 raw 파일 2,876개 중 **106개 미매핑**
   - `qualitative/kr/dart`: 최근 raw 파일 316개 중 **1개 미매핑**

---

## 검증 대상/근거 경로
- 검증 스냅샷 루트: `runtime/tmp/stage2_validation_20260308_1635/invest/stages/stage2`
- live canonical 루트: `invest/stages/stage2`
- 재현용 분석 스크립트: `runtime/tmp/JB-20260308-STAGE2SUBAUDIT_analyze.py`
- 분석 결과 JSON: `runtime/tmp/JB-20260308-STAGE2SUBAUDIT_stats.json`

---

## 재현 명령
### 1) 전체 통계 재생성
```bash
python3 runtime/tmp/JB-20260308-STAGE2SUBAUDIT_analyze.py
```

### 2) live canonical output 공백 확인
```bash
find -L invest/stages/stage2/outputs -type f | sort
```
예상 관찰: 로그 파일 2개만 출력되고 clean/quarantine 산출물은 없음.

### 3) telegram raw는 최근 데이터가 있으나 output이 0개인 샘플 확인
```bash
ls "runtime/tmp/stage2_validation_20260308_1635/invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/text/telegram/投資_아레테_mstaryun_full.md"
ls "runtime/tmp/stage2_validation_20260308_1635/invest/stages/stage2/outputs/clean/production/qualitative/text/telegram/投資_아레테_mstaryun_full.md"
ls "runtime/tmp/stage2_validation_20260308_1635/invest/stages/stage2/outputs/quarantine/production/qualitative/text/telegram/投資_아레테_mstaryun_full.md"
```
예상 관찰: raw만 존재, clean/quarantine 없음.

### 4) premium SUCCESS raw인데 output이 0개인 샘플 확인
```bash
ls runtime/tmp/stage2_validation_20260308_1635/invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/text/premium/startale/260302114544926lu_d66ee5955ce4.md
ls runtime/tmp/stage2_validation_20260308_1635/invest/stages/stage2/outputs/clean/production/qualitative/text/premium/startale/260302114544926lu_d66ee5955ce4.md
ls runtime/tmp/stage2_validation_20260308_1635/invest/stages/stage2/outputs/quarantine/production/qualitative/text/premium/startale/260302114544926lu_d66ee5955ce4.md
```
예상 관찰: raw는 존재하고 header에 `Status: SUCCESS`가 있으나 clean/quarantine 없음.

### 5) raw signal 중복은 clean/quarantine로 분리되는 샘플 확인
```bash
python3 - <<'PY'
from pathlib import Path
import pandas as pd
root=Path('runtime/tmp/stage2_validation_20260308_1635/invest/stages/stage2')
for rel in [
    'inputs/upstream_stage1/raw/signal/kr/ohlcv/000020.csv',
    'outputs/clean/production/signal/kr/ohlcv/000020.csv',
    'outputs/quarantine/production/signal/kr/ohlcv/000020.csv',
]:
    p=root/rel
    df=pd.read_csv(p)
    print(rel, len(df))
PY
```
예상 관찰: raw 14921행 / clean 2494행 / quarantine 12427행.

---

## 핵심 수치
분석 결과 JSON(`runtime/tmp/JB-20260308-STAGE2SUBAUDIT_stats.json`) 기준.

### A. canonical live output 상태
- `live_clean_total_files`: **0**
- `live_quarantine_total_files`: **0**
- 반면 검증 스냅샷에는
  - `temp_clean_total_files`: **17,129**
  - `temp_quarantine_total_files`: **5,742**

즉, **실제 Stage2 canonical 경로에는 최근 1개월 산출 결과가 비어 있고**, 검증 스냅샷에만 산출물이 존재합니다.

### B. signal 계열
- `signal/kr/ohlcv`
  - 최근 raw 파일: **2,882개**
  - 최근 raw 행: **147,728행**
  - 최신일 범위: **2026-02-11 ~ 2026-03-06**
  - temp 미매핑 raw 파일: **112개**
  - live 미매핑 raw 파일: **2,882개 전체**
- `signal/kr/supply`
  - 최근 raw 파일: **2,876개**
  - 최근 raw 행: **65,930행**
  - 최신일 범위: **2026-02-13 ~ 2026-03-06**
  - temp 미매핑 raw 파일: **106개**
  - live 미매핑 raw 파일: **2,876개 전체**
- `signal/us/ohlcv`
  - 최근 raw 파일: **508개**
  - temp 미매핑: **0개**
  - live 미매핑: **508개 전체**
- `signal/market/macro`
  - 최근 raw 파일: **15개**
  - temp 미매핑: **0개**
  - live 미매핑: **15개 전체**

### C. DART / RSS / selected_articles
- `qualitative/kr/dart`
  - 최근 raw 파일: **316개**
  - 최근 raw 행: **758,330행**
  - 최근 중복 `rcept_no`: **33행**
  - temp 미매핑 raw 파일: **1개**
  - live 미매핑 raw 파일: **316개 전체**
- `qualitative/market/rss`
  - 최근 raw 파일: **192개**
  - 최근 entry: **17,631개**
  - invalid/empty 파일: **1개**
  - temp 미매핑: **0개**
  - live 미매핑: **192개 전체**
- `qualitative/market/news/selected_articles`
  - 최근 raw 파일: **25개**
  - 최근 raw 행: **21,123행**
  - raw duplicate_title_date: **1,051행**
  - quarantine reason 집계
    - `duplicate_canonical_url`: **17,385**
    - `duplicate_title_date`: **1,073**
    - `duplicate_content_fingerprint`: **105**
    - `empty_jsonl`: **1**
  - temp 미매핑: **0개**
  - live 미매핑: **25개 전체**

### D. text 계열
- `qualitative/text/telegram`
  - raw 파일: **67개**
  - 최근 기간에 latest date가 들어오는 파일: **56개**
  - latest date 범위: **2026-02-15 ~ 2026-03-08**
  - temp clean/quarantine: **0 / 0**
  - live clean/quarantine: **0 / 0**
- `qualitative/text/premium/startale`
  - non-archive raw 파일: **708개**
  - 최근 raw 파일: **64개**
  - 이 중 `Status: SUCCESS`: **37개**
  - 이 중 blocked/paywall 계열: **27개**
  - temp clean/quarantine: **0 / 0**
  - live clean/quarantine: **0 / 0**

---

## 샘플 증빙
### 1) telegram raw 최근 데이터 존재
파일: `runtime/tmp/stage2_validation_20260308_1635/invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/text/telegram/投資_아레테_mstaryun_full.md`
- header 샘플:
  - `Date: 2026-03-05 10:49:38`
  - `Date: 2026-03-05 09:52:31`
- 대응 clean/quarantine 파일: **없음**

### 2) premium SUCCESS raw 존재
파일: `runtime/tmp/stage2_validation_20260308_1635/invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/text/premium/startale/260302114544926lu_d66ee5955ce4.md`
- header 샘플:
  - `PublishedAt: 2026.03.02. 오전 11:45`
  - `Status: SUCCESS`
- 대응 clean/quarantine 파일: **없음**

### 3) selected_articles duplicate quarantine 정상 동작 예시
파일:
- raw: `.../inputs/upstream_stage1/raw/qualitative/market/news/selected_articles/selected_articles_20260308-063933.jsonl`
- quarantine: `.../outputs/quarantine/production/qualitative/market/news/selected_articles/selected_articles_20260308-063933.jsonl`

관찰:
- raw 안에 `이란 사태에 널뛰는 환율 | 연합뉴스`가 같은 날짜(2026-03-08)로 다중 반복됨
- quarantine에서 `reason: duplicate_title_date`로 격리됨

### 4) signal duplicate date 분리 예시
파일: `.../signal/kr/ohlcv/000020.csv`
- raw: **14,921행**
- clean: **2,494행**
- quarantine: **12,427행**
- quarantine reason: `duplicate_date`

즉 raw signal 중복 자체는 존재하지만, 스냅샷 기준으로는 clean/quarantine 분리가 동작한 사례가 확인됩니다.

---

## 원인 후보
1. **canonical output 미반영/미동기화**
   - 검증 스냅샷에는 산출물이 있으나 `invest/stages/stage2/outputs/*` live 경로는 비어 있음.
   - Stage2 생성 후 canonical 경로로 반영하는 단계가 누락되었거나, temp snapshot만 생성되고 publish가 되지 않았을 가능성.

2. **refine 대상 폴더 누락 또는 writer 경로/폴더 정책 불일치**
   - telegram / premium은 최근 raw가 분명히 존재하는데 temp snapshot에서도 clean/quarantine가 0.
   - 폴더 exclude, writer routing 오류, output path mismatch, 또는 run 대상 집합 누락 가능성.

3. **일부 KR signal / DART 파일에 대한 미매핑 처리 누락**
   - 일부 raw 파일이 clean/quarantine 어디에도 없는 상태.
   - stale/delisted 종목, 비정상 헤더, schema edge case를 quarantine로도 내리지 못하고 누락했을 가능성.

4. **selected_articles 원천 중복량 과다**
   - duplicate_canonical_url / duplicate_title_date가 매우 큼.
   - 현재 quarantine는 동작하지만, upstream dedupe를 강화하지 않으면 Stage2 부하/노이즈가 지속될 가능성.

---

## 다음 액션 제안
1. **가장 먼저 canonical live output publish 문제를 해결**
   - `invest/stages/stage2/outputs/clean/production` 및 `.../quarantine/production`가 실제 결과물로 채워지도록 publish step 점검.

2. **telegram / premium 폴더를 우선 재검증**
   - 최근 1개월 raw가 있는 상태에서 output이 0개이므로 가장 명확한 FAIL 항목.
   - 폴더 매핑, writer policy, exclude 조건, output rel-path 계산 로직 확인 필요.

3. **KR signal / DART 미매핑 파일 목록 직접 triage**
   - 예: `019440.csv`, `052670.csv`, `052960.csv`, `059180.csv` 등
   - clean으로 보낼지 quarantine로 보낼지 최소한 둘 중 하나는 되게 처리해야 함.

4. **selected_articles upstream dedupe 강화**
   - Stage2 quarantine 전에도 canonical URL / title-date 중복을 줄여 raw 품질을 개선하는 편이 바람직.

---

## 감사 메모
- blog 파일 매핑 수치는 파일-level heuristic이 포함되어 **보조 지표**로만 해석하는 것이 안전합니다.
- 본 FAIL 결론은 blog 수치에 의존하지 않고, 아래의 **명확한 하드 이슈**만으로도 충분히 성립합니다.
  1) live canonical output 공백
  2) telegram 최근 raw 56개 output 0
  3) premium 최근 raw 64개(output 0, 그중 SUCCESS 37개)
  4) 일부 signal / dart raw 미매핑

---

**RESULT: FAIL**
**PROOF: runtime/tasks/JB-20260308-STAGE2SUBAUDIT_subaudit.md ; runtime/tmp/JB-20260308-STAGE2SUBAUDIT_stats.json**
**SUMMARY: 최근 1개월 Stage2는 live 산출물이 비어 있고 telegram/premium/일부 signal이 누락돼 FAIL입니다.**
