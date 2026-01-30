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

### Telegram 推送（套利机会提醒）

需要把套利机会推送到 Telegram 时，配置 Bot 与接收位置（私聊或 Channel），并设置环境变量。步骤见 **[docs/TELEGRAM_SETUP.md](docs/TELEGRAM_SETUP.md)**：

1. 在 Telegram 找 **@BotFather** → `/newbot` 创建 Bot → 复制 **Token**，设为 `TELEGRAM_BOT_TOKEN`。
2. **私聊**：给 Bot 发一条消息，用 `getUpdates` 拿到你的 **chat_id**（正数），设为 `TELEGRAM_CHAT_ID`。  
   **Channel**：创建 Channel，把 Bot 加为管理员，用 `getUpdates` 拿到 Channel 的 **chat_id**（`-100` 开头的负数），设为 `TELEGRAM_CHAT_ID`。
3. 在 `.env` 或 Railway Variables 中设置上述两个变量即可。

## 项目开始 To-Do（连接与测试）

按顺序执行以下脚本（无需密钥即可完成 1、3 纸面、4；2 与 3 实盘需配置 `.env`）：

1. **连接 Polymarket API**（Gamma + CLOB 可用性）  
   `python scripts/connect_api.py`

2. **连接 Polymarket 地址**（认证 + funder 校验）  
   `python scripts/connect_address.py`  
   需在项目根目录配置 `.env`（`PRIVATE_KEY`、`FUNDER_ADDRESS`）。

3. **测试下单**  
   - 纸面（不下单）：`python scripts/test_order.py --paper`  
   - 实盘（最小额）：`python scripts/test_order.py --live`（需 `.env`）

4. **测试 orderbook 实时监视**  
   `python scripts/test_orderbook_ws.py --seconds 30`  
   若出现 SSL 证书错误，可设置 `SSL_CERT_FILE` 或在本机安装/更新 CA 证书（如 macOS：安装 Xcode 命令行工具或运行证书安装脚本）。

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

## Railway 部署

1. 在 [Railway](https://railway.app) 新建项目，选择 **Deploy from GitHub repo**，连接 `josepumpbtc/Polysportarb`。
2. 在 Service 的 **Variables** 中配置环境变量（勿提交到 Git）：
   - `PRIVATE_KEY`：钱包私钥
   - `FUNDER_ADDRESS`：Polymarket 代理钱包地址
   - `PAPER_TRADING`：`true` 为纸面（只打 log），`false` 为实盘
   - 可选：`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`（套利机会推送到 Telegram，见 [docs/TELEGRAM_SETUP.md](docs/TELEGRAM_SETUP.md)）
   - 可选：`API_KEY`、`API_SECRET`、`API_PASSPHRASE`（不填则 L1 自动派生）
3. 构建与启动：Railway 使用 `requirements.txt` 构建；启动命令为 `python -u -m src.main`（`-u` 关闭输出缓冲，Deploy Logs 才能实时看到日志）。建议在 **Variables** 中加 `PYTHONUNBUFFERED=1` 作为备用。
4. 部署后服务会持续运行主循环；日志在 Railway 控制台查看。

**注意**：实盘需小额资金并确认当地合规；建议先用 `PAPER_TRADING=true` 验证。

## 分阶段计划

**当前阶段（测试）**

1. Paper trade：套利机会写入 log（`[PAPER] 套利机会: ...`）。
2. 套利机会推送 Telegram：配置 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID` 后，每次机会会推送到 Bot。
3. 仅监控 10 个市场：配置 `max_markets_monitor: 10`（`config/config.yaml` 或默认），后续可改为 100。

**下一阶段（待完成）**

1. 将监控从 10 个市场扩展到 100 个（改 `max_markets_monitor: 100`）。
2. 实盘下单测试：从 100 USDT 起测（配置 `.env` 与 `default_size`/仓位上限）。

## 免责声明

本仓库仅供学习与研究。实盘交易有亏损风险，请自行确认 Polymarket 条款与当地法规，仅用可承受损失的资金。
