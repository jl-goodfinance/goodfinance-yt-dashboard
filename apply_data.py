#!/usr/bin/env python3
"""把 data.json 的真實數據套進 dashboard HTML（可重複執行：每次都以錨點整段替換）"""
import json, os, re, sys

HTML = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Projects/goodfinance-yt-dashboard/goodfinance-yt-shows.html")
D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")))

def fmt_dur(sec):
    return f"{int(sec)//60}:{int(sec)%60:02d}" if sec else ""

def wan(v):
    return (f"{v/10000:.1f}".rstrip("0").rstrip(".") + "萬") if v >= 10000 else f"{v:,}"

# 各節目固定屬性（色相）；Studio 近28天曝光/CTR 由 studio28.json 提供
HUE = {"Good Morning 美好": 0, "Better Living 美好生活": 1, "Good Invest 美好投資": 2,
       "老黃 Good Talk": 3, "Good Income": 4, "投資新手村": 2, "Entrepreneurship": 0,
       "美好證券 x 志祺七七": 1, "Know Your Money 錢途診聊室": 3, "A day in the Life 美好日常": 4}
BASE = os.path.dirname(os.path.abspath(__file__))
def load(name, default):
    p = os.path.join(BASE, name)
    return json.load(open(p)) if os.path.exists(p) else default
S28 = load("studio28.json", {"channel": {}, "shows": {}, "videos": {}})
ADV = load("advice.json", {"updated": "", "channel": [], "shows": {}})
ANA = load("analysis.json", {})
CMT_RAW = load("comments.json", {})
# 每支影片嵌入前 6 則熱門留言（截 170 字）
CMT = {vid: [{"l": c["likes"], "t": c["text"][:170]} for c in info.get("comments", [])[:6]]
       for vid, info in CMT_RAW.items() if info.get("comments")}
THUMBS = load("thumbs.json", {})
RANK = load("rank.json", {"updated": "", "industry": [], "kol": []})

j = lambda o: json.dumps(o, ensure_ascii=False)

shows_js = []
recent = {}
for s in D["shows"]:
    name = s["name"]
    entry = {
        "name": name, "hue": HUE[name], "wd26": s["wd26"],
        "n": s["n"], "n26": s["n26"], "avg26": s["avg26"],
        "views": s["views"], "v26": s["views26"],
        "subs": [s["subs"], s["subs26"]],
        "dur": [fmt_dur(s["dur"]), fmt_dur(s["dur26"])],
        "ctr28": S28["shows"].get(name, {}).get("ctr"),
        "topctr": S28["shows"].get(name, {}).get("topctr"),
        "top": s["top"]["title"], "topv": s["top"]["views"], "topid": s["top"]["id"],
        "top26": s["top26"],
    }
    fields = ", ".join(f"{k}:{j(v)}" for k, v in entry.items())
    shows_js.append("  {" + fields + "}")
    for r in s["recent"]:
        r["ctr28"] = S28["videos"].get(r["id"], {}).get("ctr")
    recent[name] = s["recent"]

ch = D["channel"]
html = open(HTML, encoding="utf-8").read()

def repl(pattern, new, flags=re.S, optional=False):
    """optional=True：單向替換（第二次執行時錨點已消失即跳過）"""
    global html
    m = re.search(pattern, html, flags)
    if not m:
        if optional:
            return
        raise AssertionError(f"anchor not found: {pattern[:60]}")
    html = html[:m.start()] + new + html[m.end():]

# 1. SHOWS
repl(r"const SHOWS = \[.*?\n\];",
     "const SHOWS = [\n" + ",\n".join(shows_js) + ",\n];")
