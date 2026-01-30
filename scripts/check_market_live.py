#!/usr/bin/env python3
# 目的：检查特定市场是否是 live 状态
# 用法：python3 scripts/check_market_live.py <event_slug>
# 例如：python3 scripts/check_market_live.py dota2-mouz-strong-2026-01-30

import json
import sys
from datetime import datetime

sys.path.insert(0, __file__.rsplit("/", 2)[0])

from src.gamma import fetch_event_by_slug


def format_timestamp(ts):
    """格式化时间戳为可读时间"""
    if ts is None:
        return None
    try:
        ts_int = int(float(ts))
        return datetime.fromtimestamp(ts_int).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return str(ts)


def check_market_live(event_slug: str):
    """检查特定市场是否是 live 状态"""
    print(f"\n{'='*80}")
    print(f"检查市场: {event_slug}")
    print(f"{'='*80}\n")
    
    # 获取 event
    event = fetch_event_by_slug(event_slug)
    if not event:
        print(f"❌ 未找到 event: {event_slug}")
        print("提示：请检查 slug 是否正确")
        return
    
    # 打印 event 基本信息
    print("📋 Event 基本信息:")
    print(f"  - ID: {event.get('id')}")
    print(f"  - Slug: {event.get('slug')}")
    print(f"  - Title: {event.get('title', '')[:80]}")
    print(f"  - Category: {event.get('category')}")
    print(f"  - Tags: {event.get('tags', [])}")
    
    # 检查 event 级别的 live 相关字段
    print(f"\n🔍 Event 级别的 Live 状态检查:")
    event_live = event.get("live")
    print(f"  - live: {event_live} (类型: {type(event_live).__name__})")
    
    # 检查时间相关字段
    start_date = event.get("startDate") or event.get("start_date")
    end_date = event.get("endDate") or event.get("end_date")
    print(f"  - startDate: {start_date} -> {format_timestamp(start_date)}")
    print(f"  - endDate: {end_date} -> {format_timestamp(end_date)}")
    
    # 检查游戏状态相关字段
    game_status = event.get("gameStatus")
    score = event.get("score")
    elapsed = event.get("elapsed")
    print(f"  - gameStatus: {game_status}")
    print(f"  - score: {score}")
    print(f"  - elapsed: {elapsed}")
    
    # 检查 markets
    markets = event.get("markets") or event.get("market") or []
    if not isinstance(markets, list):
        markets = [markets] if isinstance(markets, dict) else []
    
    print(f"\n📊 Markets 数量: {len(markets)}")
    
    if not markets:
        print("  ⚠️  没有找到 markets")
        return
    
    # 检查每个 market 的 live 状态
    for i, m in enumerate(markets, 1):
        if not isinstance(m, dict):
            continue
        
        print(f"\n{'─'*80}")
        print(f"Market {i}:")
        print(f"  - Question: {m.get('question', m.get('title', ''))[:80]}")
        print(f"  - Condition ID: {m.get('conditionId') or m.get('condition_id')}")
        
        # Market 级别的 live 字段
        market_live = m.get("live")
        print(f"  - live: {market_live} (类型: {type(market_live).__name__})")
        
        # Market 的时间字段
        m_start = m.get("startDate") or m.get("start_date")
        m_end = m.get("endDate") or m.get("end_date")
        print(f"  - startDate: {m_start} -> {format_timestamp(m_start)}")
        print(f"  - endDate: {m_end} -> {format_timestamp(m_end)}")
        
        # Market 的游戏状态
        m_game_status = m.get("gameStatus")
        m_score = m.get("score")
        m_elapsed = m.get("elapsed")
        print(f"  - gameStatus: {m_game_status}")
        print(f"  - score: {m_score}")
        print(f"  - elapsed: {m_elapsed}")
        
        # 综合判断
        is_live_by_field = market_live is True or event_live is True
        has_game_status = m_game_status is not None and m_game_status != "" or game_status is not None and game_status != ""
        has_score = m_score is not None and m_score != "" or score is not None and score != ""
        has_elapsed = m_elapsed is not None and m_elapsed != "" or elapsed is not None and elapsed != ""
        
        print(f"\n  ✅ Live 状态判断:")
        print(f"     - 通过 live 字段: {is_live_by_field}")
        print(f"     - 有 gameStatus: {has_game_status}")
        print(f"     - 有 score: {has_score}")
        print(f"     - 有 elapsed: {has_elapsed}")
        
        # 综合结论
        is_likely_live = is_live_by_field or has_game_status or has_score or has_elapsed
        print(f"     - 🎯 综合判断: {'✅ 可能是 LIVE' if is_likely_live else '❌ 不是 LIVE'}")
    
    # 打印完整的 event JSON（用于调试）
    print(f"\n{'='*80}")
    print("📄 完整 Event JSON (前1000字符):")
    print(f"{'='*80}")
    event_json_str = json.dumps(event, indent=2, ensure_ascii=False)
    print(event_json_str[:1000])
    if len(event_json_str) > 1000:
        print(f"\n... (总共 {len(event_json_str)} 字符，已截断)")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/check_market_live.py <event_slug>")
        print("例如: python3 scripts/check_market_live.py dota2-mouz-strong-2026-01-30")
        sys.exit(1)
    
    event_slug = sys.argv[1]
    check_market_live(event_slug)


if __name__ == "__main__":
    main()
