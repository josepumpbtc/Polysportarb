# 目的：验证 Gamma 市场发现逻辑，不依赖真实 API 即可通过
# 方法：mock requests.get 返回固定 JSON，断言解析后 token_id、condition_id 正确，已结束市场被过滤

import time
from unittest.mock import patch, MagicMock
import pytest
from src.gamma import (
    fetch_events,
    events_to_binary_markets,
    fetch_sports_binary_markets,
    _parse_market_tokens,
    _is_market_ended,
)


def test_parse_market_tokens_clob_token_ids():
    """
    目的：验证从 clobTokenIds 数组解析出 yes/no token_id
    预期：两元素数组对应 yes、no
    """
    market = {"clobTokenIds": ["tid_yes_123", "tid_no_456"]}
    got = _parse_market_tokens(market)
    assert got is not None
    assert got["yes"] == "tid_yes_123"
    assert got["no"] == "tid_no_456"


def test_parse_market_tokens_tokens_array():
    """
    目的：验证从 tokens 数组（含 outcome）解析出 yes/no
    预期：outcome 为 Yes/No 的项对应 token_id
    """
    market = {
        "tokens": [
            {"token_id": "t1", "outcome": "Yes"},
            {"token_id": "t2", "outcome": "No"},
        ]
    }
    got = _parse_market_tokens(market)
    assert got is not None
    assert got["yes"] == "t1"
    assert got["no"] == "t2"


def test_parse_market_tokens_invalid_returns_none():
    """
    目的：非二元或缺少 token 时返回 None，避免错误市场进入套利逻辑
    预期：无 clobTokenIds 且 tokens 不足两项时为 None
    """
    assert _parse_market_tokens({}) is None
    assert _parse_market_tokens({"clobTokenIds": []}) is None
    assert _parse_market_tokens({"clobTokenIds": ["only_one"]}) is None


def test_is_market_ended_future():
    """目的：未到 endDate 的市场未结束。预期：返回 False"""
    m = {"endDate": str(int(time.time()) + 86400)}
    assert _is_market_ended(m, {}) is False


def test_is_market_ended_past():
    """目的：已过 endDate 的市场视为结束。预期：返回 True"""
    m = {"endDate": str(int(time.time()) - 86400)}
    assert _is_market_ended(m, {}) is True


@patch("src.gamma.requests.get")
def test_fetch_events_returns_list(mock_get):
    """
    目的：验证 fetch_events 在 API 返回列表时原样返回
    预期：返回与 mock 一致的 events 列表
    """
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = [{"id": "e1"}]
    mock_get.return_value = resp
    events = fetch_events()
    assert len(events) == 1
    assert events[0]["id"] == "e1"


def test_events_to_binary_markets_extracts_token_ids():
    """
    目的：从 events 中解析出二元市场列表，含 condition_id、token_id_yes、token_id_no
    预期：一条 event 一条 market 时，结果有一条且字段正确
    """
    events = [
        {
            "slug": "test-event",
            "markets": [
                {
                    "conditionId": "cond_abc",
                    "clobTokenIds": ["token_yes", "token_no"],
                    "question": "Test?",
                    "endDate": str(int(time.time()) + 86400),
                }
            ],
        }
    ]
    out = events_to_binary_markets(events)
    assert len(out) == 1
    assert out[0]["condition_id"] == "cond_abc"
    assert out[0]["token_id_yes"] == "token_yes"
    assert out[0]["token_id_no"] == "token_no"
    assert out[0]["event_slug"] == "test-event"


def test_events_to_binary_markets_filters_ended():
    """
    目的：已结束市场不进入列表，避免对已结算市场下单
    预期：endDate 已过的 market 不出现在结果中
    """
    events = [
        {
            "markets": [
                {
                    "conditionId": "ended",
                    "clobTokenIds": ["y", "n"],
                    "endDate": str(int(time.time()) - 1),
                }
            ],
        }
    ]
    out = events_to_binary_markets(events)
    assert len(out) == 0


@patch("src.gamma.fetch_events")
def test_fetch_sports_binary_markets_calls_fetch_events(mock_fetch):
    """
    目的：fetch_sports_binary_markets 应调用 fetch_events 并解析结果
    预期：mock 返回一条 event 一条 market，最终得到一条二元市场
    """
    mock_fetch.return_value = [
        {
            "markets": [
                {
                    "conditionId": "c1",
                    "clobTokenIds": ["ty", "tn"],
                    "endDate": str(int(time.time()) + 86400),
                }
            ],
        }
    ]
    out = fetch_sports_binary_markets(tag_id=100381, limit=10)
    assert len(out) == 1
    assert out[0]["token_id_yes"] == "ty"
    mock_fetch.assert_called_once()
    call_kw = mock_fetch.call_args[1]
    assert call_kw.get("tag_id") == 100381
    assert call_kw.get("closed") is False
