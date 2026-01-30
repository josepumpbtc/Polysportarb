# 目的：为套利与波动策略提供实时买卖价（best bid/ask）
# 方法：连接 CLOB WebSocket market channel，订阅 asset_ids，按 book/price_change 消息更新内存中的订单簿快照

import json
import threading
from typing import Any, Callable, Dict, List, Optional, Union

# CLOB WebSocket 市场通道地址，用于订阅订单簿与价格
WSS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def _parse_price(value: Any) -> Optional[float]:
    """目的：将 API 返回的价格转为 float，便于套利计算。方法：支持数字或字符串"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class OrderBookStore:
    """
    目的：维护每个 asset_id（token_id）的 best bid/ask，供套利与波动策略读取
    方法：线程安全 dict，key=asset_id，value={"bid": float, "ask": float}；由 WebSocket 消息更新
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # asset_id -> {"bid": best_bid, "ask": best_ask}
        self._books: Dict[str, Dict[str, Optional[float]]] = {}

    def update_from_message(self, msg: Dict[str, Any]) -> None:
        """
        目的：根据 CLOB WebSocket 的 book 或 price_change 消息更新订单簿快照
        方法：若消息含 asset_id 及 price/bid/ask 等字段，则更新对应 asset 的 best bid/ask
        """
        if not isinstance(msg, dict):
            return
        # 方法：常见字段为 asset_id 或 assetId，price_change 可能含 price、bid、ask
        asset_id = msg.get("asset_id") or msg.get("assetId")
        if not asset_id:
            return
        asset_id = str(asset_id)

        with self._lock:
            if asset_id not in self._books:
                self._books[asset_id] = {"bid": None, "ask": None}

            bid = _parse_price(msg.get("bid") or msg.get("best_bid"))
            ask = _parse_price(msg.get("ask") or msg.get("best_ask") or msg.get("price"))
            if bid is not None:
                self._books[asset_id]["bid"] = bid
            if ask is not None:
                self._books[asset_id]["ask"] = ask

            # 方法：book 消息可能含 bids/asks 数组，取第一档
            bids = msg.get("bids")
            asks = msg.get("asks")
            if isinstance(bids, list) and len(bids) > 0:
                first = bids[0]
                if isinstance(first, (list, tuple)) and len(first) >= 1:
                    self._books[asset_id]["bid"] = _parse_price(first[0])
                elif isinstance(first, dict):
                    self._books[asset_id]["bid"] = _parse_price(first.get("price"))
            if isinstance(asks, list) and len(asks) > 0:
                first = asks[0]
                if isinstance(first, (list, tuple)) and len(first) >= 1:
                    self._books[asset_id]["ask"] = _parse_price(first[0])
                elif isinstance(first, dict):
                    self._books[asset_id]["ask"] = _parse_price(first.get("price"))

    def get_best_bid(self, asset_id: str) -> Optional[float]:
        """目的：供套利/波动逻辑读取某 token 的最优买价。方法：从快照中取 bid"""
        with self._lock:
            return (self._books.get(str(asset_id)) or {}).get("bid")

    def get_best_ask(self, asset_id: str) -> Optional[float]:
        """目的：供套利逻辑读取某 token 的最优卖价（即我方买入价）。方法：从快照中取 ask"""
        with self._lock:
            return (self._books.get(str(asset_id)) or {}).get("ask")

    def get_all_asset_ids(self) -> List[str]:
        """目的：供主流程确认已订阅的 asset 列表。方法：返回当前有快照的 asset_id"""
        with self._lock:
            return list(self._books.keys())


def run_websocket_loop(
    store: OrderBookStore,
    asset_ids_or_getter: Union[List[str], Callable[[], List[str]]],
    url: str = WSS_MARKET_URL,
    reconnect_delay_sec: float = 5.0,
) -> None:
    """
    目的：在后台线程中连接 WebSocket 并持续接收消息，更新 store
    方法：连接 url，发送订阅消息 {"assets_ids": asset_ids, "type": "MARKET"}，循环 recv 并 store.update_from_message；断线后等待 reconnect_delay_sec 再重连；若第二参为可调用对象则每次重连时调用以获取最新 asset_ids，实现定期刷新监控列表
    注意：需在单独线程中调用，否则会阻塞；主程序可用 store 读 best bid/ask
    """
    try:
        import websocket
    except ImportError:
        return
    import time

    def _current_ids() -> List[str]:
        if callable(asset_ids_or_getter):
            return list(asset_ids_or_getter())
        return list(asset_ids_or_getter)

    while True:
        current_ids = _current_ids()
        if not current_ids:
            time.sleep(reconnect_delay_sec)
            continue
        try:
            ws = websocket.create_connection(url)
            sub = {"assets_ids": [str(a) for a in current_ids], "type": "MARKET"}
            ws.send(json.dumps(sub))
            while True:
                raw = ws.recv()
                if not raw:
                    break
                try:
                    msg = json.loads(raw)
                    if isinstance(msg, dict):
                        store.update_from_message(msg)
                    elif isinstance(msg, list):
                        for m in msg:
                            if isinstance(m, dict):
                                store.update_from_message(m)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        try:
            ws.close()
        except Exception:
            pass
        time.sleep(reconnect_delay_sec)
