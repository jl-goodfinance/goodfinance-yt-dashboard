#!/usr/bin/env python3
"""成本效率（CAC）私人頁：讀 data.json（公開）＋ ~/.config/goodfinance-yt/budget.json（本機、不進 repo）→ cac.html（.gitignore）。
口徑（JL 2026-09-04 定案）：成本＝第二層（節目製作費＋跨節目共用攤提，預算單價）；節目層訂閱＝影片頁歸因；頻道層另列淨增版；上線滿 30 天才算成熟。"""
import json, os, html
from datetime import date, datetime

CONF = os.path.expanduser("~/.config/goodfinance-yt/budget.json")
B = json.load(open(CONF, encoding="utf-8"))
D = json.load(open("data.json", encoding="utf-8"))
OUT = "cac.html"
TODAY = date.fromisoformat(D["generated"])
MATURE = int(B.get("mature_days", 30))
ORDER = ["Good Morning 美好", "Good Invest 美好投資", "Better Living 美好生活", "Good Income", "Entrepreneurship"]
COLOR = {"Good Morning 美好": "#3d8bfd", "Good Invest 美好投資": "#7c6ff0", "Better Living 美好生活": "#c77a1c",
         "Good Income": "#15905f", "Entrepreneurship": "#e0568f"}
SHORT = {"Good Morning 美好": "GM", "Good Invest 美好投資": "GI", "Better Living 美好生活": "BL",
         "Good Income": "Good Income", "Entrepreneurship": "Entre"}
shared_unit = B["shared"]["annual"] / B["shared"]["episodes"]

def num(v): return f"{v:,.0f}"
def wan(v): return f"{v/10000:.1f}萬" if v >= 10000 else num(v)
def esc(s): return html.escape(str(s))

rows, all_eps, months = [], [], {}
for name in ORDER:
    s = next(x for x in D["shows"] if x["name"] == name)
    b = B["shows"][name]
    unit_prod = b["annual"] / b["episodes"]
    unit = unit_prod + shared_unit
    eps = [e for e in s.get("eps26", []) if not e.get("sch") and e["pub"] <= TODAY.isoformat()]
    for e in eps:
        e["show"] = name; e["unit"] = unit
        e["age"] = (TODAY - date.fromisoformat(e["pub"])).days
        e["mature"] = e["age"] >= MATURE
        e["cac"] = unit / e["subs"] if e["subs"] else None
        m = e["pub"][:7]; mm = months.setdefault(m, {"cost": 0, "subs": 0, "n": 0, "immature": 0})
        mm["cost"] += unit; mm["subs"] += e["subs"]; mm["n"] += 1; mm["immature"] += (not e["mature"])
    all_eps += eps
    mat = [e for e in eps if e["mature"]]
    n_all, n_mat = len(eps), len(mat)
    subs_all = sum(e["subs"] for e in eps); subs_mat = sum(e["subs"] for e in mat)
    rows.append(dict(name=name, unit=unit, unit_prod=unit_prod, n_all=n_all, n_mat=n_mat, budget_eps=b["episodes"],
                     annual=b["annual"], cost_all=unit * n_all, cost_mat=unit * n_mat, subs_all=subs_all, subs_mat=subs_mat,
                     cac_mat=(unit * n_mat / subs_mat) if subs_mat else None,
                     cac_all=(unit * n_all / subs_all) if subs_all else None,
                     per_ep=(subs_mat / n_mat) if n_mat else 0))

cost_total = sum(r["cost_all"] for r in rows); subs_attr = sum(r["subs_all"] for r in rows)
cost_mat_total = sum(r["cost_mat"] for r in rows); subs_mat_total = sum(r["subs_mat"] for r in rows)
net26 = sum(w["net"] for w in D["weekly"])
gained26 = D["channel"]["subsGained26"]
cac_attr = cost_total / subs_attr if subs_attr else 0
cac_mat = cost_mat_total / subs_mat_total if subs_mat_total else 0
cac_net = cost_total / net26 if net26 else 0
months_elapsed = TODAY.month - 1 + TODAY.day / 30
staff_ytd = B["staff"]["annual"] * months_elapsed / 12
cac_full = (cost_total + staff_ytd) / subs_attr if subs_attr else 0
mat_eps = [e for e in all_eps if e["mature"]]
best = sorted([e for e in mat_eps if e["cac"]], key=lambda e: e["cac"])[:8]
worst = sorted(mat_eps, key=lambda e: -(e["cac"] or 1e12))[:8]
max_month_cac = max((m["cost"] / m["subs"]) for m in months.values() if m["subs"]) if months else 1

