#!/usr/bin/env python3
# 目的：测试下单流程；默认纸面（只打 log），加 --live 时真实下单（需 .env 与小额资金）
# 方法：从 Gamma 取一个市场的 token_id，创建最小额 BUY 限价单；paper 时只打印拟下单参数

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    import argparse
    p = argparse.ArgumentParser(description="测试 Polymarket 下单")
    p.add_argument("--paper", action="store_true", default=True, help="纸面模式，不下单（默认）")
    p.add_argument("--live", action="store_true", help="实盘下单（需配置 .env）")
    p.add_argument("--token-id", type=str, default=None, help="指定 token_id，不填则从 Gamma 取一个")
    args = p.parse_args()
    paper = not args.live

    if paper:
        print("模式: 纸面（只打 log，不下单）")
    else:
        print("模式: 实盘（将真实下单，请确认小额资金）")

    # 获取 token_id
    token_id = args.token_id or os.getenv("TEST_TOKEN_ID")
    if not token_id:
        print("从 Gamma 拉取一个市场的 token_id...")
        from src.gamma import fetch_sports_binary_markets
        markets = fetch_sports_binary_markets(limit=5)
        if not markets:
            print("当前无体育二元市场，请用 --token-id 或环境变量 TEST_TOKEN_ID 指定")
            return 1
        token_id = markets[0]["token_id_yes"]
        print("使用 token_id_yes: %s" % (token_id[:20] + "..."))
    else:
        print("使用指定 token_id: %s" % (token_id[:20] + "..."))

    if paper:
        print("[PAPER] 拟下单: BUY token_id=%s price=0.01 size=1.0（最小额测试）" % token_id[:20])
        print("测试下单（纸面）完成。实盘请加 --live 并配置 .env")
        return 0

    from src.auth import get_clob_client
    client = get_clob_client()
    if client is None:
        print("认证失败，无法下单")
        return 1

    try:
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY
    except ImportError:
        print("未安装 py-clob-client")
        return 1

    # 最小额限价单：price=0.01, size=1
    order_args = OrderArgs(price=0.01, size=1.0, side=BUY, token_id=token_id)
    signed = client.create_order(order_args)
    resp = client.post_order(signed, OrderType.GTC)
    print("下单响应:", resp)
    if resp and getattr(resp, "get", lambda k: None)("orderID") or getattr(resp, "orderId", None):
        print("测试下单（实盘）完成。请到 Polymarket 查看订单。")
    else:
        print("下单可能未成功，请查看上方响应与 Polymarket 订单列表。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
