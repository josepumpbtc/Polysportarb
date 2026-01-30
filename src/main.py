# 目的：串联数据、检测与执行，支持纸面模式（paper 时只打 log 不下单）
# 方法：加载配置与 auth，拉体育市场，订阅订单簿，主循环中读取订单簿、调用套利与波动检测、执行层根据配置决定是否真实下单

import argparse
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional

# 将项目根加入 path，便于以 python -m src.main 运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config_loader import load_config
from src.gamma import fetch_sports_binary_markets, fetch_top10_binary_markets_by_volume
from src.orderbook import OrderBookStore, run_websocket_loop
from src.arbitrage import scan_markets_for_arbitrage, ArbitrageSignal
from src.volatility import scan_markets_for_volatility
from src.volatility import VolatilityDetector
from src.execution import execute_arbitrage
from src.telegram_notify import notify_arb_opportunity, notify_startup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _is_inactive_book(bid: Optional[float], ask: Optional[float]) -> bool:
    """YES/NO 为 bid=0.01 ask=0.99 或 0.001/0.999 等视为无活跃交易，过滤不输出"""
    if bid is None or ask is None:
        return True
    return (bid <= 0.02 and ask >= 0.98) or (bid <= 0.002 and ask >= 0.998)


def log_task_status_and_workbook(
    store: OrderBookStore,
    markets: List[Dict[str, Any]],
    status: str = "运行中",
    top_n_label: Optional[str] = None,
) -> None:
    """目的：在 Deploy Logs 中输出任务状态、监控市场列表、订单簿摘要（Workbook 样子）；排除不活跃市场"""
    if top_n_label:
        logger.info("【%s】%s", top_n_label, status)
    else:
        logger.info("【任务状态】%s", status)
    for i, m in enumerate(markets, 1):
        cid = m.get("condition_id", "")
        q = (m.get("question") or "")[:60]
        logger.info("  市场 %d: condition_id=%s question=%s", i, cid, q)
    # Workbook：仅输出活跃市场（不活跃的不显示在 Log 中）
    logger.info("【Workbook】订单簿快照 (仅活跃市场)")
    active_count = 0
    for m in markets:
        ty = m.get("token_id_yes")
        tn = m.get("token_id_no")
        q = (m.get("question") or "")[:50]
        by = store.get_best_bid(ty) if ty else None
        ay = store.get_best_ask(ty) if ty else None
        bn = store.get_best_bid(tn) if tn else None
        an = store.get_best_ask(tn) if tn else None
        if _is_inactive_book(by, ay) and _is_inactive_book(bn, an):
            continue
        active_count += 1
        logger.info("  %s | YES bid=%s ask=%s | NO bid=%s ask=%s", q, by, ay, bn, an)
    logger.info("【Workbook】活跃市场 %d 个（共监控 %d 个，已过滤不活跃 %d 个）", active_count, len(markets), len(markets) - active_count)


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
        # 1. Deploy Log 醒目显示套利机会
        logger.info(
            "【套利机会】%s | YES=%.3f NO=%.3f 合计=%.3f | 预期利润=%.2f",
            (sig.question or "套利")[:60], sig.price_yes, sig.price_no, sig.price_yes + sig.price_no, sig.expected_profit,
        )
        # 2. 执行层（paper 时只打 [PAPER] 明细）
        execute_arbitrage(sig, client=client, paper=paper)
        # 3. 套利机会推送到 Telegram
        if notify_arb_opportunity(sig):
            logger.info("套利机会已推送 Telegram")

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

    # 若配置了 monitor_condition_ids 则只监控这些市场（从体育/全量事件中过滤）；否则按成交量取 top N
    monitor_ids = config.get("monitor_condition_ids") or []
    if isinstance(monitor_ids, str):
        monitor_ids = [monitor_ids]
    monitor_set = {str(cid).strip() for cid in monitor_ids if cid}
    max_markets = int(config.get("max_markets_monitor", 10))

    if monitor_set:
        # 指定 condition_id：拉体育事件后过滤
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
        markets = [m for m in markets if m.get("condition_id") in monitor_set]
        logger.info("监控指定 %d 个市场（monitor_condition_ids）", len(markets))
    else:
        # 未指定：按成交量 + 概率过滤取 top N，一直是最活跃市场
        try:
            markets = fetch_top10_binary_markets_by_volume(
                events_limit=config.get("events_limit", 150),
                min_prob=config.get("top10_min_prob", 0.01),
                max_prob=config.get("top10_max_prob", 0.99),
                top_n=max_markets,
            )
        except Exception as e:
            logger.exception("拉取 Top 市场失败: %s", e)
            markets = []
        logger.info("监控市场数量: %d（按成交量 top，max_markets_monitor=%d）", len(markets), max_markets)

    if not markets:
        logger.warning("当前无监控市场，将空跑主循环（可清空 monitor_condition_ids 用按成交量 top）")

    store = OrderBookStore()
    # 使用可变列表，便于定期刷新时更新（orderbook 通过 getter 读取，重连时拿到最新 asset_ids）
    current_markets: List[Dict[str, Any]] = list(markets)
    current_asset_ids: List[str] = []
    for m in current_markets:
        current_asset_ids.append(m["token_id_yes"])
        current_asset_ids.append(m["token_id_no"])
    current_asset_ids[:] = list(dict.fromkeys(current_asset_ids))

    def get_asset_ids() -> List[str]:
        return list(current_asset_ids)

    # Deploy Logs：输出任务状态与监控的市场列表（Top 100 时打【Top 100 监控市场】）
    top_label = "Top 100 监控市场" if not monitor_set and current_markets else None
    log_task_status_and_workbook(
        store, current_markets,
        status="主循环启动前，监控市场列表",
        top_n_label=top_label,
    )

    # Telegram 启动测试：便于排查 Railway 上未收到推送
    if notify_startup():
        logger.info("Telegram 已配置，已发送启动测试消息")
    else:
        logger.info("Telegram 未配置或发送失败（检查 TELEGRAM_BOT_TOKEN、TELEGRAM_CHAT_ID）")

    # 启动 WebSocket 线程，持续接收订单簿并更新 store；传入 getter 以便定期刷新后重连时订阅新 asset_ids
    if current_asset_ids:
        ws_thread = threading.Thread(
            target=run_websocket_loop,
            args=(store, get_asset_ids),
            daemon=True,
            name="orderbook-ws",
        )
        ws_thread.start()
        logger.info("已启动 orderbook WebSocket，订阅 %d 个 asset_ids", len(current_asset_ids))
        time.sleep(3)
        top_label = "Top 100 监控市场" if not monitor_set and current_markets else None
        log_task_status_and_workbook(
            store, current_markets, status="首批订单簿已就绪，Workbook 快照", top_n_label=top_label,
        )

    volatility_detectors: Dict[str, VolatilityDetector] = {}
    logger.info("主循环启动，paper=%s，poll_interval=%.1fs", paper, poll_interval_sec)
    last_status_log = time.monotonic()
    last_refresh = time.monotonic()
    status_log_interval = float(config.get("status_log_interval_sec", 60.0))
    refresh_interval = float(config.get("refresh_markets_interval_sec", 1800.0))
    try:
        while True:
            run_once(config, store, current_markets, paper, client, volatility_detectors)
            now = time.monotonic()
            if now - last_status_log >= status_log_interval:
                top_label = "Top 100 监控市场" if not monitor_set and current_markets else None
                log_task_status_and_workbook(
                    store, current_markets, status="主循环运行中", top_n_label=top_label,
                )
                last_status_log = now
            # 未指定 monitor_condition_ids 时，定期刷新 top 市场并更新 current_markets / current_asset_ids
            if not monitor_set and now - last_refresh >= refresh_interval:
                try:
                    new_markets = fetch_top10_binary_markets_by_volume(
                        events_limit=config.get("events_limit", 150),
                        min_prob=config.get("top10_min_prob", 0.01),
                        max_prob=config.get("top10_max_prob", 0.99),
                        top_n=max_markets,
                    )
                    if new_markets:
                        current_markets.clear()
                        current_markets.extend(new_markets)
                        new_ids: List[str] = []
                        for m in current_markets:
                            new_ids.append(m["token_id_yes"])
                            new_ids.append(m["token_id_no"])
                        current_asset_ids[:] = list(dict.fromkeys(new_ids))
                        logger.info("已刷新监控市场为 %d 个（按成交量 top），下次 WS 重连将订阅新 asset_ids", len(current_markets))
                except Exception as e:
                    logger.exception("刷新 top 市场失败: %s", e)
                last_refresh = now
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
