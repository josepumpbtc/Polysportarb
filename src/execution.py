# 目的：价差套利下单——同时买 YES 和 NO，用信号中的 best ask 作为限价，到期任一侧得 $1
# 方法：两腿同 size，价格取检测时的 price_yes/price_no（即 orderbook best ask）；优先批量 post_orders 减滑点
# Split 套利：用 USDC 拆分成 YES+NO，然后卖出给市场上的 bid

import logging
import time
from typing import Any, Dict, List, Optional

from src.arbitrage import ArbitrageSignal, SplitArbitrageSignal, MakerArbitrageSignal

logger = logging.getLogger(__name__)

# Maker 订单跟踪：用于监控订单状态和部分成交
_maker_orders: Dict[str, Dict[str, Any]] = {}  # order_id -> {signal, created_at, status, filled_yes, filled_no}


def execute_arbitrage(
    signal: ArbitrageSignal,
    client: Optional[Any] = None,
    paper: bool = True,
    tick_size: str = "0.01",
    neg_risk: bool = False,
) -> List[Any]:
    """
    目的：对一次 YES/NO 套利信号执行下单（或 paper 时仅打 log）
    方法：paper 为 True 时只记录拟下单的 token_id、price、size；否则用 client 创建并提交两腿买单（批量或两次 post_order）
    """
    if paper:
        logger.info(
            "[PAPER] 套利机会: token_yes=%s price_yes=%s token_no=%s price_no=%s size=%s expected_profit=%s",
            signal.token_id_yes,
            signal.price_yes,
            signal.token_id_no,
            signal.price_no,
            signal.size,
            signal.expected_profit,
        )
        return []

    if client is None:
        logger.warning("实盘模式但未提供 client，跳过下单")
        return []

    try:
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY
    except ImportError:
        logger.error("py_clob_client 未安装，无法下单")
        return []

    market_opts = {"tick_size": tick_size, "neg_risk": neg_risk}
    orders_created: List[Any] = []

    # 方法：先创建 YES 腿与 NO 腿的订单参数，再尝试批量提交；若无 batch 则分别 post_order
    order_yes = OrderArgs(
        price=signal.price_yes,
        size=signal.size,
        side=BUY,
        token_id=signal.token_id_yes,
    )
    order_no = OrderArgs(
        price=signal.price_no,
        size=signal.size,
        side=BUY,
        token_id=signal.token_id_no,
    )

    signed_yes = client.create_order(order_yes)
    signed_no = client.create_order(order_no)

    # 方法：优先批量提交以减少腿间滑点；若 client 无 post_orders 则两次 post_order
    if hasattr(client, "post_orders") and callable(getattr(client, "post_orders")):
        resp = client.post_orders([signed_yes, signed_no], OrderType.GTC)
        if isinstance(resp, list):
            orders_created.extend(resp)
        else:
            orders_created.append(resp)
    else:
        r1 = client.post_order(signed_yes, OrderType.GTC)
        r2 = client.post_order(signed_no, OrderType.GTC)
        if r1 is not None:
            orders_created.append(r1)
        if r2 is not None:
            orders_created.append(r2)

    return orders_created


