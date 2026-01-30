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
    "max_markets_monitor": 10,  # 测试阶段仅监控 N 个市场；后续可改为 100
    # 默认监控的 10 个二元市场：按交易量 top10，且过滤掉概率 >99% 或 <1%（0.01 < YES < 0.99）
    "monitor_condition_ids": [
        "0x450810ae738a0ff820d3248f2b24937f63fb8c8cf422ed2a915125adb4d9d3c8",  # Andrew Yang 2028 Dem
        "0xc914317b14972d5d15f30740d3bdf32f4028877c13b9d7ccc78b4ba33f67fb1e",  # Patriots Super Bowl 2026
        "0xbcb33ad98c8141b10f2350ef687eddf0660484ecc15be42ecdae64339e64dce1",  # André Ventura Portugal 2026
        "0x2ca58175aa8080357d9706c535bb0be218ce7bb156dc48753e0d8b8ee6b56635",  # Aston Villa Premier League 2025-26
        "0x1d54eb5eac2cee8f595f3097c65da7d07f8ab5dee63d7c0c6883eb70e1e9af30",  # Russia Ukraine ceasefire Mar 2026
        "0xa0eafdfa7da17483796f77f4b287d28834ab97db4a9a6e999b52c1ba239bc2f3",  # Seahawks Super Bowl 2026
        "0xf2cea45ec282af4f302d2ab85ede73678cd692ebf8c3ab6d52bfa5e19f44c553",  # Matt Gaetz 2028 Rep
        "0x32b09f6390252b37d674501527e709016d55581b2c1e544bd4b8167f5f732f4c",  # Jesus return before GTA VI
        "0xd997dc2a212a7d6673375a3b016db1fb214247142f8cde0cbf07f8e6d789877c",  # Vivek Ramaswamy 2028 Rep
        "0xaeea5f917fc5746387b5f9c0a4263dba035dbb3f0ac6ad72bf92183d21e26739",  # Russia Ukraine ceasefire end 2026
    ],
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
