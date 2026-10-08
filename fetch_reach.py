#!/usr/bin/env python3
"""YouTube Reporting API：逐日、逐支影片的縮圖曝光次數與縮圖點閱率 → ctr_daily.json

報表類型 channel_reach_basic_a1（維度 date / channel_id / video_id；指標 video_thumbnail_impressions、
video_thumbnail_impressions_ctr）。日期為美西時間（YouTube Analytics 慣例）。

首次使用（只需一次）：
  1. 在 Google Cloud 專案啟用「YouTube Reporting API」。
  2. python3 fetch_reach.py --create-job   建立報表工作；YouTube 會回補建立前 30 天的報表，約兩天內陸續產出。
之後每次執行只下載尚未處理過的報表（Actions 每輪 best-effort 呼叫）。

用法：python3 fetch_reach.py [--create-job]
"""
import csv, io, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "ctr_daily.json")
CONF = os.path.expanduser("~/.config/goodfinance-yt")
API = "https://youtubereporting.googleapis.com/v1"
REPORT_TYPE = "channel_reach_basic_a1"
JOB_NAME = "goodfinance-dashboard-reach"
MAIN_SHOWS = 5        # data.json 的前五檔主節目
TRACK_DAYS = 35       # 每支影片只記上片後 35 天內的逐日數據（儀表板最多畫到第 28 天）
KEEP_DAYS = 400       # 上片超過此天數的影片從檔案移除，控制檔案大小
EV_EVERY = 6 * 3600   # 逐日互動觀看（Analytics API）最多每 6 小時重抓一次，省配額


def access_token():
    cid, csec, rtok = (os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    if not (cid and csec and rtok):          # 本機：讀 ~/.config
        conf = json.load(open(f"{CONF}/client_secret.json"))["installed"]
        tok = json.load(open(f"{CONF}/token.json"))
        cid, csec, rtok = conf["client_id"], conf["client_secret"], tok["refresh_token"]
    body = urllib.parse.urlencode({"client_id": cid, "client_secret": csec,
                                   "refresh_token": rtok, "grant_type": "refresh_token"}).encode()
    return json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=body).read())["access_token"]


H = {}


def call(url, data=None, raw=False):
    req = urllib.request.Request(url, headers={**H, **({"Content-Type": "application/json"} if data else {})},
                                 data=json.dumps(data).encode() if data else None)
    body = urllib.request.urlopen(req, timeout=60).read()
    return body.decode("utf-8") if raw else json.loads(body or b"{}")


def paged(url, key):
    out, tok = [], None
    while True:
        r = call(url + ("&" if "?" in url else "?") + (f"pageToken={tok}" if tok else ""))
        out += r.get(key, [])
        tok = r.get("nextPageToken")
        if not tok:
            return out


def find_job(create):
    jobs = [j for j in paged(f"{API}/jobs", "jobs") if j.get("reportTypeId") == REPORT_TYPE]
    if jobs:
        return jobs[0]["id"]
    if not create:
        print(f"尚未建立 {REPORT_TYPE} 報表工作：請執行 python3 fetch_reach.py --create-job")
        return None
    j = call(f"{API}/jobs", {"reportTypeId": REPORT_TYPE, "name": JOB_NAME})
    print("已建立報表工作", j.get("id"), "（YouTube 約 48 小時內開始產出，含前 30 天回補）")
    return j.get("id")


def targets():
    """五檔主節目 2026 上片的影片 → {id: 上片日（UTC，取自 publishedAt）}"""
    D = json.load(open(os.path.join(BASE, "data.json"), encoding="utf-8"))
    return {e["id"]: e["pub"] for s in D["shows"][:MAIN_SHOWS] for e in s.get("eps26", []) if e.get("pub")}


def parse(csv_text):
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    ctrs = [float(r.get("video_thumbnail_impressions_ctr") or 0) for r in rows]
    # 文件只說是「百分比」未寫刻度：整份報表最大值 ≤ 1 視為 0–1 比例，換算成 %
    scale = 100.0 if ctrs and max(ctrs) <= 1 else 1.0
    for r, c in zip(rows, ctrs):
        d = r.get("date", "")
        if len(d) == 8:
            d = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        yield r.get("video_id"), d, int(float(r.get("video_thumbnail_impressions") or 0)), round(c * scale, 2)


def fetch_ev(S, T, today):
    """觀察期內影片的逐日互動觀看（Analytics API，日期同為美西時間）→ videos[id]["ev"] = {日期: 次數}"""
    if time.time() - S.get("evAt", 0) < EV_EVERY:
        return 0
    n = 0
    for vid, pub in T.items():
        p = date.fromisoformat(pub)
        if not (0 <= (today - p).days <= TRACK_DAYS):
            continue
        q = urllib.parse.urlencode({"ids": "channel==MINE", "startDate": (p - timedelta(days=1)).isoformat(),
                                    "endDate": today.isoformat(), "dimensions": "day",
                                    "filters": f"video=={vid}", "metrics": "engagedViews"})
        try:
            rows = call("https://youtubeanalytics.googleapis.com/v2/reports?" + q).get("rows", [])
        except urllib.error.HTTPError as e:
            print("互動觀看抓取失敗", vid, e.code)
            continue
        v = S["videos"].setdefault(vid, {"pub": pub, "d": {}})
        v["ev"] = {d: int(x) for d, x in rows}
        n += 1
    S["evAt"] = int(time.time())
    return n


def main():
    create = "--create-job" in sys.argv
    H["Authorization"] = "Bearer " + access_token()
    try:
        job = find_job(create)
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:300]
        if e.code == 403 and ("has not been used" in msg or "disabled" in msg):
            print("YouTube Reporting API 尚未在 Google Cloud 專案啟用，略過逐日 CTR。")
        else:
            print("Reporting API 錯誤", e.code, msg)
        return
    if not job:
        return
    S = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {"videos": {}, "seen": []}
    S["job"] = job
    seen = set(S.get("seen", []))
    reports = sorted(paged(f"{API}/jobs/{job}/reports", "reports"), key=lambda r: r.get("createTime", ""))
    new = [r for r in reports if r["id"] not in seen]
    T = targets()
    today = date.today()
    hit = 0
    for rep in new:     # 依產出時間先後處理：同一天的報表若重新產出，後到的覆蓋先到的
        text = call(rep["downloadUrl"], raw=True)
        for vid, d, impr, ctr in parse(text):
            pub = T.get(vid)
            if not pub or not d:
                continue
            if not (date.fromisoformat(pub) - timedelta(days=1) <= date.fromisoformat(d) <= date.fromisoformat(pub) + timedelta(days=TRACK_DAYS)):
                continue
            v = S["videos"].setdefault(vid, {"pub": pub, "d": {}})
            v["pub"] = pub
            v["d"][d] = [impr, ctr]
            hit += 1
        seen.add(rep["id"])
    nev = fetch_ev(S, T, today)
    # 移除過舊影片；seen 只留目前 API 仍列出的報表 id（報表保留 30–60 天，檔案不會無限長大）
    S["videos"] = {k: v for k, v in S["videos"].items()
                   if (today - date.fromisoformat(v["pub"])).days <= KEEP_DAYS}
    live = {r["id"] for r in reports}
    S["seen"] = sorted(seen & live)
    if new or nev:
        S["updated"] = today.isoformat()
        S["latest"] = max((r.get("startTime", "")[:10] for r in reports), default="")
    json.dump(S, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"報表 {len(reports)} 份（新 {len(new)} 份），寫入 {hit} 筆逐日數據，互動觀看更新 {nev} 支，影片 {len(S['videos'])} 支")


if __name__ == "__main__":
    main()