def chip(name):
    c = COLOR[name]; return f'<span class="chip" style="--c:{c}">{esc(SHORT[name])}</span>'
def cac_cls(v):
    if v is None: return "na"
    return "good" if v <= cac_mat * 0.85 else ("bad" if v >= cac_mat * 1.3 else "")

show_rows = "".join(f'''<tr>
  <td class="nm">{chip(r["name"])}<span>{esc(r["name"])}</span></td>
  <td class="n">{r["n_mat"]}<small>/ {r["n_all"]} 已上片</small></td>
  <td class="n">{num(r["unit"])}<small>製作 {num(r["unit_prod"])} ＋ 共用 {num(shared_unit)}</small></td>
  <td class="n">{wan(r["cost_all"])}<small>年預算 {wan(r["annual"])}</small></td>
  <td class="n">{num(r["subs_mat"])}<small>{r["per_ep"]:.0f} / 集</small></td>
  <td class="n cac {cac_cls(r["cac_mat"])}"><b>{num(r["cac_mat"]) if r["cac_mat"] else "—"}</b></td>
  <td class="n mut">{num(r["cac_all"]) if r["cac_all"] else "—"}</td>
  <td class="bar"><i style="width:{min(100, r["n_all"]/r["budget_eps"]*100):.1f}%;background:{COLOR[r["name"]]}"></i><small>{r["n_all"]} / {r["budget_eps"]} 集（{r["n_all"]/r["budget_eps"]*100:.0f}%）</small></td>
</tr>''' for r in rows)

month_rows = ""
for m in sorted(months):
    x = months[m]; cac = x["cost"] / x["subs"] if x["subs"] else None
    w = (cac / max_month_cac * 100) if cac else 0
    tag = f'<small class="pre">含 {x["immature"]} 支未滿 {MATURE} 天</small>' if x["immature"] else ""
    month_rows += f'''<div class="mrow"><span class="ml">{m[:4]}/{m[5:]}</span>
      <span class="mbar"><i style="width:{w:.1f}%"></i></span>
      <span class="mv"><b>{num(cac) if cac else "—"}</b><small>{x["n"]} 集 · {wan(x["cost"])} · +{num(x["subs"])}</small>{tag}</span></div>'''

def ep_li(e):
    cac = f"{num(e['cac'])}" if e["cac"] else "∞"
    return f'''<li>{chip(e["show"])}<span class="et"><a href="https://www.youtube.com/watch?v={e["id"]}" target="_blank" rel="noopener">{esc(e["t"])}</a><small>{e["pub"][5:].replace("-","/")} · +{num(e["subs"])} 訂閱 · 互動觀看 {wan(e["ev"] or e["views"])}</small></span><b>{cac}</b></li>'''