# 2. RECENT ＋ 建議/分析/留言
repl(r"const RECENT = \{.*?\};", "const RECENT = " + j(recent) + ";")
repl(r"const ADVICE = \{.*?\};\n", "const ADVICE = " + j(ADV) + ";\n")
repl(r"const ANALYSIS = \{.*?\};\n", "const ANALYSIS = " + j(ANA) + ";\n")
repl(r"const COMMENTS = \{.*?\};\n", "const COMMENTS = " + j(CMT) + ";\n")
repl(r"const THUMBS = \{.*?\};\n", "const THUMBS = " + j(THUMBS) + ";\n")
repl(r"const RANKS = \{.*?\};\n", "const RANKS = " + j(RANK) + ";\n")
repl(r"const WEEKLY = \[.*?\];\n", "const WEEKLY = " + j(D.get("weekly", [])) + ";\n")
# 3. 總量常數
repl(r"const CHANNEL_TOTAL = [\d]+, TOTAL_2026 = [\d]+;",
     f"const CHANNEL_TOTAL = {ch['totalViews']}, TOTAL_2026 = {ch['views26']};")
# 4. KPI 八卡
kpis = f'''<div class="kpis">
    <div class="card kpi hero">
      <div class="label">訂閱數</div>
      <div class="num">{ch["subs"]/10000:.2f}<small>萬</small></div>
      <div class="foot">{ch["subs"]:,} 位訂閱者</div>
    </div>
    <div class="card kpi hero">
      <div class="label">總觀看數</div>
      <div class="num">{ch["totalViews"]/10000:.1f}<small>萬</small></div>
      <div class="foot">{ch["totalViews"]:,} 次（全頻道 {ch["totalVideos"]} 支）</div>
    </div>
    <div class="card kpi hero">
      <div class="label">觀看訂閱轉化率</div>
      <div class="num">{round(ch["views26"]/ch["subsGained26"])}<small> : 1</small></div>
      <div class="foot">2026：{ch["views26"]/10000:.0f}萬觀看 ÷ {ch["subsGained26"]:,} 訂閱</div>
    </div>
    <div class="card kpi hero">
      <div class="label">2026 訂閱轉化</div>
      <div class="num">+{ch["subsGained26"]/10000:.2f}<small>萬</small></div>
      <div class="foot">+{ch["subsGained26"]:,}（全期間累計 +{ch["subsGainedLife"]:,}）</div>
    </div>
    <div class="card kpi hero">
      <div class="label">平均觀看時長</div>
      <div class="num">{fmt_dur(ch["avgDur26"])}</div>
      <div class="foot">2026 全頻道（全期間 {fmt_dur(ch["avgDurLife"])}）</div>
    </div>
    <div class="card kpi hero">
      <div class="label">平均完播率</div>
      <div class="num">{ch["avgPct26"]:.1f}<small>%</small></div>
      <div class="foot">2026 平均觀看百分比</div>
    </div>
    <div class="card kpi hero">
      <div class="label">縮圖 CTR（近28天）</div>
      <div class="num">{S28["channel"].get("ctr", 0)}<small>%</small></div>
      <div class="foot">曝光 {S28["channel"].get("impressions", 0)/10000:.0f}萬 · Studio {S28.get("period", "")}</div>
    </div>
    <div class="card kpi hero">
      <div class="label">新觀眾占比（近28天）</div>
      <div class="num">{S28.get("newViewers", 0)/(S28.get("newViewers", 0)+S28.get("returningViewers", 1))*100:.0f}<small>%</small></div>
      <div class="foot">新 {S28.get("newViewers", 0)/10000:.1f}萬 vs 回訪 {S28.get("returningViewers", 0)/10000:.1f}萬（影片）</div>
    </div>
  </div>'''
repl(r'<div class="kpis">.*?\n  </div>', kpis)
# 5. 觀眾輪廓：區塊 badge、性別、年齡、40+、流量
repl(r'<span class="badge demo">示意數據 · 需接 YouTube Studio</span>',
     '<span class="badge real">實 · 2026 YouTube Analytics</span>', optional=True)
repl(r'<span class="badge real">實 · 2026 YouTube Analytics</span>',
     '<span class="badge real">2026 YouTube Analytics</span>', optional=True)
g = D["gender"]
repl(r'<div class="gender-bar">.*?</div>\n      <div class="gender-legend">',
     f'''<div class="gender-bar">
        <div style="width:{g["male"]}%;background:var(--blue)" data-tip="男性觀眾 {g["male"]}%（2026 實際）">男 {g["male"]:.0f}%</div>
        <div style="width:{g["female"]}%;background:var(--pink)" data-tip="女性觀眾 {g["female"]}%（2026 實際）">女 {g["female"]:.0f}%</div>
      </div>
      <div class="gender-legend">''')
