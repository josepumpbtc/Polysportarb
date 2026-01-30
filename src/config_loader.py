# 目的：统一加载策略与运行参数，供 main、arbitrage、execution 等使用
# 方法：优先读 YAML 配置文件，缺失项用默认值或环境变量补全

import os
from typing import Any, Dict, Optional

# 默认配置：与 config.example.yaml 对齐，避免无文件时崩溃
DEFAULTS: Dict[str, Any] = {
    "min_profit": 0.005,
    "fee_bps": 0,
    "sports_tag_id": None,
    "events_limit": 50,
    "events_offset": 0,
    "default_size": 5.0,
    "max_position_per_market": 50.0,
    "min_book_depth": 10.0,
    "volatility_enabled": False,
    "volatility_deviation_pct": 0.05,
    "max_markets_monitor": 100,  # 监控 N 个市场（live_sports + top10_by_volume 合并去重，或 monitor_condition_ids）
    "live_sports_enabled": True,  # Live 体育市场监控：同时监控 live sports 和 top10_by_volume，合并去重
    "merge_arb_enabled": True,  # 启用 Merge 套利（Taker：买入 YES+NO，等待结算或合并成 USDC）
    "split_arb_enabled": True,  # 启用 Split 套利（用 USDC 拆分成 YES+NO，然后卖出，瞬间结算）
    "instant_merge": False,  # Merge 套利是否立即合并成 USDC（false 表示等待事件结算）
    "maker_arb_enabled": False,  # 启用 Maker 套利（在 YES 和 NO 两边挂 Maker 买单，等待成交，可能获得返佣）
    "maker_bid_spread": 0.01,  # Maker 买单价格低于 best ask 的价差（例如 0.01 = 1 cent）
    "maker_order_timeout_sec": 300.0,  # Maker 订单超时时间（秒），超时后考虑撤单或转为 Taker
    "top10_min_prob": 0.01,
    "top10_max_prob": 0.99,
    "status_log_interval_sec": 60.0,  # 每 N 秒在 Deploy Logs 输出任务状态与 Workbook
    "refresh_markets_interval_sec": 1800.0,  # 未指定 monitor_condition_ids 时，每 N 秒刷新一次市场
    "heartbeat_interval_sec": 3600.0,  # 每小时推送 Telegram 心跳「策略正在 Railway 运行中」
    # 为空则同时监控 live_sports 和 top10_by_volume（合并去重）；非空则只监控这些 condition_id
    "monitor_condition_ids": [],
}


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    目的：返回合并后的配置字典，供各模块读取 min_profit、fee_bps、sports_tag_id 等
    方法：若存在 config_path 或 CONFIG_PATH 指向的 YAML，则解析并与 DEFAULTS 合并；否则仅返回 DEFAULTS
    """
    path = config_path or os.getenv("CONFIG_PATH", "config/config.yaml")
    config = dict(DEFAULTS)

    if not os.path.isfile(path):
        return config

    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        if isinstance(loaded, dict):
            for k, v in loaded.items():
                if k in config:
                    config[k] = v
    except Exception:
        pass

    # 环境变量覆盖：便于 Railway 等不写 config 文件时调整
    min_profit_env = os.getenv("MIN_PROFIT")
    if min_profit_env is not None and min_profit_env.strip() != "":
        try:
            config["min_profit"] = float(min_profit_env.strip())
        except ValueError:
            pass
    heartbeat_env = os.getenv("HEARTBEAT_INTERVAL_SEC")
    if heartbeat_env is not None and heartbeat_env.strip() != "":
        try:
            config["heartbeat_interval_sec"] = float(heartbeat_env.strip())
        except ValueError:
            pass

    return config
