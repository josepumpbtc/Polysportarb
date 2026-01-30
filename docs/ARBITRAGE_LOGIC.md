# 价差套利主策略：Orderbook 监视与下单

## 一、主策略逻辑

- **二元市场**：YES 与 NO 两种结果，到期有且仅有一个为真；结算时 YES 得 $1 或 NO 得 $1，故 **YES + NO 的结算价值恒为 $1**。
- **Polymarket 特有：CTF (Conditional Token Framework)** 允许将 YES+NO 代币合并成 USDC，或用 USDC 拆分成 YES+NO，实现**瞬间结算**的套利。

### 1. Merge 套利（买入套利）

- **套利条件**：Polymarket **目前无手续费**，条件为  
  **「买 YES 的最优卖价 + 买 NO 的最优卖价」< 1**  
  即可同时买入 YES 和 NO，到期任一方得 $1，成本低于 $1，锁定利润。
- **Orderbook 上**：
  - 「买 YES 的最优卖价」= YES 合约的 **best ask**
  - 「买 NO 的最优卖价」= NO 合约的 **best ask**
- **公式**：`成本 = ask_yes + ask_no`，`利润 = 1 - (ask_yes + ask_no)`；再用 `min_profit` 过滤掉利润过小的机会。
- **执行方式**：
  - **等待结算**（默认）：买入 YES+NO 后，等待事件结束，任一方结算得 $1
  - **立即合并**（`instant_merge=true`）：买入 YES+NO 后，立即调用 CTF Merge 操作合并成 USDC，**瞬间结算**

### 2. Split 套利（拆分套利）- 新增

- **套利条件**：**「卖 YES 的最优买价 + 卖 NO 的最优买价」> 1 + min_profit**  
  即可用 $1 USDC 拆分成 1 YES + 1 NO，然后分别卖出给市场上的 bid，获得超过 $1 的收入，锁定利润。
- **Orderbook 上**：
  - 「卖 YES 的最优买价」= YES 合约的 **best bid**
  - 「卖 NO 的最优买价」= NO 合约的 **best bid**
- **公式**：`收入 = bid_yes + bid_no`，`利润 = (bid_yes + bid_no) - 1`；再用 `min_profit` 过滤掉利润过小的机会。
- **执行方式**：
  1. 调用 CTF Split 操作：用 `size` USDC 拆分成 `size` YES + `size` NO
  2. 创建两笔卖单：SELL YES 和 SELL NO，价格分别为 `bid_yes` 和 `bid_no`
  3. 批量提交卖单
  4. **瞬间结算**：不需要等到事件结束，立即获得利润

---

## 二、在 Orderbook 上怎么监视

### 1. 需要的数据

每个二元市场有两个 CLOB token：

- `token_id_yes`：YES 合约
- `token_id_no`：NO 合约

对套利而言，只需要**卖方挂单**（我们买入），Polymarket 无手续费，故：

- **买 YES 的最优卖价** = YES 合约的 **best ask**
- **买 NO 的最优卖价** = NO 合约的 **best ask**
- **套利条件**：`ask_yes + ask_no < 1`

即：`ask_yes = orderbook[token_id_yes].best_ask`，`ask_no = orderbook[token_id_no].best_ask`，满足 `ask_yes + ask_no < 1` 即存在套利。

### 2. 当前实现（代码对应）

| 步骤 | 说明 | 代码位置 |
|------|------|----------|
| 订阅 orderbook | 对每个监控市场的 `token_id_yes`、`token_id_no` 订阅 CLOB WebSocket market channel | `src/orderbook.py`：`run_websocket_loop` 订阅 `assets_ids` |
| 维护 best bid/ask | 收到 book / price_change 消息后，更新每个 asset 的 best bid、best ask | `OrderBookStore.update_from_message`，解析 `bids[0]`、`asks[0]` 或 `best_ask` |
| 读取最优卖价 | 套利检测时用「最优卖价」作为「买入价」 | `OrderBookStore.get_best_ask(asset_id)` |
| 判断套利 | 对同一市场的 YES/NO：`ask_yes + ask_no < 1`（无手续费）；再要求 `1 - sum_ask >= min_profit` | `src/arbitrage.py`：`check_arbitrage` 用 `get_best_ask` 取两腿 ask，计算 `1 - sum_ask >= min_profit`（fee=0） |

也就是说：**监视 = 订阅这两个 token 的 orderbook，用 best ask 当作买价，每轮用 `get_best_ask` 取价并代入上述不等式**。

