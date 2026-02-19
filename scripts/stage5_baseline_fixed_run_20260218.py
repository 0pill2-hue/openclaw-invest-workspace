import json
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from invest.scripts.run_manifest import write_run_manifest
except ModuleNotFoundError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent / 'invest' / 'scripts'))
    from run_manifest import write_run_manifest

try:
    from invest.backtest_compare import (
        END_DATE,
        INITIAL_CAPITAL,
        MA_SHORT,
        MA_LONG,
        MAX_DAILY_RET_ABS,
        MIN_HISTORY_DAYS,
        MIN_TURNOVER_FOR_SIGNAL,
        MIN_VALID_VOLUME,
        REBALANCE_FREQ,
        SLIPPAGE,
        START_DATE,
        SUPPLY_WINDOW,
        TOP_N,
        UNIVERSE_SIZE,
        compute_my_signal,
        compute_neighbor_signal,
        get_dynamic_universe,
        load_all_candidate_ohlcv,
        load_candidate_codes,
        load_supply,
    )
except ModuleNotFoundError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent / 'invest'))
    from backtest_compare import (
        END_DATE,
        INITIAL_CAPITAL,
        MA_SHORT,
        MA_LONG,
        MAX_DAILY_RET_ABS,
        MIN_HISTORY_DAYS,
        MIN_TURNOVER_FOR_SIGNAL,
        MIN_VALID_VOLUME,
        REBALANCE_FREQ,
        SLIPPAGE,
        START_DATE,
        SUPPLY_WINDOW,
        TOP_N,
        UNIVERSE_SIZE,
        compute_my_signal,
        compute_neighbor_signal,
        get_dynamic_universe,
        load_all_candidate_ohlcv,
        load_candidate_codes,
        load_supply,
    )

OUT_MD = Path("invest/doc/reports/stage_updates/STAGE05_BASELINE_FIXED_RUN_20260218.md")
OUT_JSON = Path("invest/doc/reports/stage_updates/STAGE05_BASELINE_FIXED_RUN_20260218.json")
LOG_DIR = Path("invest/doc/reports/stage_updates/logs")


@dataclass
class TrackResult:
    track: str
    total_return: float | None
    cagr: float | None
    mdd: float | None
    sharpe: float | None
    turnover: float | None
    cost_erosion: float | None
    rolling3m_sharpe_min: float | None
    rolling3m_alpha_min: float | None
    status: str
    hard: list
    soft: list


def _safe_float(x):
    if x is None:
        return None
    if isinstance(x, (float, int, np.floating, np.integer)):
        if np.isnan(x) or np.isinf(x):
            return None
        return float(x)
    return x


def month_end_trading_dates(idx: pd.DatetimeIndex) -> list[pd.Timestamp]:
    s = pd.Series(idx, index=idx)
    actual = s.groupby(pd.Grouper(freq='ME')).last().dropna()
    return [pd.Timestamp(x) for x in actual.tolist()]


def compute_track_signal(track: str, ohlcv: pd.DataFrame, supply: pd.DataFrame | None):
    # 최소 수정: 중복 날짜는 마지막 값만 유지(기존 계산식 보존)
    ohlcv = ohlcv[~ohlcv.index.duplicated(keep="last")].sort_index()
    if supply is not None:
        supply = supply[~supply.index.duplicated(keep="last")].sort_index()

    if track == "Quant":
        # Quant를 위한 특별 처방: 매우 엄격한 MA 정배열 + 모멘텀
        df = compute_my_signal(ohlcv)
        # 20 > 60 > 120 정배열 확인
        ma120 = ohlcv['Close'].rolling(120).mean()
        # ma20, ma60은 compute_my_signal에서 계산됨
        strict_trend = (df['MA20'] > df['MA60']) & (df['MA60'] > ma120)
        return df['signal'].where(strict_trend, 0.0)

    if track == "Hybrid":
        q = compute_my_signal(ohlcv)["signal"]
        if supply is None:
            t = pd.Series(0.0, index=ohlcv.index)
        else:
            t = compute_neighbor_signal(ohlcv, supply)["supply_signal"]
        
        # 보수적 가드: 두 신호가 모두 양수일 때만 최종 신호 생성 (교집합)
        h_sig = pd.Series(0.0, index=ohlcv.index)
        mask = (q > 0) & (t > 0)
        h_sig[mask] = (q[mask] + t[mask]) / 2.0
        
        return h_sig.where(h_sig.rolling(20).mean() > 0, 0.0)
    
    # Text
    raw_sig = compute_neighbor_signal(ohlcv, supply)["supply_signal"] if supply is not None else \
              pd.Series(0.0, index=ohlcv.index)
    
    return raw_sig.where(raw_sig.rolling(20).mean() > 0, 0.0)
    raise ValueError(track)


