import itertools

import pandas as pd

from strategies.base import StrategyBase


class EmaCrossPortfolioStrategy(StrategyBase):
    name = "ema_cross"

    def __init__(self, symbols: list[str], fast: int = 12, slow: int = 48):
        self.symbols = symbols
        self.fast = fast
        self.slow = slow
        self.features: dict[str, pd.DataFrame] = {}

    @classmethod
    def param_grid(cls) -> list[dict]:
        fast_list = [8, 12, 16]
        slow_list = [32, 48, 72]
        return [{"fast": f, "slow": s} for f, s in itertools.product(fast_list, slow_list) if f < s]

    def prepare(self, data: dict[str, pd.DataFrame]) -> None:
        for symbol in self.symbols:
            df = data[symbol].copy()
            df["ema_fast"] = df["close"].ewm(span=self.fast, adjust=False).mean()
            df["ema_slow"] = df["close"].ewm(span=self.slow, adjust=False).mean()
            self.features[symbol] = df

    def on_bar(self, ts: pd.Timestamp, state: dict) -> dict[str, float]:
        targets: dict[str, float] = {}
        for symbol in self.symbols:
            row = self.features[symbol].loc[ts]
            if pd.isna(row["ema_slow"]):
                targets[symbol] = 0.0
            elif row["ema_fast"] > row["ema_slow"]:
                targets[symbol] = 1.0
            elif row["ema_fast"] < row["ema_slow"]:
                targets[symbol] = -1.0
            else:
                targets[symbol] = 0.0
        return targets
