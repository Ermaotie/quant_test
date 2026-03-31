# Personal Quant System (Binance Data + Local Simulation)

## Features
- Binance REST 获取 BTC/ETH K线数据。
- 可选拉取并并入永续资金费率（`include_funding=true`）。
- 本地模拟撮合（手续费、滑点、杠杆、再平衡阈值）。
- 更真实的持仓核算：记录均价、已实现PnL、未实现PnL、资金费。
- 自动发现 `strategies/` 下所有策略并回测，不需要手动注册。
- 支持策略参数网格搜索并输出每日最优策略结果。

## GitHub Actions
- `CI`：在 push / PR 上安装依赖并运行 `pytest`。
- `Daily Strategy Backtest`：每天定时运行全策略回测，并上传 `results/` 工件（包含 `leaderboard.json` 与 `best_strategy.md`）。
- 当新增或修改 `strategies/` 中策略文件时，会自动触发回测工作流。

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/daily_run.py
```

## Notes
- 当前为研究型框架，便于快速验证策略，不含实盘下单。
- 高频场景请重点关注滑点、手续费、资金费率对收益侵蚀。
