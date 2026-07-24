#!/usr/bin/env python3
"""美好證券 YouTube 節目數據抓取（stdlib-only）
資料源：YouTube Analytics API（頻道/逐支影片真實數據）＋ YouTube Data API v3（播放清單、上片日期）
憑證：~/.config/goodfinance-yt/{client_secret.json, token.json}（頻道擁有者 social@ 授權）
輸出：data.json
"""
import json, os, sys, urllib.request, urllib.parse
from datetime import date, datetime, timedelta

CONF = os.path.expanduser("~/.config/goodfinance-yt")
TODAY = date.today()                       # 自動取執行當日
END_D = TODAY - timedelta(days=1)          # Analytics 有延遲，取到前一天
END = END_D.isoformat()
Y26_START = "2026-01-01"
LIFE_START = "2022-04-17"   # 開台日

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

AT = access_token()
H = {"Authorization": "Bearer " + AT}

def get(url, params, retries=3):
    import time
    u = url + "?" + urllib.parse.urlencode(params)
    for i in range(retries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60).read())
        except Exception as e:
            if i == retries - 1: raise
            time.sleep(3 * (i + 1))

def analytics(**params):
    base = {"ids": "channel==MINE", "endDate": END}
    base.update(params)
    return get("https://youtubeanalytics.googleapis.com/v2/reports", base)

def data_api(resource, **params):
    return get(f"https://www.googleapis.com/youtube/v3/{resource}", params)

def workdays(a, b):
    d, n = a, 0
    while d <= b:
        if d.weekday() < 5: n += 1
        d += timedelta(days=1)
    return n

