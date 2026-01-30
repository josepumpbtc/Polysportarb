# 目的：安全获取 Polymarket CLOB 客户端，供下单与查询使用
# 方法：从环境变量加载私钥与 funder，L1 创建/派生 API key 后设置 L2，不将密钥写入代码

import os
from typing import Optional, Any

# 仅在存在私钥时导入 CLOB 客户端，避免无依赖时报错
def _get_clob_client_class():
    from py_clob_client.client import ClobClient
    return ClobClient


def load_env_required(key: str, env_key: str) -> Optional[str]:
    """
    目的：从环境变量读取必填项，缺失时返回 None 便于上层报错
    方法：os.getenv，不写默认值以保证敏感信息不泄露
    """
    return os.getenv(env_key)


def get_clob_client(
    host: str = "https://clob.polymarket.com",
    chain_id: int = 137,
    signature_type: int = 2,
) -> Optional[Any]:
    """
    目的：构造已认证的 ClobClient，供 execution 层下单与撤单
    方法：从环境变量读 PRIVATE_KEY、FUNDER_ADDRESS；若有 API_KEY/SECRET/PASSPHRASE 则用 L2，否则 L1 创建/派生 API creds 再设 L2
    """
    private_key = load_env_required("PRIVATE_KEY", "PRIVATE_KEY")
    funder = load_env_required("Funder address", "FUNDER_ADDRESS")

    if not private_key or not funder:
        return None

    ClobClient = _get_clob_client_class()
    # 方法：Gnosis Safe 代理钱包最常见，signature_type=2；Email 登录用 1
    client = ClobClient(
        host=host,
        chain_id=chain_id,
        key=private_key,
        signature_type=signature_type,
        funder=funder,
    )

    # L2 认证：优先用环境变量中的 API 凭证，否则 L1 创建/派生
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    api_passphrase = os.getenv("API_PASSPHRASE")

    if api_key and api_secret and api_passphrase:
        client.set_api_creds({
            "apiKey": api_key,
            "secret": api_secret,
            "passphrase": api_passphrase,
        })
    else:
        api_creds = client.create_or_derive_api_creds()
        client.set_api_creds(api_creds)

    return client
