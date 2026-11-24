#!/usr/bin/env python3
"""抓各節目近期影片的熱門留言（YouTube 公開 innertube API，免金鑰免配額）→ comments.json

抓不到（例外、被擋、回應結構不符、空清單）時，保留 comments.json 既有的該支留言、不覆寫成空的，
並把失敗原因印在輸出（Actions log）方便追查。
"""
import json, os, re, time, urllib.error, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "comments.json")
IKEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"  # YouTube 網頁版公開金鑰
CLIENT_VERSION = "2.20261123.00.00"               # 網頁版 clientVersion（2026-11-24 取自 watch 頁 ytcfg）
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36",
      "Accept-Language": "zh-TW,zh;q=0.9",
      # 已回答過同意頁的 cookie：避免 watch 頁被導去 consent.youtube.com
      "Cookie": "SOCS=CAI; CONSENT=YES+cb"}
TIMEOUT = 20        # 每個請求的逾時秒數
ATTEMPTS = 2        # 每支影片最多試幾次
BLOCK_AFTER = 6     # 連續這麼多支失敗 → 視為本輪 IP 被擋，其餘不再打、直接沿用既有

class FetchError(Exception):
    """抓不到留言（訊息即失敗原因）"""

def _open(req):
    try:
        return urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code} {e.reason}（{req.full_url.split('?')[0]}）")
    except Exception as e:
        raise FetchError(f"{type(e).__name__}: {e}（{req.full_url.split('?')[0]}）")

def innertube_next(payload):
    body = {"context": {"client": {"clientName": "WEB", "clientVersion": CLIENT_VERSION, "hl": "zh-TW", "gl": "TW"}}}
    body.update(payload)
    req = urllib.request.Request(
        f"https://www.youtube.com/youtubei/v1/next?key={IKEY}&prettyPrint=false",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Origin": "https://www.youtube.com",
                 "X-YouTube-Client-Name": "1", "X-YouTube-Client-Version": CLIENT_VERSION, **UA})
    raw = _open(req).read()
    try:
        return json.loads(raw)
    except ValueError:
        raise FetchError(f"next 回應不是 JSON（{len(raw)} bytes，開頭 {raw[:80]!r}）")

def find_comment_token(o):
    """在 watch/next 資料裡找 comment-item-section 的 continuation token"""
    if isinstance(o, dict):
        if o.get("sectionIdentifier") == "comment-item-section":
            s = json.dumps(o)
            m = re.search(r'"token":\s*"([^"]+)"', s)
            if m: return m.group(1)
        for v in o.values():
            t = find_comment_token(v)
            if t: return t
    elif isinstance(o, list):
        for v in o:
            t = find_comment_token(v)
            if t: return t
    return None

def describe_page(resp, html):
    """watch 頁拿不到資料時，描述實際拿到什麼頁（同意頁／機器人驗證／其他）"""
    url = resp.geturl()
    marks = [name for name, pat in [
        ("同意頁", r"consent\.youtube\.com|consent\.google\.com"),
        ("機器人驗證", r"google\.com/sorry|unusual traffic|confirm you.{0,10}not a bot|確認你不是機器人"),
        ("要求登入", r'"LOGIN_REQUIRED"|accounts\.google\.com/ServiceLogin'),
    ] if re.search(pat, url + html[:400000])]
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    return (f"最終網址 {url.split('?')[0]}，{len(html)} 字元，title={title.group(1).strip()[:40] if title else None!r}"
            + (f"，疑似：{'、'.join(marks)}" if marks else ""))

def get_token(vid):
    """先用 next 端點（JSON，不經 watch 頁 HTML）取留言 token；拿不到再退回解析 watch 頁"""
    why = []
    try:
        d = innertube_next({"videoId": vid})
        token = find_comment_token(d)
        if token: return token
        why.append(f"next 無留言 token（keys={list(d.keys())[:5]}）")
    except FetchError as e:
        why.append(str(e))
    try:
        resp = _open(urllib.request.Request(f"https://www.youtube.com/watch?v={vid}", headers=UA))
        html = resp.read().decode("utf-8", "ignore")
        m = re.search(r"var ytInitialData = (\{.*?\});</script>", html)
        if not m:
            why.append("watch 頁沒有 ytInitialData：" + describe_page(resp, html))
        else:
            token = find_comment_token(json.loads(m.group(1)))
            if token: return token
            why.append("watch 頁無留言 token（留言可能已關閉）")
    except FetchError as e:
        why.append(str(e))
    raise FetchError("；".join(why))

def parse_likes(t):
    if not t: return 0
    t = str(t)
    m = re.search(r"([\d,.]+)\s*萬", t)
    if m: return int(float(m.group(1).replace(",", "")) * 10000)
    m = re.search(r"[\d,]+", t)
    return int(m.group(0).replace(",", "")) if m else 0

def page_items(d):
    """留言回應最外層的 continuationItems（留言串＋結尾的「下一頁」）"""
    items = []
    for ep in d.get("onResponseReceivedEndpoints", []):
        for v in ep.values():
            if isinstance(v, dict):
                items += v.get("continuationItems", [])
    return items