CSS = """
:root{--bg:#080c14;--card:rgba(148,170,220,.055);--card2:rgba(148,170,220,.035);--line:rgba(148,170,220,.14);--ink:#e9edf6;--sub:#b7c1d6;--mut:#8d97b0;
--blue:#3d8bfd;--purple:#7c6ff0;--good:#3dbb87;--warn:#e8a04b;--bad:#e0568f;--grad:linear-gradient(100deg,#3d8bfd,#7c6ff0)}
*{box-sizing:border-box}html{background:var(--bg)}
body{margin:0;padding:0 20px 56px;background:var(--bg);color:var(--ink);font:14px/1.55 -apple-system,"PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif;overflow-x:hidden}
.wrap{max-width:1080px;margin:0 auto}
header{padding:34px 4px 10px}
.eyebrow{font-size:11px;letter-spacing:.22em;color:var(--sub);text-transform:uppercase;display:flex;align-items:center;gap:10px}
.lock{font-size:10px;letter-spacing:.08em;border:1px solid rgba(224,86,143,.5);color:#f09dc2;border-radius:99px;padding:1px 8px}
h1{margin:8px 0 6px;font-size:30px;font-weight:800;letter-spacing:-.01em;text-wrap:balance}
h1 .grad{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.meta{color:var(--mut);font-size:12.5px}
.rules{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 6px}
.rule{font-size:11.5px;color:var(--sub);border:1px solid var(--line);border-radius:99px;padding:4px 11px;background:var(--card2)}
.rule b{color:var(--ink);font-weight:600}
h2{font-size:15px;font-weight:700;color:#c3cfec;margin:30px 0 10px;display:flex;align-items:baseline;gap:10px}
h2 small{font-size:11.5px;color:var(--mut);font-weight:400}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.kpi .label{font-size:11.5px;color:var(--sub)}
.kpi .num{font-size:30px;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:-.01em;line-height:1.15;margin:4px 0 2px;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.kpi .num small{font-size:13px;-webkit-text-fill-color:var(--sub);margin-left:3px}
.kpi .foot{font-size:11.5px;color:var(--mut);line-height:1.5}
.kpi.ref .num{background:none;-webkit-text-fill-color:var(--sub);color:var(--sub)}
.tbl{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:13px}
th{text-align:left;font-size:11px;color:var(--mut);font-weight:600;padding:6px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th.n,td.n{text-align:right}
td{padding:10px 10px;border-bottom:1px solid var(--line);vertical-align:middle}
tr:last-child td{border-bottom:0}
td small{display:block;font-size:10.5px;color:var(--mut);font-weight:400;line-height:1.3;margin-top:2px}
td.nm{display:flex;align-items:center;gap:9px;font-weight:600;white-space:nowrap}
td.cac b{font-size:16px}
td.cac.good b{color:var(--good)}td.cac.bad b{color:var(--bad)}
td.mut{color:var(--mut)}
td.bar{min-width:150px}
td.bar i{display:block;height:5px;border-radius:3px;background:var(--blue);opacity:.9}
td.bar{position:relative}
td.bar small{margin-top:5px}
.chip{font-size:10.5px;font-weight:700;color:var(--c);border:1px solid color-mix(in srgb,var(--c) 55%,transparent);border-radius:99px;padding:1px 8px;white-space:nowrap}
.months{display:flex;flex-direction:column;gap:9px}
.mrow{display:grid;grid-template-columns:64px 1fr 220px;align-items:center;gap:14px}
.ml{font-size:12.5px;color:var(--sub);font-variant-numeric:tabular-nums}
.mbar{height:10px;background:rgba(148,170,220,.08);border-radius:5px;overflow:hidden}
.mbar i{display:block;height:100%;background:var(--grad);border-radius:5px}
.mv{font-size:12px;color:var(--sub);display:flex;flex-direction:column;line-height:1.35}
.mv b{color:var(--ink);font-size:14px}.mv small{color:var(--mut);font-size:10.5px}
.mv .pre{color:var(--warn)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
ol.eps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}
ol.eps li{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--line)}
ol.eps li:last-child{border-bottom:0}
.et{flex:1;min-width:0;display:flex;flex-direction:column;line-height:1.35}
.et a{color:var(--ink);text-decoration:none;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.et a:hover{text-decoration:underline}.et small{color:var(--mut);font-size:10.5px}
ol.eps b{font-size:14px;font-variant-numeric:tabular-nums;min-width:56px;text-align:right}
.notes{font-size:11.5px;color:var(--mut);line-height:1.7;margin-top:26px;border-top:1px solid var(--line);padding-top:14px}
.notes b{color:var(--sub)}
@media (max-width:820px){.kpis{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}.mrow{grid-template-columns:52px 1fr 170px;gap:10px}}
@media (max-width:560px){body{padding:0 12px 40px}h1{font-size:24px}.kpi .num{font-size:24px}.mrow{grid-template-columns:48px 1fr;}.mv{grid-column:1/-1}}
"""

