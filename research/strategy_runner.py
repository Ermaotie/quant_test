import importlib
import inspect
import itertools
import json
import pkgutil
from pathlib import Path

from analytics.metrics import calc_metrics
from engine.backtest_runner import BacktestRunner
from engine.broker_sim import BrokerSim
from strategies.base import StrategyBase


def discover_strategy_classes() -> list[type[StrategyBase]]:
    classes = []
    for mod in pkgutil.iter_modules(["strategies"]):
        if mod.name.startswith("_") or mod.name == "base":
            continue
        module = importlib.import_module(f"strategies.{mod.name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, StrategyBase) and obj is not StrategyBase:
                classes.append(obj)
    return classes


def _param_combos(strategy_cls: type[StrategyBase]) -> list[dict]:
    grid = getattr(strategy_cls, "param_grid", {}) or {}
    if not grid:
        return [{}]
    keys = list(grid)
    combos = []
    for vals in itertools.product(*(grid[k] for k in keys)):
        combos.append(dict(zip(keys, vals)))
    return combos


def run_strategy(data: dict, cfg: dict, strategy_cls: type[StrategyBase], params: dict):
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
    m = calc_metrics(result["equity"], periods_per_year=periods_per_year)
    m.update(
        {
            "strategy": strategy_cls.name,
            "params": params,
            "fee_total": broker.total_fee,
            "slippage_total": broker.total_slippage_cost,
            "funding_total": broker.total_funding,
            "realized_pnl": broker.realized_pnl,
        }
    )
    return m


def run_all_strategies(data: dict, cfg: dict) -> list[dict]:
    leaderboard = []
    for cls in discover_strategy_classes():
        for params in _param_combos(cls):
            if "fast" in params and "slow" in params and params["fast"] >= params["slow"]:
                continue
            row = run_strategy(data, cfg, cls, params)
            leaderboard.append(row)

    leaderboard.sort(key=lambda x: (x["sharpe"], x["calmar"], x["total_return"]), reverse=True)
    return leaderboard


def dump_report(leaderboard: list[dict], out_dir: str = "results") -> tuple[str, str]:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    json_path = str(Path(out_dir) / "leaderboard.json")
    md_path = str(Path(out_dir) / "best_strategy.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(leaderboard, f, ensure_ascii=False, indent=2)

    top = leaderboard[0] if leaderboard else {}
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Daily Best Strategy\n\n")
        if not top:
            f.write("No strategy result generated.\n")
        else:
            f.write(f"- Strategy: `{top['strategy']}`\n")
            f.write(f"- Params: `{top['params']}`\n")
            f.write(f"- Sharpe: `{top['sharpe']:.4f}`\n")
            f.write(f"- Calmar: `{top['calmar']:.4f}`\n")
            f.write(f"- Total Return: `{top['total_return']:.4%}`\n")
    return json_path, md_path
