import pandas as pd

from research.strategy_runner import discover_strategy_classes, run_all_strategies


def _fake_df():
    idx = pd.date_range("2025-01-01", periods=200, freq="min", tz="UTC")
    px = pd.Series(range(200), index=idx, dtype=float) + 100.0
    return pd.DataFrame(
        {
            "open": px,
            "high": px + 1,
            "low": px - 1,
            "close": px,
            "volume": 1.0,
            "funding_rate": 0.0,
        },
        index=idx,
    )


def test_strategy_discovery_contains_default_strategies():
    names = {cls.name for cls in discover_strategy_classes()}
    assert "ema_cross" in names
    assert "rsi_mean_revert" in names


def test_run_all_strategies_returns_ranked_results():
    data = {"BTCUSDT": _fake_df(), "ETHUSDT": _fake_df()}
    cfg = {
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "interval": "1m",
        "initial_equity": 10000.0,
        "fee_rate_taker": 0.0005,
        "slippage_bps": 2,
        "leverage": 2.0,
        "max_position_pct": 1.0,
        "rebalance_threshold": 0.05,
    }

    leaderboard = run_all_strategies(data, cfg)
    assert len(leaderboard) > 0
    assert leaderboard[0]["strategy"] in {"ema_cross", "rsi_mean_revert"}
    assert "sharpe" in leaderboard[0]
