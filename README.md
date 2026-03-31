# Personal Quant System (Binance Data + Local Simulation)

## Features
- Binance REST 获取 BTC/ETH K线数据。
- 可选拉取并并入永续资金费率（`include_funding=true`）。
- 本地模拟撮合（手续费、滑点、杠杆、再平衡阈值）。
- 更真实的持仓核算：记录均价、已实现PnL、未实现PnL、资金费。
- 策略层完全解耦（`StrategyBase` 抽象接口）。
- 支持双品种组合回测（BTC + ETH）。
- 支持参数网格搜索，且复用同一份数据避免重复下载。

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Notes
- 当前为研究型框架，便于快速验证策略，不含实盘下单。
- 高频场景请重点关注滑点、手续费、资金费率对收益侵蚀。
