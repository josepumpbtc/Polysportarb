#!/usr/bin/env python3
# 目的：校验 Polymarket Gamma API 与 CLOB API 连通性，无需密钥
# 方法：GET Gamma /events?limit=1，再取首个二元市场的 token_id 请求 CLOB /book

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"


def main():
    print("1. 连接 Polymarket Gamma API...")
    try:
        r = requests.get(
            f"{GAMMA_BASE}/events",
            params={"closed": "false", "limit": 1},
            timeout=10,
        )
        r.raise_for_status()
        events = r.json() if isinstance(r.json(), list) else []
        print("   Gamma API OK，events 数量:", len(events))
    except Exception as e:
        print("   Gamma API 失败:", e)
        return 1

    if not events:
        print("   当前无未结束 events，跳过 CLOB 订单簿校验")
        return 0

    # 用项目内解析逻辑取二元市场的 token_id（先试当前 events，再试 fetch_sports_binary_markets）
    from src.gamma import events_to_binary_markets, fetch_sports_binary_markets
    binary = events_to_binary_markets(events)
    if not binary:
        binary = fetch_sports_binary_markets(limit=10)
    token_id = None
    if binary:
        token_id = binary[0].get("token_id_yes") or binary[0].get("token_id_no")
    if not token_id:
        print("   未解析到 token_id，跳过 CLOB 校验（Gamma 结构可能变化）")
        return 0

    print("2. 连接 Polymarket CLOB API（订单簿）...")
    # 若有多个市场，可依次尝试 token_id 直到 CLOB 返回 200（已结算市场可能 404）
    token_ids_to_try = [token_id]
    if binary and len(binary) > 1:
        t2 = binary[1].get("token_id_yes") or binary[1].get("token_id_no")
        if t2:
            token_ids_to_try.append(t2)
    last_err = None
    for tid in token_ids_to_try:
        try:
            r = requests.get(
                f"{CLOB_BASE}/book",
                params={"token_id": tid},
                timeout=10,
            )
            if r.status_code == 404:
                last_err = "404（该市场可能已结算）"
                continue
            r.raise_for_status()
            book = r.json()
            bids = book.get("bids") or []
            asks = book.get("asks") or []
            print("   CLOB API OK，token_id=%s，bids=%d，asks=%d" % (tid[:16] + "...", len(bids), len(asks)))
            if bids:
                print("   best_bid:", bids[0])
            if asks:
                print("   best_ask:", asks[0])
            last_err = None
            break
        except Exception as e:
            last_err = e
            continue
    if last_err is not None:
        print("   CLOB API 未成功:", last_err)
        print("   （若为 404，多为已结算市场；可稍后重试或换市场）")

    print("API 连接校验完成（Gamma 已连通；CLOB 见上）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