HTML = f'''<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>美好 YT 成本效率</title>
<style>{CSS}</style>
<div class="wrap">
<header>
  <div class="eyebrow">GOOD FINANCE · YOUTUBE <span class="lock">🔒 僅 JL</span></div>
  <h1>成本效率 <span class="grad">每位訂閱者的取得成本</span></h1>
  <div class="meta">資料時間 {TODAY.isoformat().replace("-","/")}（訂閱歸因至 {D["endDate"].replace("-","/")}）· 預算：{esc(B["source"])}</div>
  <div class="rules">
    <span class="rule">成本口徑 <b>第二層＝製作費＋共用攤提</b>（預算單價，不含人事）</span>
    <span class="rule">訂閱口徑 <b>影片頁歸因</b>（頻道層另列淨增版）</span>
    <span class="rule">成熟門檻 <b>上線滿 {MATURE} 天</b>才計入正式 CAC</span>
    <span class="rule">共用攤提 <b>{num(shared_unit)} 元／集</b>（{wan(B["shared"]["annual"])} ÷ {B["shared"]["episodes"]} 集）</span>
  </div>
</header>

<div class="kpis">
  <div class="card kpi"><div class="label">CAC（成熟集數）</div><div class="num">{num(cac_mat)}<small>元 / 訂閱</small></div>
    <div class="foot">{wan(cost_mat_total)} ÷ {num(subs_mat_total)} 訂閱 · 五檔已上線滿 {MATURE} 天的 {sum(r["n_mat"] for r in rows)} 集</div></div>
  <div class="card kpi"><div class="label">CAC（含初步，全部已上片）</div><div class="num">{num(cac_attr)}<small>元 / 訂閱</small></div>
    <div class="foot">{wan(cost_total)} ÷ {num(subs_attr)} 訂閱 · {sum(r["n_all"] for r in rows)} 集，新集訂閱仍在累積、會下修</div></div>
  <div class="card kpi"><div class="label">CAC（頻道淨增口徑）</div><div class="num">{num(cac_net)}<small>元 / 訂閱</small></div>
    <div class="foot">同一筆成本 ÷ 2026 頻道淨增 {num(net26)}（含流失、含 Shorts 與清單外影片；頻道歸因 +{num(gained26)}）</div></div>
  <div class="card kpi ref"><div class="label">全成本參考（含人事）</div><div class="num">{num(cac_full)}<small>元 / 訂閱</small></div>
    <div class="foot">人事 {wan(B["staff"]["annual"])} 按 {months_elapsed:.1f} 個月折算 {wan(staff_ytd)}；不拆節目，只看年度量級</div></div>
</div>

<h2>各節目 <small>CAC 綠＝優於頻道成熟值 15% 以上，紅＝差 30% 以上</small></h2>
<div class="card tbl"><table>
<tr><th>節目</th><th class="n">成熟集數</th><th class="n">每集成本</th><th class="n">已投入</th><th class="n">歸因訂閱（成熟）</th><th class="n">CAC 成熟</th><th class="n">CAC 含初步</th><th>集數執行率（vs 年預算）</th></tr>
{show_rows}
</table></div>

<h2>依上片月份 <small>每月上片集數的成本 ÷ 該批影片至今累積訂閱（愈右愈貴）</small></h2>
<div class="card months">{month_rows}</div>

<div class="two">
  <div><h2>最划算的集 <small>成熟集數 · 元／訂閱</small></h2><div class="card"><ol class="eps">{"".join(ep_li(e) for e in best)}</ol></div></div>
  <div><h2>最貴的集 <small>成熟集數 · 元／訂閱</small></h2><div class="card"><ol class="eps">{"".join(ep_li(e) for e in worst)}</ol></div></div>
</div>

<div class="notes">
<b>怎麼讀</b> — CAC＝該批影片的製作成本（預算單價 × 集數）÷ 這些影片觀看頁帶來的訂閱。訂閱會持續累積數月，所以「成熟」值才是可比較的正式數字；含初步的版本一定偏高。GM 的價值在每日觸及與曝光，CAC 只反映它換訂閱的效率，不宜單用 CAC 評 GM。<br>
<b>成本假設</b> — {esc(B["tier"])}。各節目每集製作費＝年預算 ÷ 預算集數（{"、".join(f"{SHORT[r['name']]} {wan(r['annual'])}/{r['budget_eps']} 集" for r in rows)}）；共用項目 {wan(B["shared"]["annual"])} 依 {B["shared"]["episodes"]} 集攤提。實際請採購數與預算單價的差異未反映。<br>
<b>訂閱口徑</b> — YouTube Analytics 影片頁歸因（subscribersGained），新片 1–3 天內尚未完整歸因；淨增版本＝訂閱減流失。觀看數皆為互動觀看（8/24 計法變更後本站口徑）。<br>
<b>保密</b> — 本頁由本機預算檔生成，預算數字不在 GitHub repo；此 artifact 未分享，僅你可見。
</div>
</div>
'''
open(OUT, "w", encoding="utf-8").write(HTML)
print(f"✅ {OUT}｜成熟 CAC {cac_mat:,.0f}｜含初步 {cac_attr:,.0f}｜淨增口徑 {cac_net:,.0f}｜全成本 {cac_full:,.0f}｜成熟集數 {len(mat_eps)}/{len(all_eps)}")
