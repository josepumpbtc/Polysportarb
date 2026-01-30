# 目的：串联数据、检测与执行，支持纸面模式（paper 时只打 log 不下单）
# 方法：加载配置与 auth，拉体育市场，订阅订单簿，主循环中读取订单簿、调用套利与波动检测、执行层根据配置决定是否真实下单

import argparse
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

# 将项目根加入 path，便于以 python -m src.main 运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config_loader import load_config
from src.gamma import fetch_sports_binary_markets
from src.orderbook import OrderBookStore
from src.arbitrage import scan_markets_for_arbitrage, ArbitrageSignal
from src.volatility import scan_markets_for_volatility
from src.volatility import VolatilityDetector
from src.execution import execute_arbitrage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_once(
    config: Dict[str, Any],
    store: OrderBookStore,
    markets: List[Dict[str, Any]],
    paper: bool,
    client: Optional[Any],
    volatility_detectors: Dict[str, Any],
) -> None:
    """
    目的：执行一轮检测与执行（套利 + 可选波动），供主循环调用
    方法：用 store 的 get_best_ask 扫描套利；若开启波动则扫描波动；对每个信号调用 execute_arbitrage
    """
    def get_ask(asset_id: str) -> Optional[float]:
        return store.get_best_ask(asset_id)

    def get_bid(asset_id: str) -> Optional[float]:
        return store.get_best_bid(asset_id)

    # 套利检测：YES/NO 买价之和 < 1 - fee - min_profit
    arb_signals = scan_markets_for_arbitrage(
        markets,
        get_best_ask=get_ask,
        min_profit=config.get("min_profit", 0.005),
        fee_bps=config.get("fee_bps", 0),
        default_size=config.get("default_size", 5.0),
    )
    for sig in arb_signals:
        execute_arbitrage(sig, client=client, paper=paper)

    # 波动策略（可选）
    if config.get("volatility_enabled"):
        vol_signals = scan_markets_for_volatility(
            markets,
            get_bid=get_bid,
            get_ask=get_ask,
            detectors=volatility_detectors,
            deviation_pct=config.get("volatility_deviation_pct", 0.05),
            default_size=config.get("default_size", 5.0),
            max_position=config.get("max_position_per_market", 50.0),
        )
        for sig in vol_signals:
            logger.info(
                "[波动] token=%s side=%s price=%s size=%s deviation_pct=%s",
                sig.token_id, sig.side, sig.price, sig.size, sig.deviation_pct,
            )
            # 波动策略单腿下单可在此扩展 execution 层


def main(
    paper: Optional[bool] = None,
    config_path: Optional[str] = None,
    poll_interval_sec: float = 2.0,
) -> None:
    """
    目的：主入口：加载配置与认证，拉取体育市场，启动订单簿订阅（或模拟），主循环检测与执行
    方法：paper 默认从环境变量 PAPER_TRADING 读取；无 WebSocket 时可用 store 手动 update 模拟
    """
    config = load_config(config_path)
    if paper is None:
        paper = os.getenv("PAPER_TRADING", "true").lower() in ("true", "1", "yes")

    client = None
    if not paper:
        from src.auth import get_clob_client
        client = get_clob_client()
        if client is None:
            logger.warning("实盘模式但认证失败（缺 PRIVATE_KEY/FUNDER_ADDRESS），改为纸面模式")
            paper = True

    # 拉取体育二元市场（可选 tag_id）
    tag_id = config.get("sports_tag_id")
    try:
        markets = fetch_sports_binary_markets(
            tag_id=tag_id,
            limit=config.get("events_limit", 50),
            offset=config.get("events_offset", 0),
        )
    except Exception as e:
        logger.exception("拉取体育市场失败: %s", e)
        markets = []
    if not markets:
        logger.warning("当前无体育二元市场，将空跑主循环（可手动注入 markets 测试）")

    store = OrderBookStore()
    # 方法：若无 WebSocket 线程，可在此用 mock 数据 update_from_message 做纸面测试
    asset_ids = []
    for m in markets:
        asset_ids.append(m["token_id_yes"])
        asset_ids.append(m["token_id_no"])
    asset_ids = list(dict.fromkeys(asset_ids))
    if asset_ids:
        logger.info("订阅 %d 个 asset_ids（实际 WebSocket 需在 run_websocket_loop 中启动）", len(asset_ids))

    volatility_detectors: Dict[str, VolatilityDetector] = {}
    logger.info("主循环启动，paper=%s，poll_interval=%.1fs", paper, poll_interval_sec)
    try:
        while True:
            run_once(config, store, markets, paper, client, volatility_detectors)
            time.sleep(poll_interval_sec)
    except KeyboardInterrupt:
        logger.info("用户中断退出")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket 体育赛事实时波动套利")
    parser.add_argument("--paper", action="store_true", help="纸面模式，不下单")
    parser.add_argument("--live", action="store_true", help="实盘模式（需配置 .env）")
    parser.add_argument("--config", type=str, default=None, help="配置文件路径")
    parser.add_argument("--poll", type=float, default=2.0, help="轮询间隔秒")
    args = parser.parse_args()
    paper = None
    if args.live:
        paper = False
    elif args.paper:
        paper = True
    main(paper=paper, config_path=args.config, poll_interval_sec=args.poll)
