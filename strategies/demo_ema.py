import pandas as pd

from strategies.base import StrategyBase


class EmaCrossPortfolioStrategy(StrategyBase):
    name = "ema_cross"
    param_grid = {
        "fast": [8, 12, 16],
        "slow": [32, 48, 72],
    }

    def __init__(self, symbols: list[str], fast: int = 12, slow: int = 48):
        self.symbols = symbols
        self.fast = fast
        self.slow = slow
        self.features: dict[str, pd.DataFrame] = {}

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
