#!/usr/bin/env python3
"""競品排行：台灣金融業官方頻道＋財經 KOL 的訂閱/觀看數 → rank.json
頻道 ID 首次用 search 解析後快取到 rank_channels.json（之後每小時只花 channels.list 的 1 quota）"""
import json, os, urllib.request, urllib.parse
from datetime import date, timedelta

CONF = os.path.expanduser("~/.config/goodfinance-yt")
BASE = os.path.dirname(os.path.abspath(__file__))

# 候選名單（name -> 已知 channelId 或 None=用搜尋解析；可自行增刪）
INDUSTRY = {
    "美好證券 Good Finance": "UCadQDNkNdOGwYnXK3HSTBsA",
    "永豐金證券 豐雲學堂": "UCqdf3aTRV9T2bIAoIvWYT0Q",
    "元大投信": "UC-lpGvvB9OpHS0GdF5iatcQ",
    "元大證券": "UCcTY_h1Y38ZwsB9AEpWQdQw",
    "富邦證券": None,
    "凱基證券 樂活投資人": "UCAb0OrzVjoc_3S97ng5lemg",
    "凱基 股股漲": None,
    "群益期貨 KeensPie": "UC2x6Dy8O6JGHcyS27oAI4zg",
    "國泰世華銀行": "UCnJ41_Tdf65EaM8-lfWg8Hg",
    "國泰投信 大樹下學投資": "UCmf5iH3_OQa_Z3ab8F5iscA",
    "中國信託 CTBC": "UCK-qHFerEXOQG0q6yOkm_SQ",
    "玉山銀行 E.SUN": "UC3tl5_Ff9aPYEHgtJELpcnw",
    "台新銀行 Richart": "UCjoEdiFwtGZS_z4n-iA6TQw",
    "統一投信": "UCYkIQ8mfEd0e1M2F2cNTShA",
    "兆豐銀行": "UCTHisK1U5uIToyCfaiKYUdA",
}
KOL = {
    "小Lin説": "UCilwQlk62k1z7aUEZPOB6yw",
    "柴鼠兄弟 ZRBros": "UC45i13dEfEVac2IEJT_Nr5Q",
    "游庭皓的財經皓角": "UC0lbAQVpenvfA2QqzsRtL_g",
    "股癌 Gooaye": "UC23rnlQU_qE3cec9x709peA",
    "老王愛說笑": None,
    "財報狗": "UC2TsM2pyabGznSvB9llmsFA",
    "SHIN LI 李勛": "UCK-qc_POQZwWrMg-Pr-oYtg",
    "阿格力": "UC4douYiP0O4ABtxoMuo9yNA",
    "清流君": "UCeTLfPD7thTMabtL7w87Aug",
    "Ms.Selena": "UCDGQy_7kFITT3VHbVNPnXKg",
    "Nicolas 楊應超": "UCXUP_aBLQBNFgLjvnrMTHtw",
    "M觀點 Miula": "UCT3uWFvKLVpRnEealmRwvrw",
    "慢活夫妻": "UCVNqvJSKVl0bsdb15gKUZfg",
    "雨果的投資理財生活觀": "UCsrEBPmcX6bT2easAwI_dMA",
}

def access_token():
    cid = os.environ.get("YT_CLIENT_ID"); csec = os.environ.get("YT_CLIENT_SECRET"); rtok = os.environ.get("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        conf = json.load(open(f"{CONF}/client_secret.json"))["installed"]
        tok = json.load(open(f"{CONF}/token.json"))
        cid, csec, rtok = conf["client_id"], conf["client_secret"], tok["refresh_token"]
    body = urllib.parse.urlencode({"client_id": cid, "client_secret": csec,
        "refresh_token": rtok, "grant_type": "refresh_token"}).encode()
    return json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=body).read())["access_token"]

H = {"Authorization": "Bearer " + access_token()}

def get(resource, **params):
    u = f"https://www.googleapis.com/youtube/v3/{resource}?" + urllib.parse.urlencode(params)
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60).read())

