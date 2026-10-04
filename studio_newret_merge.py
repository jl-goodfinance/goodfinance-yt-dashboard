#!/usr/bin/env python3
"""把 studio_newret_scrape.js 的結果（JSON：{id: {pct} | {na:1} | {fail:1}}）合併進 studio_newret.json。
只寫入有數字者；na/fail 不動既有值（超過 90 天 Studio 就不再提供，既有值絕不刪）。
用法：python3 studio_newret_merge.py <scrape結果.json>"""
import json, sys
from datetime import date

raw = json.load(open(sys.argv[1], encoding="utf-8"))
N = json.load(open("studio_newret.json", encoding="utf-8"))
N.setdefault("videos", {})
ok = na = bad = 0
for vid, r in raw.items():
    if r and isinstance(r.get("pct"), (int, float)) and not r.get("jl"):
        N["videos"][vid] = r["pct"]; ok += 1
    elif r and r.get("na"):
        na += 1
    else:
        bad += 1
N["updated"] = date.today().isoformat()
json.dump(N, open("studio_newret.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"merged {ok}, 資料不足 {na}, 失敗 {bad}, 共 {len(raw)}")