def header_count(o):
    """留言區標頭（commentsHeaderRenderer）顯示的留言總數；找不到回 None"""
    if isinstance(o, dict):
        h = o.get("commentsHeaderRenderer")
        if isinstance(h, dict):
            txt = "".join(r.get("text", "") for r in h.get("countText", {}).get("runs", []))
            m = re.search(r"[\d,]+", txt)
            if m: return int(m.group(0).replace(",", ""))
        for v in o.values():
            n = header_count(v)
            if n is not None: return n
    elif isinstance(o, list):
        for v in o:
            n = header_count(v)
            if n is not None: return n
    return None

def get_comments(vid, limit=30):
    """回傳 (留言清單, 標頭顯示的留言總數或 None)；抓不到丟 FetchError"""
    token = get_token(vid)
    comments, header_total = [], None
    for _ in range(2):  # 最多兩頁（每頁 20 則熱門留言）
        d = innertube_next({"continuation": token})
        if header_total is None:
            header_total = header_count(d)
        # 新版留言在 frameworkUpdates 的 commentEntityPayload
        muts = (d.get("frameworkUpdates", {}).get("entityBatchUpdate", {}).get("mutations", []))
        for mu in muts:
            p = mu.get("payload", {}).get("commentEntityPayload")
            if not p: continue
            props = p.get("properties", {})
            toolbar = p.get("toolbar", {})
            author = p.get("author", {})
            comments.append({
                "text": props.get("content", {}).get("content", "")[:220].replace("\n", " "),
                "likes": parse_likes(toolbar.get("likeCountNotliked") or toolbar.get("likeCountLiked")),
                "author": author.get("displayName", ""),
                "replies": parse_likes(toolbar.get("replyCount")),
            })
        if len(comments) >= limit: break
        # 下一頁 token 只認最外層結尾的 continuationItemRenderer
        # （舊寫法取回應裡「最後一個 token」，沒有下一頁時會拿到某串回覆或排序選單的 token，混進回覆或重複留言）
        token = None
        for it in page_items(d):
            if "continuationItemRenderer" in it:
                m = re.search(r'"token":\s*"([^"]+)"', json.dumps(it))
                if m: token = m.group(1)
        if not token: break
    if not comments:
        if header_total == 0:
            return [], 0
        raise FetchError(f"回應裡沒有留言（標頭留言數={header_total}，keys={list(d.keys())[:5]}）")
    comments.sort(key=lambda c: -c["likes"])
    return comments[:limit], header_total

def fetch_with_retry(vid):
    for i in range(ATTEMPTS):
        try:
            return get_comments(vid)
        except FetchError as e:
            err = e
        except Exception as e:  # 回應結構變動等非預期錯誤，同樣視為抓不到
            err = FetchError(f"{type(e).__name__}: {e}")
        if i + 1 < ATTEMPTS: time.sleep(3)
    raise err

def main():
    D = json.load(open(os.path.join(BASE, "data.json")))
    try:
        old = json.load(open(OUT))
    except Exception:
        old = {}
    out, fails, kept, streak, blocked = {}, [], 0, 0, False
    for s in D["shows"]:
        total = show_fail = 0
        for v in s["recent"]:
            vid, prev, reason = v["id"], (old.get(v["id"]) or {}).get("comments") or [], None
            if blocked:
                reason = "本輪疑似被擋，未嘗試"
            else:
                try:
                    cs, header_total = fetch_with_retry(vid)
                    streak = 0
                    if not cs and prev:  # 抓到空清單但原本有留言：照樣保留，不洗掉
                        reason = "回應為 0 則（標頭留言數=0）但原本有留言"
                except FetchError as e:
                    reason = str(e)
                    streak += 1
                    if streak >= BLOCK_AFTER:
                        blocked = True
                        print(f"  ⛔ 連續 {streak} 支失敗，視為本輪 IP 被擋：其餘影片不再嘗試，沿用既有留言")
            if reason:
                cs = prev
                show_fail += 1
                kept += bool(prev)
                fails.append((vid, reason))
                if reason != "本輪疑似被擋，未嘗試":
                    print(f"  ⚠️ {vid} 抓不到：{reason} → 沿用既有 {len(prev)} 則")
            out[vid] = {"show": s["name"], "title": v["title"], "n": len(cs), "comments": cs}
            total += len(cs)
        print(f'{s["name"]}: {total} 則 / {len(s["recent"])} 支' + (f"（{show_fail} 支抓不到、沿用既有）" if show_fail else ""))
    tmp = OUT + ".tmp"
    json.dump(out, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    n = len(out)
    print(f"✅ comments.json written：成功 {n - len(fails)} 支、抓不到 {len(fails)} 支（其中 {kept} 支沿用既有留言）")
    if fails and os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning title=留言抓取::{len(fails)}/{n} 支抓不到{'（本輪疑似被擋）' if blocked else ''}，已沿用既有留言。首例 {fails[0][0]}：{fails[0][1][:300]}")

if __name__ == "__main__":
    main()
