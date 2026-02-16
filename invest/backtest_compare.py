"""
내지표 vs 이웃지표 알고리즘 10년 연도별 수익률 비교 백테스트
=============================================================
[DRAFT - TEST ONLY] 본 결과는 검증되지 않은 테스트 결과입니다.
=============================================================
내지표(My Indicator): MA 장기추세 + 모멘텀 기반 전략
이웃지표(Neighbor Indicator): 기관+외국인 수급 모멘텀 기반 전략

데이터: invest/data/ohlcv/*.csv, invest/data/supply/*_supply.csv
기간: 2016-01 ~ 2025-12 (최대 10년)

[수정 이력]
- C1 fix: 신호 시점(T) ≠ 체결 시점(T+1).
          이전 리밸런스 월말 종가 신호 → 다음 리밸런스 월말 시가 체결 (룩어헤드 제거)
- C2 fix: 동적 유니버스. 각 리밸런스 신호 시점 기준 과거 데이터만 사용 (생존편향 완화)
- C3 fix: 결과 거버넌스. DRAFT/TEST ONLY 표기. invest/results/test/ 에 저장
"""

import pandas as pd
import numpy as np
import os
import glob
import warnings
import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
warnings.filterwarnings('ignore')

# ─────────────────────────── C3: 결과 등급 ───────────────────────────
RESULT_GRADE = 'DRAFT'
# DRAFT: 내부 테스트용. TEST ONLY. 공식 결과로 사용 불가.
# 승격 절차: DRAFT → VALIDATED (검증 완료) → PRODUCTION (공식 채택)

# ─────────────────────────── C3: 경로 설정 (results/test/) ───────────────────────────
BASE_DIR   = '/Users/jobiseu/.openclaw/workspace/invest'
OHLCV_DIR  = os.path.join(BASE_DIR, 'data/ohlcv')
SUPPLY_DIR = os.path.join(BASE_DIR, 'data/supply')
# C3: DRAFT 결과는 반드시 results/test/ 에만 저장
OUTPUT_DIR = os.path.join(BASE_DIR, 'results/test')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────── 파라미터 ───────────────────────────
UNIVERSE_SIZE    = 200   # 유니버스 종목 수 (속도 vs 품질 균형)
TOP_N            = 5     # 보유 종목 수
REBALANCE_FREQ   = 'M'   # 월별 리밸런싱
MA_SHORT         = 20    # 단기 MA
MA_LONG          = 60    # 장기 MA
SUPPLY_WINDOW    = 20    # 수급 집계 기간
INITIAL_CAPITAL  = 1_000 # 기준 자본 (정규화)
SLIPPAGE         = 0.005 # 편도 슬리피지 (0.5%)
START_DATE       = '2016-01-01'
END_DATE         = '2025-12-31'
# C2: 유니버스 편입 최소 과거 데이터 (거래일 수)
MIN_HISTORY_DAYS = 120

# ─────────────────────────── C2: 유니버스 구성 (동적) ───────────────────────────
def load_candidate_codes():
    """OHLCV + supply 교집합 6자리 종목코드 후보 반환"""
    supply_codes = {
        os.path.basename(f).replace('_supply.csv', '')
        for f in glob.glob(os.path.join(SUPPLY_DIR, '*_supply.csv'))
    }
    ohlcv_codes = {
        os.path.basename(f).replace('.csv', '')
        for f in glob.glob(os.path.join(OHLCV_DIR, '*.csv'))
    }
    common = sorted(supply_codes & ohlcv_codes)
    # 6자리 숫자 종목코드만 (우선주 등 제외)
    return [c for c in common if c.isdigit() and len(c) == 6]


