# Code Review 与 Peer Review 检查清单

目的：提交前或同伴审查时按阶段逐项自检，确保每阶段实现、测试与注释符合计划。

## 约定

- 所有新增代码需加**中文注释**说明：**目的**（解决什么问题）、**方法**（简要实现思路）。
- 每阶段均含：实现 → 单元/集成测试 → Code Review 自查 → Peer Review 要点。

---

## 阶段 0：项目骨架与仓库准备

| 类型 | 检查项 |
|------|--------|
| Code Review | 无 `.env` 或真实密钥；README 注明仓库 https://github.com/josepumpbtc/Polysportarb；目录与计划一致 |
| Peer Review | 新成员能否仅凭 README 与 .env.example 完成环境搭建 |

---

## 阶段 1：认证与配置

| 类型 | 检查项 |
|------|--------|
| Code Review | 是否在任何地方硬编码密钥；是否仅从 env 或配置文件读敏感项；中文注释是否覆盖目的与方法 |
| Peer Review | 他人运行 test_auth 是否无需真实密钥即可通过 |

---

## 阶段 2：Gamma 市场发现

| 类型 | 检查项 |
|------|--------|
| Code Review | 是否处理 HTTP 错误与超时；是否遵守 API 限频（limit/offset）；注释是否完整 |
| Peer Review | 给定 mock 响应，解析结果是否与文档中的 token_id/condition_id 结构一致 |

---

## 阶段 3：订单簿与 WebSocket

| 类型 | 检查项 |
|------|--------|
| Code Review | 断线重连或错误处理是否具备；并发访问是否安全；是否暴露 token_id 与价格对应关系清晰 |
| Peer Review | 模拟消息格式是否与 CLOB 文档一致；best bid/ask 计算是否与文档定义一致 |

---

## 阶段 4：套利检测

| 类型 | 检查项 |
|------|--------|
| Code Review | 是否显式扣除 fee 与 min_profit；边界是否包含等于情况；注释是否解释公式 |
| Peer Review | 利润计算公式是否与文档一致（结算 $1、成本 sum_ask） |

---

## 阶段 5：执行层

| 类型 | 检查项 |
|------|--------|
| Code Review | paper 模式是否在所有路径下都不发真实单；错误处理是否记录并可选重试 |
| Peer Review | 批量下单参数（token_id、price、size、side）是否与 CLOB 文档一致 |

---

## 阶段 6：波动策略

| 类型 | 检查项 |
|------|--------|
| Code Review | 是否限制单市场/总仓位；注释是否说明方向性风险 |
| Peer Review | 信号条件是否可复现（给定相同输入得相同输出） |

---

## 阶段 7：主流程与纸面运行

| 类型 | 检查项 |
|------|--------|
| Code Review | 异常是否被捕获并记录；paper 是否为默认或显式可选；日志是否足够用于排查 |
| Peer Review | 从「拉市场 → 订阅 → 检测 → 执行」全流程是否清晰、是否易于切换 paper/实盘 |

---

## 阶段 8：CI/Review 文档与推送

| 类型 | 检查项 |
|------|--------|
| Code Review | 是否所有阶段测试已加入；REVIEW 文档是否覆盖各阶段 |
| Peer Review | 新 clone 仓库后能否在无 .env 下跑通测试并阅读本清单完成自检 |

---

## 运行全部测试

```bash
cd /path/to/Polysportarb
pip install -r requirements.txt
pytest tests/ -v
```

推送前请确保 `pytest tests/ -v` 全部通过。
