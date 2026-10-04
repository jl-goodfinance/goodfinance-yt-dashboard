#!/usr/bin/env python3
"""列出需要從 Studio 逐支抓 CTR 的影片 id（空白分隔），給 studio_ctr_scrape.js 用。
範圍：五檔主節目、上片 2–28 天（之內「自發布至今」≈ 近 28 天口徑）、非排定中影片。
用法：python3 studio_ctr_targets.py [最大天數，預設 28]"""
import json, sys
from datetime import date, timedelta

MAX_D = int(sys.argv[1]) if len(sys.argv) > 1 else 28
today = date.today()
lo, hi = (today - timedelta(days=MAX_D)).isoformat(), (today - timedelta(days=2)).isoformat()
D = json.load(open("data.json", encoding="utf-8"))
ids = [e["id"] for s in D["shows"][:5] for e in s.get("eps26", [])
       if lo <= e["pub"] <= hi and not e.get("sch")]
print(" ".join(ids))