def load_all_candidate_ohlcv(candidate_codes, limit=500):
    """
    C2: 후보 종목 OHLCV 전체 사전 로드.
    - 미래 참조 금지: 전체 기간 데이터를 메모리에 올리되,
      유니버스 선정은 각 리밸런스 신호 시점 이전 데이터만 사용.
    - limit: 후보 최대 개수 (속도 조절)
    """
    all_ohlcv = {}
    for code in candidate_codes[:limit]:
        path = os.path.join(OHLCV_DIR, f'{code}.csv')
        try:
            df = pd.read_csv(path)
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date').sort_index()
            df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]
            if len(df) >= MIN_HISTORY_DAYS:
                cols = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
                all_ohlcv[code] = df[cols]
        except Exception:
            continue
    return all_ohlcv


def get_dynamic_universe(signal_date, all_ohlcv):
    """
    C2 핵심: 신호 시점 기준 과거 데이터로만 유니버스 동적 구성 (생존편향 완화).

    signal_date 당일까지의 데이터만 참조하여 과거 평균 거래대금 기준
    상위 UNIVERSE_SIZE 종목을 반환. 미래 생존 여부는 참조하지 않음.
    """
    scored = []
    for code, df in all_ohlcv.items():
        # signal_date 당일 포함 이전 데이터만 참조 (미래 데이터 차단)
        hist = df[df.index <= signal_date]
        if len(hist) < MIN_HISTORY_DAYS:
            continue
        # 과거 평균 거래대금(원) 기준 랭킹
        avg_turnover = (hist['Close'] * hist['Volume']).mean()
        scored.append((code, avg_turnover))
    scored.sort(key=lambda x: -x[1])
    return [c for c, _ in scored[:UNIVERSE_SIZE]]


# ─────────────────────────── 데이터 로더 ───────────────────────────
def load_ohlcv(code):
    path = os.path.join(OHLCV_DIR, f'{code}.csv')
    df = pd.read_csv(path)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date').sort_index()
    df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]


def load_supply(code):
    path = os.path.join(SUPPLY_DIR, f'{code}_supply.csv')
    df = pd.read_csv(path, header=0)
    df.columns = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date').sort_index()
    df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]
    return df


# ─────────────────────────── 신호 계산 ───────────────────────────
def compute_my_signal(ohlcv_df):
    """
    내지표: MA 장기추세 + 모멘텀
    - MA20 > MA60 → 상승추세
    - 20일 모멘텀(수익률) > 0
    - 스코어 = 모멘텀 강도 (랭킹용)
    """
    df = ohlcv_df.copy()
    df['MA20'] = df['Close'].rolling(MA_SHORT).mean()
    df['MA60'] = df['Close'].rolling(MA_LONG).mean()
    df['Mom20'] = df['Close'].pct_change(MA_SHORT)
    df['trend_up'] = (df['MA20'] > df['MA60']).astype(int)
    df['signal'] = df['trend_up'] * df['Mom20']  # 추세 있을 때만 모멘텀
    return df


def compute_neighbor_signal(ohlcv_df, supply_df):
    """
    이웃지표: 기관+외국인 수급 모멘텀
    - 20일 외국인+기관 누적 순매수
    - 스코어 = 수급 강도 (가격·거래량 정규화)
    """
    df = ohlcv_df.copy()
    sup = supply_df.reindex(df.index).fillna(0)
    sup['Net'] = sup['Inst'] + sup['Foreign']
    sup['Net20'] = sup['Net'].rolling(SUPPLY_WINDOW).sum()
    df['supply_net20'] = sup['Net20']
    df['supply_signal'] = sup['Net20'] / (df['Close'] * df['Volume'] + 1e-9)
    return df


