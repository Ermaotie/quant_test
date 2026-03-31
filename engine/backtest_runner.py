import pandas as pd


class BacktestRunner:
    def __init__(self, data: dict[str, pd.DataFrame], strategy, broker):
        self.data = data
        self.strategy = strategy
        self.broker = broker
        self.history = []

    def _timeline(self) -> pd.DatetimeIndex:
        timeline = None
        for df in self.data.values():
            timeline = df.index if timeline is None else timeline.intersection(df.index)
        return timeline if timeline is not None else pd.DatetimeIndex([])

    def run(self) -> pd.DataFrame:
        self.strategy.prepare(self.data)
        timeline = self._timeline()

        for ts in timeline:
            prices = {s: self.data[s].loc[ts, "close"] for s in self.data}
            funding_rates = {
                s: float(self.data[s].loc[ts, "funding_rate"]) if "funding_rate" in self.data[s].columns else 0.0
                for s in self.data
            }

            self.broker.mark_to_market(prices)
            state = {
                "equity": self.broker.equity,
                "positions": {s: self.broker.positions[s].qty for s in self.broker.symbols},
            }

            targets = self.strategy.on_bar(ts, state)
            self.broker.rebalance(targets, prices)
            self.broker.apply_funding(funding_rates)
            self.broker.mark_to_market(prices)

            row = {
                "timestamp": ts,
                "equity": self.broker.equity,
                "cash": self.broker.cash,
                "realized_pnl": self.broker.realized_pnl,
                "fee": self.broker.total_fee,
                "slippage_cost": self.broker.total_slippage_cost,
                "funding_total": self.broker.total_funding,
            }
            for s in self.broker.symbols:
                row[f"pos_{s}"] = self.broker.positions[s].qty
                row[f"entry_{s}"] = self.broker.positions[s].entry_price
                row[f"px_{s}"] = prices[s]
            self.history.append(row)

        return pd.DataFrame(self.history).set_index("timestamp")
