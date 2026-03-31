# Personal Quant System (Binance Data + Local Simulation)

## Features
- Binance REST 获取 BTC/ETH K线数据。
- 可选拉取并并入永续资金费率（`include_funding=true`）。
- 本地模拟撮合（手续费、滑点、杠杆、再平衡阈值）。
- 更真实的持仓核算：记录均价、已实现PnL、未实现PnL、资金费。
- 策略层完全解耦（`StrategyBase` 抽象接口）。
- 自动发现 `strategies/` 里的策略并批量回测。
- GitHub Actions 每日自动运行策略并输出最优策略。
- 新增策略文件后，会自动触发回测工作流并生成排行榜产物。
- 数据获取具备容灾链路：Binance REST -> data.binance.vision ->（可选）合成数据。
- 支持双品种组合回测（BTC + ETH）。
- 支持参数网格搜索，且复用同一份数据避免重复下载。

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_daily.py --output-dir artifacts
```

## GitHub Actions
- 工作流文件：`.github/workflows/strategy_backtest.yml`
- 触发场景：
  - 每天 UTC 00:15 定时执行
  - 手动触发（workflow_dispatch）
  - `strategies/**` 等核心路径变更时自动触发
- 产物：
  - `artifacts/leaderboard.csv`
  - `artifacts/best_strategy.json`
  - `artifacts/summary.md`（同步到 Action Summary）

## Fallback Behavior
- 若 GitHub Runner 对 Binance 接口返回 `451`，会自动尝试 `data.binance.vision`。
- 若外部数据源仍不可用且 `ALLOW_SYNTHETIC_DATA=1`，会生成确定性的合成K线以保证 CI 不中断。

## Add New Strategy
1. 在 `strategies/` 新增策略类，继承 `StrategyBase`。
2. 实现 `name`、`param_grid()`、`prepare()`、`on_bar()`。
3. 推送后 GitHub Actions 自动回测并在产物中展示结果。
python main.py
```

## Notes
- 当前为研究型框架，便于快速验证策略，不含实盘下单。
- 高频场景请重点关注滑点、手续费、资金费率对收益侵蚀。
