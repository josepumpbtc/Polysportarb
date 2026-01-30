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
    "max_markets_monitor": 100,  # 监控 N 个市场（按成交量 top 或 monitor_condition_ids）
    "top10_min_prob": 0.01,
    "top10_max_prob": 0.99,
    "status_log_interval_sec": 60.0,  # 每 N 秒在 Deploy Logs 输出任务状态与 Workbook
    "refresh_markets_interval_sec": 1800.0,  # 未指定 monitor_condition_ids 时，每 N 秒刷新一次 top 市场
    # 为空则按「Top 100 Polymarket 24h 交易量」动态拉取；非空则只监控这些 condition_id
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

    return config
