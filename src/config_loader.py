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
    # 默认监控的 10 个 Polymarket 二元市场（condition_id）；可被 config 或 YAML 覆盖
    "monitor_condition_ids": [
        "0x19ee98e348c0ccb341d1b9566fa14521566e9b2ea7aed34dc407a0ec56be36a2",  # MicroStrategy sells any Bitcoin in 2025?
        "0x8213d395e079614d6c4d7f4cbb9be9337ab51648a21cc2a334ae8f1966d164b4",  # MicroStrategy by Dec 31, 2026?
        "0x9a4db724246b51cbfbc8000dbbd6b54d72b057767c3690e63d940b26d78c6cb0",  # MicroStrategy by Mar 31, 2026?
        "0x5b70123b2c37355840b38bc60752919dae7ca5fe11d5e5184aa69be01b9db458",  # Kraken IPO in 2025?
        "0x9b3c3177fe473124c756b01e123b4b03e3a99880844ed8dea21b0a7879ca04aa",  # Kraken IPO by Mar 31, 2026?
        "0x6301809524e73edb9ab1bd180101ae6d9588ba78075a64c479f334a6d2a12975",  # Macron out in 2025?
        "0xda5c517dd5b78c80dec8ceb08ca4f466317633487827d7290332b4851cc4a4fa",  # Macron out by June 30, 2026?
        "0xaf9d0e448129a9f657f851d49495ba4742055d80e0ef1166ba0ee81d4d594214",  # Trump deport <250k?
        "0x49686d26fb712515cd5e12c23f0a1c7e10214c7faa3cb0a730aabe0c33694082",  # Trump deport 250k-500k?
        "0x2393ed0b0fdc450054c7b9071907eca75cf4fc36e385adf4a0a5f99ee62243e8",  # Trump deport 500k-750k?
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
