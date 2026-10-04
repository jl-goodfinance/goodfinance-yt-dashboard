#!/usr/bin/env python3
"""列出需要從 Studio 補抓新觀眾比的影片 id（空白分隔），給 studio_newret_scrape.js 用。
範圍：五檔主節目、上片 5–90 天（Studio 只提供這個窗口）、非排定中、studio_newret.json 尚無數值者。
用法：python3 studio_newret_targets.py [--all]（--all＝窗口內全部重抓，含已有值者）"""
import json, sys
from datetime import date, timedelta

today = date.today()
lo, hi = (today - timedelta(days=90)).isoformat(), (today - timedelta(days=5)).isoformat()
D = json.load(open("data.json", encoding="utf-8"))
N = json.load(open("studio_newret.json", encoding="utf-8")).get("videos", {})
redo = "--all" in sys.argv
ids = [e["id"] for s in D["shows"][:5] for e in s.get("eps26", [])
       if lo <= e["pub"] <= hi and not e.get("sch") and (redo or N.get(e["id"]) is None)]
print(" ".join(ids))
