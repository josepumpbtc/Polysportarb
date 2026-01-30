# 目的：统一下单入口并支持无实盘风险的纸面模式（paper 时只写日志不调用 CLOB）
# 方法：套利信号用批量下单（YES+NO 两腿同 size）；paper 模式下不调用 post_order

import logging
from typing import Any, List, Optional

from src.arbitrage import ArbitrageSignal

logger = logging.getLogger(__name__)


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
            return True
    except Exception as e:
        logger.exception("撤单失败: %s", e)
    return False
