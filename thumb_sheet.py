#!/usr/bin/env python3
"""縮圖對照表：把近期影片的「現在的縮圖」抓下來，依 CTR 排序拼成一張圖，給週更顧問實際看縮圖再寫看法。
每格標：節目｜上片日｜Studio 自發布至今 CTR／曝光｜逐日第 1、第 2 天 CTR｜標題前 28 字。
縮圖每次重抓（不用 thumbs.json 快取），換過縮圖會反映。
用法：
  python3 thumb_sheet.py <輸出.png> [天數=14]                 # 五檔主節目近 N 天上片
  python3 thumb_sheet.py <輸出.png> --compet <compet_raw.json> [N=12]   # 競品近 15 支中觀看前 N 名
"""
import io, json, os, sys, urllib.request
from datetime import date, timedelta
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
W, H, PAD, TXT = 320, 180, 10, 58
COLS = 4

def font(sz):
    for p in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Light.ttc", "/Library/Fonts/Arial Unicode.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()

def thumb(vid):
    for q in ("mqdefault", "hqdefault"):
        try:
            raw = urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/{q}.jpg", timeout=20).read()
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            if q == "hqdefault": im = im.crop((0, 45, 480, 315))
            return im.resize((W, H))
        except Exception:
            continue
    return Image.new("RGB", (W, H), (40, 40, 40))

def sheet(items, out, title):
    rows = (len(items) + COLS - 1) // COLS
    img = Image.new("RGB", (COLS * (W + PAD) + PAD, rows * (H + TXT + PAD) + PAD + 30), (18, 20, 28))
    dr = ImageDraw.Draw(img); f1, f2 = font(13), font(11)
    dr.text((PAD, 8), title, fill=(230, 230, 240), font=f1)
    for i, it in enumerate(items):
        x = PAD + (i % COLS) * (W + PAD); y = 30 + PAD + (i // COLS) * (H + TXT + PAD)
        img.paste(thumb(it["id"]), (x, y))
        dr.rectangle([x, y, x + 46, y + 18], fill=(0, 0, 0))
        dr.text((x + 4, y + 2), f"#{i+1}", fill=(255, 220, 80), font=f1)
        for j, line in enumerate(it["lines"]):
            dr.text((x, y + H + 3 + j * 14), line, fill=(215, 220, 235) if j else (255, 255, 255), font=f2)
    img.save(out); print(f"✅ {out}: {len(items)} 張")

def own(days):
    D = json.load(open(f"{BASE}/data.json", encoding="utf-8"))
    S = json.load(open(f"{BASE}/studio28.json", encoding="utf-8")).get("videos", {})
    C = json.load(open(f"{BASE}/ctr_daily.json", encoding="utf-8")).get("videos", {})
    lo = (date.today() - timedelta(days=days)).isoformat()
    items = []
    for s in D["shows"][:5]:
        for e in s.get("recent", []):
            if e["pub"] < lo or e.get("sch"): continue
            st = S.get(e["id"], {}); dd = sorted(C.get(e["id"], {}).get("d", {}).items())
            d1 = f"{dd[0][1][1]}%" if dd else "—"; d2 = f"{dd[1][1][1]}%" if len(dd) > 1 else "—"
            ctr = st.get("ctr"); impr = st.get("impr")
            items.append({"id": e["id"], "ctr": ctr if ctr is not None else -1, "lines": [
                f"{s['name'][:12]}｜{e['pub'][5:]}｜CTR {ctr if ctr is not None else '—'}%｜曝光 {impr/10000:.1f}萬" if impr else f"{s['name'][:12]}｜{e['pub'][5:]}｜CTR —",
                f"第1天 {d1}  第2天 {d2}  公開 {e['views']:,}",
                e["title"][:28]]})
    items.sort(key=lambda x: -x["ctr"])
    return items

def compet(path, n):
    R = json.load(open(path, encoding="utf-8"))
    lo = (date.today() - timedelta(days=8)).isoformat()
    vids = []
    for name, ch in R.items():
        if name.startswith("美好證券"): continue
        for v in ch["videos"]:
            if v["pub"] >= lo and v["dur"] > 60:
                vids.append({"id": v["id"], "ctr": v["views"], "lines": [
                    f"{name[:10]}｜{v['pub'][5:]}｜{v['views']:,} 觀看",
                    f"讚 {v['likes'] if v['likes'] is not None else '—'}  留言 {v['comments'] if v['comments'] is not None else '—'}  {v['dur']//60} 分",
                    v["title"][:28]]})
    vids.sort(key=lambda x: -x["ctr"])
    return vids[:n]

if __name__ == "__main__":
    out = sys.argv[1]
    if "--compet" in sys.argv:
        i = sys.argv.index("--compet"); n = int(sys.argv[i + 2]) if len(sys.argv) > i + 2 else 12
        sheet(compet(sys.argv[i + 1], n), out, f"競品近一週長片觀看前 {n} 名（依觀看排序）")
    else:
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 14
        sheet(own(days), out, f"美好五檔主節目近 {days} 天上片縮圖（依 Studio 自發布至今 CTR 排序，高→低）")
