#!/usr/bin/env python3
# 目的：对单个 Polymarket 市场（按 event slug）测试价差套利策略，监视 orderbook 是否出现「买 YES 最优卖价 + 买 NO 最优卖价 < 1」
# 方法：Gamma GET /events/slug/{slug} 拉取市场，取 token_id_yes/no，订阅 CLOB WebSocket，轮询 best ask 并判断套利条件
# 示例：python scripts/test_arb_one_market.py --slug will-there-be-another-us-government-shutdown-by-january-31 --seconds 60
# 若出现 SSL 证书错误，可设置环境变量 SSL_CERT_FILE 或使用系统证书后再运行

import argparse
import json
import sys
import threading
import time

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))

# 默认测试市场：US government shutdown by January 31
# https://polymarket.com/event/will-there-be-another-us-government-shutdown-by-january-31
DEFAULT_SLUG = "will-there-be-another-us-government-shutdown-by-january-31"
WSS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def main():
    p = argparse.ArgumentParser(description="单市场套利监视：监视 best ask YES + best ask NO 是否 < 1")
    p.add_argument("--slug", type=str, default=DEFAULT_SLUG, help="Polymarket event slug（默认 US government shutdown）")
    p.add_argument("--seconds", type=int, default=60, help="监视秒数")
    p.add_argument("--interval", type=float, default=2.0, help="轮询间隔秒")
    args = p.parse_args()

    print("1. 按 event slug 拉取市场...")
    from src.gamma import fetch_event_by_slug, event_to_binary_markets

    ev = fetch_event_by_slug(args.slug)
    if not ev:
        print("   拉取失败或 slug 不存在:", args.slug)
        return 1
    markets = event_to_binary_markets(ev)
    if not markets:
        print("   该 event 下无有效二元市场")
        return 1
    # 取第一个二元市场
    m = markets[0]
    ty = m["token_id_yes"]
    tn = m["token_id_no"]
    q = (m.get("question") or "")[:60]
    cid = m.get("condition_id", "")
    print("   市场:", q)
    print("   condition_id:", cid)
    print("   token_id_yes:", ty[:20] + "...")
    print("   token_id_no:", tn[:20] + "...")

    print("2. 连接 CLOB WebSocket，订阅 YES/NO 两个 token...")
    try:
        import websocket
    except ImportError:
        print("   请安装: pip install websocket-client")
        return 1

    from src.orderbook import OrderBookStore

    store = OrderBookStore()
    asset_ids = [ty, tn]

    def run_ws():
        ws = websocket.create_connection(WSS_MARKET_URL)
        ws.send(json.dumps({"assets_ids": [str(a) for a in asset_ids], "type": "MARKET"}))
        while True:
            try:
                raw = ws.recv()
                if not raw:
                    break
                msg = json.loads(raw)
                if isinstance(msg, dict):
                    store.update_from_message(msg)
                elif isinstance(msg, list):
                    for x in msg:
                        if isinstance(x, dict):
                            store.update_from_message(x)
            except (json.JSONDecodeError, websocket.WebSocketConnectionClosedException):
                break
        try:
            ws.close()
        except Exception:
            pass

    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()
    time.sleep(3)

    from src.telegram_notify import send_telegram_message

    def _push_arb_telegram(question: str, ask_yes: float, ask_no: float, total: float, condition_id: str) -> None:
        """检测到套利时推送 Telegram，内容与终端输出一致并带市场链接"""
        url = ("https://polymarket.com/market/%s" % condition_id.strip()) if condition_id else ""
        lines = [
            "🔔 套利机会（单市场监视）",
            "",
            "【市场】%s" % (question[:80] if question else "套利"),
            "",
            "best ask YES=%.4f  best ask NO=%.4f  合计=%.4f  【套利机会】" % (ask_yes, ask_no, total),
        ]
        if url:
            lines.append("")
            lines.append("【市场链接】")
            lines.append(url)
        text = "\n".join(lines)
        if send_telegram_message(text):
            print("   → 已推送 Telegram")
        else:
            print("   → Telegram 未配置或发送失败（TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID）")

    print("3. 监视套利条件：best ask YES + best ask NO < 1（Polymarket 无手续费）")
    print("   每 %.1f 秒轮询一次，共 %d 秒；若合计<1 会同时推送 Telegram\n" % (args.interval, args.seconds))
    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        ask_yes = store.get_best_ask(ty)
        ask_no = store.get_best_ask(tn)
        if ask_yes is not None and ask_no is not None:
            total = ask_yes + ask_no
            arb = total < 1.0
            status = "【套利机会】" if arb else "无套利"
            print(
                "   best ask YES=%.4f  best ask NO=%.4f  合计=%.4f  %s"
                % (ask_yes, ask_no, total, status)
            )
            if arb:
                _push_arb_telegram(q, ask_yes, ask_no, total, cid)
        else:
            print("   (等待 orderbook 数据: ask_yes=%s ask_no=%s)" % (ask_yes, ask_no))
        time.sleep(args.interval)

    print("\n单市场套利监视结束。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
