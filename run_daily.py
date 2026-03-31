import argparse
import importlib
import inspect
import json
import pkgutil
from pathlib import Path

import pandas as pd
import yaml

from analytics.metrics import calc_metrics
from engine.backtest_runner import BacktestRunner
from engine.broker_sim import BrokerSim
from exchange.binance_rest import fetch_klines_multi
from strategies.base import StrategyBase
import strategies


def load_config(path: str = "config/settings.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def discover_strategies() -> list[type[StrategyBase]]:
    found: list[type[StrategyBase]] = []
    for _, modname, _ in pkgutil.iter_modules(strategies.__path__):
        if modname in {"base", "__init__"}:
            continue
        module = importlib.import_module(f"strategies.{modname}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, StrategyBase) and obj is not StrategyBase:
                found.append(obj)
    return found


def run_one(cfg: dict, data: dict[str, pd.DataFrame], strategy_cls: type[StrategyBase], params: dict) -> dict:
    strategy = strategy_cls(symbols=cfg["symbols"], **params)
    broker = BrokerSim(
        symbols=cfg["symbols"],
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
    return {
        "strategy": strategy_cls.name,
        "params": params,
        **metrics,
        "fee_total": broker.total_fee,
        "slippage_total": broker.total_slippage_cost,
        "funding_total": broker.total_funding,
        "realized_pnl": broker.realized_pnl,
    }


def evaluate_all(cfg: dict) -> pd.DataFrame:
    data = fetch_klines_multi(
        cfg["symbols"],
        cfg["interval"],
        cfg["start_time"],
        cfg["end_time"],
        include_funding=cfg.get("include_funding", True),
    )
    if any(df.empty for df in data.values()):
        raise RuntimeError("One or more symbols returned empty data.")

    rows = []
    for strategy_cls in discover_strategies():
        for params in strategy_cls.param_grid():
            rows.append(run_one(cfg, data, strategy_cls, params))

    leaderboard = pd.DataFrame(rows)
    leaderboard = leaderboard.sort_values(
        by=["sharpe", "calmar", "total_return"], ascending=[False, False, False]
    ).reset_index(drop=True)
    return leaderboard


def write_outputs(df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "leaderboard.csv"
    json_path = output_dir / "best_strategy.json"
    md_path = output_dir / "summary.md"

    df.to_csv(csv_path, index=False)

    best = df.iloc[0].to_dict()
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(best, f, ensure_ascii=False, indent=2)

    top = df.head(10).copy()
    md_lines = [
        "# Daily Strategy Leaderboard",
        "",
        f"Best Strategy: **{best['strategy']}**  ",
        f"Params: `{best['params']}`  ",
        f"Sharpe: `{best['sharpe']:.4f}`, Calmar: `{best['calmar']:.4f}`, Return: `{best['total_return']:.4%}`",
        "",
        "## Top 10",
        top[["strategy", "params", "sharpe", "calmar", "total_return", "max_drawdown"]].to_markdown(index=False),
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("\n".join(md_lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--output-dir", default="artifacts")
    args = parser.parse_args()

    cfg = load_config(args.config)
    leaderboard = evaluate_all(cfg)
    write_outputs(leaderboard, Path(args.output_dir))


if __name__ == "__main__":
    main()
