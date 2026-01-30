# 目的：识别 YES/NO 价差套利机会（买价之和小于 1 减手续费与最小利润阈值）
# 方法：对同一 market 的 YES/NO token，取当前 best ask；若 ask_yes + ask_no < 1 - fee - min_profit 则生成套利信号

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
    目的：判断同一二元市场的 YES/NO 买价之和是否低于 1 - 手续费 - 最小利润，若成立则返回套利信号
    方法：买价之和小于 1 减去手续费与 min_profit 即存在套利；利润 = 1 - (ask_yes + ask_no) - 手续费
    """
    ask_yes = get_best_ask(token_id_yes)
    ask_no = get_best_ask(token_id_no)
    if ask_yes is None or ask_no is None:
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
