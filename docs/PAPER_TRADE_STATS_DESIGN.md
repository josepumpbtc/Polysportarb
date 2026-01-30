# 纸面交易统计设计（Win/Loss Rate + 下单数据）

## 1. 目标

- **下单数据**：记录每笔 paper 模拟下单（时间、市场、方向、价格、数量、策略类型）。
- **胜率与盈亏**：能按策略（套利 / 波动）统计 win rate、总笔数、总盈亏、平均盈亏。

## 2. 记录范围

| 策略 | 记录内容 | Win 定义 |
|------|----------|----------|
| **套利 (arb)** | 每次执行 `execute_arbitrage(paper=True)` 时记一笔：两腿 YES/NO 同 size、price_yes、price_no、expected_profit | 纸面假设按价成交，结算得 $1/size，成本 = size*(price_yes+price_no)，profit = expected_profit > 0 视为 win |
| **波动 (vol)** | 每次执行波动单腿下单时记一笔：token_id、side、price、size；若后续有「平仓」则记 realized_profit | 平仓后 realized_profit > 0 为 win，< 0 为 loss；未平仓不参与胜率 |

首期可只做**套利**的完整统计；波动可先只记下单数据，等有平仓规则后再算 win/loss。

## 3. 存储方案

- **推荐：SQLite**（单文件、无需服务、易查聚合）。
- **路径**：项目根下 `data/paper_trades.db`（或由环境变量 `PAPER_STATS_DB` 指定），`data/` 加入 `.gitignore`。
- **备选**：JSONL 按日追加（`data/paper_orders_YYYYMMDD.jsonl`），再写脚本做聚合；实现简单但查胜率需扫文件。

## 4. 表结构（SQLite）

```sql
-- 每笔 paper 下单/成交记录
CREATE TABLE paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc TEXT NOT NULL,           -- ISO8601 时间
    strategy TEXT NOT NULL,         -- 'arb' | 'vol'
    condition_id TEXT,
    token_id_yes TEXT,
    token_id_no TEXT,
    price_yes REAL,
    price_no REAL,
    size REAL NOT NULL,
    side TEXT,                      -- 仅 vol：'BUY'|'SELL'
    expected_profit REAL,           -- 套利为预期利润；波动可为 NULL
    realized_profit REAL,           -- 实际利润：套利=expected_profit，波动=平仓后填入
    is_win INTEGER,                 -- 1=win, 0=loss, NULL=未结算(如波动未平仓)
    question TEXT                   -- 市场描述，便于排查
);

CREATE INDEX idx_paper_trades_ts ON paper_trades(ts_utc);
CREATE INDEX idx_paper_trades_strategy ON paper_trades(strategy);
```

- **套利**：插入时即填 `expected_profit`、`realized_profit = expected_profit`、`is_win = 1`（纸面按价成交即视为赢）。
- **波动**：插入时 `realized_profit`、`is_win` 为 NULL；平仓时更新 `realized_profit` 与 `is_win`。

## 5. 统计口径

- **Win rate**：`(is_win = 1 的笔数) / (is_win 非 NULL 的笔数)`，可按 `strategy` 分组。
- **下单数据**：总笔数、按日/按策略笔数、总 `realized_profit`、平均 `realized_profit`、最大单笔盈亏等；可由同一张表聚合。

## 6. 接入点

- **execution 层**：  
  - `execute_arbitrage(..., paper=True)` 在打 log 之后，调用 `paper_stats.record_arb(signal)` 写入一条 `strategy='arb'` 记录。  
  - 波动单腿下单（若已有 paper 分支）同理调用 `paper_stats.record_vol(signal)`，平仓时调用 `paper_stats.close_vol(trade_id, realized_profit)` 更新 `realized_profit` 与 `is_win`。
- **配置**：通过环境变量或 config 控制是否写入统计（例如 `PAPER_STATS_ENABLED=true`），默认 true；可指定 `PAPER_STATS_DB` 路径。

## 7. 查询与展示

- **脚本**：`scripts/paper_stats_report.py`（或 `python -m src.paper_stats --report`）读取 SQLite，按日/按策略输出：总笔数、win 笔数、loss 笔数、win rate、总盈亏、平均盈亏；可选导出 CSV。
- **主流程**：可在 main 循环中每隔 N 分钟或每 N 笔打印一次简要汇总（调用同一统计函数），避免依赖外部脚本才能看数。

## 8. 小结

| 项目 | 设计 |
|------|------|
| 记录内容 | 每笔 paper 套利/波动下单 + 套利即时盈亏、波动平仓后盈亏 |
| 存储 | SQLite `data/paper_trades.db`，表 `paper_trades` |
| Win/Loss | 套利：每笔 is_win=1；波动：平仓后按 realized_profit 填 is_win |
| 接入 | execution 层 paper 分支里调用 record_arb / record_vol（及平仓更新） |
| 查看 | 脚本 `paper_stats_report.py` + 可选 main 内周期汇总 |

按此设计即可实现「先统计 paper trade 的 win/loss rate 和下单数据」；若需要，我可以再按该设计写出具体代码改动（建表、record_arb/record_vol、report 脚本）。
