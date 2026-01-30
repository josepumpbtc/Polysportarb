# 目的：验证执行层在 paper 模式下不调用 CLOB、在实盘模式下以预期参数调用
# 方法：mock client.create_order 与 client.post_order/post_orders，断言 paper 不调用、非 paper 调用

import logging
from unittest.mock import MagicMock, patch
import pytest
from src.arbitrage import ArbitrageSignal
from src.execution import execute_arbitrage, cancel_orders


def test_execute_arbitrage_paper_mode_does_not_call_client():
    """
    目的：paper=True 时不应调用 client 的 create_order 或 post_order，避免误发单
    预期：execute_arbitrage(..., paper=True) 后 client.create_order 与 post_order 未被调用
    """
    client = MagicMock()
    signal = ArbitrageSignal(
        token_id_yes="ty",
        token_id_no="tn",
        price_yes=0.48,
        price_no=0.50,
        size=5.0,
        expected_profit=0.1,
    )
    with patch("src.execution.logger"):
        execute_arbitrage(signal, client=client, paper=True)
    client.create_order.assert_not_called()
    assert not (hasattr(client, "post_order") and client.post_order.called)


def test_execute_arbitrage_live_mode_calls_create_and_post():
    """
    目的：paper=False 且 client 存在时，应创建两腿订单并提交
    预期：create_order 被调用两次（YES、NO），post_order 被调用两次（若无 post_orders）
    """
    client = MagicMock()
    client.create_order.side_effect = [MagicMock(), MagicMock()]
    client.post_order.return_value = MagicMock()
    client.post_orders = None  # 无批量接口，走两次 post_order

    signal = ArbitrageSignal(
        token_id_yes="ty",
        token_id_no="tn",
        price_yes=0.48,
        price_no=0.50,
        size=5.0,
        expected_profit=0.1,
    )
    with patch("src.execution.logger"):
        result = execute_arbitrage(signal, client=client, paper=False)
    assert client.create_order.call_count == 2
    assert client.post_order.call_count == 2
    assert len(result) == 2


def test_execute_arbitrage_live_mode_no_client_returns_empty():
    """
    目的：实盘模式但 client 为 None 时不下单并返回空列表
    预期：返回 []，且不抛异常
    """
    signal = ArbitrageSignal(
        token_id_yes="ty",
        token_id_no="tn",
        price_yes=0.48,
        price_no=0.50,
        size=5.0,
        expected_profit=0.1,
    )
    with patch("src.execution.logger"):
        result = execute_arbitrage(signal, client=None, paper=False)
    assert result == []


def test_cancel_orders_paper_mode_does_not_call_client():
    """
    目的：paper=True 时撤单只打 log，不调用 client
    预期：client.cancel_orders 未被调用
    """
    client = MagicMock()
    with patch("src.execution.logger"):
        cancel_orders(client, ["oid1"], paper=True)
    client.cancel_orders.assert_not_called()


def test_cancel_orders_live_mode_calls_client():
    """
    目的：paper=False 且 client 有 cancel_orders 时应调用
    预期：client.cancel_orders(["oid1"]) 被调用一次
    """
    client = MagicMock()
    with patch("src.execution.logger"):
        cancel_orders(client, ["oid1"], paper=False)
    client.cancel_orders.assert_called_once_with(["oid1"])
