#!/usr/bin/env python3
"""把 studio_ctr_scrape.js 抓到的逐支 CTR（JSON：{id: {impr: "3.2萬", ctr: "7.8"}}）合併進 studio28.json 的 videos。
用法：python3 studio_ctr_merge.py <scrape結果.json>"""
import json, sys
from datetime import date

def num(s):
    s = str(s).replace(",", "")
    return int(round(float(s[:-1]) * 10000)) if s.endswith("萬") else int(float(s))

raw = json.load(open(sys.argv[1], encoding="utf-8"))
S = json.load(open("studio28.json", encoding="utf-8"))
ok = 0
for vid, r in raw.items():
    if not r or "ctr" not in r:
        continue
    S["videos"][vid] = {"ctr": float(r["ctr"]), "impr": num(r["impr"]),
                        "src": "since_publish", "date": date.today().isoformat()}
    ok += 1
json.dump(S, open("studio28.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"merged {ok}/{len(raw)}")