# 1. 解析頻道 ID（有快取就不搜尋）
cache_p = os.path.join(BASE, "rank_channels.json")
cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
def resolve(name, known):
    """回傳候選 id 清單；已知/快取單一，未知取搜尋前 3（後續以訂閱數最高者為準——官方主頻道通常最大）"""
    if known: return [known]
    if name in cache: return [cache[name]]
    try:
        r = get("search", part="snippet", q=name, type="channel", maxResults=3, regionCode="TW", relevanceLanguage="zh-Hant")
        ids = [i["snippet"]["channelId"] for i in r.get("items", [])]
        return ids
    except Exception as e:
        print("  解析失敗", name, e)
        return []

def build(group):
    cands = {name: resolve(name, known) for name, known in group.items()}
    all_ids = sorted({i for ids in cands.values() for i in ids})
    stats = {}
    for i in range(0, len(all_ids), 50):
        r = get("channels", part="snippet,statistics", id=",".join(all_ids[i:i+50]), maxResults=50)
        for it in r.get("items", []):
            st = it["statistics"]
            stats[it["id"]] = {
                "yt_title": it["snippet"]["title"], "handle": it["snippet"].get("customUrl", ""),
                "subs": int(st.get("subscriberCount", 0)),
                "views": int(st.get("viewCount", 0)), "videos": int(st.get("videoCount", 0)),
            }
    rows = []
    for name, ids in cands.items():
        got = [(i, stats[i]) for i in ids if i in stats]
        if not got: continue
        import re as _re
        toks = [t for t in _re.split(r"[\s（）()]+", name) if len(t) >= 2]
        def score(x):
            title = x[1]["yt_title"]
            hit = any(t in title or t.lower() in title.lower() for t in toks)
            return (1 if hit else 0, x[1]["subs"])
        cid, st = max(got, key=score)   # 標題吻合優先，訂閱數決勝
        cache[name] = cid
        rows.append({"name": name, "id": cid, **st})
    rows.sort(key=lambda x: -x["subs"])
    return rows

print("金融業：")
industry = build(INDUSTRY)
print("KOL：")
kol = build(KOL)
json.dump(cache, open(cache_p, "w"), ensure_ascii=False, indent=1)

# 每日訂閱快照 → 累積各頻道週增（YouTube 不給他人歷史，只能自建時序，滿一週後生效）
TODAY = date.today()
hist_p = os.path.join(BASE, "rank_history.json")
hist = json.load(open(hist_p)) if os.path.exists(hist_p) else []
snap = {r["id"]: [r["subs"], r["videos"]] for r in industry + kol}   # [訂閱, 影片數]
hist = [h for h in hist if h["date"] != TODAY.isoformat()]   # 同日覆蓋為最新
hist.append({"date": TODAY.isoformat(), "subs": snap})
hist.sort(key=lambda h: h["date"])
hist = hist[-160:]
json.dump(hist, open(hist_p, "w"), ensure_ascii=False)

def week_delta(cid, cur, idx):
    """取 5–10 天前、最接近 7 天的快照算增加（idx 0=訂閱 1=影片數）；無足夠歷史回 None
    相容舊格式（值為 int＝僅訂閱快照，無影片歷史）"""
    best, best_gap = None, 99
    for h in hist:
        age = (TODAY - date.fromisoformat(h["date"])).days
        if 5 <= age <= 10 and cid in h["subs"] and abs(age - 7) < best_gap:
            best, best_gap = h, abs(age - 7)
    if not best:
        return None
    prev = best["subs"][cid]
    if isinstance(prev, list):
        return cur - prev[idx]
    return cur - prev if idx == 0 else None   # 舊 int 只有訂閱
for r in industry + kol:
    r["w7"] = week_delta(r["id"], r["subs"], 0)
    r["w7v"] = week_delta(r["id"], r["videos"], 1)

out = {"updated": TODAY.isoformat(), "industry": industry, "kol": kol}
json.dump(out, open(os.path.join(BASE, "rank.json"), "w"), ensure_ascii=False, indent=1)
for r in industry[:12]: print(f'  {r["subs"]:>9,} {r["name"]} ({r["yt_title"]})')
print("---")
for r in kol[:12]: print(f'  {r["subs"]:>9,} {r["name"]} ({r["yt_title"]})')
print("✅ rank.json written")
