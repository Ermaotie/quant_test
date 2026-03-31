from abc import ABC, abstractmethod

import pandas as pd


class StrategyBase(ABC):
    @abstractmethod
    def prepare(self, data: dict[str, pd.DataFrame]) -> None:
        """Pre-compute indicators/features to speed up on_bar."""

    @abstractmethod
    def on_bar(self, ts: pd.Timestamp, state: dict) -> dict[str, float]:
        """Return target position pct by symbol, each in [-1, 1]."""
