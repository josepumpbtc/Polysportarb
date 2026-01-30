# 目的：识别 YES/NO 价差套利机会（主策略）
# 逻辑：二元市场 YES+NO 结算恒为 $1。Polymarket 目前无手续费，套利条件为：
#       「买 YES 的最优卖价 + 买 NO 的最优卖价」< 1
# orderbook 上：买 YES 的最优卖价 = YES 合约的 best ask，买 NO 的最优卖价 = NO 合约的 best ask
# 方法：对同一 market 的 YES/NO token 取 get_best_ask；若 ask_yes + ask_no < 1 - min_profit 则生成套利信号（fee=0 时）

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ArbitrageSignal:
    """
    目的：表示一次 YES/NO Merge 套利机会（买入 YES+NO，等待结算或合并成 USDC）
    方法：含 token_id_yes/no、价格、建议 size、预期利润（结算 $1，成本为两腿买价之和）
    """
    token_id_yes: str
    token_id_no: str
    price_yes: float
    price_no: float
    size: float
    expected_profit: float
    condition_id: str = ""
    question: str = ""
    arb_type: str = "merge"  # "merge" 表示买入 YES+NO 后等待结算或合并


@dataclass
class SplitArbitrageSignal:
    """
    目的：表示一次 YES/NO Split 套利机会（用 USDC 拆分成 YES+NO，然后卖出）
    方法：含 token_id_yes/no、卖出价格（bid）、建议 size、预期利润（卖出价之和 - 1）
    """
    token_id_yes: str
    token_id_no: str
    bid_yes: float
    bid_no: float
    size: float
    expected_profit: float
    condition_id: str = ""
    question: str = ""
    arb_type: str = "split"  # "split" 表示拆分 USDC 后卖出


@dataclass
class MakerArbitrageSignal:
    """
    目的：表示一次 Maker 套利机会（在 YES 和 NO 两边挂 Maker 买单，等待成交）
    方法：含 token_id_yes/no、Maker 买单价格（略低于 best ask）、建议 size、预期利润
    注意：Maker 策略需要挂低于 best ask 的价格才能成为 Maker，可能获得返佣/奖励
    """
    token_id_yes: str
    token_id_no: str
    maker_bid_yes: float  # Maker 买单价格（略低于 best ask）
    maker_bid_no: float   # Maker 买单价格（略低于 best ask）
    best_ask_yes: float   # 当前 best ask（用于参考）
    best_ask_no: float    # 当前 best ask（用于参考）
    size: float
    expected_profit: float
    condition_id: str = ""
    question: str = ""
    arb_type: str = "maker"  # "maker" 表示 Maker 策略


def check_arbitrage(
    token_id_yes: str,
    token_id_no: str,
    get_best_ask: Callable[[str], Optional[float]],
    min_profit: float = 0.005,
    fee_bps: float = 0.0,
    default_size: float = 5.0,
    condition_id: str = "",
    question: str = "",
) -> Optional[ArbitrageSignal]:
    """
    目的：判断同一二元市场的 YES/NO 买价之和是否 < 1，若成立则返回套利信号
    方法：Polymarket 无手续费，套利条件为 ask_yes + ask_no < 1（再扣 min_profit 阈值）；利润 = 1 - (ask_yes + ask_no)
    """
    ask_yes = get_best_ask(token_id_yes)
    ask_no = get_best_ask(token_id_no)
    if ask_yes is None or ask_no is None:
        return None
    # 排除不活跃/极端概率市场：YES 或 NO 的 ask 在 0.01 或 0.99 附近视为无真实交易
    if ask_yes <= 0.01 or ask_yes >= 0.99 or ask_no <= 0.01 or ask_no >= 0.99:
        return None

    fee = fee_bps / 10000.0 if fee_bps else 0.0
    sum_ask = ask_yes + ask_no
    # 方法：结算时任一方得 $1，成本为 sum_ask，再扣手续费；利润 = 1 - sum_ask - fee
    gross_profit = 1.0 - sum_ask
    net_profit = gross_profit - fee if fee else gross_profit

    if net_profit < min_profit:
        return None

    return ArbitrageSignal(
        token_id_yes=token_id_yes,
        token_id_no=token_id_no,
        price_yes=ask_yes,
        price_no=ask_no,
        size=default_size,
        expected_profit=net_profit * default_size,
        condition_id=condition_id,
        question=question,
    )


