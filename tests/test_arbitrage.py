# 目的：验证套利检测逻辑，不依赖真实订单簿即可通过
# 方法：构造模拟 get_best_ask，断言存在套利时返回信号且利润计算正确，边界情况不触发

import pytest
from src.arbitrage import (
    check_arbitrage,
    scan_markets_for_arbitrage,
    ArbitrageSignal,
)


def test_check_arbitrage_detects_opportunity():
    """
    目的：当 YES+NO 买价之和小于 1 减手续费时，应检测到套利并返回信号
    预期：ask_yes=0.48, ask_no=0.50 时利润约 0.02，返回非空信号且 expected_profit 正确
    """
    def get_ask(tid):
        return 0.48 if "yes" in tid else 0.50

    sig = check_arbitrage(
        token_id_yes="yes_1",
        token_id_no="no_1",
        get_best_ask=get_ask,
        min_profit=0.005,
        fee_bps=0,
        default_size=10.0,
    )
    assert sig is not None
    assert sig.price_yes == 0.48
    assert sig.price_no == 0.50
    # 利润 = (1 - 0.48 - 0.50) * 10 = 0.2
    assert abs(sig.expected_profit - 0.2) < 1e-6


def test_check_arbitrage_no_opportunity_when_sum_equals_one():
    """
    目的：买价之和等于 1 时无套利空间，不触发
    预期：ask_yes=0.5, ask_no=0.5 时返回 None
    """
    def get_ask(tid):
        return 0.5

    sig = check_arbitrage(
        token_id_yes="y",
        token_id_no="n",
        get_best_ask=get_ask,
        min_profit=0.001,
    )
    assert sig is None


def test_check_arbitrage_respects_min_profit():
    """
    目的：利润存在但低于 min_profit 时不触发，避免假机会
    预期：利润 0.003、min_profit=0.005 时返回 None
    """
    # sum_ask=0.997 -> profit=0.003
    def get_ask(tid):
        return 0.4985 if "yes" in tid else 0.4985

    sig = check_arbitrage(
        token_id_yes="yes",
        token_id_no="no",
        get_best_ask=get_ask,
        min_profit=0.005,
    )
    assert sig is None


def test_check_arbitrage_respects_fee_bps():
    """
    目的：手续费应从利润中扣除，扣费后低于 min_profit 则不触发
    预期：毛利 0.01、fee_bps=100（1%）则净利 0，min_profit=0.001 时返回 None
    """
    # sum_ask=0.99 -> gross=0.01, fee 1%=0.01 -> net=0
    def get_ask(tid):
        return 0.495 if "yes" in tid else 0.495

    sig = check_arbitrage(
        token_id_yes="y",
        token_id_no="n",
        get_best_ask=get_ask,
        min_profit=0.001,
        fee_bps=100,
    )
    assert sig is None


def test_check_arbitrage_returns_none_when_missing_price():
    """
    目的：任一腿无报价时不应发信号，避免误用
    预期：get_best_ask 对 no 返回 None 时，check_arbitrage 返回 None
    """
    def get_ask(tid):
        return 0.48 if "yes" in tid else None

    sig = check_arbitrage(
        token_id_yes="yes",
        token_id_no="no",
        get_best_ask=get_ask,
    )
    assert sig is None


def test_scan_markets_for_arbitrage_collects_signals():
    """
    目的：对多个市场扫描时，仅有机会的市场产生信号
    预期：两个市场，一个有机会一个无，返回一个信号
    """
    def get_ask(tid):
        if tid == "ty1":
            return 0.46
        if tid == "tn1":
            return 0.50
        if tid == "ty2":
            return 0.50
        if tid == "tn2":
            return 0.50
        return None

    markets = [
        {"token_id_yes": "ty1", "token_id_no": "tn1", "condition_id": "c1"},
        {"token_id_yes": "ty2", "token_id_no": "tn2", "condition_id": "c2"},
    ]
    signals = scan_markets_for_arbitrage(
        markets,
        get_best_ask=get_ask,
        min_profit=0.005,
    )
    assert len(signals) == 1
    assert signals[0].condition_id == "c1"
    assert signals[0].price_yes == 0.46
    assert signals[0].price_no == 0.50
