#!/usr/bin/env python3
"""逐集深度指標（YouTube Analytics API）→ episode_metrics.json，給週更顧問寫各節目 insights 用。
範圍：四檔來賓節目 2026 全部集數＋Good Morning 近 N 天（預設 60）與全年互動觀看前 5。
每集：互動觀看、平均觀看時長與比例、分享、訂閱、流量來源占比、已訂閱觀看時間占比、年齡性別、
裝置、搜尋字詞、推薦來源影片、0:30 續看率與各四分位續看率。
用法：python3 fetch_episode_metrics.py [GM天數=60]"""
import json, os, sys, time, urllib.request, urllib.parse, re
from datetime import date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__)); CONF = os.path.expanduser("~/.config/goodfinance-yt")
GM_DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 60
TODAY = date.today().isoformat()

def access_token():
    cid, csec, rtok = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET"), os.environ.get("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        conf = json.load(open(f"{CONF}/client_secret.json"))["installed"]; tok = json.load(open(f"{CONF}/token.json"))
        cid, csec, rtok = conf["client_id"], conf["client_secret"], tok["refresh_token"]
    body = urllib.parse.urlencode({"client_id": cid, "client_secret": csec, "refresh_token": rtok, "grant_type": "refresh_token"}).encode()
    return json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=body).read())["access_token"]
H = {"Authorization": "Bearer " + access_token()}

def get(url, params, retries=3):
    u = url + "?" + urllib.parse.urlencode(params)
    for i in range(retries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60).read())
        except Exception as e:
            if i == retries - 1: return {"error": str(e)}
            time.sleep(2 * (i + 1))
def rep(**p):
    base = {"ids": "channel==MINE", "startDate": "2026-01-01", "endDate": TODAY}; base.update(p)
    return get("https://youtubeanalytics.googleapis.com/v2/reports", base)
def sec(s):
    m = re.search(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or ""); h, mi, se = [int(x or 0) for x in m.groups()]; return h*3600+mi*60+se

D = json.load(open(f"{BASE}/data.json", encoding="utf-8"))
lo = (date.today() - timedelta(days=GM_DAYS)).isoformat()
sel = {}
for i, s in enumerate(D["shows"][:5]):
    eps = [e for e in s.get("eps26", []) if not e.get("sch") or e["sch"] <= TODAY]
    if i == 0:
        keep = [e for e in eps if e["pub"] >= lo] + sorted(eps, key=lambda e: -(e.get("ev") or 0))[:5]
    else:
        keep = eps
    for e in keep: sel[e["id"]] = {"show": s["name"], "pub": e["pub"], "title": e["t"]}
ids = list(sel)
print("videos", len(ids), flush=True)

# 片長
for i in range(0, len(ids), 50):
    r = get("https://www.googleapis.com/youtube/v3/videos", {"part": "contentDetails,statistics", "id": ",".join(ids[i:i+50])})
    for it in r.get("items", []):
        sel[it["id"]]["dur"] = sec(it["contentDetails"].get("duration"))
        st = it["statistics"]; sel[it["id"]]["public"] = int(st.get("viewCount", 0)); sel[it["id"]]["likes"] = int(st.get("likeCount", 0)); sel[it["id"]]["comments"] = int(st.get("commentCount", 0))

# 基本指標（批次）
METRICS = "views,engagedViews,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,shares,subscribersGained,subscribersLost"
for i in range(0, len(ids), 150):
    chunk = ids[i:i+150]
    r = rep(dimensions="video", metrics=METRICS, filters="video==" + ",".join(chunk), sort="-views", maxResults=200)
    if "error" in r:
        r = rep(dimensions="video", metrics=METRICS.replace("engagedViews,", ""), filters="video==" + ",".join(chunk), sort="-views", maxResults=200)
    cols = [c["name"] for c in r.get("columnHeaders", [])]
    for row in r.get("rows", []):
        o = dict(zip(cols, row)); v = sel.get(o["video"]);
        if not v: continue
        v.update({"views": o.get("views"), "ev": o.get("engagedViews"), "minutes": o.get("estimatedMinutesWatched"), "avgDur": o.get("averageViewDuration"),
                  "avgPct": o.get("averageViewPercentage"), "shares": o.get("shares"), "subs": o.get("subscribersGained"), "subsLost": o.get("subscribersLost")})