AGE_LABELS = [("age13-17", "13–17"), ("age18-24", "18–24"), ("age25-34", "25–34"), ("age35-44", "35–44"),
              ("age45-54", "45–54"), ("age55-64", "55–64"), ("age65-", "65+")]
ages = [(lb, D["age"].get(k, 0)) for k, lb in AGE_LABELS]
mx = max(p for _, p in ages) or 1
cols = "\n        ".join(
    f'<div class="col"><span class="v">{p:.0f}%</span><div class="bar" style="height:{max(p/mx*100,2):.0f}%" data-tip="{lb} 歲：{p}%（2026 實際）"></div><span class="t">{lb}</span></div>'
    for lb, p in ages)
repl(r'<div class="age">.*?\n      </div>', f'<div class="age">\n        {cols}\n      </div>')
repl(r'<span class="age40"[^>]*>40\+ 佔 ≈?\d+%</span>',
     f'<span class="age40" data-tip="35–44 取一半＋45 歲以上各組加總（2026 實際）">40+ 佔 {D["age40"]:.0f}%</span>')
repl(r'\.age40\{font-size:11px;font-weight:600;color:#f09dc2;border:1\.5px dashed rgba\(224,86,143,\.55\);',
     '.age40{font-size:11px;font-weight:600;color:#8fc1ff;border:1px solid rgba(61,139,253,.45);', optional=True)
rows = "\n        ".join(
    f'<div class="row"><span class="name">{t["type"]}</span><div class="track"><div class="fill" style="width:{t["pct"]}%" data-tip="{t["type"]} {t["pct"]}%（2026 實際）"></div></div><span class="val">{t["pct"]:.0f}%</span></div>'
    for t in D["traffic"])
repl(r'<h3>流量來源</h3>\n      <div class="rows">.*?\n      </div>',
     f'<h3>流量來源</h3>\n      <div class="rows">\n        {rows}\n      </div>')
# 6. 頁首圖例與資料時間
repl(r'<span>資料時間 [^<]+</span>', f'<span>資料時間 {D["generated"].replace("-", "/")}（數據至 {D["endDate"].replace("-", "/")}）</span>')
repl(r'<span><span class="dot"></span>公開數據實抓</span>\s*<span><span class="dot demo"></span>示意 · 待接 YouTube Studio</span>',
     '<span><span class="dot"></span>YouTube Analytics 官方數據</span>', optional=True)
repl(r'<span><span class="dot demo"></span>「≈」示意：CTR、新舊觀眾比（API 未提供）</span>',
     f'<span><span class="dot"></span>CTR／新觀眾：Studio 近 28 天（{S28.get("period", "")}）</span>', optional=True)
# 7. 頁尾資料說明
repl(r'<footer class="src">.*?</footer>',
     f'''<footer class="src">
  <b>資料說明</b> — 觀看數為 YouTube 即時數（與影片頁面一致）；時長、訂閱轉化、觀眾輪廓來自 <b>YouTube Analytics API</b>（頻道擁有者授權，統計至 {D["endDate"].replace("-", "/")}）；<b>縮圖 CTR、曝光、新觀眾占比</b>來自 <b>YouTube Studio</b>（近 28 天：{S28.get("period", "")}，API 未提供此三項，更新時需重新自 Studio 抓取）。「2026」為該期間實際發生之觀看／訂閱（含舊影片今年的觀看）；「2026 集數」與「平均單支觀看」以 2026 上片影片計。<b>平均更新週期以天計</b>，自該節目 2026 年首支上片日起算。訂閱轉化數＝該影片觀看頁產生的訂閱；觀看訂閱轉化率＝觀看數 ÷ 訂閱轉化數（愈低愈好）。節目數據以 10 檔播放清單歸屬（{sum(s["n"] for s in D["shows"])} 支）；Shorts 與清單外影片計入頻道總量、不入節目卡。
</footer>''')

open(HTML, "w", encoding="utf-8").write(html)
print("✅ applied to", HTML)
