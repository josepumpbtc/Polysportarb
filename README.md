# Polysportarb

Polymarket 体育赛事实时波动套利：YES/NO 价差套利 + 可选波动策略。代码推送至 [josepumpbtc/Polysportarb](https://github.com/josepumpbtc/Polysportarb)。

## 目的

- **主策略**：当同一二元市场的 YES 买价 + NO 买价 < 1 - 手续费时，同时买入 YES 和 NO 锁定到期利润。
- **辅策略**：利用体育赛事实时价格波动做单边方向性交易（有风险，需风控）。

## 环境

- Python 3.10+
- 依赖：`pip install -r requirements.txt`

## 配置

1. 复制 `.env.example` 为 `.env`，填入 `PRIVATE_KEY`、`FUNDER_ADDRESS`（见 [Polymarket 设置](https://polymarket.com/settings)）。
2. 复制 `config/config.example.yaml` 为 `config/config.yaml`，按需调整 `min_profit`、`fee_bps`、`sports_tag_id` 等。

**切勿将 `.env` 或真实密钥提交到 Git。**

## 运行

- **纸面/模拟（推荐先跑）**：`PAPER_TRADING=true python -m src.main` 或 `python scripts/paper_trade.py`，只打 log 不下单。
- **实盘**：确认小额资金与合规后，`PAPER_TRADING=false python -m src.main`。

## 测试

```bash
pytest tests/ -v
```

无需 `.env` 即可跑测试（测试使用 mock）。

## Code Review

提交前或同伴审查时可按 [docs/CODE_REVIEW.md](docs/CODE_REVIEW.md) 逐阶段自检。

## 推送到 GitHub（Polysportarb）

```bash
git init
git add .
git commit -m "Initial: Polymarket 体育赛事实时波动套利"
git remote add origin https://github.com/josepumpbtc/Polysportarb.git
git branch -M main
git push -u origin main
```

请勿提交 `.env` 或真实密钥。

## 免责声明

本仓库仅供学习与研究。实盘交易有亏损风险，请自行确认 Polymarket 条款与当地法规，仅用可承受损失的资金。
