#!/usr/bin/env python3
# 目的：从 Gamma 拉取二元市场，按交易量排序，过滤掉概率 >99% 或 <1%，输出 top 10 的 condition_id
# 方法：供日后刷新 monitor_condition_ids 时使用；可将输出粘贴到 config 或 DEFAULTS

import json
import sys

sys.path.insert(0, __file__.rsplit("/", 2)[0])

from src.gamma import fetch_events


def main():
    e = fetch_events(limit=150)
    cands = []
    for ev in e:
        for m in ev.get("markets") or []:
            if not isinstance(m, dict):
                continue
            cid = m.get("conditionId") or m.get("condition_id")
            if not cid:
                continue
            vol_raw = m.get("volume") or m.get("volumeNum") or m.get("volumeClob") or 0
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
            if yes_p <= 0.01 or yes_p >= 0.99:
                continue
            q = (m.get("question") or "")[:60]
            cands.append((vol, cid, yes_p, q))
    cands.sort(key=lambda x: -x[0])
    top = cands[:10]
    print("# Top 10 by volume, 0.01 < prob < 0.99")
    for vol, cid, yp, q in top:
        print('  - "%s"  # %.0f vol, YES=%.2f | %s' % (cid, vol, yp, q))
    return 0


if __name__ == "__main__":
    sys.exit(main())
