#!/usr/bin/env python3
# 目的：校验 Polymarket 地址认证（PRIVATE_KEY + FUNDER_ADDRESS），并确认 CLOB 客户端可用
# 方法：加载 .env，调用 get_clob_client()，成功则打印 funder 与「已连接」

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载 .env（若存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    print("1. 检查环境变量...")
    pk = os.getenv("PRIVATE_KEY")
    funder = os.getenv("FUNDER_ADDRESS")
    if not pk or not pk.strip():
        print("   缺少 PRIVATE_KEY（在 .env 或环境变量中设置）")
        return 1
    if not funder or not funder.strip():
        print("   缺少 FUNDER_ADDRESS（Polymarket 代理钱包地址，见 polymarket.com/settings）")
        return 1
    print("   PRIVATE_KEY: 已设置（长度 %d）" % len(pk))
    print("   FUNDER_ADDRESS: %s" % (funder[:10] + "..." + funder[-6:] if len(funder) > 20 else funder))

    print("2. 连接 Polymarket 地址（创建 CLOB 客户端）...")
    from src.auth import get_clob_client
    client = get_clob_client()
    if client is None:
        print("   认证失败，请检查 PRIVATE_KEY 与 FUNDER_ADDRESS 是否正确")
        return 1
    print("   已连接，funder=%s" % (funder[:10] + "..." + funder[-6:] if len(funder) > 20 else funder))
    print("Polymarket 地址连接校验完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
