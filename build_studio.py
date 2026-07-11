#!/usr/bin/env python3
"""解析 Studio 近28天曝光/CTR 表（studio_scrape_raw.txt），按節目歸屬聚合 → studio28.json
影片歸屬：用 Data API 播放清單標題比對"""
import json, os, urllib.request, urllib.parse

CONF = os.path.expanduser("~/.config/goodfinance-yt")
BASE = os.path.dirname(os.path.abspath(__file__))
PLAYLISTS = {
    "Good Morning 美好": "PL_WDNfI-qkZJ7dli_NEY99khoieK3Vz5R",
    "Good Invest 美好投資": "PL_WDNfI-qkZKcQD0_RmziC7mKTGDkH3Eo",
    "Better Living 美好生活": "PL_WDNfI-qkZKDJmfWTp6ohYDU7RXEB_Qo",
    "Good Income": "PL_WDNfI-qkZIbBvd2I-0L15CF2oejfJVM",
    "Entrepreneurship": "PL_WDNfI-qkZL4fTdXrty8EiyylCV25W9z",
    "老黃 Good Talk": "PL_WDNfI-qkZLg_y4iuD0_1bVZ4RpKs7gY",
    "投資新手村": "PL_WDNfI-qkZJG7yCM6WiIMc2DGBeUN6eL",
    "美好證券 x 志祺七七": "PL_WDNfI-qkZIoyfo52RSOfeWuBwBLmE2J",
    "Know Your Money 錢途診聊室": "PL_WDNfI-qkZKr24fwjWQykEBvH57d0dbJ",
    "A day in the Life 美好日常": "PL_WDNfI-qkZLVQL9HKGlh_2lZ7ypcD7_K",
}

def access_token():
    cid = os.environ.get("YT_CLIENT_ID")
    csec = os.environ.get("YT_CLIENT_SECRET")
    rtok = os.environ.get("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):          # 本機：讀 ~/.config
        conf = json.load(open(f"{CONF}/client_secret.json"))["installed"]
        tok = json.load(open(f"{CONF}/token.json"))
        cid, csec, rtok = conf["client_id"], conf["client_secret"], tok["refresh_token"]
    body = urllib.parse.urlencode({
        "client_id": cid, "client_secret": csec,
        "refresh_token": rtok, "grant_type": "refresh_token"}).encode()
    return json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=body).read())["access_token"]

H = {"Authorization": "Bearer " + access_token()}

def get(url, params):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        url + "?" + urllib.parse.urlencode(params), headers=H), timeout=60).read())

norm = lambda t: t.replace(" ", "").replace("​", "").replace("﻿", "").strip()

# 標題 -> (節目, videoId)
title_map = {}
for name, pid in PLAYLISTS.items():
    ids, page = [], None
    while True:
        p = {"part": "contentDetails", "playlistId": pid, "maxResults": 50}
        if page: p["pageToken"] = page
        r = get("https://www.googleapis.com/youtube/v3/playlistItems", p)
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        page = r.get("nextPageToken")
        if not page: break
    for i in range(0, len(ids), 50):
        r = get("https://www.googleapis.com/youtube/v3/videos",
                {"part": "snippet", "id": ",".join(ids[i:i+50]), "maxResults": 50})
        for it in r.get("items", []):
            title_map[norm(it["snippet"]["title"])] = (name, it["id"])

channel = None
rows = []
for line in open(os.path.join(BASE, "studio_scrape_raw.txt"), encoding="utf-8"):
    parts = line.strip().split("|")
    if len(parts) != 4: continue
    title, impr, ctr, views = parts
    impr = int(impr.replace(",", ""))
    ctr = float(ctr.rstrip("%"))
    views = int(views.replace(",", ""))
    if title == "總計":
        channel = {"impressions": impr, "ctr": ctr, "views28": views}
        continue
    show, vid = title_map.get(norm(title), (None, None))
    rows.append({"title": title, "impr": impr, "ctr": ctr, "views28": views, "show": show, "id": vid})

# 各節目 28 天：曝光加權 CTR
shows = {}
for r in rows:
    if not r["show"]: continue
    s = shows.setdefault(r["show"], {"impr": 0, "wctr": 0.0, "videos": 0})
    s["impr"] += r["impr"]
    s["wctr"] += r["impr"] * r["ctr"]
    s["videos"] += 1
for name, s in shows.items():
    s["ctr"] = round(s["wctr"] / s["impr"], 1) if s["impr"] else None
    del s["wctr"]
# 各節目 CTR 王（曝光 ≥1 萬才列入，避免小樣本噪音）
for r in rows:
    if not r["show"] or r["impr"] < 10000: continue
    cur = shows[r["show"]].get("topctr")
    if not cur or r["ctr"] > cur["ctr"]:
        shows[r["show"]]["topctr"] = {"id": r["id"], "title": r["title"][:70],
                                      "ctr": r["ctr"], "views": r["views28"]}

out = {
    "period": "2026/6/12–2026/7/9",
    "channel": channel,
    # 頻道層新舊觀眾（Studio 內容分頁，28 天、影片格式）
    "newViewers": 76000, "returningViewers": 26000,
    "shows": shows,
    "videos": {r["id"]: {"ctr": r["ctr"], "impr": r["impr"]} for r in rows if r["id"]},
}
json.dump(out, open(os.path.join(BASE, "studio28.json"), "w"), ensure_ascii=False, indent=1)
unmatched = [r["title"][:30] for r in rows if not r["show"]]
print("節目聚合:", {k: (v["impr"], v["ctr"]) for k, v in shows.items()})
print("未歸屬（Shorts/清單外）:", len(unmatched), "支")
print("✅ studio28.json written")
