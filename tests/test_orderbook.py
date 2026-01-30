# 目的：验证订单簿解析与更新逻辑，不依赖真实 WebSocket 即可通过
# 方法：构造模拟的 book/price_change 消息，调用 update_from_message，断言 get_best_bid/get_best_ask 正确

import pytest
from src.orderbook import OrderBookStore, _parse_price


def test_parse_price():
    """
    目的：验证价格解析支持数字与字符串，无效值返回 None
    预期：0.5、"0.5" 得 0.5，None、"x" 得 None
    """
    assert _parse_price(0.5) == 0.5
    assert _parse_price("0.52") == 0.52
    assert _parse_price(None) is None
    assert _parse_price("x") is None


def test_update_from_message_sets_bid_ask():
    """
    目的：验证含 asset_id、bid、ask 的消息能更新 store 的 best bid/ask
    预期：更新后 get_best_bid/get_best_ask 返回消息中的值
    """
    store = OrderBookStore()
    store.update_from_message({
        "asset_id": "token_123",
        "bid": 0.48,
        "ask": 0.52,
    })
    assert store.get_best_bid("token_123") == 0.48
    assert store.get_best_ask("token_123") == 0.52


def test_update_from_message_asset_id_alias():
    """
    目的：验证 assetId 与 asset_id 均被识别，便于兼容不同 API 写法
    预期：assetId 也能更新对应 asset 的快照
    """
    store = OrderBookStore()
    store.update_from_message({
        "assetId": "token_456",
        "best_bid": 0.45,
        "best_ask": 0.55,
    })
    assert store.get_best_bid("token_456") == 0.45
    assert store.get_best_ask("token_456") == 0.55


def test_update_from_message_bids_asks_arrays():
    """
    目的：验证 book 消息中 bids/asks 数组第一档被解析为 best bid/ask
    预期：bids[0][0] 为 bid，asks[0][0] 为 ask
    """
    store = OrderBookStore()
    store.update_from_message({
        "asset_id": "t1",
        "bids": [[0.47, 100]],
        "asks": [[0.53, 200]],
    })
    assert store.get_best_bid("t1") == 0.47
    assert store.get_best_ask("t1") == 0.53


def test_get_best_bid_ask_unknown_asset_returns_none():
    """
    目的：未订阅或尚未收到消息的 asset 返回 None，避免套利逻辑误用
    预期：get_best_bid("unknown") 与 get_best_ask("unknown") 为 None
    """
    store = OrderBookStore()
    assert store.get_best_bid("unknown") is None
    assert store.get_best_ask("unknown") is None


def test_get_all_asset_ids():
    """
    目的：确认已更新过的 asset 列表，供主流程或调试使用
    预期：更新两个 asset 后，get_all_asset_ids 含两个 id
    """
    store = OrderBookStore()
    store.update_from_message({"asset_id": "a1", "bid": 0.1, "ask": 0.9})
    store.update_from_message({"asset_id": "a2", "bid": 0.2, "ask": 0.8})
    ids = store.get_all_asset_ids()
    assert set(ids) == {"a1", "a2"}


def test_update_from_message_overwrites_previous():
    """
    目的：后续消息覆盖同一 asset 的 bid/ask，保证为最新快照
    预期：第二次更新后 get 得到第二次的值
    """
    store = OrderBookStore()
    store.update_from_message({"asset_id": "t", "bid": 0.4, "ask": 0.6})
    store.update_from_message({"asset_id": "t", "bid": 0.42, "ask": 0.58})
    assert store.get_best_bid("t") == 0.42
    assert store.get_best_ask("t") == 0.58
