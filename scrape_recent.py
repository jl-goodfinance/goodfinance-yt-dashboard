#!/usr/bin/env python3
"""抓美好證券各節目播放清單最新 10 支影片（YouTube 公開 innertube API）"""
import json, re, urllib.request

PLAYLISTS = {
    "Good Morning 美好": "PL_WDNfI-qkZJ7dli_NEY99khoieK3Vz5R",
    "Better Living 美好生活": "PL_WDNfI-qkZKDJmfWTp6ohYDU7RXEB_Qo",
    "Good Invest 美好投資": "PL_WDNfI-qkZKcQD0_RmziC7mKTGDkH3Eo",
    "投資新手村": "PL_WDNfI-qkZJG7yCM6WiIMc2DGBeUN6eL",
    "Know Your Money 錢途診聊室": "PL_WDNfI-qkZKr24fwjWQykEBvH57d0dbJ",
    "老黃 Good Talk": "PL_WDNfI-qkZLg_y4iuD0_1bVZ4RpKs7gY",
    "Good Income": "PL_WDNfI-qkZIbBvd2I-0L15CF2oejfJVM",
    "美好證券 x 志祺七七": "PL_WDNfI-qkZIoyfo52RSOfeWuBwBLmE2J",
    "A day in the Life 美好日常": "PL_WDNfI-qkZLVQL9HKGlh_2lZ7ypcD7_K",
    "Entrepreneurship": "PL_WDNfI-qkZL4fTdXrty8EiyylCV25W9z",
}
KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"

def innertube(payload):
    body = {"context": {"client": {"clientName": "WEB", "clientVersion": "2.20240701.00.00", "hl": "zh-TW", "gl": "TW"}}}
    body.update(payload)
    req = urllib.request.Request(
        f"https://www.youtube.com/youtubei/v1/browse?key={KEY}&prettyPrint=false",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def parse_views(txt):
    m = re.search(r"([\d,.]+)\s*萬", txt)
    if m: return int(float(m.group(1).replace(",", "")) * 10000)
    m = re.search(r"([\d,]+)", txt)
    return int(m.group(1).replace(",", "")) if m else 0

def meta_texts(o, out):
    if isinstance(o, dict):
        if "text" in o and isinstance(o["text"], dict) and "content" in o["text"]:
            out.append(o["text"]["content"])
        for v in o.values(): meta_texts(v, out)
    elif isinstance(o, list):
        for v in o: meta_texts(v, out)

def walk(o, out):
    if isinstance(o, dict):
        if "lockupViewModel" in o:
            lv = o["lockupViewModel"]
            try:
                title = lv["metadata"]["lockupMetadataViewModel"]["title"]["content"]
                texts = []
                meta_texts(lv["metadata"]["lockupMetadataViewModel"].get("metadata", {}), texts)
                views, rel = 0, ""
                for t in texts:
                    if "觀看" in t: views = parse_views(t)
                    m = re.search(r"[\d,]+\s*(?:年|個月|週|天|小時|分鐘)前", t)
                    if m: rel = m.group(0)
                out.append({"id": lv.get("contentId", ""), "title": title[:70], "views": views, "rel": rel})
            except Exception: pass
            return
        for v in o.values(): walk(v, out)
    elif isinstance(o, list):
        for v in o: walk(v, out)

recent = {}
for name, pid in PLAYLISTS.items():
    videos = []
    d = innertube({"browseId": "VL" + pid})
    walk(d, videos)
    recent[name] = videos[:10]
    print(f"{name}: {len(videos[:10])} 支", videos[0]["rel"] if videos else "")
json.dump(recent, open("recent10.json", "w"), ensure_ascii=False, indent=1)