### 3. 主循环中的监视流程

```
1. 拉取监控市场列表（每个市场含 token_id_yes、token_id_no）
2. 启动 WebSocket，订阅所有 token_id_yes + token_id_no 的 asset_id
3. 主循环每隔 poll_interval（如 2 秒）：
   - 对每个市场：ask_yes = store.get_best_ask(token_id_yes), ask_no = store.get_best_ask(token_id_no)
   - 若 ask_yes + ask_no < 1 且 1 - sum_ask >= min_profit，且通过过滤（非极端概率）→ 生成套利信号
4. 对每个套利信号调用执行层下单（或 paper 只打 log）
```

---

## 三、怎么下单

### 1. 下单逻辑

- **两腿同时下单**：  
  - 腿 1：**买 YES**，价格 = `ask_yes`（当前 best ask），数量 = `size`  
  - 腿 2：**买 NO**，价格 = `ask_no`，数量 = `size`（与 YES 相同）
- **到期**：YES 或 NO 一方结算得 $1/share，总得 = `size * 1`；成本 = `size * (ask_yes + ask_no)`；净利 ≈ `size * (1 - ask_yes - ask_no) - 手续费`。

因此：**监视到的是 best ask，下单时就用这两个价格、同一 size 去下两笔买单**。

### 2. 当前实现（代码对应）

| 步骤 | 说明 | 代码位置 |
|------|------|----------|
| 订单参数 | 用信号里的 `price_yes`、`price_no`（即检测时的 best ask）和 `size` 构造两笔买单 | `src/execution.py`：`OrderArgs(price=signal.price_yes, size=signal.size, side=BUY, token_id=signal.token_id_yes)` 与 NO 同理 |
| 提交 | 优先 `post_orders([signed_yes, signed_no])` 批量提交，减少两腿间滑点；否则分别 `post_order` | `execute_arbitrage` 内 |

注意：实盘时 best ask 可能在我们下单前被吃掉，因此存在**滑点/部分成交**风险；批量提交、尽快下单有助于减轻。

---

## 四、套利策略对比

| 策略 | 条件 | 操作 | 结算方式 | 优势 | 劣势 |
|------|------|------|----------|------|------|
| **Merge 套利 (Taker)** | `ask_yes + ask_no < 1` | 立即买入 YES + NO | 等待结算或立即合并 | 立即成交，锁定利润 | 可能支付 Taker 费用 |
| **Split 套利** | `bid_yes + bid_no > 1` | 拆分 USDC → 卖出 YES + NO | **瞬间结算** | 无需等待，资金周转快 | 需要链上 Split 操作 |
| **Maker 套利** | `ask_yes + ask_no < 1` | 挂 Maker 买单等待成交 | 等待成交后结算 | 可能获得 Maker 返佣 | 部分成交风险，资金占用 |

### Split 套利的优势

1. **瞬间结算**：不需要等到事件结束，立即获得利润
2. **资金效率高**：资金可以快速周转，进行下一轮套利
3. **无时间风险**：不承担事件结果的不确定性

### Merge 套利（Taker）的优势

1. **简单直接**：只需要买入，不需要链上 Split 操作
2. **Gas 费用低**：如果等待结算，不需要支付 Merge 的 Gas 费用
3. **流动性要求低**：只需要有足够的 ask 深度即可
4. **立即成交**：锁定利润，不承担等待风险

### Maker 套利的优势与风险

**优势**：
1. **可能获得返佣**：作为 Maker 提供流动性，可能获得交易所的返佣或奖励
2. **更好的价格**：可以等待更好的成交价格（虽然利润可能略低）
3. **提供流动性**：有助于市场深度，可能获得额外奖励

**风险**：
1. **部分成交风险**：可能只成交一边（例如只成交 YES，NO 未成交）
2. **资金占用**：需要等待成交，资金被占用
3. **机会成本**：可能错过立即成交的机会
4. **超时风险**：如果订单超时未成交，需要撤单或转为 Taker

**实现要点**：
- Maker 买单价格 = `best_ask - maker_bid_spread`（例如 best_ask = 0.40，maker_bid_spread = 0.01，则挂 0.39）
- 确保 `maker_bid_yes + maker_bid_no < 1` 且仍有利润
- 监控订单状态，处理部分成交和超时情况

## 五、Maker 策略详细说明