def scan_markets_for_arbitrage(
    markets: List[Dict[str, Any]],
    get_best_ask: Callable[[str], Optional[float]],
    min_profit: float = 0.005,
    fee_bps: float = 0.0,
    default_size: float = 5.0,
) -> List[ArbitrageSignal]:
    """
    目的：对多个二元市场批量检测 Merge 套利机会，供 main 循环调用
    方法：遍历 markets（每项含 token_id_yes、token_id_no 等），对每个调用 check_arbitrage，收集非空信号
    """
    signals: List[ArbitrageSignal] = []
    for m in markets:
        ty = m.get("token_id_yes")
        tn = m.get("token_id_no")
        if not ty or not tn:
            continue
        sig = check_arbitrage(
            token_id_yes=ty,
            token_id_no=tn,
            get_best_ask=get_best_ask,
            min_profit=min_profit,
            fee_bps=fee_bps,
            default_size=default_size,
            condition_id=m.get("condition_id", ""),
            question=m.get("question", ""),
        )
        if sig is not None:
            signals.append(sig)
    return signals


def check_split_arbitrage(
    token_id_yes: str,
    token_id_no: str,
    get_best_bid: Callable[[str], Optional[float]],
    min_profit: float = 0.005,
    fee_bps: float = 0.0,
    default_size: float = 5.0,
    condition_id: str = "",
    question: str = "",
) -> Optional[SplitArbitrageSignal]:
    """
    目的：判断同一二元市场的 YES/NO 卖价（bid）之和是否 > 1，若成立则返回 Split 套利信号
    方法：Polymarket 无手续费，Split 套利条件为 bid_yes + bid_no > 1 + min_profit；
         利润 = (bid_yes + bid_no) - 1（用 $1 USDC 拆分成 YES+NO，然后卖出）
    """
    bid_yes = get_best_bid(token_id_yes)
    bid_no = get_best_bid(token_id_no)
    if bid_yes is None or bid_no is None:
        return None
    # 排除不活跃/极端概率市场：YES 或 NO 的 bid 在 0.01 或 0.99 附近视为无真实交易
    if bid_yes <= 0.01 or bid_yes >= 0.99 or bid_no <= 0.01 or bid_no >= 0.99:
        return None

    fee = fee_bps / 10000.0 if fee_bps else 0.0
    sum_bid = bid_yes + bid_no
    # 方法：用 $1 USDC 拆分成 YES+NO，然后卖出得到 sum_bid，再扣手续费；利润 = sum_bid - 1 - fee
    gross_profit = sum_bid - 1.0
    net_profit = gross_profit - fee if fee else gross_profit

    if net_profit < min_profit:
        return None

    return SplitArbitrageSignal(
        token_id_yes=token_id_yes,
        token_id_no=token_id_no,
        bid_yes=bid_yes,
        bid_no=bid_no,
        size=default_size,
        expected_profit=net_profit * default_size,
        condition_id=condition_id,
        question=question,
    )


def scan_markets_for_split_arbitrage(
    markets: List[Dict[str, Any]],
    get_best_bid: Callable[[str], Optional[float]],
    min_profit: float = 0.005,
    fee_bps: float = 0.0,
    default_size: float = 5.0,
) -> List[SplitArbitrageSignal]:
    """
    目的：对多个二元市场批量检测 Split 套利机会，供 main 循环调用
    方法：遍历 markets（每项含 token_id_yes、token_id_no 等），对每个调用 check_split_arbitrage，收集非空信号
    """
    signals: List[SplitArbitrageSignal] = []
    for m in markets:
        ty = m.get("token_id_yes")
        tn = m.get("token_id_no")
        if not ty or not tn:
            continue
        sig = check_split_arbitrage(
            token_id_yes=ty,
            token_id_no=tn,
            get_best_bid=get_best_bid,
            min_profit=min_profit,
            fee_bps=fee_bps,
            default_size=default_size,
            condition_id=m.get("condition_id", ""),
            question=m.get("question", ""),
        )
        if sig is not None:
            signals.append(sig)
    return signals


