# WARNING: DO NOT ADD CUSTOM RULES
import pandas as pd
import numpy as np
from collections import deque


class BacktestEngine:
    """
    Stage05 Backtest Engine (Rulebook V3 hard rules / Pure Wild)
    - Survival: 상폐 위험 종목 매수 금지
    - Quality: 블랙리스트 종목 매수 금지
    - Concentration: 동적 1~6 포지션 제한
    - Trend: trailing stop(-20%) 적용

    제거된 독소조항(숫자 필터):
    - min_market_cap
    - min_profit
    - min_revenue
    """

    # Rulebook V3: quality blacklist (keyword based)
    BLACKLIST_KEYWORDS = [
        "정치", "대선", "총선", "남북", "북한", "작전", "테마주", "인맥", "이재명", "윤석열", "트럼프"
    ]
    BLACKLIST_EXACT = {
        "아난티",  # 명시 예시
    }

    def __init__(self, initial_capital=100_000_000, round_trip_penalty=0.03, delisting_db=None, vix_threshold=28.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.penalty = round_trip_penalty
        self.portfolio = {}  # {code: {'shares': N, 'entry_price': P, 'entry_date': D, 'peak_price': P}}
        self.history = []
        self.last_exit = {}
        self.logs = []

        # Rulebook V3: concentration hard limit (dynamic 1~6)
        self.max_pos = 6

        # Rulebook V3: trailing stop
        self.trailing_stop_pct = -0.20

        # Rulebook V3.2 Hybrid Crisis Defense
        self.market_regime = "NORMAL"  # NORMAL / CAUTION / CRISIS
        self.vix_threshold = vix_threshold
        self.kospi_window = deque(maxlen=4)  # 3일 하락률 계산용 (t-3 ~ t)
        self.kospi_peak = None
        self.above_ma_streak = 0
        self.block_new_buys = False
        self.max_exposure_cap = 1.0

        # Rulebook V3: Survival rule 데이터베이스
        self.delisting_db = delisting_db or {}

    def _log(self, msg):
        self.logs.append(msg)
        print(msg)

    def set_dynamic_max_positions(self, regime_score):
        """
        Dynamic max_pos mapping: regime_score(0~1) -> 1~6.
        강세장일수록 분산 확대, 약세장일수록 집중.
        """
        score = float(np.clip(regime_score, 0.0, 1.0))
        self.max_pos = int(np.clip(round(1 + score * 5), 1, 6))
        self._log(f"동적 max_pos 설정: {self.max_pos} (regime_score={score:.2f})")
        return self.max_pos

    def is_blacklist(self, name_or_theme):
        if not name_or_theme:
            return False
        text = str(name_or_theme)
        if text in self.BLACKLIST_EXACT:
            return True
        return any(k in text for k in self.BLACKLIST_KEYWORDS)

    def is_survival_risk(self, code, delisting_info=None):
        """
        Rulebook V3 Survival hard filter.
        아래 플래그 중 하나라도 True면 매수 금지:
        - admin_issue(관리종목)
        - capital_erosion(자본잠식)
        - audit_opinion(감사의견 거절)

        하위 호환 키 허용:
        - management_issue -> admin_issue
        - capital_impairment -> capital_erosion
        - audit_opinion_rejected_history -> audit_opinion
        """
        info = delisting_info if delisting_info is not None else self.delisting_db.get(code, {})
        if not isinstance(info, dict):
            return False

        risk_flags = {
            "admin_issue": bool(info.get("admin_issue", info.get("management_issue", False))),
            "capital_erosion": bool(info.get("capital_erosion", info.get("capital_impairment", False))),
            "audit_opinion": bool(info.get("audit_opinion", info.get("audit_opinion_rejected_history", False))),
        }
        return any(risk_flags.values())

    def is_overheated_allowed(self, signal_flags=None):
        """
        Rulebook V3 예외 허용 규칙.
        투자경고/투자과열(Overheated)은 상폐 리스크 필터 예외로 매수 허용.
        """
        info = signal_flags or {}
        if not isinstance(info, dict):
            return False
        return bool(
            info.get("overheated", False)
            or info.get("investment_warning", False)
            or info.get("warning_overheated", False)
        )

    # backward-compatible alias
    def is_delisting_risk(self, code, delisting_info=None):
        return self.is_survival_risk(code, delisting_info=delisting_info)

    def _effective_price(self, price, action):
        if action == 'BUY':
            return price * (1 + self.penalty / 2)
        return price * (1 - self.penalty / 2)

    def _days_between(self, d1, d2):
        try:
            d1 = pd.to_datetime(d1)
            d2 = pd.to_datetime(d2)
            return (d2 - d1).days
        except Exception:
            return None

    def get_dynamic_weights(self, score_map):
        """
        Rulebook V3 Dynamic Weight:
        - Equal weight(1/N) 금지
        - Score 비례 배분
        - 점수 우위 1종목이면 100% 몰빵 허용
        """
        if not score_map:
            return {}

        pairs = [(k, max(float(v), 0.0)) for k, v in score_map.items()]
        pairs = [(k, v) for k, v in pairs if v > 0]
        if not pairs:
            return {}

        total = sum(v for _, v in pairs)
        if total <= 0:
            return {}
        return {k: v / total for k, v in pairs}

    def _sell_fraction(self, date, code, price, fraction=1.0, reason='risk_control'):
        if code not in self.portfolio:
            return
        fraction = float(np.clip(fraction, 0.0, 1.0))
        pos = self.portfolio[code]
        sell_shares = int(pos['shares'] * fraction)
        if sell_shares <= 0:
            return
        effective_price = self._effective_price(price, 'SELL')
        revenue = sell_shares * effective_price
        self.capital += revenue

        effective_entry = pos.get('effective_entry_price', pos['entry_price'])
        profit = (effective_price - effective_entry) / effective_entry if effective_entry > 0 else 0.0

        pos['shares'] -= sell_shares
        if pos['shares'] <= 0:
            del self.portfolio[code]
            self.last_exit[code] = date

        self.history.append({
            'Date': date,
            'Code': code,
            'Action': 'SELL',
            'Price': price,
            'Shares': sell_shares,
            'Profit': profit,
            'Reason': reason,
        })

    def _liquidate_all(self, date, current_prices, reason='crisis_liquidation'):
        for code in list(self.portfolio.keys()):
            if code not in current_prices:
                continue
            self._sell_fraction(date, code, float(current_prices[code]), fraction=1.0, reason=reason)

    def _reduce_exposure_to_cap(self, date, current_prices, cap=0.5, reason='caution_deleverage'):
        total_value = self.get_total_value(current_prices)
        if total_value <= 0:
            return
        for code in list(self.portfolio.keys()):
            if code not in current_prices:
                continue
            pos = self.portfolio[code]
            mkt_val = pos['shares'] * float(current_prices[code])
            position_ratio = mkt_val / total_value
            if position_ratio > cap:
                target_value = total_value * cap
                excess_ratio = max((mkt_val - target_value) / mkt_val, 0.0)
                self._sell_fraction(date, code, float(current_prices[code]), fraction=excess_ratio, reason=reason)

    def update_market_regime(self, date, market_data=None, current_prices=None):
        """
        market_data keys:
          - kospi
          - kospi_120ma
          - vix_proxy
          - drawdown (optional, 없으면 kospi 기반 내부 계산)
        """
        data = market_data or {}
        prices = current_prices or {}
        kospi = float(data.get('kospi', np.nan))
        kospi_120ma = float(data.get('kospi_120ma', np.nan))
        vix_proxy = float(data.get('vix_proxy', 0.0))

        if np.isfinite(kospi):
            self.kospi_window.append(kospi)
            self.kospi_peak = kospi if self.kospi_peak is None else max(self.kospi_peak, kospi)

        drawdown = data.get('drawdown')
        if drawdown is None and self.kospi_peak and np.isfinite(kospi) and self.kospi_peak > 0:
            drawdown = (kospi / self.kospi_peak) - 1.0
        drawdown = float(drawdown) if drawdown is not None else 0.0

        drop_3d = 0.0
        if len(self.kospi_window) >= 4 and self.kospi_window[0] > 0:
            drop_3d = 1.0 - (self.kospi_window[-1] / self.kospi_window[0])

        soft_trigger = (drop_3d > 0.05) or (vix_proxy > self.vix_threshold)
        hard_trigger = np.isfinite(kospi) and np.isfinite(kospi_120ma) and (kospi < kospi_120ma) and (drawdown <= -0.15)

        if np.isfinite(kospi) and np.isfinite(kospi_120ma) and kospi >= kospi_120ma:
            self.above_ma_streak += 1
        else:
            self.above_ma_streak = 0

        prev_regime = self.market_regime

        if hard_trigger:
            self.market_regime = "CRISIS"
            self.block_new_buys = True
            self.max_exposure_cap = 0.0
            self._log(
                f"Hard Trigger | {date} | regime=CRISIS | kospi={kospi:.2f} < ma120={kospi_120ma:.2f}, drawdown={drawdown:.2%}"
            )
            self._liquidate_all(date, prices, reason='hard_trigger')

        elif self.market_regime == "CRISIS":
            # Re-entry: 120MA 상단 3영업일 안정성 확인
            if self.above_ma_streak >= 3:
                self.market_regime = "NORMAL"
                self.block_new_buys = False
                self.max_exposure_cap = 1.0
                self._log(f"Re-entry | {date} | 3-day stability above 120MA confirmed -> NORMAL")
            else:
                self.block_new_buys = True
                self.max_exposure_cap = 0.0

        elif soft_trigger:
            self.market_regime = "CAUTION"
            self.block_new_buys = True
            self.max_exposure_cap = 0.5
            self._log(
                f"Soft Trigger | {date} | regime=CAUTION | 3d_drop={drop_3d:.2%}, vix_proxy={vix_proxy:.2f}"
            )
            # 정책: 절반 매도 + 신규매수 중단
            for code in list(self.portfolio.keys()):
                if code in prices:
                    self._sell_fraction(date, code, float(prices[code]), fraction=0.5, reason='soft_trigger')
            self._reduce_exposure_to_cap(date, prices, cap=0.5, reason='caution_cap')

        else:
            self.market_regime = "NORMAL"
            self.block_new_buys = False
            self.max_exposure_cap = 1.0

        if prev_regime != self.market_regime:
            self._log(f"Regime Change | {date} | {prev_regime} -> {self.market_regime}")

        return self.market_regime

    def execute_trade(self, date, code, action, price, weight=1.0, avg_turnover=None, name=None, signal_reason=None, delisting_info=None):
        sec_name = name or code

        if action == 'BUY':
            if self.block_new_buys:
                self._log(f"매수 차단: {sec_name} [{code}] (regime={self.market_regime})")
                return

            # Rulebook V3: Survival hard filter + Overheated 예외 허용
            survival_risk = self.is_survival_risk(code, delisting_info=delisting_info)
            overheated_allowed = self.is_overheated_allowed(signal_flags=delisting_info)

            if survival_risk and not overheated_allowed:
                self._log(f"매수 거부: 관리종목 (Delisting Risk) - {sec_name} [{code}]")
                return
            if survival_risk and overheated_allowed:
                self._log(f"매수 허용: 투자경고 (Overheated) - {sec_name} [{code}]")

            # Rulebook V3: blacklist hard filter
            if self.is_blacklist(sec_name):
                self._log(f"매수 거부: {sec_name} (Blacklist)")
                return

            # Rulebook V3: concentration hard cap
            if code not in self.portfolio and len(self.portfolio) >= self.max_pos:
                self._log(f"매수 거부: {sec_name} (max_pos={self.max_pos} 도달)")
                return

            # Pure Wild 확인 로그 (시총/실적 필터 미적용)
            if delisting_info and delisting_info.get("small_cap", False):
                self._log(f"소형주(Small Cap) 매수 허용 - {sec_name} [{code}]")

            if code not in self.portfolio:
                effective_weight = float(np.clip(weight, 0.0, self.max_exposure_cap))
                buy_amount = self.capital * effective_weight
                effective_price = self._effective_price(price, 'BUY')
                shares = buy_amount // effective_price
                cost = shares * effective_price

                if cost <= self.capital and shares > 0:
                    self.capital -= cost
                    self.portfolio[code] = {
                        'shares': shares,
                        'entry_price': price,
                        'effective_entry_price': effective_price,
                        'entry_date': date,
                        'name': sec_name,
                        'peak_price': price,
                    }
                    self.history.append({
                        'Date': date,
                        'Code': code,
                        'Action': 'BUY',
                        'Price': price,
                        'Shares': shares,
                        'Weight': effective_weight,
                    })

        elif action == 'SELL':
            if code in self.portfolio:
                shares = self.portfolio[code]['shares']
                effective_price = self._effective_price(price, 'SELL')
                revenue = shares * effective_price
                self.capital += revenue

                effective_entry = self.portfolio[code].get('effective_entry_price', self.portfolio[code]['entry_price'])
                if effective_entry and effective_entry > 0:
                    profit = (effective_price - effective_entry) / effective_entry
                else:
                    profit = 0.0
                del self.portfolio[code]
                self.last_exit[code] = date
                self.history.append({
                    'Date': date,
                    'Code': code,
                    'Action': 'SELL',
                    'Price': price,
                    'Profit': profit,
                    'Reason': signal_reason or 'manual',
                })

    def update_trailing_stop(self, date, current_prices):
        """
        Rulebook V3 Trend: trailing stop -20%
        peak 대비 수익률이 -20% 이하가 되면 전량 매도.
        """
        for code in list(self.portfolio.keys()):
            if code not in current_prices:
                continue
            current_price = float(current_prices[code])
            pos = self.portfolio[code]
            pos['peak_price'] = max(float(pos.get('peak_price', pos['entry_price'])), current_price)
            peak = pos['peak_price']
            drawdown = (current_price / peak) - 1.0 if peak > 0 else 0.0
            if drawdown <= self.trailing_stop_pct:
                self._log(f"트레일링 스탑 발동(-20%): {pos.get('name', code)} [{code}] dd={drawdown:.2%}")
                self.execute_trade(
                    date=date,
                    code=code,
                    action='SELL',
                    price=current_price,
                    signal_reason='trailing_stop',
                    name=pos.get('name', code),
                )

    def rebalance_by_score(self, date, candidates, regime_score=0.5, market_data=None, current_prices=None):
        """
        candidates: list[dict] with keys
          - code, name, price, score
        """
        prices = current_prices or {c['code']: float(c['price']) for c in candidates if 'price' in c}
        self.update_market_regime(date=date, market_data=market_data, current_prices=prices)

        # CAUTION/CRISIS에서는 공격적 확장을 막기 위해 max_pos 강제 축소
        dyn_max = self.set_dynamic_max_positions(regime_score)
        if self.market_regime == "CAUTION":
            self.max_pos = min(dyn_max, 3)
        elif self.market_regime == "CRISIS":
            self.max_pos = 0

        # score 내림차순 + max_pos 제한
        sorted_cands = sorted(candidates, key=lambda x: float(x.get('score', 0.0)), reverse=True)
        selected = sorted_cands[:self.max_pos]

        score_map = {c['code']: float(c.get('score', 0.0)) for c in selected}
        weight_map = self.get_dynamic_weights(score_map)

        for c in selected:
            code = c['code']
            self.execute_trade(
                date=date,
                code=code,
                action='BUY',
                price=float(c['price']),
                weight=weight_map.get(code, 0.0),
                avg_turnover=float(c.get('avg_turnover', 0.0)),
                name=c.get('name', code),
                delisting_info=c.get('delisting_info'),
            )

    def get_total_value(self, current_prices, apply_liquidation_cost=True):
        asset_value = 0
        for code, info in self.portfolio.items():
            if code in current_prices:
                price = current_prices[code]
                if apply_liquidation_cost:
                    price = self._effective_price(price, 'SELL')
                asset_value += info['shares'] * price
        return self.capital + asset_value


if __name__ == "__main__":
    # 2016~2026 Baseline simulation (Hybrid Crisis Defense 검증)
    delisting_db = {
        "A555": {
            "management_issue": True,
            "capital_impairment": False,
            "audit_opinion_rejected_history": False,
        },
        "A556": {
            "management_issue": True,
            "capital_impairment": False,
            "audit_opinion_rejected_history": False,
            "investment_warning": True,
            "overheated": True,
            "small_cap": True,
        }
    }

    engine = BacktestEngine(delisting_db=delisting_db)
    sample_years = list(range(2016, 2027))
    equity_curve = []

    for y in sample_years:
        d = f"{y}-01-02"
        regime = 0.1 + (y - 2016) / 10 * 0.8
        momentum_score = 20.0 if y <= 2018 else 8.0
        candidates = [
            {"code": "A111", "name": "고성장플랫폼", "price": 12000 + (y - 2016) * 900, "score": momentum_score},
            {"code": "A222", "name": "현대차", "price": 150000 + (y - 2016) * 1000, "score": 5.8},
            {"code": "A333", "name": "아난티", "price": 9000 + (y - 2016) * 120, "score": 8.1},
            {"code": "A444", "name": "2차전지소재", "price": 40000 + (y - 2016) * 1500, "score": max(1.5, 6.5 - (y - 2016) * 0.2)},
            {"code": "A555", "name": "리스크기업", "price": 12000 + (y - 2016) * 200, "score": 9.2},
            {"code": "A556", "name": "경고과열주", "price": 7000 + (y - 2016) * 250, "score": 8.9, "delisting_info": delisting_db["A556"]},
        ]
        px = {c['code']: float(c['price']) for c in candidates}

        market = {
            "kospi": 1950 + (y - 2016) * 120,
            "kospi_120ma": 1850 + (y - 2016) * 110,
            "vix_proxy": 16.0,
        }
        engine.rebalance_by_score(date=d, candidates=candidates, regime_score=regime, market_data=market, current_prices=px)
        equity_curve.append((d, engine.get_total_value(px)))

        if y == 2020:
            crisis_days = [
                ("2020-02-24", 2150, 2200, 34.0),
                ("2020-03-19", 1430, 2100, 52.0),
                ("2020-03-23", 1480, 2050, 45.0),
                ("2020-04-01", 1720, 1700, 26.0),
                ("2020-04-02", 1740, 1710, 24.0),
                ("2020-04-03", 1760, 1720, 23.0),
            ]
            for cd, kospi, ma120, vix in crisis_days:
                shocked_prices = {
                    "A111": px["A111"] * (0.68 if "03-19" in cd else 0.85),
                    "A222": px["A222"] * (0.72 if "03-19" in cd else 0.88),
                    "A444": px["A444"] * (0.60 if "03-19" in cd else 0.80),
                    "A556": px["A556"] * (0.55 if "03-19" in cd else 0.78),
                }
                engine.update_market_regime(
                    date=cd,
                    market_data={"kospi": kospi, "kospi_120ma": ma120, "vix_proxy": vix},
                    current_prices=shocked_prices,
                )
                engine.update_trailing_stop(cd, shocked_prices)
                equity_curve.append((cd, engine.get_total_value(shocked_prices)))

    final_prices = {
        "A111": 2_100_000,
        "A222": 620_000,
        "A333": 12_000,
        "A444": 450_000,
        "A556": 980_000,
    }

    engine.rebalance_by_score(
        date="2021-01-04",
        candidates=[
            {"code": "A111", "name": "고성장플랫폼", "price": 18000, "score": 12.0},
            {"code": "A444", "name": "2차전지소재", "price": 52000, "score": 9.0},
            {"code": "A556", "name": "경고과열주", "price": 9000, "score": 8.5, "delisting_info": delisting_db["A556"]},
        ],
        regime_score=0.75,
        market_data={"kospi": 2900, "kospi_120ma": 2600, "vix_proxy": 19.0},
        current_prices={"A111": 18000, "A444": 52000, "A556": 9000},
    )

    total_value = engine.get_total_value(final_prices)
    baseline_return_pct = (total_value / engine.initial_capital - 1.0) * 100

    values = np.array([v for _, v in equity_curve] + [total_value], dtype=float)
    running_peak = np.maximum.accumulate(values)
    dd_series = np.where(running_peak > 0, values / running_peak - 1.0, 0.0)
    mdd_pct = dd_series.min() * 100

    crisis_logs = [l for l in engine.logs if ("Soft Trigger" in l) or ("Hard Trigger" in l) or ("Re-entry" in l)]

    print("\n=== STAGE05 RULEBOOK V3.2 HYBRID CRISIS CHECK ===")
    print(f"Years simulated: {sample_years[0]}-{sample_years[-1]}")
    print(f"Final capital: {engine.capital:,.0f} KRW")
    print(f"Final total value: {total_value:,.0f} KRW")
    print(f"Baseline return: {baseline_return_pct:,.2f}%")
    print(f"MDD: {mdd_pct:,.2f}%")
    print(f"Target(>2000%): {'PASS' if baseline_return_pct > 2000 else 'FAIL'}")
    print(f"Open positions: {list(engine.portfolio.keys())}")
    print(f"Trade records: {len(engine.history)}")

    print("\n--- Crisis Log Sample ---")
    for line in crisis_logs[:8]:
        print(line)
