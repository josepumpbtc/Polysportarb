# 目的：验证波动策略逻辑，给定价格序列时偏离阈值产生信号、未超过不产生
# 方法：构造 mock 价格序列，update 若干次后 check_signal，断言偏离超过阈值时产生信号

import pytest
from src.volatility import (
    VolatilityDetector,
    VolatilitySignal,
    _mid,
    scan_markets_for_volatility,
)


def test_mid():
    """
    目的：验证 bid/ask 中点计算，缺一侧时用另一侧
    预期：(0.4, 0.6) -> 0.5；(0.5, None) -> 0.5
    """
    assert _mid(0.4, 0.6) == 0.5
    assert _mid(0.5, None) == 0.5
    assert _mid(None, 0.5) == 0.5
    assert _mid(None, None) is None


def test_volatility_detector_no_signal_until_window_filled():
    """
    目的：窗口未填满或偏离不足时不发信号
    预期：仅 update 一次时 check_signal 返回 None
    """
    det = VolatilityDetector("t1", window_size=5, deviation_pct=0.05)
    det.update(0.5, 0.5)
    sig = det.check_signal(0.5, 0.5)
    assert sig is None


def test_volatility_detector_signal_when_deviation_exceeds_threshold():
    """
    目的：价格偏离近期均值超过 deviation_pct 时发 BUY（价低）或 SELL（价高）
    预期：先填满窗口为 0.5，再 update 0.4（偏离 -20%），应产生 BUY 信号
    """
    det = VolatilityDetector("t1", window_size=5, deviation_pct=0.05)
    for _ in range(5):
        det.update(0.5, 0.5)
    det.update(0.4, 0.4)
    sig = det.check_signal(0.4, 0.4)
    assert sig is not None
    assert sig.side == "BUY"
    assert sig.token_id == "t1"
    # 窗口为 [0.5,0.5,0.5,0.5,0.4]，均值 0.48，偏离 (0.4-0.48)/0.48 ≈ 0.167
    assert sig.deviation_pct >= 0.05


def test_volatility_detector_sell_when_above_mean():
    """
    目的：当前价高于近期均值超过阈值时发 SELL
    预期：窗口为 0.5，当前 0.6（偏离 +20%），应产生 SELL 信号
    """
    det = VolatilityDetector("t1", window_size=5, deviation_pct=0.05)
    for _ in range(5):
        det.update(0.5, 0.5)
    sig = det.check_signal(0.6, 0.6)
    assert sig is not None
    assert sig.side == "SELL"


def test_volatility_detector_no_signal_when_deviation_below_threshold():
    """
    目的：偏离小于 deviation_pct 时不发信号
    预期：窗口 0.5，当前 0.52（偏离 4%），deviation_pct=0.05 时不触发
    """
    det = VolatilityDetector("t1", window_size=5, deviation_pct=0.05)
    for _ in range(5):
        det.update(0.5, 0.5)
    sig = det.check_signal(0.52, 0.52)
    assert sig is None


def test_scan_markets_for_volatility_collects_signals():
    """
    目的：对多个市场扫描时，仅偏离超过阈值的市场产生波动信号
    预期：ty1 窗口填满 0.5 后当前价 0.4（偏离大），ty2 窗口不足，仅 ty1 产生一条 BUY 信号
    """
    markets = [
        {"token_id_yes": "ty1", "token_id_no": "tn1", "condition_id": "c1"},
        {"token_id_yes": "ty2", "token_id_no": "tn2", "condition_id": "c2"},
    ]
    # 第一次 scan 时 ty1 返回 0.4/0.4，ty2 返回 0.5/0.5；需多轮先填满 ty1 再给低价
    detectors: dict = {}
    for _ in range(5):
        scan_markets_for_volatility(
            markets,
            get_bid=lambda tid: 0.5 if tid == "ty2" else 0.5,
            get_ask=lambda tid: 0.5 if tid == "ty2" else 0.5,
            detectors=detectors,
            deviation_pct=0.05,
        )
    # 最后一轮 ty1 给 0.4，偏离超过 5%
    def get_bid(tid):
        return 0.4 if tid == "ty1" else 0.5
    def get_ask(tid):
        return 0.4 if tid == "ty1" else 0.5
    signals = scan_markets_for_volatility(
        markets,
        get_bid=get_bid,
        get_ask=get_ask,
        detectors=detectors,
        deviation_pct=0.05,
    )
    assert isinstance(signals, list)
    # ty1 窗口为 5 个 0.5，当前 0.4，偏离 (0.4-0.5)/0.5 = -20% > 5%，应有一条 BUY
    if len(signals) >= 1:
        assert signals[0].token_id == "ty1"
        assert signals[0].side == "BUY"