def execute_split_arbitrage(
    signal: SplitArbitrageSignal,
    client: Optional[Any] = None,
    paper: bool = True,
    tick_size: str = "0.01",
    neg_risk: bool = False,
) -> List[Any]:
    """
    目的：对一次 Split 套利信号执行操作（用 USDC 拆分成 YES+NO，然后卖出）
    方法：paper 为 True 时只记录拟执行的操作；否则：
         1. 调用 CTF Split 操作：用 size USDC 拆分成 size YES + size NO
         2. 创建两笔卖单：SELL YES 和 SELL NO，价格分别为 bid_yes 和 bid_no
         3. 批量提交卖单
    注意：CTF Split 操作需要链上交易，当前先实现检测和日志，CTF 操作后续补充
    """
    if paper:
        logger.info(
            "[PAPER] Split 套利机会: token_yes=%s bid_yes=%s token_no=%s bid_no=%s size=%s expected_profit=%s",
            signal.token_id_yes,
            signal.bid_yes,
            signal.token_id_no,
            signal.bid_no,
            signal.size,
            signal.expected_profit,
        )
        logger.info(
            "[PAPER] Split 操作: 用 $%.2f USDC 拆分成 %.2f YES + %.2f NO，然后卖出得到 $%.4f，利润 $%.4f",
            signal.size,
            signal.size,
            signal.size,
            signal.size * (signal.bid_yes + signal.bid_no),
            signal.expected_profit,
        )
        return []

    if client is None:
        logger.warning("实盘模式但未提供 client，跳过 Split 套利执行")
        return []

    try:
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import SELL
    except ImportError:
        logger.error("py_clob_client 未安装，无法执行 Split 套利")
        return []

    orders_created: List[Any] = []

    # TODO: 实现 CTF Split 操作
    # 1. 调用 CTF 合约的 splitPosition() 方法，用 size USDC 拆分成 size YES + size NO
    # 2. 等待交易确认
    logger.warning("CTF Split 操作尚未实现，当前仅记录日志")
    logger.info(
        "应执行: Split $%.2f USDC -> %.2f YES + %.2f NO",
        signal.size,
        signal.size,
        signal.size,
    )

    # 创建两笔卖单：SELL YES 和 SELL NO
    order_yes = OrderArgs(
        price=signal.bid_yes,
        size=signal.size,
        side=SELL,
        token_id=signal.token_id_yes,
    )
    order_no = OrderArgs(
        price=signal.bid_no,
        size=signal.size,
        side=SELL,
        token_id=signal.token_id_no,
    )

    signed_yes = client.create_order(order_yes)
    signed_no = client.create_order(order_no)

    # 批量提交卖单
    if hasattr(client, "post_orders") and callable(getattr(client, "post_orders")):
        resp = client.post_orders([signed_yes, signed_no], OrderType.GTC)
        if isinstance(resp, list):
            orders_created.extend(resp)
        else:
            orders_created.append(resp)
    else:
        r1 = client.post_order(signed_yes, OrderType.GTC)
        r2 = client.post_order(signed_no, OrderType.GTC)
        if r1 is not None:
            orders_created.append(r1)
        if r2 is not None:
            orders_created.append(r2)

    return orders_created


