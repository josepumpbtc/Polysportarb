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
    目的：表示一次 YES/NO 套利机会，供执行层批量下单
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
    目的：对多个二元市场批量检测套利机会，供 main 循环调用
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
