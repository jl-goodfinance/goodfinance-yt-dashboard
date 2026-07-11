#!/usr/bin/env python3
"""抓各節目近期 10 支影片的熱門留言（YouTube 公開 innertube API，免金鑰免配額）→ comments.json"""
import json, os, re, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
IKEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"  # YouTube 網頁版公開金鑰
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
      "Accept-Language": "zh-TW"}

def innertube_next(payload):
    body = {"context": {"client": {"clientName": "WEB", "clientVersion": "2.20240701.00.00", "hl": "zh-TW", "gl": "TW"}}}
    body.update(payload)
    req = urllib.request.Request(
        f"https://www.youtube.com/youtubei/v1/next?key={IKEY}&prettyPrint=false",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **UA})
    return json.loads(urllib.request.urlopen(req, timeout=45).read())

def find_comment_token(o):
    """watch 頁 ytInitialData 裡找 comment-item-section 的 continuation token"""
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

def parse_likes(t):
    if not t: return 0
    t = str(t)
    m = re.search(r"([\d,.]+)\s*萬", t)
    if m: return int(float(m.group(1).replace(",", "")) * 10000)
    m = re.search(r"[\d,]+", t)
    return int(m.group(0).replace(",", "")) if m else 0

def get_comments(vid, limit=30):
    html = urllib.request.urlopen(urllib.request.Request(
        f"https://www.youtube.com/watch?v={vid}", headers=UA), timeout=45).read().decode("utf-8", "ignore")
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html)
    if not m: return []
    token = find_comment_token(json.loads(m.group(1)))
    if not token: return []
    comments = []
    for _ in range(2):  # 最多兩頁
        d = innertube_next({"continuation": token})
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
        s = json.dumps(d)
        nxt = re.findall(r'"token":\s*"([^"]+)"', s)
        token = nxt[-1] if nxt else None
        if not token: break
    comments.sort(key=lambda c: -c["likes"])
    return comments[:limit]

D = json.load(open(os.path.join(BASE, "data.json")))
out = {}
for s in D["shows"]:
    total = 0
    for v in s["recent"]:
        try:
            cs = get_comments(v["id"])
        except Exception as e:
            cs = []
        out[v["id"]] = {"show": s["name"], "title": v["title"], "n": len(cs), "comments": cs}
        total += len(cs)
    print(f'{s["name"]}: {total} 則 / {len(s["recent"])} 支')
json.dump(out, open(os.path.join(BASE, "comments.json"), "w"), ensure_ascii=False, indent=1)
print("✅ comments.json written")
