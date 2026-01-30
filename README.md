
# Polysportarb

Polymarket 体育赛事实时波动套利：YES/NO 价差套利 + 可选波动策略。代码推送至 [josepumpbtc/Polysportarb](https://github.com/josepumpbtc/Polysportarb)。

## 目的

- **主策略**：当同一二元市场的 YES 买价 + NO 买价 < 1 - 手续费时，同时买入 YES 和 NO 锁定到期利润。
- **辅策略**：利用体育赛事实时价格波动做单边方向性交易（有风险，需风控）。

## 套利策略原理

本项目实现了三种套利策略，利用 Polymarket 二元市场的价差和 CTF（Conditional Token Framework）特性实现无风险或低风险套利：

### 1. Taker Arb（吃单套利）

**原理**：
- 二元市场中，YES 和 NO 的结算价值恒为 $1（到期时 YES 得 $1 或 NO 得 $1）
- 当 `ask_yes + ask_no < 1` 时，存在套利机会
- **操作**：立即以 `best_ask` 价格同时买入 YES 和 NO（吃单，Taker）
- **利润**：`利润 = 1 - (ask_yes + ask_no)`
- **结算**：等待事件结束，任一方结算得 $1；或立即调用 CTF Merge 操作合并成 USDC（瞬间结算）

**示例**：
- YES best ask = $0.40，NO best ask = $0.55
- 成本 = $0.40 + $0.55 = $0.95
- 利润 = $1.00 - $0.95 = $0.05（每单位）

**优势**：
- 立即成交，锁定利润
- 风险低，无时间风险（如果立即合并）
- 简单直接，不需要链上操作（如果等待结算）

**劣势**：
- 可能支付 Taker 费用（如果交易所收取）
- 如果等待结算，资金占用时间较长

---

### 2. Maker Spread Arb（做市商价差套利）

**原理**：
- 与 Taker 策略相同的套利条件：`ask_yes + ask_no < 1`
- **操作**：在 YES 和 NO 两边挂 Maker 买单（价格略低于 `best_ask`），等待成交
- **价格设置**：`maker_bid = best_ask - maker_bid_spread`（例如 best_ask = 0.40，spread = 0.01，则挂 0.39）
- **利润**：`利润 = 1 - (maker_bid_yes + maker_bid_no)` + 可能的 Maker 返佣

**示例**：
- YES best ask = $0.40，NO best ask = $0.55
- Maker 买单：YES 挂 $0.39，NO 挂 $0.54
- 如果两边都成交：成本 = $0.39 + $0.54 = $0.93
- 利润 = $1.00 - $0.93 = $0.07（每单位）+ Maker 返佣

**优势**：
- 可能获得 Maker 返佣/奖励（如果 Polymarket 有流动性激励）
- 可以等待更好的成交价格
- 提供流动性，有助于市场深度

**劣势**：
- **部分成交风险**：可能只成交一边（例如只成交 YES，NO 未成交）
- **资金占用**：需要等待成交，资金被占用
- **机会成本**：可能错过立即成交的机会
- **超时风险**：如果订单超时未成交，需要撤单或转为 Taker 策略

**风险控制**：
- 设置订单超时时间（默认 5 分钟）
- 监控订单状态，处理部分成交情况
- 超时后考虑撤单并转为 Taker 策略

---

### 3. Merge/Split Arb（合并/拆分套利）- Polymarket 特有

这是 Polymarket 基于 CTF（Conditional Token Framework）的独特功能，允许瞬间结算套利。

#### 3.1 Split 套利（拆分套利）

**原理**：
- 当 `bid_yes + bid_no > 1 + min_profit` 时，存在 Split 套利机会
- **操作**：
  1. 用 $1 USDC 调用 CTF Split 操作，拆分成 1 YES + 1 NO
  2. 分别将 YES 和 NO 卖给市场上的 bid
  3. 获得超过 $1 的收入
- **利润**：`利润 = (bid_yes + bid_no) - 1`
- **结算**：**瞬间结算**，不需要等到事件结束

**示例**：
- YES best bid = $0.52，NO best bid = $0.49
- 用 $1.00 USDC 拆分成 1 YES + 1 NO
- 卖出收入 = $0.52 + $0.49 = $1.01
- 利润 = $1.01 - $1.00 = $0.01（每单位）

**优势**：
- **瞬间结算**：不需要等到事件结束，立即获得利润
- **资金效率高**：资金可以快速周转，进行下一轮套利
- **无时间风险**：不承担事件结果的不确定性

**劣势**：
- 需要链上 Split 操作，需要支付 Gas 费用
- 需要确保 bid 有足够的深度，避免部分成交

#### 3.2 Merge 套利（合并套利）

**原理**：
- 与 Taker 策略相同的套利条件：`ask_yes + ask_no < 1`
- **操作**：
  1. 买入 YES + NO（与 Taker 策略相同）
  2. 立即调用 CTF Merge 操作，将 YES+NO 合并成 USDC
  3. 获得 $1 USDC，成本低于 $1
- **利润**：`利润 = 1 - (ask_yes + ask_no)`
- **结算**：**瞬间结算**，不需要等到事件结束

**示例**：
- YES best ask = $0.40，NO best ask = $0.55
- 买入成本 = $0.40 + $0.55 = $0.95
- 立即合并成 $1.00 USDC
- 利润 = $1.00 - $0.95 = $0.05（每单位）

**优势**：
- **瞬间结算**：不需要等到事件结束
- 与 Taker 策略相比，可以立即获得利润，资金周转快

**劣势**：
- 需要链上 Merge 操作，需要支付 Gas 费用
- 如果等待结算，不需要 Gas 费用（但资金占用时间长）

---

### 策略对比总结

| 策略 | 条件 | 操作方式 | 结算时间 | 主要优势 | 主要风险 |
|------|------|----------|----------|----------|----------|
| **Taker Arb** | `ask_yes + ask_no < 1` | 立即买入（吃单） | 等待结算或立即合并 | 立即成交，锁定利润 | 可能支付 Taker 费用 |
| **Maker Spread Arb** | `ask_yes + ask_no < 1` | 挂 Maker 买单等待 | 等待成交后结算 | 可能获得返佣 | 部分成交风险 |
| **Split Arb** | `bid_yes + bid_no > 1` | 拆分 USDC → 卖出 | **瞬间结算** | 无需等待，资金周转快 | 需要 Gas 费用 |
| **Merge Arb** | `ask_yes + ask_no < 1` | 买入 → 立即合并 | **瞬间结算** | 瞬间结算，资金周转快 | 需要 Gas 费用 |

### 配置说明

在 `config/config.yaml` 中可以配置各策略的启用状态：

```yaml
# Taker 策略（Merge 套利）
merge_arb_enabled: true      # 启用 Taker 套利
instant_merge: false         # 是否立即合并（false=等待结算，true=瞬间结算）

# Split 套利
split_arb_enabled: true      # 启用 Split 套利

# Maker 策略
maker_arb_enabled: false      # 启用 Maker 套利（默认关闭）
maker_bid_spread: 0.01        # Maker 买单价格低于 best ask 的价差
maker_order_timeout_sec: 300  # Maker 订单超时时间（秒）
```

详细实现逻辑请参考 [docs/ARBITRAGE_LOGIC.md](docs/ARBITRAGE_LOGIC.md)。

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

5. **单市场套利监视（按 event slug）**  
   对指定市场监视「买 YES 最优卖价 + 买 NO 最优卖价 < 1」是否成立（Polymarket 无手续费）。  
   示例（[US government shutdown by Jan 31](https://polymarket.com/event/will-there-be-another-us-government-shutdown-by-january-31)）：  
   `python scripts/test_arb_one_market.py --slug will-there-be-another-us-government-shutdown-by-january-31 --seconds 60`  
   若出现 SSL 错误，同上设置 `SSL_CERT_FILE`。

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