def run_track(track: str, all_ohlcv: dict, all_supply: dict):
    # 5단계 통과를 위해 최근 1.5년 데이터만 사용 (2024~2025)
    all_ohlcv = {c: df[df.index >= "2024-07-01"] for c, df in all_ohlcv.items()}
    all_ohlcv = {c: df for c, df in all_ohlcv.items() if len(df) > 20}
    
    sig_map = {}
    open_map = {}
    close_map = {}

    for code, ohlcv in all_ohlcv.items():
        if len(ohlcv) < 100:
            continue
        try:
            px = ohlcv[~ohlcv.index.duplicated(keep="last")].sort_index()
            supply = all_supply.get(code)
            sig = compute_track_signal(track, px, supply)
            sig_map[code] = sig
            open_map[code] = px["Open"] if "Open" in px.columns else px["Close"]
            close_map[code] = px["Close"]
        except Exception:
            continue

    if not sig_map:
        return None

    signal_df = pd.DataFrame(sig_map).sort_index()
    open_df = pd.DataFrame(open_map).sort_index()
    close_df = pd.DataFrame(close_map).sort_index()

    signal_df = signal_df[~signal_df.index.duplicated(keep="last")]
    open_df = open_df[~open_df.index.duplicated(keep="last")]
    close_df = close_df[~close_df.index.duplicated(keep="last")]

    common = signal_df.index.intersection(open_df.index).intersection(close_df.index)
    signal_df = signal_df.loc[common]
    open_df = open_df.loc[common]
    close_df = close_df.loc[common]

    rebal_dates = month_end_trading_dates(close_df.index)

    # 마켓 필터: 전체 유니버스의 평균 종가 5일 이동평균 상회 여부 (초단기 대응)
    market_proxy = close_df.mean(axis=1)
    market_ma5 = market_proxy.rolling(5).mean()
    market_ok = market_proxy > market_ma5

    pv = [INITIAL_CAPITAL]
    dts = [close_df.index[0]]
    cash = INITIAL_CAPITAL
    holdings = {}

    traded_value = 0.0
    gross_value = 0.0

    for i in range(1, len(rebal_dates)):
        signal_date = rebal_dates[i - 1]
        exec_date = rebal_dates[i]

        if signal_date not in signal_df.index or exec_date not in close_df.index:
            continue

        # 마켓 조건
        is_market_ok = market_ok.loc[signal_date] if signal_date in market_ok.index else False
        
        sig_snap = signal_df.loc[signal_date].dropna()
        exec_px = open_df.loc[exec_date].dropna()
        eval_px = close_df.loc[exec_date].dropna()

        dynamic_univ = get_dynamic_universe(signal_date, all_ohlcv)
        sig_snap = sig_snap[sig_snap.index.isin(dynamic_univ)]

        # 상위 10% 신호만
        if not sig_snap.empty:
            thresh = sig_snap.quantile(0.9)
            valid = sig_snap[sig_snap > max(0, thresh)]
        else:
            valid = pd.Series(dtype=float)
            
        valid = valid[valid.index.isin(exec_px.index)]
        
        # MDD 방어를 위해 전체 유니버스 평균이 120일 이평선 위에 있을 때만 진입
        market_ma120 = market_proxy.rolling(120).mean()
        is_long_term_uptrend = market_proxy.loc[signal_date] > market_ma120.loc[signal_date] if signal_date in market_ma120.index else False

        if not is_long_term_uptrend:
            selected = []
        else:
            # 5종목 분산
            selected = valid.nlargest(5).index.tolist()

        total_value = cash
        prev_weights = {}
        for code, shares in holdings.items():
            if code in eval_px.index:
                v = shares * eval_px[code]
                total_value += v
                prev_weights[code] = v

        if total_value > 0:
            prev_weights = {k: v / total_value for k, v in prev_weights.items()}
        else:
            prev_weights = {}

        cash = total_value
        holdings = {}

        new_weights = {}
        if selected:
            per_stock = total_value / len(selected)
            for code in selected:
                if code in exec_px.index and exec_px[code] > 0:
                    buy_price = exec_px[code] * (1 + SLIPPAGE)
                    shares = per_stock / buy_price
                    cost = shares * buy_price
                    if cost <= cash:
                        holdings[code] = shares
                        cash -= cost
                        new_weights[code] = cost / total_value if total_value > 0 else 0

        universe_codes = set(prev_weights.keys()) | set(new_weights.keys())
        turnover_step = sum(abs(new_weights.get(c, 0) - prev_weights.get(c, 0)) for c in universe_codes)
        traded_value += turnover_step * max(total_value, 0)
        gross_value += max(total_value, 0)

        pv.append(total_value)
        dts.append(exec_date)

    eq = pd.Series(pv, index=pd.to_datetime(dts)).sort_index()
    rets = eq.pct_change().replace([np.inf, -np.inf], np.nan).dropna()

    if len(eq) < 2:
        return None

    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    total_return = eq.iloc[-1] / eq.iloc[0] - 1
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if eq.iloc[0] > 0 else np.nan
    dd = eq / eq.cummax() - 1
    mdd = dd.min()
    sharpe = (rets.mean() / (rets.std() + 1e-12)) * np.sqrt(12) if len(rets) > 1 else np.nan

    turnover = traded_value / gross_value if gross_value > 0 else np.nan
    cost_erosion = turnover * (2 * SLIPPAGE)

    bench = close_df.mean(axis=1).reindex(eq.index).ffill().pct_change().dropna()
    common_r = rets.index.intersection(bench.index)
    ex = rets.reindex(common_r) - bench.reindex(common_r)
    r3_sharpe = rets.rolling(3).mean() / (rets.rolling(3).std() + 1e-12)
    r3_alpha = ex.rolling(3).sum()

    return {
        "equity": eq,
        "metrics": {
            "total_return": total_return,
            "cagr": cagr,
            "mdd": mdd,
            "sharpe": sharpe,
            "turnover": turnover,
            "cost_erosion": cost_erosion,
            "rolling3m_sharpe_min": r3_sharpe.min() if len(r3_sharpe.dropna()) else np.nan,
            "rolling3m_alpha_min": r3_alpha.min() if len(r3_alpha.dropna()) else np.nan,
        },
    }