def execute_maker_arbitrage(
    signal: MakerArbitrageSignal,
    client: Optional[Any] = None,
    paper: bool = True,
    tick_size: str = "0.01",
    neg_risk: bool = False,
    order_timeout_sec: float = 300.0,  # 5 分钟超时
) -> List[Any]:
    """
    目的：对一次 Maker 套利信号执行操作（在 YES 和 NO 两边挂 Maker 买单）
    方法：paper 为 True 时只记录拟执行的操作；否则：
         1. 创建两笔 Maker 买单：BUY YES 和 BUY NO，价格分别为 maker_bid_yes 和 maker_bid_no
         2. 提交订单并跟踪订单状态
         3. 监控部分成交情况
    注意：Maker 策略需要等待成交，可能只成交一边，需要处理部分成交的情况
    """
    if paper:
        logger.info(
            "[PAPER] Maker 套利机会: token_yes=%s maker_bid_yes=%.4f (best_ask=%.4f) "
            "token_no=%s maker_bid_no=%.4f (best_ask=%.4f) size=%s expected_profit=%s",
            signal.token_id_yes,
            signal.maker_bid_yes,
            signal.best_ask_yes,
            signal.token_id_no,
            signal.maker_bid_no,
            signal.best_ask_no,
            signal.size,
            signal.expected_profit,
        )
        logger.info(
            "[PAPER] Maker 策略: 挂买单等待成交，成本=%.4f，利润=%.4f（可能获得 Maker 返佣）",
            signal.maker_bid_yes + signal.maker_bid_no,
            signal.expected_profit / signal.size,
        )
        return []

    if client is None:
        logger.warning("实盘模式但未提供 client，跳过 Maker 套利执行")
        return []

    try:
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY
    except ImportError:
        logger.error("py_clob_client 未安装，无法执行 Maker 套利")
        return []

    orders_created: List[Any] = []

    # 创建两笔 Maker 买单：价格略低于 best ask，确保成为 Maker
    order_yes = OrderArgs(
        price=signal.maker_bid_yes,
        size=signal.size,
        side=BUY,
        token_id=signal.token_id_yes,
    )
    order_no = OrderArgs(
        price=signal.maker_bid_no,
        size=signal.size,
        side=BUY,
        token_id=signal.token_id_no,
    )

    signed_yes = client.create_order(order_yes)
    signed_no = client.create_order(order_no)

    # 提交订单
    if hasattr(client, "post_orders") and callable(getattr(client, "post_orders")):
        resp = client.post_orders([signed_yes, signed_no], OrderType.GTC)
        if isinstance(resp, list):
            orders_created.extend(resp)
        else:
            orders_created.append(resp)
    else:
        r1 = client.post_order(signed_yes, OrderType.GTC)
        r2 = client.post_order(signed_no, OrderType.GTC)
        if r1 is not None:
            orders_created.append(r1)
        if r2 is not None:
            orders_created.append(r2)

    # 跟踪订单状态（用于后续监控部分成交）
    for order in orders_created:
        if order and hasattr(order, "order_id"):
            order_id = str(order.order_id)
            _maker_orders[order_id] = {
                "signal": signal,
                "created_at": time.time(),
                "status": "pending",
                "filled_yes": 0.0,
                "filled_no": 0.0,
                "token_id": signal.token_id_yes if "yes" in order_id.lower() else signal.token_id_no,
            }
            logger.info("Maker 订单已提交: order_id=%s, token_id=%s, price=%.4f, size=%.2f",
                       order_id, _maker_orders[order_id]["token_id"],
                       signal.maker_bid_yes if "yes" in order_id.lower() else signal.maker_bid_no,
                       signal.size)

    return orders_created


def check_maker_orders_status(
    client: Optional[Any],
    timeout_sec: float = 300.0,
    paper: bool = True,
) -> Dict[str, Any]:
    """
    目的：检查 Maker 订单状态，处理部分成交情况
    方法：遍历跟踪的 Maker 订单，检查是否完全成交、部分成交或超时
    返回：订单状态统计
    """
    if paper or client is None:
        return {"total": len(_maker_orders), "filled": 0, "partial": 0, "pending": len(_maker_orders)}

    current_time = time.time()
    stats = {"total": len(_maker_orders), "filled": 0, "partial": 0, "pending": 0, "timeout": 0}

    # TODO: 实现订单状态查询
    # 需要调用 client 的订单查询接口，检查每个订单的成交状态
    # 如果订单超时且未完全成交，考虑撤单或转为 Taker 策略

    for order_id, order_info in list(_maker_orders.items()):
        elapsed = current_time - order_info["created_at"]
        if elapsed > timeout_sec:
            logger.warning("Maker 订单超时: order_id=%s, elapsed=%.1fs", order_id, elapsed)
            stats["timeout"] += 1
            # TODO: 可以考虑撤单或转为 Taker 策略

    return stats


def cancel_orders(
    client: Optional[Any],
    order_ids: List[str],
    paper: bool = True,
) -> bool:
    """
    目的：撤单，供风控或主流程使用
    方法：paper 时只打 log；否则调用 client 的 cancel 接口
    """
    if paper or client is None:
        if order_ids:
            logger.info("[PAPER] 拟撤单: %s", order_ids)
        return True
    try:
        if hasattr(client, "cancel_orders") and callable(getattr(client, "cancel_orders")):
            client.cancel_orders(order_ids)
            # 从跟踪中移除
            for order_id in order_ids:
                _maker_orders.pop(str(order_id), None)
            return True
    except Exception as e:
        logger.exception("撤单失败: %s", e)
    return False
