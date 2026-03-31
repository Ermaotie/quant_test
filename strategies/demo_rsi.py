import itertools

import pandas as pd

from strategies.base import StrategyBase


class RsiMeanReversionStrategy(StrategyBase):
    name = "rsi_reversion"

    def __init__(
        self,
        symbols: list[str],
        period: int = 14,
        overbought: float = 70.0,
        oversold: float = 30.0,
    ):
        self.symbols = symbols
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        self.features: dict[str, pd.DataFrame] = {}

    @classmethod
    def param_grid(cls) -> list[dict]:
        periods = [10, 14]
        levels = [(75.0, 25.0), (70.0, 30.0)]
        return [
            {"period": p, "overbought": ob, "oversold": os}
            for p, (ob, os) in itertools.product(periods, levels)
        ]

    def _rsi(self, close: pd.Series) -> pd.Series:
        diff = close.diff()
        up = diff.clip(lower=0)
        down = -diff.clip(upper=0)
        avg_up = up.ewm(alpha=1 / self.period, adjust=False).mean()
        avg_down = down.ewm(alpha=1 / self.period, adjust=False).mean()
        rs = avg_up / avg_down.replace(0, pd.NA)
        return 100 - (100 / (1 + rs))

    def prepare(self, data: dict[str, pd.DataFrame]) -> None:
        for symbol in self.symbols:
            df = data[symbol].copy()
            df["rsi"] = self._rsi(df["close"]).fillna(50)
            self.features[symbol] = df

    def on_bar(self, ts: pd.Timestamp, state: dict) -> dict[str, float]:
        targets: dict[str, float] = {}
        for symbol in self.symbols:
            rsi = self.features[symbol].loc[ts, "rsi"]
            if rsi >= self.overbought:
                targets[symbol] = -1.0
            elif rsi <= self.oversold:
                targets[symbol] = 1.0
            else:
                targets[symbol] = 0.0
        return targets
