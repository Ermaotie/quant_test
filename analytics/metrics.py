import numpy as np
import pandas as pd


def calc_metrics(equity_series: pd.Series, periods_per_year: int) -> dict:
    ret = equity_series.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    total_return = equity_series.iloc[-1] / equity_series.iloc[0] - 1 if len(equity_series) > 1 else 0.0

    ann_return = (1 + total_return) ** (periods_per_year / max(len(ret), 1)) - 1
    ann_vol = ret.std() * np.sqrt(periods_per_year)
    downside_vol = ret.clip(upper=0).std() * np.sqrt(periods_per_year)

    sharpe = ann_return / ann_vol if ann_vol > 1e-12 else 0.0
    sortino = ann_return / downside_vol if downside_vol > 1e-12 else 0.0

    roll_max = equity_series.cummax()
    drawdown = equity_series / roll_max - 1.0
    max_dd = drawdown.min() if len(drawdown) else 0.0
    calmar = ann_return / abs(max_dd) if abs(max_dd) > 1e-12 else 0.0

    turnover = ret.abs().sum()

    return {
        "total_return": float(total_return),
        "annual_return": float(ann_return),
        "annual_vol": float(ann_vol),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(max_dd),
        "calmar": float(calmar),
        "turnover_proxy": float(turnover),
    }
