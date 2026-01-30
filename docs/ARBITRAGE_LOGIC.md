# 价差套利主策略：Orderbook 监视与下单

## 一、主策略逻辑

- **二元市场**：YES 与 NO 两种结果，到期有且仅有一个为真；结算时 YES 得 $1 或 NO 得 $1，故 **YES + NO 的结算价值恒为 $1**。
- **套利条件**：Polymarket **目前无手续费**，因此条件简化为  
  **「买 YES 的最优卖价 + 买 NO 的最优卖价」< 1**  
  即可同时买入 YES 和 NO，到期任一方得 $1，成本低于 $1，锁定利润。
- **Orderbook 上**：
  - 「买 YES 的最优卖价」= YES 合约的 **best ask**
  - 「买 NO 的最优卖价」= NO 合约的 **best ask**
- **公式**：`成本 = ask_yes + ask_no`，`利润 = 1 - (ask_yes + ask_no)`；再用 `min_profit` 过滤掉利润过小的机会。

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

## 四、小结

- **监视**：用 CLOB WebSocket 订阅每个市场的 YES/NO 两个 token，在内存中维护 best ask；主循环用 `get_best_ask` 取价，判断 `ask_yes + ask_no < 1`（Polymarket 无手续费）。
- **下单**：用当前的 `ask_yes`、`ask_no` 作为限价，以相同 `size` 同时下两笔买单（YES 一单、NO 一单）；到期任一侧得 $1，成本 < $1，实现价差套利。

逻辑对应代码：`src/orderbook.py`（监视）、`src/arbitrage.py`（检测）、`src/execution.py`（下单）。
