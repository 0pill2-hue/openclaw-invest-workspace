# 워크스페이스 즉시 적용안 (Refine-Validate-Value)

## 1. 우선 수정 스크립트 선정
- **1순위 (정제):** `invest/scripts/refine_quant_data.py` (OHLCV 이상치/결측치 처리 로직 강화)
- **2순위 (검증):** `invest/scripts/validate_quant_data.py` (수익률 이상치 검출 기준 정교화)
- **3순위 (밸류):** `invest/scripts/calculate_stage3_values.py` (정제된 데이터 기반 팩터 계산 무결성 확보)

## 2. 최소 코드 변경안

### 2.1 invest/scripts/refine_quant_data.py 수정
- `fix_ohlcv` 함수에 수익률 이상치(>80%) 및 0 가격(Halt 제외) 보정 로직 추가.
```python
def fix_ohlcv(df, market='KR'):
    # ... 기존 로직 ...
    # 추가: 가격 0인 행 제거 (거래량 0인 정지 상태는 허용할지 검토 필요하나, 일단 팩터 계산 위해 제거)
    df = df[df['Close'] > 0]
    
    # 추가: 수익률 이상치 처리 (80% 초과 시 전일 종가 유지 또는 해당 행 제거)
    ret = df['Close'].pct_change().abs()
    df = df[ret < 0.8].copy() 
    return df
```

### 2.2 invest/scripts/validate_quant_data.py 수정
- WARN 상태인 수익률 이상치 검출 로직을 `validate_ohlcv`에 명시적으로 추가.
```python
def validate_ohlcv(df, market='KR'):
    # ... 기존 로직 ...
    # 추가: 수익률 이상치 검토
    ret = df['Close'].pct_change().abs()
    if (ret > 0.8).any():
        errors.append("Return outlier (>80%) detected")
    return errors
```

## 3. 보고 포맷 (STAGE3_SUMMARY)
매 실행 시 `invest/reports/stage_updates/SUMMARY_YYYYMMDD.md` 생성:
```markdown
# Stage 3 가치 산출 요약 (YYYY-MM-DD)
- **정제율:** 99.8% (Issue: 68 -> 2)
- **검증결과:** PASS (KR/US OHLCV WARN 해결 완료)
- **주요 팩터 분포:**
  - VAL_MOM_20: Mean 0.02, Std 0.05
  - VALUE_SCORE: Top 10% 종목군 식별 완료
- **특이사항:** 상한가/하한가 외의 비정상적 점프 데이터 제거됨.
```

## 4. 24시간 실행 계획

| 시각 (KST) | 작업 내용 | 비고 |
| :--- | :--- | :--- |
| **00:00 (H+0)** | `refine_quant_data.py` 수정 및 재실행 | 이상치 처리 로직 반영 |
| **01:00 (H+1)** | `validate_quant_data.py` 검증 수행 | `production` 데이터 무결성 최종 확인 |
| **02:00 (H+2)** | `calculate_stage3_values.py` 전체 시장 실행 | 팩터(MOM, FLOW, LIQ, RISK) 산출 |
| **09:00 (H+9)** | 오전 정기 보고 (STAGE3_SUMMARY) | 주인님께 결과 브리핑 |
| **14:00 (H+14)** | 팩터 안정성 테스트 (Z-score Rolling 검증) | 이상 급등락 종목 필터링 품질 체크 |
| **23:00 (H+23)** | 차기 스테이지(Stage 4: Baseline) 준비 완료 보고 | TASKS.md 업데이트 |

---
**보고 예정:** 내일 오전 09:00 KST까지 정제 결과 및 팩터 분포 리포트를 제출하겠습니다.
