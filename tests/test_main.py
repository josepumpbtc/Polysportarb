# 目的：验证主流程一轮（run_once）不抛异常，且 paper 模式下不调用 client
# 方法：mock store 与 markets，调用 run_once，断言无异常且执行层仅打 log

from unittest.mock import MagicMock, patch
import pytest
from src.main import run_once
from src.orderbook import OrderBookStore
from src.arbitrage import ArbitrageSignal
from src.execution import execute_arbitrage


def test_run_once_paper_mode_no_exception():
    """
    目的：主流程一轮在 paper 模式下不抛异常，便于纸面跑通
    预期：run_once(..., paper=True) 不抛出，且 execute_arbitrage 被调用（paper 只打 log）
    """
    config = {
        "min_profit": 0.005,
        "fee_bps": 0,
        "default_size": 5.0,
        "volatility_enabled": False,
    }
    store = OrderBookStore()
    # 注入模拟订单簿：YES=0.48, NO=0.50 存在套利
    store.update_from_message({"asset_id": "ty1", "bid": 0.47, "ask": 0.48})
    store.update_from_message({"asset_id": "tn1", "bid": 0.49, "ask": 0.50})
    markets = [
        {
            "token_id_yes": "ty1",
            "token_id_no": "tn1",
            "condition_id": "c1",
            "question": "Test?",
        },
    ]
    client = None
    volatility_detectors = {}
    with patch("src.main.execute_arbitrage") as mock_exec:
        run_once(config, store, markets, paper=True, client=client, volatility_detectors=volatility_detectors)
        # 应检测到套利并调用 execute_arbitrage 一次（paper 只打 log）
        assert mock_exec.called
        call_args = mock_exec.call_args[0]
        assert isinstance(call_args[0], ArbitrageSignal)
        assert call_args[0].token_id_yes == "ty1"
        assert call_args[0].token_id_no == "tn1"


def test_run_once_no_markets_no_exception():
    """
    目的：无市场时 run_once 不抛异常
    预期：markets=[] 时 run_once 正常返回
    """
    config = {"min_profit": 0.005, "fee_bps": 0, "default_size": 5.0, "volatility_enabled": False}
    store = OrderBookStore()
    with patch("src.main.execute_arbitrage"):
        run_once(config, store, [], paper=True, client=None, volatility_detectors={})
