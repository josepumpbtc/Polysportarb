# 目的：纸面/模拟模式入口，只打 log 不下单，用于验证主流程
# 方法：调用 src.main.main(paper=True)，与实盘相同逻辑但执行层不调用 CLOB

import os
import sys

# 将项目根加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 强制纸面模式，避免误实盘
os.environ.setdefault("PAPER_TRADING", "true")

from src.main import main

if __name__ == "__main__":
    main(paper=True, poll_interval_sec=2.0)
