#!/usr/bin/env python3
# 目的：调试 Live Sports 市场获取，找出为什么拉取不到 live 市场
# 方法：测试不同的 API 参数组合，查看实际返回的数据

import json
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 2)[0])

import requests

GAMMA_BASE = "https://gamma-api.polymarket.com"


def test_api_call(url, params, description):
    """测试 API 调用并打印结果"""
    print(f"\n{'='*60}")
    print(f"测试: {description}")
    print(f"URL: {url}")
    print(f"参数: {params}")
    print(f"{'='*60}")
    try:
        resp = requests.get(url, params=params, timeout=15)
        print(f"状态码: {resp.status_code}")
        if resp.status_code != 200:
            print(f"错误: {resp.text[:200]}")
            return []
        data = resp.json()
        if isinstance(data, list):
            print(f"返回 {len(data)} 个 events")
            if len(data) > 0:
                print(f"\n前3个 events 的详细信息:")
                for i, ev in enumerate(data[:3], 1):
                    print(f"\nEvent {i}:")
                    print(f"  - id: {ev.get('id')}")
                    print(f"  - slug: {ev.get('slug')}")
                    print(f"  - title: {ev.get('title', '')[:60]}")
                    print(f"  - live: {ev.get('live')}")
                    print(f"  - category: {ev.get('category')}")
                    print(f"  - startDate: {ev.get('startDate')}")
                    print(f"  - endDate: {ev.get('endDate')}")
                    print(f"  - gameStatus: {ev.get('gameStatus')}")
                    print(f"  - score: {ev.get('score')}")
                    print(f"  - elapsed: {ev.get('elapsed')}")
                    # 检查 markets
                    markets = ev.get("markets", [])
                    if markets:
                        print(f"  - markets 数量: {len(markets)}")
                        if len(markets) > 0:
                            m = markets[0] if isinstance(markets, list) else markets
                            if isinstance(m, dict):
                                print(f"  - 第一个 market:")
                                print(f"    - question: {m.get('question', '')[:50]}")
                                print(f"    - live: {m.get('live')}")
                                print(f"    - gameStatus: {m.get('gameStatus')}")
                                print(f"    - startDate: {m.get('startDate')}")
                                print(f"    - endDate: {m.get('endDate')}")
            return data
        else:
            print(f"返回类型不是 list: {type(data)}")
            return []
    except Exception as e:
        print(f"异常: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    print("开始调试 Live Sports 市场获取...")
    
    # 测试 1: 使用 tag_slug="sports"，检查所有字段
    events1 = test_api_call(
        f"{GAMMA_BASE}/events",
        {"closed": "false", "limit": 50, "tag_slug": "sports"},
        "使用 tag_slug='sports' 获取体育事件（详细检查）"
    )
    
    # 检查是否有 gameStatus、score、elapsed 等字段表示 live
    if events1:
        print(f"\n{'='*60}")
        print("分析：查找可能表示 live 的字段")
        print(f"{'='*60}")
        live_candidates = []
        for ev in events1:
            # 检查各种可能表示 live 的字段
            has_game_status = ev.get("gameStatus") is not None and ev.get("gameStatus") != ""
            has_score = ev.get("score") is not None and ev.get("score") != ""
            has_elapsed = ev.get("elapsed") is not None and ev.get("elapsed") != ""
            has_live_field = ev.get("live") is True
            
            # 检查 markets 的 live 字段
            markets = ev.get("markets", [])
            market_live = False
            if markets:
                for m in markets if isinstance(markets, list) else [markets]:
                    if isinstance(m, dict) and m.get("live") is True:
                        market_live = True
                        break
            
            if has_game_status or has_score or has_elapsed or has_live_field or market_live:
                live_candidates.append({
                    "id": ev.get("id"),
                    "title": ev.get("title", "")[:60],
                    "gameStatus": ev.get("gameStatus"),
                    "score": ev.get("score"),
                    "elapsed": ev.get("elapsed"),
                    "live": ev.get("live"),
                    "market_live": market_live,
                })
        
        print(f"找到 {len(live_candidates)} 个可能的 live events:")
        for i, cand in enumerate(live_candidates[:10], 1):
            print(f"  {i}. {cand['title']}")
            print(f"     gameStatus={cand['gameStatus']}, score={cand['score']}, elapsed={cand['elapsed']}, live={cand['live']}, market_live={cand['market_live']}")
    
    print(f"\n{'='*60}")
    print("调试完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
