# 目的：捕捉体育赛事实时波动带来的单边机会（价格偏离近期均值超过阈值时发信号）
# 方法：维护短期价格窗口，当价格偏离均值超过 deviation_pct 且满足仓位上限时生成信号；简单版用固定阈值

from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Optional


@dataclass
class VolatilitySignal:
    """
    目的：表示一次波动策略信号，供执行层单腿下单
    方法：含 token_id、side（BUY/SELL）、建议 price、size、偏离幅度
    """
    token_id: str
    side: str  # "BUY" or "SELL"
    price: float
    size: float
    deviation_pct: float
    condition_id: str = ""
    question: str = ""


def _mid(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    """目的：用 bid/ask 中点作为当前价。方法：若缺一侧则用另一侧"""
    if bid is not None and ask is not None:
        return (bid + ask) / 2.0
    return bid if bid is not None else ask


class VolatilityDetector:
    """
    目的：对单个 token 维护短期价格窗口，当价格偏离均值超过阈值时生成信号
    方法：用 deque 存最近 N 个 mid 价，均值与当前价比较；超过 deviation_pct 则发 BUY（价低）或 SELL（价高）
    """

    def __init__(
        self,
        token_id: str,
        window_size: int = 20,
        deviation_pct: float = 0.05,
        max_position: float = 50.0,
        default_size: float = 5.0,
    ) -> None:
        self.token_id = token_id
        self.window_size = window_size
        self.deviation_pct = deviation_pct
        self.max_position = max_position
        self.default_size = default_size
        self._prices: Deque[float] = deque(maxlen=window_size)
        self._current_position: float = 0.0

    def update(self, bid: Optional[float], ask: Optional[float]) -> None:
        """目的：用最新 bid/ask 更新价格窗口。方法：计算 mid 并加入 deque"""
        mid = _mid(bid, ask)
        if mid is not None:
            self._prices.append(mid)

    def check_signal(
        self,
        current_bid: Optional[float],
        current_ask: Optional[float],
        condition_id: str = "",
        question: str = "",
    ) -> Optional[VolatilitySignal]:
        """
        目的：若当前价偏离近期均值超过 deviation_pct 且未超仓位，则生成 BUY 或 SELL 信号
        方法：均值 = sum(prices)/len；偏离 = (current - mean)/mean；超过阈值且仓位+size <= max_position 则发信号
        """
        if len(self._prices) < 2:
            return None
        mid = _mid(current_bid, current_ask)
        if mid is None:
            return None
        mean = sum(self._prices) / len(self._prices)
        if mean <= 0:
            return None
        deviation = (mid - mean) / mean
        if abs(deviation) < self.deviation_pct:
            return None
        if self._current_position + self.default_size > self.max_position:
            return None
        side = "BUY" if deviation < 0 else "SELL"
        return VolatilitySignal(
            token_id=self.token_id,
            side=side,
            price=mid,
            size=self.default_size,
            deviation_pct=abs(deviation),
            condition_id=condition_id,
            question=question,
        )


def scan_markets_for_volatility(
    markets: List[Dict],
    get_bid: Callable[[str], Optional[float]],
    get_ask: Callable[[str], Optional[float]],
    detectors: Dict[str, VolatilityDetector],
    deviation_pct: float = 0.05,
    default_size: float = 5.0,
    max_position: float = 50.0,
) -> List[VolatilitySignal]:
    """
    目的：对多个市场的 YES token 检测波动信号（仅对 YES 做单边，NO 可对称扩展）
    方法：遍历 markets，对 token_id_yes 维护或获取 detector，update 后 check_signal，收集非空信号
    """
    signals: List[VolatilitySignal] = []
    for m in markets:
        ty = m.get("token_id_yes")
        if not ty:
            continue
        if ty not in detectors:
            detectors[ty] = VolatilityDetector(
                token_id=ty,
                deviation_pct=deviation_pct,
                default_size=default_size,
                max_position=max_position,
            )
        det = detectors[ty]
        bid, ask = get_bid(ty), get_ask(ty)
        det.update(bid, ask)
        sig = det.check_signal(
            bid, ask,
            condition_id=m.get("condition_id", ""),
            question=m.get("question", ""),
        )
        if sig is not None:
            signals.append(sig)
    return signals