### 1. Maker 策略逻辑

- **检测条件**：`ask_yes + ask_no < 1`（与 Merge 套利相同）
- **价格设置**：
  - Maker 买单价格 = `best_ask - maker_bid_spread`
  - 例如：`best_ask_yes = 0.40`，`maker_bid_spread = 0.01`，则挂 `0.39` 的 Maker 买单
  - 确保 `maker_bid_yes + maker_bid_no < 1` 且仍有利润
- **执行方式**：
  1. 在 YES 和 NO 两边同时挂 Maker 买单
  2. 等待成交（可能只成交一边）
  3. 监控订单状态，处理部分成交和超时

### 2. 与 Taker 策略的区别

| 特性 | Taker 策略（Merge） | Maker 策略 |
|------|---------------------|------------|
| **成交方式** | 立即成交（吃单） | 等待成交（挂单） |
| **价格** | 使用 `best_ask` | 使用 `best_ask - spread` |
| **利润** | 立即锁定 | 可能更高（加上返佣） |
| **风险** | 低（立即成交） | 中（部分成交风险） |
| **资金占用** | 短（立即成交） | 长（等待成交） |

### 3. 部分成交处理

- **场景**：只成交了 YES，NO 未成交
- **处理方式**：
  1. 等待 NO 成交（继续持有 YES）
  2. 撤单并转为 Taker 策略（立即买入 NO）
  3. 平仓 YES（如果市场变化导致不再有利可图）

### 4. 超时处理

- **超时时间**：`maker_order_timeout_sec`（默认 300 秒 = 5 分钟）
- **超时后**：
  1. 检查订单状态
  2. 如果部分成交：考虑撤单并转为 Taker 策略
  3. 如果未成交：撤单，等待下一个机会

## 六、小结

- **监视**：
  - Merge 套利（Taker）：用 CLOB WebSocket 订阅每个市场的 YES/NO 两个 token，在内存中维护 best ask；主循环用 `get_best_ask` 取价，判断 `ask_yes + ask_no < 1`
  - Split 套利：同样订阅 orderbook，但用 `get_best_bid` 取价，判断 `bid_yes + bid_no > 1`
  - Maker 套利：同时需要 `best_ask` 和 `best_bid`，判断 `ask_yes + ask_no < 1`，然后计算 Maker 价格
- **下单**：
  - Merge 套利（Taker）：用当前的 `ask_yes`、`ask_no` 作为限价，以相同 `size` 同时下两笔买单（YES 一单、NO 一单）；到期任一侧得 $1，成本 < $1
  - Split 套利：先执行 CTF Split 操作（用 USDC 拆分成 YES+NO），然后用 `bid_yes`、`bid_no` 作为限价，同时下两笔卖单；收入 > $1，利润 = 收入 - $1
  - Maker 套利：用 `best_ask - maker_bid_spread` 作为限价，同时下两笔 Maker 买单；等待成交，可能获得返佣

逻辑对应代码：`src/orderbook.py`（监视）、`src/arbitrage.py`（检测）、`src/execution.py`（下单）。

---

## 五、bid=0.001 / 0.01 是 API 错误还是流动性差？

**结论：一般是市场流动性不足，不是 API 信息出错。**

- **数据来源**：我们显示的 `bid` / `ask` 来自 Polymarket CLOB WebSocket 的 **原始 best bid / best ask**。代码只做解析与展示（`msg.get("bid")`、`bids[0]`、`asks[0]`），**不会**自己填 0.001 或 0.01。
- **为何常见 bid=0.001 或 0.01**：  
  - Polymarket 有最小报价单位（如 $0.01 或 $0.001）。当买盘很薄时，订单簿上的「最优买价」可能就是最低档（0.001 或 0.01），即**真实有人挂在该价位的买单**。  
  - 若某合约几乎没人挂买单，API 仍可能返回该最低档作为 best bid（或交易所对「空档」的表示方式），语义上都是**没有更高买价 = 买盘极薄**。
- **多市场同时出现**：很多市场同时出现 `YES bid=0.001`、`NO bid=0.001`，是因为这些市场本身买盘很薄或冷门，而不是我们这边解析错或 API 随机出错。
- **策略上的处理**：我们把 `bid≤0.02 且 ask≥0.98`（或 0.001/0.999）视为**不活跃市场**并过滤，不参与套利检测与 Workbook 活跃列表，正是为了排除这类流动性极差、难以真实成交的档位。
