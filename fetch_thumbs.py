#!/usr/bin/env python3
"""抓五檔主節目近期 10 支影片縮圖（mqdefault 320x180）→ base64 內嵌 thumbs.json
（artifact CSP 擋外部圖片，必須內嵌）"""
import base64, json, os, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PAGE_SHOWS = ["Good Morning 美好", "Good Invest 美好投資", "Better Living 美好生活", "Good Income", "Entrepreneurship"]

D = json.load(open(os.path.join(BASE, "data.json")))
old = {}
p = os.path.join(BASE, "thumbs.json")
if os.path.exists(p):
    old = json.load(open(p))

out = {}
total = 0
for s in D["shows"]:
    if s["name"] not in PAGE_SHOWS: continue
    for v in s["recent"]:
        vid = v["id"]
        if vid in old:          # 快取：縮圖不會變
            out[vid] = old[vid]
            continue
        try:
            raw = urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg", timeout=30).read()
            out[vid] = "data:image/jpeg;base64," + base64.b64encode(raw).decode()
            total += len(raw)
        except Exception as e:
            print("skip", vid, e)
json.dump(out, open(p, "w"))
print(f"✅ thumbs.json: {len(out)} 張（新抓 {total//1024} KB）")