def pct(rows, key=1):
    tot = sum(r[key] for r in rows) or 1
    return {r[0]: round(r[key] / tot * 100, 1) for r in sorted(rows, key=lambda r: -r[key])}

rel_ids = set()
for n, vid in enumerate(ids):
    v = sel[vid]; f = "video==" + vid
    r = rep(dimensions="insightTrafficSourceType", metrics="views", filters=f)
    if r.get("rows"): v["traffic"] = pct(r["rows"])
    r = rep(dimensions="subscribedStatus", metrics="views,estimatedMinutesWatched", filters=f)
    if r.get("rows"):
        v["subscribedViews"] = pct(r["rows"], 1).get("SUBSCRIBED"); v["subscribedWatch"] = pct(r["rows"], 2).get("SUBSCRIBED")
    r = rep(dimensions="ageGroup,gender", metrics="viewerPercentage", filters=f)
    if r.get("rows"):
        age = {}; g = {}
        for a, s_, p in r["rows"]:
            age[a] = age.get(a, 0) + p; g[s_] = g.get(s_, 0) + p
        v["age"] = {k.replace("age", ""): round(x, 1) for k, x in sorted(age.items())}; v["female"] = round(g.get("female", 0), 1)
        v["age45"] = round(sum(x for k, x in age.items() if k in ("age45-54", "age55-64", "age65-")), 1)
        v["age35_54"] = round(sum(x for k, x in age.items() if k in ("age35-44", "age45-54")), 1)
    r = rep(dimensions="deviceType", metrics="estimatedMinutesWatched", filters=f)
    if r.get("rows"): v["device"] = pct(r["rows"])
    r = rep(dimensions="insightTrafficSourceDetail", metrics="views", filters=f + ";insightTrafficSourceType==YT_SEARCH", sort="-views", maxResults=8)
    if r.get("rows"): v["search"] = [[a, b] for a, b in r["rows"]]
    r = rep(dimensions="insightTrafficSourceDetail", metrics="views", filters=f + ";insightTrafficSourceType==RELATED_VIDEO", sort="-views", maxResults=6)
    if r.get("rows"):
        v["related"] = [[a, b] for a, b in r["rows"]]; rel_ids.update(a for a, _ in r["rows"])
    r = rep(dimensions="elapsedVideoTimeRatio", metrics="audienceWatchRatio", filters=f)
    rows = r.get("rows") or []
    if rows and v.get("dur"):
        pts = sorted(rows)
        def at(ratio):
            return round(min(pts, key=lambda p: abs(p[0] - ratio))[1] * 100, 1)
        # 0:30：取含 0:30 的那一格（第 n 格涵蓋片長的 (n-1)%～n%），與 Studio〈參與度〉的數字一致；長片一格超過 30 秒時不準
        first = [p for p in pts if p[0] >= 30 / v["dur"] - 1e-9]
        v["ret30s"] = round(first[0][1] * 100, 1) if first else None; v["ret25"] = at(0.25); v["ret50"] = at(0.5); v["ret75"] = at(0.75); v["ret95"] = at(0.95)
    if n % 10 == 9: print("done", n + 1, flush=True)

# 推薦來源影片的標題與頻道
rel = {}
rl = [x for x in rel_ids if re.fullmatch(r"[\w-]{11}", x or "")]
for i in range(0, len(rl), 50):
    r = get("https://www.googleapis.com/youtube/v3/videos", {"part": "snippet", "id": ",".join(rl[i:i+50])})
    for it in r.get("items", []): rel[it["id"]] = [it["snippet"]["title"][:60], it["snippet"]["channelTitle"]]
for v in sel.values():
    if v.get("related"): v["related"] = [[*(rel.get(a, [a, ""])), b] for a, b in v["related"]]

json.dump({"updated": TODAY, "note": "YouTube Analytics API；流量與年齡為觀看次數占比、裝置為觀看時間占比；ret30s＝0:30 仍在觀看的比例", "videos": sel},
          open(f"{BASE}/episode_metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", len(sel))