def check_maker_arbitrage(
    token_id_yes: str,
    token_id_no: str,
    get_best_ask: Callable[[str], Optional[float]],
    get_best_bid: Callable[[str], Optional[float]],
    min_profit: float = 0.005,
    maker_bid_spread: float = 0.01,  # Maker 买单价格低于 best ask 的价差（例如 0.01 = 1 cent）
    fee_bps: float = 0.0,
    default_size: float = 5.0,
    condition_id: str = "",
    question: str = "",
) -> Optional[MakerArbitrageSignal]:
    """
    目的：判断是否存在 Maker 套利机会（在 YES 和 NO 两边挂 Maker 买单）
    方法：
    1. 检查 ask_yes + ask_no < 1（存在套利空间）
    2. 计算 Maker 买单价格：maker_bid = best_ask - maker_bid_spread
    3. 确保 maker_bid_yes + maker_bid_no < 1 且仍有利润
    4. 返回 Maker 套利信号
    """
    ask_yes = get_best_ask(token_id_yes)
    ask_no = get_best_ask(token_id_no)
    bid_yes = get_best_bid(token_id_yes)
    bid_no = get_best_bid(token_id_no)
    
    if ask_yes is None or ask_no is None:
        return None
    
    # 排除不活跃/极端概率市场
    if ask_yes <= 0.01 or ask_yes >= 0.99 or ask_no <= 0.01 or ask_no >= 0.99:
        return None
    
    # 计算 Maker 买单价格（略低于 best ask，确保成为 Maker）
    maker_bid_yes = ask_yes - maker_bid_spread
    maker_bid_no = ask_no - maker_bid_spread
    
    # 确保 Maker 价格不低于当前 best bid（否则可能立即成交，成为 Taker）
    if bid_yes is not None and maker_bid_yes < bid_yes:
        maker_bid_yes = bid_yes + 0.001  # 略高于 best bid，确保是 Maker
    if bid_no is not None and maker_bid_no < bid_no:
        maker_bid_no = bid_no + 0.001
    
    # 确保 Maker 价格合理（不能为负或超过 1）
    if maker_bid_yes <= 0.01 or maker_bid_yes >= 0.99:
        return None
    if maker_bid_no <= 0.01 or maker_bid_no >= 0.99:
        return None
    
    # 检查 Maker 价格之和是否 < 1 且仍有利润
    sum_maker_bid = maker_bid_yes + maker_bid_no
    if sum_maker_bid >= 1.0:
        return None
    
    fee = fee_bps / 10000.0 if fee_bps else 0.0
    # 利润 = 1 - (maker_bid_yes + maker_bid_no) - fee
    gross_profit = 1.0 - sum_maker_bid
    net_profit = gross_profit - fee if fee else gross_profit
    
    if net_profit < min_profit:
        return None
    
    return MakerArbitrageSignal(
        token_id_yes=token_id_yes,
        token_id_no=token_id_no,
        maker_bid_yes=maker_bid_yes,
        maker_bid_no=maker_bid_no,
        best_ask_yes=ask_yes,
        best_ask_no=ask_no,
        size=default_size,
        expected_profit=net_profit * default_size,
        condition_id=condition_id,
        question=question,
    )


def scan_markets_for_maker_arbitrage(
    markets: List[Dict[str, Any]],
    get_best_ask: Callable[[str], Optional[float]],
    get_best_bid: Callable[[str], Optional[float]],
    min_profit: float = 0.005,
    maker_bid_spread: float = 0.01,
    fee_bps: float = 0.0,
    default_size: float = 5.0,
) -> List[MakerArbitrageSignal]:
    """
    目的：对多个二元市场批量检测 Maker 套利机会，供 main 循环调用
    方法：遍历 markets（每项含 token_id_yes、token_id_no 等），对每个调用 check_maker_arbitrage，收集非空信号
    """
    signals: List[MakerArbitrageSignal] = []
    for m in markets:
        ty = m.get("token_id_yes")
        tn = m.get("token_id_no")
        if not ty or not tn:
            continue
        sig = check_maker_arbitrage(
            token_id_yes=ty,
            token_id_no=tn,
            get_best_ask=get_best_ask,
            get_best_bid=get_best_bid,
            min_profit=min_profit,
            maker_bid_spread=maker_bid_spread,
            fee_bps=fee_bps,
            default_size=default_size,
            condition_id=m.get("condition_id", ""),
            question=m.get("question", ""),
        )
        if sig is not None:
            signals.append(sig)
    return signals
