#!/usr/bin/env python3
# 目的：测试 orderbook 实时监视，通过 CLOB WebSocket 订阅若干 asset_id 并打印价格/订单簿更新
# 方法：从 Gamma 拉取少量体育二元市场，取 token_id，连接 WSS market channel，订阅后打印 N 秒内的消息

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WSS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def main():
    import argparse
    p = argparse.ArgumentParser(description="测试 Polymarket orderbook 实时监视")
    p.add_argument("--seconds", type=int, default=30, help="监视秒数（默认 30）")
    p.add_argument("--limit", type=int, default=2, help="订阅的市场数量（默认 2，即 4 个 token）")
    args = p.parse_args()

    print("1. 从 Gamma 拉取体育二元市场...")
    from src.gamma import fetch_sports_binary_markets
    markets = fetch_sports_binary_markets(limit=args.limit)
    if not markets:
        print("   当前无体育二元市场，请稍后重试或检查 tag_id")
        return 1
    asset_ids = []
    for m in markets:
        asset_ids.append(m["token_id_yes"])
        asset_ids.append(m["token_id_no"])
    asset_ids = list(dict.fromkeys(asset_ids))[:10]
    print("   订阅 %d 个 asset_id" % len(asset_ids))

    print("2. 连接 CLOB WebSocket 并订阅...")
    try:
        import websocket
    except ImportError:
        print("   请安装: pip install websocket-client")
        return 1

    store = __import__("src.orderbook", fromlist=["OrderBookStore"]).OrderBookStore
    ob = store()

    def on_message(ws, message):
        try:
            msg = json.loads(message)
            if isinstance(msg, dict):
                ob.update_from_message(msg)
                aid = msg.get("asset_id") or msg.get("assetId")
                bid = ob.get_best_bid(str(aid)) if aid else None
                ask = ob.get_best_ask(str(aid)) if aid else None
                if bid is not None or ask is not None:
                    print("   [book] asset_id=%s best_bid=%s best_ask=%s" % (
                        (aid or "")[:16], bid, ask,
                    ))
            elif isinstance(msg, list):
                for m in msg:
                    if isinstance(m, dict):
                        ob.update_from_message(m)
        except Exception as e:
            print("   [parse] %s" % e)

    def on_error(ws, error):
        print("   [ws error]", error)

    def on_close(ws, close_status_code, close_msg):
        print("   WebSocket 已关闭")

    def on_open(ws):
        sub = {"assets_ids": [str(a) for a in asset_ids], "type": "MARKET"}
        ws.send(json.dumps(sub))
        print("   已发送订阅: %d 个 assets" % len(asset_ids))

    ws = websocket.WebSocketApp(
        WSS_MARKET_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )
    import threading
    thread = threading.Thread(target=lambda: ws.run_forever())
    thread.daemon = True
    thread.start()
    time.sleep(2)
    print("3. 监视 %d 秒（收到订单簿更新会打印）..." % args.seconds)
    time.sleep(args.seconds)
    ws.close()
    thread.join(timeout=3)
    print("orderbook 实时监视测试结束。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
