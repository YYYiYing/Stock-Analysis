#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
manage_reports.py — 調整清單：互動刪除報告/raw_data/summaries

當使用者說「調整清單」時執行此檔，開 checkbox 讓使用者勾選要刪除的標的，
選中後自動清除對應的 reports/{sid}_*_analysis.html、reports/raw_data/{sid}_raw_data.json、reports/summaries/{sid}_summary.md
並重建 reports/index.html

設計：呼叫 update_reports.py 的 _do_manage_delete 共用邏輯，避免重複
Usage:
  python scripts/manage_reports.py          # 互動刪除
  python scripts/update_reports.py --manage # 同上（別名）
"""
import sys
from pathlib import Path
SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))
from update_reports import inventory, _do_manage_delete

if __name__ == "__main__":
    inv = inventory()
    if not inv:
        print("無任何報告可管理")
        sys.exit(0)
    _do_manage_delete(inv)
