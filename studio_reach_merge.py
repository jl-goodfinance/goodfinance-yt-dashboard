#!/usr/bin/env python3
"""把 studio_reach_scrape.js 抓到的原始結果併進 studio_reach.json。
用法：python3 studio_reach_merge.py <raw.json>
raw.json 格式：{videoId: {since:{imp,ctr,views,from}, impact:{imp,ctr,ev,avd}, h24:{...}|字串, ab:字串|null, traffic:字串, abImg:[網址]}}
輸出 studio_reach.json：
  videos[id] = {asOf, since:{impr,ctr,views}, h24:{impr,ctr,views,from}, evFromImpr, avd,
                ab:{status, period, variants:[{title, share, win, thumb}]}, traffic:{來源: %}}
h24＝上線前 24 小時（團隊 KR 口徑）；已有 h24 的影片不會被較差的新抓取覆蓋。"""
import json, os, re, sys
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "studio_reach.json")


def num(s):
    if s is None: return None
    s = str(s).replace(",", "").strip()
    m = re.fullmatch(r"([\d.]+)萬", s)
    if m: return int(round(float(m.group(1)) * 10000))
    try: return int(float(s))
    except ValueError: return None


def head(h):
    if not isinstance(h, dict) or not h.get("imp"): return None
    return {"impr": num(h.get("imp")), "ctr": float(h["ctr"]) if h.get("ctr") else None, "views": num(h.get("views")), "from": h.get("from")}


def parse_ab(s, imgs):
    """A/B 卡片文字 → 狀態與各版本。版本順序與 Studio 相同；縮圖網址依 custom_N 編號對應。"""
    if not s: return None
    s = s.replace(" | ", " ｜ ")  # 標題本身含「 | 」時不要被當成欄位分隔
    parts = [p.strip() for p in s.split("|") if p.strip()]
    if not parts: return None
    meta = [x.strip() for x in parts[0].split("•")]
    ab = {"metric": meta[0] if meta else "", "status": meta[1] if len(meta) > 1 else "", "period": meta[2] if len(meta) > 2 else "", "variants": []}
    for p in parts[1:]:
        if re.fullmatch(r"[\d.]+%", p):
            if ab["variants"]: ab["variants"][-1]["share"] = float(p[:-1])
        elif p == "獲勝者":
            if ab["variants"]: ab["variants"][-1]["win"] = True
        elif p.startswith("現在起") or p.startswith("成效相同") or len(p) < 8:
            ab.setdefault("notes", []).append(p)
        else:
            ab["variants"].append({"title": p})
    thumbs = {}
    for u in imgs or []:
        m = re.search(r"custom_(\d)", u)
        if m: thumbs[int(m.group(1))] = u
    for i, v in enumerate(ab["variants"], 1):
        if i in thumbs: v["thumb"] = thumbs[i]
    titles = {v["title"] for v in ab["variants"]}
    ab["tests"] = "縮圖" if len(titles) == 1 else ("標題＋縮圖" if len(titles) == len(ab["variants"]) else "標題與縮圖混合")
    return ab


def main():
    raw = json.load(open(sys.argv[1], encoding="utf-8"))
    J = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {"videos": {}}
    V = J.setdefault("videos", {})
    today = date.today().isoformat(); n = 0
    for vid, r in raw.items():
        since = head(r.get("since"))
        if not since: continue
        cur = V.get(vid, {})
        rec = {"asOf": today, "since": since}
        h24 = head(r.get("h24")) or cur.get("h24")
        if h24: rec["h24"] = h24
        imp = r.get("impact") or {}
        if imp.get("ev"): rec["evFromImpr"] = num(imp["ev"]); rec["avd"] = imp.get("avd")
        ab = parse_ab(r.get("ab"), r.get("abImg")) or cur.get("ab")
        if ab:
            old = (cur.get("ab") or {}).get("variants") or []
            for i, v in enumerate(ab["variants"]):  # 舊紀錄有縮圖網址而這次沒抓到就沿用
                if "thumb" not in v and i < len(old) and old[i].get("title") == v["title"] and old[i].get("thumb"): v["thumb"] = old[i]["thumb"]
            rec["ab"] = ab
        if r.get("traffic"):
            t = r["traffic"].split("|"); rec["traffic"] = {t[i]: float(t[i + 1].rstrip("%")) for i in range(0, len(t) - 1, 2) if re.fullmatch(r"[\d.]+%", t[i + 1])}
        V[vid] = rec; n += 1
    J["updated"] = today
    J["note"] = "Studio 影片分析〈觸及〉分頁逐集抓取：h24＝上線前 24 小時曝光與 CTR（團隊 KR 口徑）、since＝自發布至今、ab＝A/B 測試各版本與觀看時間占比。"
    json.dump(J, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("merged", n, "total", len(V))


if __name__ == "__main__":
    main()
