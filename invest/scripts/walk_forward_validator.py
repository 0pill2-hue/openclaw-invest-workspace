"""
Walk-Forward Validation Framework
- Prevents overfitting by using rolling train/validation windows
- Supports regime-separated performance analysis
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Tuple, Any
import json
import os

class WalkForwardValidator:
    """
    Walk-forward optimization and validation framework.
    
    Usage:
        validator = WalkForwardValidator(
            train_months=24,
            validation_months=6,
            step_months=3
        )
        results = validator.run(data, strategy_fn, optimize_fn)
    """
    
    def __init__(
        self,
        train_months: int = 24,
        validation_months: int = 6,
        step_months: int = 3,
        min_train_samples: int = 100
    ):
        self.train_months = train_months
        self.validation_months = validation_months
        self.step_months = step_months
        self.min_train_samples = min_train_samples
        self.results = []
    
    def _generate_windows(self, start_date: datetime, end_date: datetime) -> List[Tuple[datetime, datetime, datetime, datetime]]:
        """Generate train/validation window pairs."""
        windows = []
        current = start_date + timedelta(days=self.train_months * 30)
        
        while current + timedelta(days=self.validation_months * 30) <= end_date:
            train_start = current - timedelta(days=self.train_months * 30)
            train_end = current
            val_start = current
            val_end = current + timedelta(days=self.validation_months * 30)
            
            windows.append((train_start, train_end, val_start, val_end))
            current += timedelta(days=self.step_months * 30)
        
        return windows
    
    def run(
        self,
        data: pd.DataFrame,
        strategy_fn: Callable,
        optimize_fn: Callable = None,
        date_col: str = 'Date'
    ) -> Dict[str, Any]:
        """
        Run walk-forward validation.
        
        Args:
            data: DataFrame with date column
            strategy_fn: Function(data, params) -> returns
            optimize_fn: Function(train_data) -> optimal_params (optional)
        
        Returns:
            Dictionary with OOS results and statistics
        """
        if date_col not in data.columns and data.index.name != date_col:
            raise ValueError(f"Date column '{date_col}' not found")
        
        if data.index.name != date_col:
            data = data.set_index(date_col)
        
        data.index = pd.to_datetime(data.index)
        start_date = data.index.min()
        end_date = data.index.max()
        
        windows = self._generate_windows(start_date, end_date)
        
        all_oos_returns = []
        window_results = []
        
        for i, (train_start, train_end, val_start, val_end) in enumerate(windows):
            train_data = data[(data.index >= train_start) & (data.index < train_end)]
            val_data = data[(data.index >= val_start) & (data.index < val_end)]
            
            if len(train_data) < self.min_train_samples:
                continue
            
            # Optimize on training data (if optimizer provided)
            if optimize_fn:
                params = optimize_fn(train_data)
            else:
                params = {}
            
            # Validate on out-of-sample data
            oos_returns = strategy_fn(val_data, params)
            
            window_result = {
                'window': i + 1,
                'train_start': train_start.strftime('%Y-%m-%d'),
                'train_end': train_end.strftime('%Y-%m-%d'),
                'val_start': val_start.strftime('%Y-%m-%d'),
                'val_end': val_end.strftime('%Y-%m-%d'),
                'params': params,
                'oos_return': float(np.sum(oos_returns)) if len(oos_returns) > 0 else 0,
                'oos_sharpe': self._calc_sharpe(oos_returns),
                'oos_mdd': self._calc_mdd(oos_returns),
                'n_trades': len(oos_returns)
            }
            window_results.append(window_result)
            all_oos_returns.extend(oos_returns)
        
        # Aggregate statistics
        if all_oos_returns:
            aggregate = {
                'total_oos_return': float(np.sum(all_oos_returns)),
                'avg_oos_return': float(np.mean(all_oos_returns)),
                'oos_sharpe': self._calc_sharpe(all_oos_returns),
                'oos_mdd': self._calc_mdd(all_oos_returns),
                'n_windows': len(window_results),
                'win_rate': sum(1 for r in all_oos_returns if r > 0) / len(all_oos_returns) if all_oos_returns else 0
            }
        else:
            aggregate = {'error': 'No valid windows'}
        
        self.results = {
            'windows': window_results,
            'aggregate': aggregate,
            'config': {
                'train_months': self.train_months,
                'validation_months': self.validation_months,
                'step_months': self.step_months
            }
        }
        
        return self.results
    
    def _calc_sharpe(self, returns: List[float], risk_free: float = 0.03) -> float:
        """Calculate annualized Sharpe ratio."""
        if not returns or len(returns) < 2:
            return 0.0
        returns = np.array(returns)
        excess = returns - risk_free / 252
        if np.std(excess) == 0:
            return 0.0
        return float(np.mean(excess) / np.std(excess) * np.sqrt(252))
    
    def _calc_mdd(self, returns: List[float]) -> float:
        """Calculate maximum drawdown."""
        if not returns:
            return 0.0
        cumulative = np.cumprod(1 + np.array(returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        return float(np.min(drawdowns))
    
    def save_results(self, path: str):
        """Save results to JSON file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)


class RegimeAnalyzer:
    """
    Analyze strategy performance by market regime.
    """
    
    REGIMES = {
        'bull': {'condition': lambda r: r > 0.10},      # >10% annual
        'bear': {'condition': lambda r: r < -0.10},     # <-10% annual
        'sideways': {'condition': lambda r: abs(r) <= 0.10},
        'high_vol': {'condition': lambda v: v > 0.25},  # >25% annual vol
    }
    
    def __init__(self, market_data: pd.DataFrame, lookback_days: int = 60):
        self.market_data = market_data
        self.lookback_days = lookback_days
    
    def classify_regime(self, date: datetime) -> str:
        """Classify market regime at a given date."""
        lookback_start = date - timedelta(days=self.lookback_days)
        period_data = self.market_data[
            (self.market_data.index >= lookback_start) & 
            (self.market_data.index <= date)
        ]
        
        if len(period_data) < 20:
            return 'unknown'
        
        returns = period_data['Close'].pct_change().dropna()
        total_return = (period_data['Close'].iloc[-1] / period_data['Close'].iloc[0]) - 1
        annualized_return = total_return * (252 / len(period_data))
        annualized_vol = returns.std() * np.sqrt(252)
        
        if annualized_vol > 0.25:  # Match REGIMES threshold
            return 'high_vol'
        elif annualized_return > 0.10:  # Match REGIMES threshold
            return 'bull'
        elif annualized_return < -0.10:  # Match REGIMES threshold
            return 'bear'
        else:
            return 'sideways'
    
    def analyze_by_regime(self, trades: List[Dict]) -> Dict[str, Dict]:
        """Analyze trade performance by regime."""
        regime_trades = {'bull': [], 'bear': [], 'sideways': [], 'high_vol': [], 'unknown': []}
        
        for trade in trades:
            trade_date = pd.to_datetime(trade.get('Date'))
            regime = self.classify_regime(trade_date)
            regime_trades[regime].append(trade)
        
        results = {}
        for regime, trades_list in regime_trades.items():
            if not trades_list:
                continue
            profits = [t.get('Profit', 0) for t in trades_list if 'Profit' in t]
            results[regime] = {
                'n_trades': len(trades_list),
                'avg_profit': float(np.mean(profits)) if profits else 0,
                'win_rate': sum(1 for p in profits if p > 0) / len(profits) if profits else 0,
                'total_profit': float(np.sum(profits)) if profits else 0
            }
        
        return results


if __name__ == "__main__":
    print("Walk-Forward Validator initialized.")
    print("Usage: Import WalkForwardValidator and RegimeAnalyzer classes.")
