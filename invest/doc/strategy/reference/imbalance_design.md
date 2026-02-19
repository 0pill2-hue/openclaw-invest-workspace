# 투자 데이터 불균형 문제 대응 모델 파이프라인 설계

투자 데이터의 불균형(Imbalance) 문제는 단순한 수량 차이를 넘어, **정보 밀도와 국면(Regime)의 비대칭성**에서 기인합니다. 이를 해결하기 위한 4단계 설계안을 보고합니다.

---

### 1. 투자 데이터 불균형 유형 정의 (Imbalance Taxonomy)

투자 데이터에서 발생하는 불균형은 크게 5가지 차원으로 분류됩니다.

1.  **시장 국면 불균형 (Regime Imbalance):**
    *   강세장(Bull) 대비 약세장(Bear)의 기간이 짧아, 위기 상황에 대한 학습 데이터가 절대적으로 부족함.
2.  **섹터별 특성 불균형 (Sector/Style Imbalance):**
    *   IT/성장주(고변동성, 많은 종목 수) vs 유틸리티/방어주(저변동성, 적은 종목 수) 간의 데이터 편향.
3.  **시가총액/유동성 불균형 (Size & Liquidity Imbalance):**
    *   대형주는 정보가 풍부하고 노이즈가 적으나 샘플 수가 적고, 중소형주는 샘플은 많으나 호가 스프레드 및 노이즈가 큼.
4.  **클래스(수익률) 불균형 (Label Imbalance):**
    *   극단적 상한가/하한가 또는 상위 5% 초과 수익률 종목은 전체의 극소수임 (Fat-tail).
5.  **이벤트 빈도 불균형 (Event/Temporal Imbalance):**
    *   실적 발표, M&A, 공시 등 결정적 트리거 데이터는 비정기적이며 희소함.

---

### 2. 데이터 레벨 보정 (Data-level Mitigation)

학습 데이터셋 구성 단계에서 불균형을 완화하는 전략입니다.

*   **계층적 리샘플링 (Stratified Resampling):**
    *   훈련 데이터 구성 시 섹터(Sector)와 시가총액(Size) 분위수별로 동일한 비중이 뽑히도록 층화 추출을 수행하여 특정 집단에 과적합되는 것을 방지.
*   **샘플 가중치 부여 (Sample Weighting):**
    *   **Recency Weighting:** 최근 데이터에 높은 가중치를 부여하여 현재 시장 국면 반영.
    *   **Liquidity Weighting:** 거래대금이 너무 적은 종목은 가중치를 낮추어 실무 실행 가능성(Execution)을 반영.
    *   **Volatility Scaling:** 변동성이 큰 구간의 샘플은 Inverse-vol 가중치를 주어 학습의 안정성 도모.
*   **합성 데이터 생성 (SMOTE for Finance):**
    *   희귀한 '폭락/급등' 구간의 시계열 패턴을 변동성 클러스터링 기반으로 증강(Augmentation)하여 엣지 케이스 학습 강화.

---

### 3. 학습 및 평가 레벨 보정 (Model & Evaluation Level)

모델 구조와 검증 지표를 통해 편향을 제거하는 전략입니다.

*   **손실 함수 고도화 (Loss Function):**
    *   **Focal Loss:** 맞추기 쉬운 다수 샘플(횡보장)의 가중치는 낮추고, 틀리기 쉬운 소수 샘플(급변동)에 집중.
    *   **Class-balanced Loss:** 샘플 수의 역수에 비례하여 손실을 계산하여 소수 섹터/이벤트의 기여도 보장.
*   **교차 검증 설계 (Validation Strategy):**
    *   **Purged K-Fold:** 시계열 데이터의 전후 오염(Leakage)을 방지하면서, 각 Fold가 특정 국면에 치우치지 않게 'Regime-aware Fold' 구성.
*   **섹터/스타일 중립화 (Neutralization):**
    *   평가 시 전체 정확도가 아닌, 섹터 내 순위(Sector-relative ranking)나 스타일 중립화 후의 IC(Information Coefficient)를 주요 지표로 채택.

---

### 4. 실무 적용 우선순위 (Implementation Roadmap)

리소스 투입 대비 효과가 큰 순서대로 적용합니다.

1.  **[High] 평가 지표 및 검증 셋 교정 (Evaluation First):**
    *   단순 MSE/Accuracy 대신 섹터 중립적 수익률과 Max Drawdown(MDD) 기반 평가 시스템 구축. (잘못된 지표로 인한 오판 방지)
2.  **[High] 시총/유동성 필터링 및 가중치 (Sample Weighting):**
    *   실제 매매 불가능한 유동성 부족 종목을 학습에서 제외하거나 낮은 가중치 부여.
3.  **[Mid] 시장 국면별 층화 추출 (Regime Stratification):**
    *   훈련 세트에 상승/하락/횡보 국면이 균형 있게 포함되도록 데이터셋 믹싱.
4.  **[Low] 합성 데이터 및 복합 손실 함수 (Advanced Tech):**
    *   기본 모델 성능이 안정화된 후, 희귀 이벤트 대응을 위한 SMOTE나 Focal Loss 도입.

---
**보고 완료.** 위 설계안을 바탕으로 현재 파이프라인의 `DataLoader`와 `Loss` 모듈 업데이트를 제안합니다.