# ── 1. 頻道層 ───────────────────────────────────────────
ch = data_api("channels", part="snippet,statistics", mine="true")["items"][0]
st = ch["statistics"]
ch26 = analytics(startDate=Y26_START,
    metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained")["rows"][0]
chLife = analytics(startDate=LIFE_START,
    metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained")["rows"][0]
channel = {
    "subs": int(st["subscriberCount"]), "totalViews": int(st["viewCount"]),
    "totalVideos": int(st["videoCount"]),
    "views26": ch26[0], "watchMin26": ch26[1], "avgDur26": ch26[2], "avgPct26": ch26[3], "subsGained26": ch26[4],
    "avgDurLife": chLife[2], "avgPctLife": chLife[3], "subsGainedLife": chLife[4],
}
print("頻道:", channel)

# ── 1b. 2026 逐日訂閱增減 → 每週彙整（週一為週首）────────────
day_rows = analytics(startDate=Y26_START, metrics="subscribersGained,subscribersLost",
                     dimensions="day", sort="day").get("rows", [])
weeks = {}   # 週一 ISO 日期 -> {gained, lost}
for d, g, l in day_rows:
    dd = date.fromisoformat(d)
    monday = dd - timedelta(days=dd.weekday())
    w = weeks.setdefault(monday.isoformat(), {"gained": 0, "lost": 0})
    w["gained"] += int(g); w["lost"] += int(l)
weekly = [{"w": k, "gained": v["gained"], "lost": v["lost"], "net": v["gained"] - v["lost"]}
          for k, v in sorted(weeks.items())]
print(f"每週訂閱：{len(weekly)} 週，最近一週淨增 {weekly[-1]['net'] if weekly else 0:+d}")

# ── 2. 觀眾輪廓（2026）──────────────────────────────────
demo_rows = analytics(startDate=Y26_START, metrics="viewerPercentage", dimensions="ageGroup,gender").get("rows", [])
gender = {"male": 0.0, "female": 0.0, "user_specified": 0.0}
age = {}
for grp, g, pct in demo_rows:
    gender[g] = gender.get(g, 0) + pct
    age[grp] = age.get(grp, 0) + pct
age40 = age.get("age35-44", 0) / 2 + sum(age.get(k, 0) for k in ("age45-54", "age55-64", "age65-"))
traffic_rows = analytics(startDate=Y26_START, metrics="views", dimensions="insightTrafficSourceType", sort="-views").get("rows", [])
tv = sum(r[1] for r in traffic_rows) or 1
TRAFFIC_ZH = {"RELATED_VIDEO": "推薦影片", "YT_SEARCH": "搜尋", "SUBSCRIBER": "訂閱內容/首頁", "BROWSE": "首頁瀏覽",
              "EXT_URL": "外部連結", "NO_LINK_OTHER": "直接/未知", "PLAYLIST": "播放清單", "NOTIFICATION": "通知",
              "YT_CHANNEL": "頻道頁", "YT_OTHER_PAGE": "其他 YT 頁", "SHORTS": "Shorts 動態", "ADVERTISING": "廣告",
              "END_SCREEN": "結束畫面", "YT_PLAYLIST_PAGE": "清單頁", "HASHTAGS": "主題標籤", "SOUND_PAGE": "音訊頁",
              "LIVE_REDIRECT": "直播導流", "VIDEO_REMIXES": "Remix", "CAMPAIGN_CARD": "宣傳卡", "ANNOTATION": "註解"}
traffic = [{"type": TRAFFIC_ZH.get(r[0], r[0]), "pct": round(r[1] / tv * 100, 1)} for r in traffic_rows[:5]]
print("性別:", {k: round(v,1) for k,v in gender.items()}, "| 40+:", round(age40,1), "| 流量:", traffic)

# ── 3. 播放清單 → 影片清單（含上片日期）──────────────────
show_videos = {}   # name -> [videoId]
vid_meta = {}      # id -> {title, published}
for name, pid in PLAYLISTS.items():
    ids, page = [], None
    while True:
        p = {"part": "contentDetails", "playlistId": pid, "maxResults": 50}
        if page: p["pageToken"] = page
        r = data_api("playlistItems", **p)
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        page = r.get("nextPageToken")
        if not page: break
    show_videos[name] = ids
    print(f"{name}: {len(ids)} 支")
all_ids = [v for ids in show_videos.values() for v in ids]
for i in range(0, len(all_ids), 50):
    r = data_api("videos", part="snippet,statistics", id=",".join(all_ids[i:i+50]), maxResults=50)
    for it in r.get("items", []):
        vid_meta[it["id"]] = {"title": it["snippet"]["title"], "published": it["snippet"]["publishedAt"][:10],
                              "viewCount": int(it["statistics"].get("viewCount", 0))}

# ── 4. 逐支影片 Analytics（兩期間）────────────────────────
def video_stats(ids, start):
    out = {}
    for i in range(0, len(ids), 40):
        batch = ids[i:i+40]
        r = analytics(startDate=start, metrics="views,averageViewDuration,subscribersGained",
                      dimensions="video", filters="video==" + ",".join(batch), maxResults=200)
        for row in r.get("rows", []):
            out[row[0]] = {"views": row[1], "dur": row[2], "subs": row[3]}
    return out
stat26 = video_stats(all_ids, Y26_START)
statLife = video_stats(all_ids, LIFE_START)
print(f"影片 stats: 2026 {len(stat26)} 支 / 全期間 {len(statLife)} 支")

# ── 4b. 各月增幅最高週：標記＋抓當週訂閱轉化最高影片（峰值原因）────
by_month = {}
for w in weekly:
    m = w["w"][:7]
    if m not in by_month or w["net"] > by_month[m]["net"]:
        by_month[m] = w
for w in by_month.values():
    w["peak"] = True
    ws = date.fromisoformat(w["w"])
    we = min(ws + timedelta(days=6), END_D)
    try:
        rows = analytics(startDate=ws.isoformat(), endDate=we.isoformat(),
                         metrics="subscribersGained", dimensions="video",
                         sort="-subscribersGained", maxResults=5).get("rows", [])
    except Exception as e:
        print("  峰值影片查詢失敗", w["w"], e)
        rows = []
    if rows and rows[0][1] > 0:
        vid, sg = rows[0][0], int(rows[0][1])
        title = vid_meta.get(vid, {}).get("title")
        if not title:
            try:
                vr = data_api("videos", part="snippet", id=vid).get("items", [])
                title = vr[0]["snippet"]["title"] if vr else vid
            except Exception:
                title = vid
        w["why"] = {"id": vid, "title": title[:70], "subs": sg}
        print(f"  峰值 {w['w']} +{w['net']}: 《{title[:40]}》 +{sg}")

# ── 5. 組節目層 ──────────────────────────────────────────
def rel_str(pub):
    d = (TODAY - date.fromisoformat(pub)).days
    if d < 1: return "今天"
    if d < 7: return f"{d} 天前"
    if d < 30: return f"{d // 7} 週前"
    if d < 365: return f"{d // 30} 個月前"
    return f"{d // 365} 年前"

shows = []
for name, ids in show_videos.items():
    vids = [{"id": v, **vid_meta.get(v, {"title": "?", "published": "2022-01-01", "viewCount": 0}),
             "s26": stat26.get(v, {"views": 0, "dur": 0, "subs": 0}),
             "life": statLife.get(v, {"views": 0, "dur": 0, "subs": 0})} for v in ids]
    # 觀看數以 Data API 即時值為準（與 YouTube 頁面一致；Analytics 對近日/新片有處理延遲會少算）
    for v in vids:
        v["life"]["views"] = v["viewCount"]
        if v["published"] >= Y26_START:            # 2026 上片：全部觀看都發生在 2026
            v["s26"]["views"] = v["viewCount"]
    vids.sort(key=lambda x: x["published"], reverse=True)
    n = len(vids)
    up26 = [v for v in vids if v["published"] >= Y26_START]
    views26 = sum(v["s26"]["views"] for v in vids)
    viewsL = sum(v["life"]["views"] for v in vids)
    subs26 = sum(v["s26"]["subs"] for v in vids)
    subsL = sum(v["life"]["subs"] for v in vids)
    # 平均時長（觀看加權）
    def wdur(key):
        tot = sum(v[key]["views"] for v in vids)
        return round(sum(v[key]["dur"] * v[key]["views"] for v in vids) / tot) if tot else 0
    # 更新週期：2026 首支上片日起算，以「工作天」計（週末不計；顯示端仍只寫「天」）
    if up26:
        first = min(date.fromisoformat(v["published"]) for v in up26)
        wd26 = workdays(max(first, date(2026, 1, 1)), END_D)
    else:
        wd26 = None
    top = max(vids, key=lambda v: v["life"]["views"]) if vids else None
    top26 = max(vids, key=lambda v: v["s26"]["views"]) if vids else None
    recent = [{"id": v["id"], "title": v["title"][:70], "rel": rel_str(v["published"]), "pub": v["published"],
               "views": v["life"]["views"], "dur": v["life"]["dur"], "subs": v["life"]["subs"],
               "ratio": round(v["life"]["views"] / v["life"]["subs"]) if v["life"]["subs"] else None}
              for v in vids[:20]]
    views_up26 = sum(v["life"]["views"] for v in up26)
    subs_up26 = sum(v["life"]["subs"] for v in up26)
    shows.append({
        "name": name, "n": n, "n26": len(up26), "wd26": wd26,
        "viewsUp26": views_up26 or None, "subsUp26": subs_up26 or None,
        "avg26": round(views_up26 / len(up26)) if up26 else None,
        "views": viewsL, "views26": views26,
        "subs": subsL, "subs26": subs26,
        "dur": wdur("life"), "dur26": wdur("s26"),
        "top": {"id": top["id"], "title": top["title"][:70], "views": top["life"]["views"]} if top else None,
        "top26": {"id": top26["id"], "title": top26["title"][:70], "views": top26["s26"]["views"],
                  "dur": top26["s26"]["dur"], "subs": top26["s26"]["subs"]} if top26 and top26["s26"]["views"] else None,
        "recent": recent,
    })
    print(f"{name}: 2026 觀看 {views26:,} 訂閱 +{subs26:,} | 全期間 {viewsL:,} +{subsL:,} | 週期分母 {wd26}")

out = {
    "generated": TODAY.isoformat(), "endDate": END,
    "channel": channel,
    "gender": {k: round(v, 1) for k, v in gender.items()},
    "age": {k: round(v, 1) for k, v in age.items()},
    "age40": round(age40, 1),
    "traffic": traffic,
    "weekly": weekly,
    "shows": shows,
}
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json"), "w"), ensure_ascii=False, indent=1)
print("\n✅ data.json written")
