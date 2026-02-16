import pandas as pd
import numpy as np

class BacktestEngine:
    # Liquidity tiers based on 20d avg turnover (KRW)
    LIQUIDITY_TIERS = [
        (300_000_000_000, "L1"),  # >= 300억
        (100_000_000_000, "L2"),  # 100억 ~ 300억
        (30_000_000_000, "L3"),   # 30억 ~ 100억
        (0, "L4"),                # < 30억
    ]

    # Slippage / spread cost (round-trip) by tier
    SLIPPAGE = {
        "L1": 0.005,
        "L2": 0.010,
        "L3": 0.015,
        "L4": 0.025,
    }

    # Trading constraints by tier
    CONSTRAINTS = {
        "L1": {"min_hold_days": 0, "cooldown_days": 0, "tranches": 1},
        "L2": {"min_hold_days": 3, "cooldown_days": 0, "tranches": 2},
        "L3": {"min_hold_days": 7, "cooldown_days": 5, "tranches": 3},
        "L4": {"min_hold_days": 0, "cooldown_days": 0, "tranches": 0},  # buy blocked
    }

    def __init__(self, initial_capital=100_000_000, round_trip_penalty=0.03):
        self.capital = initial_capital
        self.penalty = round_trip_penalty
        self.portfolio = {} # {code: {'shares': N, 'entry_price': P, 'entry_date': D, 'tier': 'L1'}}
        self.history = []
        self.last_exit = {}  # {code: last_sell_date}

    def _classify_liquidity(self, avg_turnover):
        if avg_turnover is None:
            return None
        for threshold, tier in self.LIQUIDITY_TIERS:
            if avg_turnover >= threshold:
                return tier
        return "L4"

    def _effective_price(self, price, action, tier):
        if tier is None:
            penalty = self.penalty
        else:
            penalty = self.SLIPPAGE.get(tier, self.penalty)
        if action == 'BUY':
            return price * (1 + penalty / 2)
        return price * (1 - penalty / 2)

    def _days_between(self, d1, d2):
        try:
            d1 = pd.to_datetime(d1)
            d2 = pd.to_datetime(d2)
            return (d2 - d1).days
        except Exception:
            return None

    def execute_trade(self, date, code, action, price, weight=1.0, avg_turnover=None):
        """
        Simulates a trade.
        action: 'BUY' or 'SELL'
        avg_turnover: 20d avg turnover (KRW) for liquidity tier rules
        """
        tier = self._classify_liquidity(avg_turnover)
        constraints = self.CONSTRAINTS.get(tier, {}) if tier else {}

        if action == 'BUY':
            if tier == "L4":
                return  # buy blocked for ultra-low liquidity
            if code in self.last_exit and constraints.get("cooldown_days", 0) > 0:
                gap = self._days_between(self.last_exit[code], date)
                if gap is not None and gap < constraints["cooldown_days"]:
                    return

            if code not in self.portfolio:
                buy_amount = self.capital * weight
                effective_price = self._effective_price(price, 'BUY', tier)
                shares = buy_amount // effective_price
                cost = shares * effective_price

                if cost <= self.capital and shares > 0:
                    self.capital -= cost
                    self.portfolio[code] = {
                        'shares': shares,
                        'entry_price': price,
                        'effective_entry_price': effective_price,  # slippage-adjusted
                        'entry_date': date,
                        'tier': tier
                    }
                    self.history.append({
                        'Date': date,
                        'Code': code,
                        'Action': 'BUY',
                        'Price': price,
                        'Shares': shares,
                        'Tier': tier
                    })

        elif action == 'SELL':
            if code in self.portfolio:
                entry_tier = self.portfolio[code].get('tier')
                sell_tier = tier or entry_tier
                sell_constraints = self.CONSTRAINTS.get(sell_tier, {}) if sell_tier else {}

                min_hold = sell_constraints.get("min_hold_days", 0)
                entry_date = self.portfolio[code].get('entry_date')
                if min_hold and entry_date is not None:
                    held_days = self._days_between(entry_date, date)
                    if held_days is not None and held_days < min_hold:
                        return

                shares = self.portfolio[code]['shares']
                effective_price = self._effective_price(price, 'SELL', sell_tier)
                revenue = shares * effective_price
                self.capital += revenue

                # Use effective prices for accurate profit calculation (includes slippage)
                effective_entry = self.portfolio[code].get('effective_entry_price', self.portfolio[code]['entry_price'])
                if effective_entry and effective_entry > 0:
                    profit = (effective_price - effective_entry) / effective_entry
                else:
                    profit = 0.0  # Guard against division by zero
                del self.portfolio[code]
                self.last_exit[code] = date
                self.history.append({
                    'Date': date,
                    'Code': code,
                    'Action': 'SELL',
                    'Price': price,
                    'Profit': profit,
                    'Tier': sell_tier
                })

    def get_total_value(self, current_prices, apply_liquidation_cost=True):
        """
        Calculates current liquidation value.
        current_prices: {code: price}
        apply_liquidation_cost: if True, applies slippage to exit prices (conservative)
        """
        asset_value = 0
        for code, info in self.portfolio.items():
            if code in current_prices:
                price = current_prices[code]
                if apply_liquidation_cost:
                    tier = info.get('tier', 'L2')
                    price = self._effective_price(price, 'SELL', tier)
                asset_value += info['shares'] * price
        return self.capital + asset_value

if __name__ == "__main__":
    engine = BacktestEngine()
    print(f"Engine Initialized. Capital: {engine.capital:,} KRW, Penalty: {engine.penalty*100}%")