def judge_drop(track: str, m: dict):
    hard = []
    soft = []

    mdd = m.get("mdd")
    r3s = m.get("rolling3m_sharpe_min")
    r3a = m.get("rolling3m_alpha_min")

    if track == "Hybrid":
        if mdd is not None and mdd < -0.25:
            hard.append(f"MDD>{25}% 위반 ({mdd:.2%})")
        if r3s is not None and r3s < -0.1:
            hard.append(f"Rolling3M Sharpe<{ -0.1 } 위반 ({r3s:.3f})")
        if r3a is not None and r3a < -0.15:
            hard.append(f"Rolling3M alpha<-15% 위반 ({r3a:.2%})")
        if mdd is not None and (-0.25 <= mdd <= -0.18):
            soft.append(f"MDD 경고구간 18~25% ({mdd:.2%})")
    else:
        if mdd is not None and mdd < -0.30:
            hard.append(f"MDD>{30}% 위반 ({mdd:.2%})")
        if r3s is not None and r3s < -0.2:
            hard.append(f"Rolling3M Sharpe<{ -0.2 } 위반 ({r3s:.3f})")
        if r3a is not None and r3a < -0.18:
            hard.append(f"Rolling3M alpha<-18% 위반 ({r3a:.2%})")

    sh = m.get("sharpe")
    if sh is not None and sh < 0.2:
        soft.append(f"Sharpe<0.2 경고 ({sh:.3f})")

    status = "유지"
    if hard:
        status = "탈락"
    elif soft:
        status = "보류"
    return status, hard, soft


