import itertools

import yaml

from analytics.metrics import calc_metrics
from engine.backtest_runner import BacktestRunner
from engine.broker_sim import BrokerSim
from exchange.binance_rest import fetch_klines_multi
from strategies.demo_ema import EmaCrossPortfolioStrategy


def load_config(path: str = "config/settings.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_once(cfg: dict, data: dict, fast: int, slow: int):
    symbols = cfg["symbols"]
    strategy = EmaCrossPortfolioStrategy(symbols=symbols, fast=fast, slow=slow)
    broker = BrokerSim(
        symbols=symbols,
        initial_equity=cfg["initial_equity"],
        fee_rate_taker=cfg["fee_rate_taker"],
        slippage_bps=cfg["slippage_bps"],
        leverage=cfg["leverage"],
        max_position_pct=cfg["max_position_pct"],
        rebalance_threshold=cfg.get("rebalance_threshold", 0.05),
    )

    result = BacktestRunner(data, strategy, broker).run()
    periods_per_year = 365 * 24 * (60 // int(cfg["interval"].replace("m", "")))
    metrics = calc_metrics(result["equity"], periods_per_year=periods_per_year)
    metrics["fee_total"] = broker.total_fee
    metrics["slippage_total"] = broker.total_slippage_cost
    metrics["funding_total"] = broker.total_funding
    metrics["realized_pnl"] = broker.realized_pnl
    return result, metrics


def grid_search(cfg: dict, data: dict):
    gs = cfg.get("grid_search", {})
    fast_list = gs.get("fast_list", [cfg["strategy"]["params"].get("fast", 12)])
    slow_list = gs.get("slow_list", [cfg["strategy"]["params"].get("slow", 48)])

    leaderboard = []
    for fast, slow in itertools.product(fast_list, slow_list):
        if fast >= slow:
            continue
        _, m = run_once(cfg, data, fast, slow)
        leaderboard.append({"fast": fast, "slow": slow, **m})

    leaderboard.sort(key=lambda x: (x["sharpe"], x["calmar"], x["total_return"]), reverse=True)
    return leaderboard


def main():
    cfg = load_config()
    data = fetch_klines_multi(
        cfg["symbols"],
        cfg["interval"],
        cfg["start_time"],
        cfg["end_time"],
        include_funding=cfg.get("include_funding", True),
    )
    if any(df.empty for df in data.values()):
        raise RuntimeError("One or more symbols returned empty data.")

    if cfg.get("grid_search", {}).get("enabled", False):
        board = grid_search(cfg, data)
        print("=== Grid Search Leaderboard (Top 5) ===")
        for row in board[:5]:
            print(row)
        best = board[0]
        fast, slow = best["fast"], best["slow"]
        print(f"\nBest Params -> fast={fast}, slow={slow}")
    else:
        fast = cfg["strategy"]["params"].get("fast", 12)
        slow = cfg["strategy"]["params"].get("slow", 48)

    _, metrics = run_once(cfg, data, fast, slow)
    print("\n=== Backtest Metrics ===")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"{k}: {v:.6f}")
        else:
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()
