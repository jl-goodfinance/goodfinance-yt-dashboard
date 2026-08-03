#!/usr/bin/env python3
"""本週數據速報：純運算、無需 AI，可在 GitHub Actions 每小時自動更新
資料源：data.json（頻道/節目/每週訂閱）＋ rank.json（競品）＋ comments.json
輸出：weekly_brief.json → apply_data.py 注入 const BRIEF
歷史快照：brief_history.json 保存每週一的頻道/節目快照，用來算「真實週變化」
"""
import json, os
from datetime import date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
def load(n, d=None):
    p = os.path.join(BASE, n)
    return json.load(open(p)) if os.path.exists(p) else d

D = load("data.json")
RANK = load("rank.json", {"industry": [], "kol": []})
CMT = load("comments.json", {})
ME = "UCadQDNkNdOGwYnXK3HSTBsA"
MAIN = ["Good Morning 美好", "Good Invest 美好投資", "Better Living 美好生活", "Good Income", "Entrepreneurship"]
TODAY = date.today()

# ── 1. 每週快照（每週一存一次，供週對週比較）──────────────────
hist_p = os.path.join(BASE, "brief_history.json")
hist = load("brief_history.json", [])
monday = (TODAY - timedelta(days=TODAY.weekday())).isoformat()
snap = {
    "w": monday, "gen": D["generated"],
    "subs": D["channel"]["subs"], "views26": D["channel"]["views26"],
    "subsGained26": D["channel"]["subsGained26"],
    "shows": {s["name"]: {"n26": s["n26"], "v26": s["views26"], "s26": s["subs26"]}
              for s in D["shows"] if s["name"] in MAIN},
}
hist = [h for h in hist if h["w"] != monday] + [snap]
hist.sort(key=lambda h: h["w"])
hist = hist[-30:]
json.dump(hist, open(hist_p, "w"), ensure_ascii=False, indent=1)

prev = hist[-2] if len(hist) > 1 else None   # 上週一的快照

# ── 2. 訂閱動能（每週淨增趨勢＋警示）──────────────────────────
weekly = D.get("weekly", [])
done = [w for w in weekly if w["w"] < monday]        # 只取已完整結束的週
recent = done[-4:]
momentum = None
if len(recent) >= 2:
    last, prior = recent[-1], recent[-2]
    avg3 = sum(w["net"] for w in recent[-4:-1]) / max(len(recent[-4:-1]), 1)
    momentum = {
        "trend": [{"w": w["w"], "net": w["net"]} for w in recent],
        "last": last["net"], "prevWeeks": round(avg3),
        "chg": round((last["net"] - avg3) / avg3 * 100) if avg3 else None,
        "alert": last["net"] < avg3 * 0.7,            # 低於前三週均值 30% 以上＝警示
    }

# ── 3. 各節目本週產出與效率 ─────────────────────────────────
shows = []
week_start = (TODAY - timedelta(days=TODAY.weekday() + 7)).isoformat()   # 上週一
for s in D["shows"]:
    if s["name"] not in MAIN: continue
    o = (prev or {}).get("shows", {}).get(s["name"]) or {}
    ups = [r for r in s["recent"] if r["pub"] >= week_start and not r.get("sch")]
    dv = (s["views26"] - o["v26"]) if "v26" in o else None
    ds = (s["subs26"] - o["s26"]) if "s26" in o else None
    shows.append({
        "name": s["name"], "newEps": len(ups),
        "dViews": dv, "dSubs": ds,
        "ratio": round(dv / ds) if (dv and ds) else None,   # 本週每 N 觀看換 1 訂閱
        "avg26": s["avg26"], "stale": len(ups) == 0,
        "lastPub": max((r["pub"] for r in s["recent"] if not r.get("sch")), default=None),
    })
shows.sort(key=lambda x: (-(x["dSubs"] or 0), x["stale"]))

# ── 4. 競品週增排名（美好位置）───────────────────────────────
comp = None
ind = [c for c in RANK.get("industry", []) if c.get("w7") is not None]
if ind:
    ind.sort(key=lambda c: -c["w7"])
    mi = next((i for i, c in enumerate(ind) if c["id"] == ME), None)
    comp = {
        "rows": [{"name": c["name"], "w7": c["w7"], "subs": c["subs"], "w7v": c.get("w7v"),
                  "me": c["id"] == ME} for c in ind[:6]],
        "myRank": (mi + 1) if mi is not None else None, "total": len(ind),
        "myW7": ind[mi]["w7"] if mi is not None else None,
        "leader": ind[0]["name"], "leaderW7": ind[0]["w7"],
    }
    # 貼身對手：訂閱數最接近美好者
    if mi is not None:
        me_subs = ind[mi]["subs"]
        rivals = sorted([c for c in ind if c["id"] != ME], key=lambda c: abs(c["subs"] - me_subs))
        if rivals:
            r = rivals[0]
            comp["rival"] = {"name": r["name"], "subs": r["subs"], "w7": r["w7"],
                             "gap": me_subs - r["subs"]}

# ── 5. 本週最佳單集＋最熱留言 ───────────────────────────────
allv = [dict(r, show=s["name"]) for s in D["shows"] if s["name"] in MAIN
        for r in s["recent"] if r["pub"] >= week_start and not r.get("sch")]
best = max(allv, key=lambda v: v["views"], default=None)
bestSub = max([v for v in allv if v.get("subs")], key=lambda v: v["subs"], default=None)
hot = None
for v in allv:
    for c in CMT.get(v["id"], {}).get("comments", []):
        if not hot or c["likes"] > hot["likes"]:
            hot = {"likes": c["likes"], "text": c["text"][:120], "id": v["id"], "title": v["title"][:50]}

out = {
    "updated": D["generated"], "week": week_start,
    "channel": {
        "subs": D["channel"]["subs"],
        "dSubs": D["channel"]["subs"] - prev["subs"] if prev else None,
        "dViews": D["channel"]["views26"] - prev["views26"] if prev else None,
        "dGained": D["channel"]["subsGained26"] - prev["subsGained26"] if prev else None,
    },
    "momentum": momentum, "shows": shows, "compet": comp,
    "best": {"views": best, "subs": bestSub} if best else None, "hotComment": hot,
}
json.dump(out, open(os.path.join(BASE, "weekly_brief.json"), "w"), ensure_ascii=False, indent=1)

print(f"✅ weekly_brief.json（週 {week_start} 起算，歷史快照 {len(hist)} 週）")
if momentum:
    print(f"   訂閱動能：上週 {momentum['last']:+} vs 前三週均 {momentum['prevWeeks']:+}"
          f"（{momentum['chg']:+}%）{'⚠️ 警示' if momentum['alert'] else ''}")
for s in shows:
    print(f"   {s['name'][:18]:20s} 新片 {s['newEps']:>2} 觀看 {(f"{s['dViews']:+,}" if s['dViews'] is not None else '待累積'):>9s} 訂閱 {(f"{s['dSubs']:+}" if s['dSubs'] is not None else '—'):>6s}"
          f"{'  ⚠️ 本週零產出（最後 ' + str(s['lastPub']) + '）' if s['stale'] else ''}")
if comp:
    print(f"   競品：美好週增 +{comp['myW7']:,} 排名 {comp['myRank']}/{comp['total']}，"
          f"領先者 {comp['leader']} +{comp['leaderW7']:,}")