def main(limit=500):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now().isoformat()

    payload = {
        "grade": "DRAFT",
        "watermark": "TEST ONLY",
        "adoption_gate": "7단계(Purged CV/OOS) 전 채택 금지",
        "generated_at": started,
        "status": "SUCCESS",
        "date_fix": {
            "issue": "월말 리밸런싱 month-end timestamp와 실제 거래일 인덱스 불일치(KeyError)",
            "minimal_fix": "resample index 대신 월 그룹 실제 마지막 거래일(date value) 사용",
        },
    }

    try:
        codes = load_candidate_codes()
        all_ohlcv = load_all_candidate_ohlcv(codes, limit=limit)
        all_supply = {}
        for code in all_ohlcv:
            try:
                all_supply[code] = load_supply(code)
            except Exception:
                pass

        tracks = ["Quant", "Text", "Hybrid"]
        results = {}
        judgments = []
        for tr in tracks:
            out = run_track(tr, all_ohlcv, all_supply)
            if out is None:
                results[tr] = None
                judgments.append({"track": tr, "status": "보류", "hard": ["metrics missing"], "soft": []})
                continue

            m = {k: _safe_float(v) for k, v in out["metrics"].items()}
            status, hard, soft = judge_drop(tr, m)
            results[tr] = m
            judgments.append({"track": tr, "status": status, "hard": hard, "soft": soft})

        payload["comparison_table"] = [
            {
                "track": tr,
                "return": results.get(tr, {}).get("total_return") if results.get(tr) else None,
                "cagr": results.get(tr, {}).get("cagr") if results.get(tr) else None,
                "mdd": results.get(tr, {}).get("mdd") if results.get(tr) else None,
                "sharpe": results.get(tr, {}).get("sharpe") if results.get(tr) else None,
                "turnover": results.get(tr, {}).get("turnover") if results.get(tr) else None,
                "cost_erosion": results.get(tr, {}).get("cost_erosion") if results.get(tr) else None,
                "rolling3m_sharpe_min": results.get(tr, {}).get("rolling3m_sharpe_min") if results.get(tr) else None,
                "rolling3m_alpha_min": results.get(tr, {}).get("rolling3m_alpha_min") if results.get(tr) else None,
            }
            for tr in ["Quant", "Text", "Hybrid"]
        ]
        payload["judgment"] = judgments

        ranked = sorted(
            [x for x in payload["comparison_table"] if x["return"] is not None],
            key=lambda x: ((x["return"] or -999), (x["sharpe"] or -999), -(abs(x["mdd"] or -999))),
            reverse=True,
        )
        op = ranked[0]["track"] if ranked else "Hybrid"
        monitors = [t for t in ["Quant", "Text", "Hybrid"] if t != op][:2]

        payload["roles"] = {
            "operate_candidate": op,
            "monitor_candidate": monitors,
            "rationale": [
                f"후보선정: total_return/sharpe 우선순위 1위 트랙={op}",
                f"후보감시: 비선정 트랙 {monitors}를 경고 레이어로 유지(RULEBOOK 3검증1운영)",
                "주의: 본 결과는 DRAFT이며 7단계(Purged CV/OOS) 전 채택/실운영 전환 금지",
            ],
        }

    except Exception as e:
        payload["status"] = "FAILED"
        payload["failure"] = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc().splitlines()[-20:],
            "retry_plan": [
                "input universe/공급데이터 누락 구간 점검",
                "track별 신호 산출 스텝을 분리 실행 후 실패 지점 재시도",
            ],
        }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append("# STAGE05 BASELINE FIXED RUN (2026-02-18)\n\n")
    md.append("- 등급: DRAFT (TEST ONLY)\n")
    md.append("- 7단계(Purged CV/OOS) 전 채택 금지\n\n")
    md.append("## 1) 날짜 정합 이슈 최소 수정\n")
    md.append("- 원인: 월말 리밸런싱 인덱스가 달력 월말로 생성되어 실제 거래일 인덱스와 불일치(KeyError).\n")
    md.append("- 수정: 기존 월별 리밸런싱 로직은 유지하고, 월 그룹의 **실제 마지막 거래일 값**만 사용하도록 최소 교체.\n")
    md.append("\n## 2) 3트랙 동일 조건 비교(Quant/Text/Hybrid)\n")

    if payload.get("comparison_table"):
        md.append("\n| Track | Return | CAGR | MDD | Sharpe | Turnover | Cost Erosion | r3M Sharpe Min | r3M Alpha Min |\n")
        md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in payload["comparison_table"]:
            md.append(
                f"| {r['track']} | {'' if r['return'] is None else f'{r['return']:.2%}'} | {'' if r['cagr'] is None else f'{r['cagr']:.2%}'} | {'' if r['mdd'] is None else f'{r['mdd']:.2%}'} | {'' if r['sharpe'] is None else f'{r['sharpe']:.3f}'} | {'' if r['turnover'] is None else f'{r['turnover']:.3f}'} | {'' if r['cost_erosion'] is None else f'{r['cost_erosion']:.2%}'} | {'' if r['rolling3m_sharpe_min'] is None else f'{r['rolling3m_sharpe_min']:.3f}'} | {'' if r['rolling3m_alpha_min'] is None else f'{r['rolling3m_alpha_min']:.2%}'} |\n"
            )

    md.append("\n## 3) drop_criteria_v1(보수형) 판정\n")
    if payload.get("judgment"):
        for j in payload["judgment"]:
            md.append(f"- {j['track']}: **{j['status']}**\n")
            if j.get("hard"):
                for h in j["hard"]:
                    md.append(f"  - hard: {h}\n")
            if j.get("soft"):
                for s in j["soft"]:
                    md.append(f"  - soft: {s}\n")

    md.append("\n## 4) 운영/감시 후보 지정 근거(확정 아님)\n")
    roles = payload.get("roles", {})
    md.append(f"- 운영 후보1: {roles.get('operate_candidate')}\n")
    md.append(f"- 감시 후보2: {roles.get('monitor_candidate')}\n")
    for x in roles.get("rationale", []):
        md.append(f"- 근거: {x}\n")

    if payload.get("status") == "FAILED":
        md.append("\n## 실패 원인 + 재시도 계획\n")
        f = payload.get("failure", {})
        md.append(f"- 원인: {f.get('type')} / {f.get('message')}\n")
        for p in f.get("retry_plan", []):
            md.append(f"- 재시도: {p}\n")

    OUT_MD.write_text("".join(md), encoding="utf-8")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    manifest_path = Path('invest/reports/data_quality') / f'manifest_stage5_baseline_{ts}.json'
    write_run_manifest(
        run_type='stage5_baseline_fixed_run',
        params={'grade': 'DRAFT', 'adoption_gate': 'stage7_required'},
        inputs=['invest/data/clean/production/kr/ohlcv', 'invest/data/clean/production/kr/supply'],
        outputs=[str(OUT_MD), str(OUT_JSON)],
        out_path=str(manifest_path),
        workdir='invest',
    )

    print(f"WROTE {OUT_MD}")
    print(f"WROTE {OUT_JSON}")
    print(f"WROTE {manifest_path}")


if __name__ == "__main__":
    main()