# ─────────────────────────── C1/C2 백테스트 코어 ───────────────────────────
def run_backtest(all_ohlcv, all_supply, strategy='my_algo'):
    """
    월별 리밸런싱 포트폴리오 백테스트

    [C1 수정] 신호-체결 시점 분리:
      - 신호 시점(signal_date) = rebal_dates[i-1] 월말 종가 기준
      - 체결 시점(exec_date)   = rebal_dates[i]   월말 시가(Open) 기준
      → 신호 계산 후 다음 거래 기회(시가)에 체결: 룩어헤드 바이어스 제거

    [C2 수정] 동적 유니버스:
      - 각 신호 시점 기준 그 이전 데이터로만 유니버스 구성
      - 미래 생존 종목 편향(생존편향) 완화

    strategy: 'my_algo' or 'neighbor_algo'
    """
    print(f"\n  [{strategy}] 신호/가격 데이터 준비 중...")

    all_close_signals = {}  # 종가 기반 신호 (신호 시점 참조용)
    all_open_prices   = {}  # 시가 (C1: 체결 가격)
    all_close_prices  = {}  # 종가 (포트폴리오 평가용)

    for i, (code, ohlcv) in enumerate(all_ohlcv.items()):
        if i % 50 == 0:
            print(f"    {i}/{len(all_ohlcv)} 처리 중...")
        try:
            if len(ohlcv) < 100:
                continue

            if strategy == 'my_algo':
                sig_df = compute_my_signal(ohlcv)
                all_close_signals[code] = sig_df['signal']
            else:  # neighbor_algo
                if code not in all_supply:
                    continue
                sig_df = compute_neighbor_signal(ohlcv, all_supply[code])
                all_close_signals[code] = sig_df['supply_signal']

            # C1: Open 가격 별도 보관 (체결 시 사용)
            if 'Open' in ohlcv.columns:
                all_open_prices[code] = ohlcv['Open']
            all_close_prices[code] = ohlcv['Close']

        except Exception:
            continue

    if not all_close_signals:
        return {}

    signal_df = pd.DataFrame(all_close_signals).sort_index()
    open_df   = pd.DataFrame(all_open_prices).sort_index()   if all_open_prices else pd.DataFrame()
    close_df  = pd.DataFrame(all_close_prices).sort_index()

    # 공통 날짜 정렬
    common_idx = signal_df.index.intersection(close_df.index)
    signal_df  = signal_df.loc[common_idx]
    close_df   = close_df.loc[common_idx]
    if not open_df.empty:
        open_df = open_df.loc[open_df.index.intersection(common_idx)]

    # 월말 리밸런싱 날짜 (실제 마지막 거래일)
    rebal_dates = close_df.resample(REBALANCE_FREQ).last().index

    # 포트폴리오 시뮬레이션
    portfolio_value   = [INITIAL_CAPITAL]
    dates_list        = [close_df.index[0]]
    current_portfolio = {}   # {code: shares}
    cash              = INITIAL_CAPITAL

    # ── C1 핵심: i=1부터 시작, signal_date = i-1월말, exec_date = i월말 ──
    for i in range(1, len(rebal_dates)):
        signal_date = rebal_dates[i - 1]  # 신호 시점: 이전 월말 종가
        exec_date   = rebal_dates[i]      # 체결 시점: 현재 월말 (시가 사용)

        if signal_date not in signal_df.index or exec_date not in close_df.index:
            continue

        # ── 신호: signal_date 종가 기준 (미래 종가 미참조) ──
        sig_snap = signal_df.loc[signal_date].dropna()

        # ── 체결 가격: exec_date 시가 (C1 핵심) ──
        # Open이 없으면 Close로 폴백 (보수적 근사)
        if not open_df.empty and exec_date in open_df.index:
            exec_price_snap = open_df.loc[exec_date].dropna()
        else:
            exec_price_snap = close_df.loc[exec_date].dropna()

        # ── 평가 가격: exec_date 종가 (포트폴리오 가치 계산) ──
        eval_price_snap = close_df.loc[exec_date].dropna()

        # ── C2: 신호 시점 기준 동적 유니버스 (과거 데이터만 참조) ──
        dynamic_univ = get_dynamic_universe(signal_date, all_ohlcv)
        sig_snap = sig_snap[sig_snap.index.isin(dynamic_univ)]

        # ── 종목 선택 (동적 유니버스 내에서 신호 양수 상위 TOP_N) ──
        valid    = sig_snap[sig_snap > 0]
        valid    = valid[valid.index.isin(exec_price_snap.index)]
        selected = valid.nlargest(TOP_N).index.tolist()

        # ── 현재 포트폴리오 평가 (exec_date 종가 기준 청산) ──
        total_value = cash
        for code, shares in current_portfolio.items():
            if code in eval_price_snap.index:
                total_value += shares * eval_price_snap[code] * (1 - SLIPPAGE)

        # ── 리밸런싱 실행 (exec_date 시가 기준 매수) ──
        cash              = total_value
        current_portfolio = {}

        if selected:
            per_stock = total_value / len(selected)
            for code in selected:
                if code in exec_price_snap.index and exec_price_snap[code] > 0:
                    buy_price = exec_price_snap[code] * (1 + SLIPPAGE)
                    shares    = per_stock / buy_price
                    cost      = shares * buy_price
                    if cost <= cash:
                        current_portfolio[code] = shares
                        cash -= cost

        portfolio_value.append(total_value)
        dates_list.append(exec_date)

    # 연도별 수익률 계산
    result_df = pd.DataFrame({'value': portfolio_value}, index=pd.to_datetime(dates_list))
    annual_returns = {}
    for year in sorted(result_df.index.year.unique()):
        year_data = result_df[result_df.index.year == year]
        if len(year_data) < 2:
            continue
        start_val = year_data['value'].iloc[0]
        end_val   = year_data['value'].iloc[-1]
        if start_val > 0:
            annual_returns[year] = round((end_val - start_val) / start_val * 100, 2)

    return annual_returns


