from dataclasses import dataclass


@dataclass
class Position:
    qty: float = 0.0
    entry_price: float = 0.0


class BrokerSim:
    def __init__(
        self,
        symbols: list[str],
        initial_equity: float,
        fee_rate_taker: float,
        slippage_bps: float,
        leverage: float,
        max_position_pct: float = 1.0,
        rebalance_threshold: float = 0.05,
    ):
        self.symbols = symbols
        self.cash = initial_equity
        self.equity = initial_equity

        self.fee_rate = fee_rate_taker
        self.slippage = slippage_bps / 10000.0
        self.leverage = leverage
        self.max_position_pct = max_position_pct
        self.rebalance_threshold = rebalance_threshold

        self.positions = {s: Position() for s in symbols}
        self.last_prices = {s: None for s in symbols}

        self.total_fee = 0.0
        self.total_slippage_cost = 0.0
        self.total_funding = 0.0
        self.realized_pnl = 0.0

    def _unrealized_pnl(self) -> float:
        upnl = 0.0
        for s in self.symbols:
            pos = self.positions[s]
            px = self.last_prices[s]
            if px is None or pos.qty == 0.0:
                continue
            upnl += (px - pos.entry_price) * pos.qty
        return upnl

    def mark_to_market(self, prices: dict[str, float]) -> None:
        self.last_prices.update(prices)
        self.equity = self.cash + self._unrealized_pnl()

    def apply_funding(self, funding_rates: dict[str, float]) -> None:
        """
        Funding for linear perp:
        - positive funding_rate => longs pay shorts
        - payment = - qty * mark_price * funding_rate
        """
        funding_delta = 0.0
        for s in self.symbols:
            pos = self.positions[s]
            px = self.last_prices[s]
            fr = funding_rates.get(s, 0.0)
            if px is None or pos.qty == 0.0 or fr == 0.0:
                continue
            funding_delta += -pos.qty * px * fr

        self.cash += funding_delta
        self.total_funding += funding_delta

    def _update_position(self, symbol: str, delta_qty: float, exec_price: float) -> None:
        pos = self.positions[symbol]
        old_qty = pos.qty
        new_qty = old_qty + delta_qty

        # Same direction add
        if old_qty == 0.0 or old_qty * delta_qty > 0:
            total_abs = abs(old_qty) + abs(delta_qty)
            if total_abs == 0:
                pos.qty, pos.entry_price = 0.0, 0.0
                return
            pos.entry_price = (pos.entry_price * abs(old_qty) + exec_price * abs(delta_qty)) / total_abs
            pos.qty = new_qty
            return

        # Reduce or flip direction
        closing_qty = min(abs(old_qty), abs(delta_qty))
        pnl = (exec_price - pos.entry_price) * closing_qty * (1 if old_qty > 0 else -1)
        self.cash += pnl
        self.realized_pnl += pnl

        if abs(new_qty) < 1e-12:
            pos.qty, pos.entry_price = 0.0, 0.0
            return

        # flipped: remaining qty opens at new trade price
        if old_qty * new_qty < 0:
            pos.qty = new_qty
            pos.entry_price = exec_price
        else:
            pos.qty = new_qty

    def rebalance(self, targets: dict[str, float], prices: dict[str, float]) -> None:
        n = max(len(self.symbols), 1)
        budget_per_symbol = self.equity * self.leverage / n

        for symbol in self.symbols:
            price = prices[symbol]
            target = max(-self.max_position_pct, min(self.max_position_pct, targets.get(symbol, 0.0)))
            target_notional = budget_per_symbol * target
            current_notional = self.positions[symbol].qty * price

            if budget_per_symbol > 0 and abs(target_notional - current_notional) / budget_per_symbol < self.rebalance_threshold:
                continue

            delta_notional = target_notional - current_notional
            if abs(delta_notional) < 1e-12:
                continue

            side = 1 if delta_notional > 0 else -1
            exec_price = price * (1 + self.slippage * side)
            delta_qty = delta_notional / exec_price
            trade_notional = abs(delta_qty * exec_price)

            fee = trade_notional * self.fee_rate
            slippage_cost = abs(delta_qty) * abs(exec_price - price)

            self._update_position(symbol, delta_qty, exec_price)
            self.cash -= fee + slippage_cost
            self.total_fee += fee
            self.total_slippage_cost += slippage_cost
