# 目的：套利机会出现时推送消息到 Telegram Bot，便于远程提醒
# 方法：从环境变量读 TELEGRAM_BOT_TOKEN、TELEGRAM_CHAT_ID，用 Bot API sendMessage 发送；未配置则跳过

import logging
import os
from typing import Optional

import requests

from src.arbitrage import ArbitrageSignal

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


def format_arb_opportunity(signal: ArbitrageSignal) -> str:
    """目的：将套利信号格式化为 Telegram 可读的一行摘要。方法：含 question、价格、预期利润"""
    q = (signal.question or "套利机会")[:80]
    return (
        "🔔 套利机会\n"
        "市场: %s\n"
        "YES价=%.3f NO价=%.3f 合计=%.3f\n"
        "size=%.1f 预期利润=%.2f"
    ) % (q, signal.price_yes, signal.price_no, signal.price_yes + signal.price_no, signal.size, signal.expected_profit)


def notify_arb_opportunity(signal: ArbitrageSignal) -> bool:
    """
    目的：出现套利机会时推送到 Telegram；供 run_once 或 execution 层调用
    方法：格式化 signal 后调用 send_telegram_message；未配置 TELEGRAM_* 则跳过
    """
    text = format_arb_opportunity(signal)
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
