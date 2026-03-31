import time
from typing import Iterable

import pandas as pd
import requests

SPOT_BASE_URL = "https://api.binance.com"
FUTURES_BASE_URL = "https://fapi.binance.com"


def _to_millis(dt_str: str) -> int:
    return int(pd.Timestamp(dt_str, tz="UTC").timestamp() * 1000)


def fetch_klines(symbol: str, interval: str, start_time: str, end_time: str) -> pd.DataFrame:
    """Fetch spot klines as OHLCV for research/backtest bars."""
    start_ms = _to_millis(start_time)
    end_ms = _to_millis(end_time)

    all_rows = []
    limit = 1000
    url = f"{SPOT_BASE_URL}/api/v3/klines"

    while True:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": limit,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            break

        all_rows.extend(rows)
        start_ms = rows[-1][0] + 1
        if len(rows) < limit:
            break
        time.sleep(0.08)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        all_rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "num_trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df[["open_time", "open", "high", "low", "close", "volume"]].set_index("open_time")


def fetch_funding_rates(symbol: str, start_time: str, end_time: str) -> pd.Series:
    """Fetch perpetual funding rates and return time-indexed rate series."""
    start_ms = _to_millis(start_time)
    end_ms = _to_millis(end_time)
    url = f"{FUTURES_BASE_URL}/fapi/v1/fundingRate"
    limit = 1000

    rows_all = []
    while True:
        params = {
            "symbol": symbol,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": limit,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            break

        rows_all.extend(rows)
        start_ms = int(rows[-1]["fundingTime"]) + 1
        if len(rows) < limit:
            break
        time.sleep(0.08)

    if not rows_all:
        return pd.Series(dtype=float, name="funding_rate")

    df = pd.DataFrame(rows_all)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["fundingRate"] = df["fundingRate"].astype(float)
    return df.set_index("fundingTime")["fundingRate"].rename("funding_rate")


def fetch_klines_multi(
    symbols: Iterable[str], interval: str, start_time: str, end_time: str, include_funding: bool = True
) -> dict[str, pd.DataFrame]:
    """Fetch multi-symbol bars. Optionally merge perpetual funding into bar frame."""
    out: dict[str, pd.DataFrame] = {}
    for s in symbols:
        bars = fetch_klines(s, interval, start_time, end_time)
        if include_funding and not bars.empty:
            fr = fetch_funding_rates(s, start_time, end_time)
            if fr.empty:
                bars["funding_rate"] = 0.0
            else:
                bars = bars.join(fr, how="left")
                bars["funding_rate"] = bars["funding_rate"].fillna(0.0)
        out[s] = bars
    return out
