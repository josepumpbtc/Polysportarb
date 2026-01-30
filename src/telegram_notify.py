# 目的：套利机会出现时推送消息到 Telegram Bot，便于远程提醒
# 方法：从环境变量读 TELEGRAM_BOT_TOKEN、TELEGRAM_CHAT_ID，用 Bot API sendMessage 发送；未配置则跳过

import logging
import os
from typing import Optional

import requests

from src.arbitrage import ArbitrageSignal, SplitArbitrageSignal, MakerArbitrageSignal

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot%s/sendMessage"


def send_telegram_message(text: str, bot_token: Optional[str] = None, chat_id: Optional[str] = None) -> bool:
    """
    目的：发送一条文本到 Telegram 指定 chat
    方法：GET https://api.telegram.org/bot<token>/sendMessage?chat_id=...&text=...
    未配置 token 或 chat_id 时返回 False，不抛异常
    """
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    cid = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not cid:
        return False
    try:
        url = TELEGRAM_API % token.strip()
        r = requests.get(url, params={"chat_id": cid.strip(), "text": text}, timeout=10)
        if r.status_code != 200:
            logger.warning("Telegram 发送失败: status=%s body=%s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:
        logger.warning("Telegram 发送异常: %s", e)
        return False


# Polymarket 市场页面 URL（用 condition_id 可跳转或搜索）
def _market_url(condition_id: str) -> str:
    if not condition_id or not condition_id.strip():
        return ""
    cid = condition_id.strip()
    return f"https://polymarket.com/market/{cid}"


def format_arb_opportunity(signal: ArbitrageSignal) -> str:
    """
    目的：将套利信号格式化为 Telegram 详细消息
    内容：套利市场名称、市场 URL、买卖价格（YES/NO 买价）、建议下单量与预期利润
    """
    q = (signal.question or "套利机会").strip()
    if len(q) > 120:
        q = q[:117] + "..."
    url = _market_url(signal.condition_id)
    sum_price = signal.price_yes + signal.price_no
    lines = [
        "🔔 套利机会",
        "",
        "【市场】",
        q,
        "",
        "【买卖价格】",
        f"买 YES: {signal.price_yes:.3f}",
        f"买 NO:  {signal.price_no:.3f}",
        f"合计:   {sum_price:.3f} (< 1 存在套利)",
        "",
        "【建议下单】",
        f"每腿数量: {signal.size:.1f}",
        f"预期利润: ${signal.expected_profit:.2f}",
        "",
    ]
    if url:
        lines.append("【市场链接】")
        lines.append(url)
    return "\n".join(lines)


def format_split_arb_opportunity(signal: SplitArbitrageSignal) -> str:
    """
    目的：将 Split 套利信号格式化为 Telegram 详细消息
    """
    q = (signal.question or "Split 套利机会").strip()
    if len(q) > 120:
        q = q[:117] + "..."
    url = _market_url(signal.condition_id)
    sum_bid = signal.bid_yes + signal.bid_no
    lines = [
        "🚀 Split 套利机会（瞬间结算）",
        "",
        "【市场】",
        q,
        "",
        "【卖出价格】",
        f"卖 YES: {signal.bid_yes:.3f}",
        f"卖 NO:  {signal.bid_no:.3f}",
        f"合计:   {sum_bid:.3f} (> 1 存在套利)",
        "",
        "【操作】",
        f"1. 用 ${signal.size:.2f} USDC 拆分成 {signal.size:.2f} YES + {signal.size:.2f} NO",
        f"2. 分别卖出给市场上的 bid",
        "",
        "【预期利润】",
        f"${signal.expected_profit:.2f}（瞬间结算，无需等待）",
        "",
    ]
    if url:
        lines.append("【市场链接】")
        lines.append(url)
    return "\n".join(lines)


def format_maker_arb_opportunity(signal: MakerArbitrageSignal) -> str:
    """
    目的：将 Maker 套利信号格式化为 Telegram 详细消息
    """
    q = (signal.question or "Maker 套利机会").strip()
    if len(q) > 120:
        q = q[:117] + "..."
    url = _market_url(signal.condition_id)
    sum_maker_bid = signal.maker_bid_yes + signal.maker_bid_no
    lines = [
        "📊 Maker 套利机会（做市商价差）",
        "",
        "【市场】",
        q,
        "",
        "【Maker 买单价格】",
        f"YES Maker Bid: {signal.maker_bid_yes:.4f} (当前 Ask: {signal.best_ask_yes:.4f})",
        f"NO  Maker Bid: {signal.maker_bid_no:.4f} (当前 Ask: {signal.best_ask_no:.4f})",
        f"合计:         {sum_maker_bid:.4f} (< 1 存在套利)",
        "",
        "【操作】",
        f"在 YES 和 NO 两边挂 Maker 买单，等待成交",
        f"每腿数量: {signal.size:.1f}",
        "",
        "【预期利润】",
        f"${signal.expected_profit:.2f}（可能获得 Maker 返佣）",
        "",
        "⚠️ 注意：可能只成交一边，需要监控订单状态",
        "",
    ]
    if url:
        lines.append("【市场链接】")
        lines.append(url)
    return "\n".join(lines)


def notify_arb_opportunity(signal: ArbitrageSignal) -> bool:
    """
    目的：出现 Taker/Merge 套利机会时推送到 Telegram；供 run_once 或 execution 层调用
    方法：格式化 signal 后调用 send_telegram_message；未配置 TELEGRAM_* 则跳过
    """
    text = format_arb_opportunity(signal)
    return send_telegram_message(text)


def notify_split_arb_opportunity(signal: SplitArbitrageSignal) -> bool:
    """
    目的：出现 Split 套利机会时推送到 Telegram
    """
    text = format_split_arb_opportunity(signal)
    return send_telegram_message(text)


def notify_maker_arb_opportunity(signal: MakerArbitrageSignal) -> bool:
    """
    目的：出现 Maker 套利机会时推送到 Telegram
    """
    text = format_maker_arb_opportunity(signal)
    return send_telegram_message(text)


def notify_startup() -> bool:
    """
    目的：启动时发送一条测试消息到 Telegram，便于排查 Railway 上未收到推送
    方法：发送「Polysportarb 已启动」；未配置 TELEGRAM_* 或发送失败时返回 False 并打 log
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    cid = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not cid:
        logger.info(
            "Telegram 未配置: TELEGRAM_BOT_TOKEN=%s TELEGRAM_CHAT_ID=%s",
            "已设置" if token else "未设置",
            "已设置" if cid else "未设置",
        )
        return False
    text = "Polysportarb 已启动（Paper 模式）"
    ok = send_telegram_message(text, bot_token=token, chat_id=cid)
    if not ok:
        logger.warning("Telegram 启动测试消息发送失败，请检查 BOT_TOKEN 与 CHAT_ID 是否正确")
    return ok


def notify_heartbeat() -> bool:
    """
    目的：每小时推送一条「策略正在 Railway 运行中」，确认服务存活
    方法：发送固定文案；未配置 TELEGRAM_* 时返回 False，不抛异常
    """
    text = "⏱ Polysportarb 策略正在 Railway 运行中"
    return send_telegram_message(text)
