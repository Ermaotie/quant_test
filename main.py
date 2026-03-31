import yaml

from exchange.binance_rest import fetch_klines_multi
from research.strategy_runner import dump_report, run_all_strategies


def load_config(path: str = "config/settings.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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

    leaderboard = run_all_strategies(data, cfg)
    if not leaderboard:
        raise RuntimeError("No strategy results generated.")

    dump_report(leaderboard, out_dir=cfg.get("result_dir", "results"))

    print("=== Strategy Leaderboard Top 5 ===")
    for row in leaderboard[:5]:
        print(row)


if __name__ == "__main__":
    main()
