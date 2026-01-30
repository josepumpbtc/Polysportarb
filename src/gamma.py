# 目的：为套利与 WebSocket 提供可交易的体育市场列表（condition_id、YES/NO token_id）
# 方法：请求 Gamma API events（可选 tag_id 过滤体育），解析 markets，过滤未结束且含二元 outcome 的市场

import time
from typing import Any, Dict, List, Optional

import requests

# Gamma API 基址，用于拉取 events 与 markets
GAMMA_BASE = "https://gamma-api.polymarket.com"


def fetch_markets(
    closed: bool = False,
    limit: int = 200,
    offset: int = 0,
    order: str = "volume24hrClob",
    ascending: bool = False,
    timeout: int = 15,
) -> List[Dict[str, Any]]:
    """
    目的：拉取 Gamma /markets 列表，支持按 volume24hrClob 排序（仅 24h 交易量）
    方法：GET /markets，用于 Top 100 按 24h 交易量筛选
    """
    params: Dict[str, Any] = {
        "closed": str(closed).lower(),
        "limit": limit,
        "offset": offset,
        "order": order,
        "ascending": str(ascending).lower(),
    }
    resp = requests.get(
        f"{GAMMA_BASE}/markets",
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def fetch_event_by_slug(slug: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
    """
    目的：按 event slug 拉取单个 event（如 polymarket.com/event/<slug>），供单市场套利测试
    方法：GET /events/slug/{slug}，返回单个 event 或 None
    """
    if not slug or not str(slug).strip():
        return None
    slug = str(slug).strip()
    resp = requests.get(
        f"{GAMMA_BASE}/events/slug/{slug}",
        timeout=timeout,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    return data if isinstance(data, dict) else None


def event_to_binary_markets(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    目的：将单个 event（含 markets）转为可交易二元市场列表，与 events_to_binary_markets 单条逻辑一致
    方法：遍历 event.markets，解析 YES/NO token_id，过滤已结束与非二元
    """
    out: List[Dict[str, Any]] = []
    markets = event.get("markets") or event.get("market") or []
    if not isinstance(markets, list):
        markets = [markets] if isinstance(markets, dict) else []
    for m in markets:
        if not isinstance(m, dict):
            continue
        tokens = _parse_market_tokens(m)
        if not tokens:
            continue
        if _is_market_ended(m, event):
            continue
        condition_id = m.get("conditionId") or m.get("condition_id") or ""
        if not condition_id:
            continue
        out.append({
            "condition_id": condition_id,
            "token_id_yes": tokens["yes"],
            "token_id_no": tokens["no"],
            "event_slug": event.get("slug") or event.get("id") or "",
            "question": m.get("question") or m.get("title") or "",
        })
    return out


def fetch_events(
    tag_id: Optional[int] = None,
    closed: bool = False,
    limit: int = 50,
    offset: int = 0,
    timeout: int = 15,
) -> List[Dict[str, Any]]:
    """
    目的：拉取 Gamma 的 events 列表，供后续解析出可交易的二元市场
    方法：GET /events，用 tag_id 过滤体育等分类，closed=false 只取未结束
    """
    params: Dict[str, Any] = {
        "closed": str(closed).lower(),
        "limit": limit,
        "offset": offset,
    }
    if tag_id is not None:
        params["tag_id"] = tag_id

    resp = requests.get(
        f"{GAMMA_BASE}/events",
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def _parse_market_tokens(market: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    目的：从单个 market 中解析出 YES/NO 对应的 CLOB token_id，供订单簿订阅与套利用
    方法：优先 clobTokenIds 数组（顺序通常为 [yes_token_id, no_token_id]），否则从 tokens 或 outcomes 中取
    """
    # 方法：Gamma 常见字段为 clobTokenIds，可能为 JSON 字符串或数组，二元市场为两元素
    clob_ids = market.get("clobTokenIds") or market.get("clob_token_ids")
    if isinstance(clob_ids, str):
        try:
            import json
            clob_ids = json.loads(clob_ids)
        except (ValueError, TypeError):
            clob_ids = None
    if isinstance(clob_ids, list) and len(clob_ids) >= 2:
        return {"yes": str(clob_ids[0]), "no": str(clob_ids[1])}

    # 备用：tokens 数组，每项含 token_id 与 outcome
    tokens = market.get("tokens") or market.get("outcomes")
    if not isinstance(tokens, list) or len(tokens) < 2:
        return None

    result: Dict[str, str] = {}
    for t in tokens:
        if not isinstance(t, dict):
            continue
        tid = t.get("token_id") or t.get("tokenId")
        outcome = (t.get("outcome") or t.get("side") or "").upper()
        if tid and outcome:
            if "YES" in outcome:
                result["yes"] = str(tid)
            elif "NO" in outcome:
                result["no"] = str(tid)
    if "yes" in result and "no" in result:
        return result
    return None


def _is_market_ended(market: Dict[str, Any], event: Dict[str, Any]) -> bool:
    """目的：判断市场是否已结束，避免对已结算市场下单。方法：endDate 或 end_date 已过则视为结束"""
    end = market.get("endDate") or market.get("end_date") or event.get("endDate") or event.get("end_date")
    if not end:
        return False
    try:
        ts = int(end) if isinstance(end, (int, float)) else int(float(end))
        return ts < time.time()
    except (ValueError, TypeError):
        return False


def events_to_binary_markets(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    目的：将 Gamma 的 events 转为「可交易二元市场」列表，每项含 condition_id、token_id_yes、token_id_no
    方法：遍历每个 event 的 markets，解析出 YES/NO token_id，过滤已结束或非二元市场
    """
    out: List[Dict[str, Any]] = []
    for ev in events:
        markets = ev.get("markets") or ev.get("market") or []
        if not isinstance(markets, list):
            markets = [markets] if isinstance(markets, dict) else []
        for m in markets:
            if not isinstance(m, dict):
                continue
            tokens = _parse_market_tokens(m)
            if not tokens:
                continue
            if _is_market_ended(m, ev):
                continue
            condition_id = m.get("conditionId") or m.get("condition_id") or ""
            if not condition_id:
                continue
            out.append({
                "condition_id": condition_id,
                "token_id_yes": tokens["yes"],
                "token_id_no": tokens["no"],
                "event_slug": ev.get("slug") or ev.get("id") or "",
                "question": m.get("question") or m.get("title") or "",
            })
    return out


def fetch_sports_binary_markets(
    tag_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    目的：一站式拉取体育（或指定 tag）下未结束的二元市场，供 main 与 orderbook 订阅
    方法：fetch_events(tag_id=..., closed=false) 后 events_to_binary_markets
    """
    events = fetch_events(tag_id=tag_id, closed=False, limit=limit, offset=offset)
    return events_to_binary_markets(events)


def fetch_top10_binary_markets_by_volume(
    events_limit: int = 200,
    min_prob: float = 0.01,
    max_prob: float = 0.99,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """
    目的：拉取二元市场后按「仅 24 小时」交易量排序，过滤概率在 (min_prob, max_prob) 内，返回 top N
    活跃市场定义：Top 100 Polymarket 24h 交易量（不看历史总交易量），且 0.01 < YES 概率 < 0.99
    方法：GET /markets 按 volume24hrClob 降序，只取 volume24hr/volume24hrClob 作为排序依据，过滤已结束与极端概率
    """
    import json
    # 仅用 24h 交易量：直接请求 /markets 按 volume24hrClob 降序
    markets_raw = fetch_markets(
        closed=False,
        limit=events_limit,
        offset=0,
        order="volume24hrClob",
        ascending=False,
    )
    cands: List[tuple] = []
    for m in markets_raw:
        if not isinstance(m, dict):
            continue
        if _is_market_ended(m, {}):
            continue
        tokens = _parse_market_tokens(m)
        if not tokens:
            continue
        cid = m.get("conditionId") or m.get("condition_id") or ""
        if not cid:
            continue
        # 只看 24h 交易量，不看历史 volume
        vol_raw = m.get("volume24hrClob") or m.get("volume24hr") or 0
        try:
            vol = float(vol_raw)
        except (TypeError, ValueError):
            vol = 0
        op = m.get("outcomePrices") or m.get("outcome_prices")
        if isinstance(op, str):
            try:
                op = json.loads(op)
            except (ValueError, TypeError):
                op = []
        if not isinstance(op, list) or len(op) < 2:
            continue
        try:
            yes_p = float(op[0])
        except (TypeError, ValueError):
            yes_p = 0.5
        if yes_p <= min_prob or yes_p >= max_prob:
            continue
        q = m.get("question") or m.get("title") or ""
        cands.append((vol, cid, tokens["yes"], tokens["no"], q))
    # 已按 API 的 volume24hrClob 顺序返回，再按 vol 降序取前 top_n（保证只用 24h）
    cands.sort(key=lambda x: -x[0])
    out: List[Dict[str, Any]] = []
    for _, cid, ty, tn, q in cands[:top_n]:
        out.append({
            "condition_id": cid,
            "token_id_yes": ty,
            "token_id_no": tn,
            "question": q,
            "event_slug": "",
        })
    return out
