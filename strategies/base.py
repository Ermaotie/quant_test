from abc import ABC, abstractmethod

import pandas as pd


class StrategyBase(ABC):
    name = "base"

    @classmethod
    def param_grid(cls) -> list[dict]:
        """Parameter combinations used by auto-backtest pipeline."""
        return [{}]

    @abstractmethod
    def prepare(self, data: dict[str, pd.DataFrame]) -> None:
        """Pre-compute indicators/features to speed up on_bar."""

    @abstractmethod
    def on_bar(self, ts: pd.Timestamp, state: dict) -> dict[str, float]:
        """Return target position pct by symbol, each in [-1, 1]."""