# ─────────────────────────── 메인 실행 ───────────────────────────
def main():
    run_ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    print("=" * 60)
    print(f"[{RESULT_GRADE} - TEST ONLY]")
    print("내지표 vs 이웃지표 10년 연도별 수익률 백테스트")
    print("C1/C2/C3 치명 이슈 수정 버전")
    print("=" * 60)
    print("※ 이 결과는 검증되지 않은 DRAFT 결과입니다. 공식 사용 불가.")
    print()

    print("[1] 후보 종목 코드 수집...")
    candidate_codes = load_candidate_codes()
    print(f"  후보 종목: {len(candidate_codes)}개")

    print("[2] OHLCV 전체 사전 로드 (C2 동적 유니버스 준비)...")
    all_ohlcv = load_all_candidate_ohlcv(candidate_codes, limit=500)
    print(f"  로드 완료: {len(all_ohlcv)}개")

    print("[3] 수급 데이터 사전 로드 (이웃지표용)...")
    all_supply = {}
    for code in all_ohlcv:
        try:
            all_supply[code] = load_supply(code)
        except Exception:
            pass
    print(f"  수급 데이터: {len(all_supply)}개")

    print("\n[4] 내지표 알고리즘 백테스트 (C1 룩어헤드 수정 + C2 동적 유니버스)...")
    my_returns = run_backtest(all_ohlcv, all_supply, strategy='my_algo')

    print("\n[5] 이웃지표 알고리즘 백테스트 (C1 룩어헤드 수정 + C2 동적 유니버스)...")
    neighbor_returns = run_backtest(all_ohlcv, all_supply, strategy='neighbor_algo')

    # 결과 통합
    all_years = sorted(set(my_returns.keys()) | set(neighbor_returns.keys()))
    rows = [
        {
            'year': y,
            'my_algo_return': my_returns.get(y),
            'neighbor_algo_return': neighbor_returns.get(y),
        }
        for y in all_years if 2016 <= y <= 2025
    ]
    result_df = pd.DataFrame(rows)

    print("\n[6] C3 결과 저장 (DRAFT / TEST ONLY)...")

    # ── CSV 저장: DRAFT 메타 헤더 포함 ──
    csv_path = os.path.join(OUTPUT_DIR, f'annual_returns_comparison_{run_ts}.csv')
    with open(csv_path, 'w', encoding='utf-8-sig') as f:
        f.write(f'# RESULT_GRADE: {RESULT_GRADE}\n')
        f.write(f'# TEST ONLY - 검증되지 않은 결과. 공식 사용 불가.\n')
        f.write(f'# 생성시각: {run_ts}\n')
        f.write(f'# C1_fix: 신호(signal_date=T-1 월말) → 체결(exec_date=T 시가)\n')
        f.write(f'# C2_fix: 동적 유니버스 (신호 시점 기준 과거 데이터로만 종목 선정)\n')
        f.write(f'# C3_fix: DRAFT 등급, results/test/ 저장\n')
        result_df.to_csv(f, index=False)
    print(f"  CSV: {csv_path}")

    # ── PNG 저장: DRAFT 워터마크 포함 ──
    print("[7] 그래프 생성 (TEST ONLY 워터마크 포함)...")
    fig, ax = plt.subplots(figsize=(14, 7))

    x           = np.arange(len(rows))
    width       = 0.35
    my_vals     = [r['my_algo_return'] or 0 for r in rows]
    nb_vals     = [r['neighbor_algo_return'] or 0 for r in rows]
    years_label = [str(r['year']) for r in rows]

    bars1 = ax.bar(x - width/2, my_vals, width, label='내지표 (MA+모멘텀)', color='steelblue', alpha=0.85)
    bars2 = ax.bar(x + width/2, nb_vals, width, label='이웃지표 (기관+외국인 수급)', color='coral', alpha=0.85)

    for bar in bars1:
        h = bar.get_height()
        ax.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width()/2, h),
                    xytext=(0, 3), textcoords='offset points', ha='center', va='bottom', fontsize=8)
    for bar in bars2:
        h = bar.get_height()
        ax.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width()/2, h),
                    xytext=(0, 3), textcoords='offset points', ha='center', va='bottom', fontsize=8)

    ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
    ax.set_xlabel('연도', fontsize=12)
    ax.set_ylabel('연간 수익률 (%)', fontsize=12)
    ax.set_title(
        f'[{RESULT_GRADE} - TEST ONLY]  내지표 vs 이웃지표 연도별 수익률 비교 (2016-2025)\n'
        f'C1 룩어헤드 제거 · C2 동적 유니버스 · C3 거버넌스 적용',
        fontsize=13, fontweight='bold'
    )
    ax.set_xticks(x)
    ax.set_xticklabels(years_label)
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.4)

    # C3: 워터마크 (대각선 DRAFT)
    fig.text(0.5, 0.5, 'DRAFT - TEST ONLY',
             fontsize=52, color='gray', alpha=0.18,
             ha='center', va='center', rotation=30,
             fontweight='bold', transform=ax.transAxes)

    plt.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, f'annual_returns_comparison_{run_ts}.png')
    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  PNG: {png_path}")

    # ── 콘솔 요약 ──
    print("\n" + "=" * 60)
    print(f"[{RESULT_GRADE} - TEST ONLY] 연도별 수익률 요약 (단위: %)")
    print("=" * 60)
    print(f"{'연도':>6} | {'내지표(MA+모멘텀)':>18} | {'이웃지표(수급)':>16}")
    print("-" * 50)
    total_my, total_nb = [], []
    for r in rows:
        my_r = f"{r['my_algo_return']:.2f}%" if r['my_algo_return'] is not None else "N/A"
        nb_r = f"{r['neighbor_algo_return']:.2f}%" if r['neighbor_algo_return'] is not None else "N/A"
        print(f"{r['year']:>6} | {my_r:>18} | {nb_r:>16}")
        if r['my_algo_return'] is not None:
            total_my.append(r['my_algo_return'])
        if r['neighbor_algo_return'] is not None:
            total_nb.append(r['neighbor_algo_return'])

    print("-" * 50)
    if total_my:
        print(f"{'평균':>6} | {np.mean(total_my):>17.2f}% | {np.mean(total_nb):>15.2f}%")
        print(f"{'누적합':>6} | {sum(total_my):>17.2f}% | {sum(total_nb):>15.2f}%")

    print(f"\n✅ 결과 파일 ({RESULT_GRADE}):")
    print(f"  CSV: {csv_path}")
    print(f"  PNG: {png_path}")
    print("\n⚠️  DRAFT 결과: 검증 완료 후 VALIDATED → PRODUCTION 승격 필요")

    return result_df


if __name__ == '__main__':
    result = main()
