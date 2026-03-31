import pandas as pd

from strategies.base import StrategyBase


class RsiMeanRevertStrategy(StrategyBase):
    name = "rsi_mean_revert"
    param_grid = {
        "period": [8, 14],
        "lower": [25, 30],
        "upper": [70, 75],
    }

    def __init__(self, symbols: list[str], period: int = 14, lower: float = 30, upper: float = 70):
        self.symbols = symbols
        self.period = period
        self.lower = lower
        self.upper = upper
        self.features: dict[str, pd.DataFrame] = {}

    def prepare(self, data: dict[str, pd.DataFrame]) -> None:
        for symbol in self.symbols:
            df = data[symbol].copy()
            delta = df["close"].diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(self.period).mean()
            avg_loss = loss.rolling(self.period).mean()
            rs = avg_gain / avg_loss.replace(0, pd.NA)
            df["rsi"] = 100 - (100 / (1 + rs))
            self.features[symbol] = df

    def on_bar(self, ts: pd.Timestamp, state: dict) -> dict[str, float]:
        targets: dict[str, float] = {}
        for symbol in self.symbols:
            rsi = self.features[symbol].loc[ts, "rsi"]
            if pd.isna(rsi):
                targets[symbol] = 0.0
            elif rsi < self.lower:
                targets[symbol] = 1.0
            elif rsi > self.upper:
                targets[symbol] = -1.0
            else:
                targets[symbol] = 0.0
        return targets
