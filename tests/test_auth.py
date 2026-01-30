# 目的：验证认证与配置逻辑，不依赖真实密钥即可通过
# 方法：mock os.environ，断言缺 PRIVATE_KEY 时返回 None、有合法 env 时能构造 client（可 mock ClobClient）

import os
import pytest
from unittest.mock import patch, MagicMock


def test_load_env_required_missing_returns_none():
    """
    目的：验证缺少 PRIVATE_KEY 时 get_clob_client 返回 None，便于上层安全处理
    预期：在清空 PRIVATE_KEY 的环境下，get_clob_client() 为 None
    """
    with patch.dict(os.environ, {}, clear=True):
        from src.auth import get_clob_client
        assert get_clob_client() is None


def test_load_env_required_missing_funder_returns_none():
    """
    目的：验证仅有 PRIVATE_KEY 但无 FUNDER_ADDRESS 时也返回 None
    预期：只设 PRIVATE_KEY、不设 FUNDER_ADDRESS，get_clob_client() 为 None
    """
    env = {"PRIVATE_KEY": "0xdeadbeef"}
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("FUNDER_ADDRESS", None)
        from src.auth import get_clob_client
        assert get_clob_client() is None


@patch("src.auth._get_clob_client_class")
def test_get_clob_client_with_valid_env_returns_client(mock_get_clob):
    """
    目的：验证在提供 PRIVATE_KEY 和 FUNDER_ADDRESS 且 mock ClobClient 时能返回客户端实例
    预期：返回非 None，且为 mock 的 ClobClient 实例
    """
    mock_clob = MagicMock()
    mock_get_clob.return_value = MagicMock(return_value=mock_clob)

    with patch.dict(os.environ, {"PRIVATE_KEY": "0x123", "FUNDER_ADDRESS": "0xabc"}, clear=False):
        from src.auth import get_clob_client
        client = get_clob_client()
        assert client is not None
        assert client == mock_clob
