import io
import os
import time
import zipfile
from datetime import timedelta
from typing import Iterable

import pandas as pd
import requests

SPOT_BASE_URL = "https://api.binance.com"
FUTURES_BASE_URL = "https://fapi.binance.com"
DATA_VISION_BASE_URL = "https://data.binance.vision"


def _to_millis(dt_str: str) -> int:
    return int(pd.Timestamp(dt_str, tz="UTC").timestamp() * 1000)


def _interval_to_pandas_freq(interval: str) -> str:
    if interval.endswith("m"):
        return f"{int(interval[:-1])}min"
    if interval.endswith("h"):
        return f"{int(interval[:-1])}h"
    raise ValueError(f"Unsupported interval: {interval}")


def _generate_synthetic_klines(symbol: str, interval: str, start_time: str, end_time: str) -> pd.DataFrame:
    """Deterministic fallback so CI can still run when exchange endpoints are blocked (e.g., HTTP 451)."""
    freq = _interval_to_pandas_freq(interval)
    idx = pd.date_range(start=pd.Timestamp(start_time, tz="UTC"), end=pd.Timestamp(end_time, tz="UTC"), freq=freq)
    if len(idx) == 0:
        return pd.DataFrame()

    seed = abs(hash(symbol)) % (2**32)
    rnd = pd.Series(range(len(idx)), index=idx, dtype=float)
    drift = 0.00005
    base = 1000.0 if "ETH" in symbol else 30000.0
    close = base * (1 + drift * rnd + 0.01 * (rnd / 97.0).apply(lambda x: (x % 1) - 0.5))
    open_ = close.shift(1).fillna(close.iloc[0])
    high = pd.concat([open_, close], axis=1).max(axis=1) * 1.0005
    low = pd.concat([open_, close], axis=1).min(axis=1) * 0.9995
    volume = (100 + (rnd + seed % 100).mod(50)).astype(float)

    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)


def _fetch_klines_from_data_vision(symbol: str, interval: str, start_time: str, end_time: str) -> pd.DataFrame:
    """Fallback source using Binance public historical files."""
    start = pd.Timestamp(start_time, tz="UTC").floor("D")
    end = pd.Timestamp(end_time, tz="UTC").floor("D")

    frames: list[pd.DataFrame] = []
    d = start
    while d <= end:
        day = d.strftime("%Y-%m-%d")
        url = (
            f"{DATA_VISION_BASE_URL}/data/spot/daily/klines/{symbol}/{interval}/"
            f"{symbol}-{interval}-{day}.zip"
        )
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                name = zf.namelist()[0]
                with zf.open(name) as f:
                    df = pd.read_csv(
                        f,
                        header=None,
                        names=[
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
                    frames.append(df[["open_time", "open", "high", "low", "close", "volume"]])
        d += timedelta(days=1)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["open_time"])
    out = out.set_index("open_time").sort_index()
    return out.loc[pd.Timestamp(start_time, tz="UTC") : pd.Timestamp(end_time, tz="UTC")]


def fetch_klines(symbol: str, interval: str, start_time: str, end_time: str) -> pd.DataFrame:
    """Fetch klines with resilient fallback chain: REST -> Data Vision -> synthetic(optional)."""
    start_ms = _to_millis(start_time)
    end_ms = _to_millis(end_time)

    all_rows = []
    limit = 1000
    url = f"{SPOT_BASE_URL}/api/v3/klines"

    try:
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
    except requests.HTTPError as e:
        if e.response is None or e.response.status_code != 451:
            raise

    if all_rows:
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

    # Fallback 1: data.binance.vision public archive
    dv = _fetch_klines_from_data_vision(symbol, interval, start_time, end_time)
    if not dv.empty:
        return dv

    # Fallback 2: deterministic synthetic bars for CI survivability
    if os.getenv("ALLOW_SYNTHETIC_DATA", "0") == "1":
        return _generate_synthetic_klines(symbol, interval, start_time, end_time)

    return pd.DataFrame()


def fetch_funding_rates(symbol: str, start_time: str, end_time: str) -> pd.Series:
    """Fetch perpetual funding rates. If blocked/unavailable, return empty and caller will fill zeros."""
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
        if resp.status_code in {418, 429, 451}:
            return pd.Series(dtype=float, name="funding_rate")
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
