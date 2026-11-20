// Studio 逐集「觸及」抓取：A/B 測試各版本（標題、觀看時間占比、勝負、縮圖網址）、
// 自發布至今與「前 24 小時」的曝光與 CTR（團隊 KR 口徑）、流量來源占比。
// 用法：在已登入 studio.youtube.com 的分頁（內建瀏覽器優先）以 javascript_tool 執行本檔，
//   再呼叫 window.__runReach([...videoId])；結果逐支寫進 sessionStorage 的 reach_<id>，
//   全部完成後 window.__reachDone === true。用 studio_reach_merge.py 併進 studio_reach.json。
// 注意（2026-11-20 實測）：
//   1. 分頁在背景超過 5 分鐘會被瀏覽器深度節流，計時器變成每分鐘一次；
//      先開一條本頁自連的 WebRTC data channel 即可免除（下面 keepAwake）。
//   2. 並行最多 2 個 iframe；4 個會讓分頁的 renderer 當掉。
//   3. A/B 縮圖是 lazy load，iframe 必須在畫面內（opacity 0.01）且捲到該圖才有網址。
//   4. 「前 24 小時」沒有對應網址，只能點「更多 › 前 24 小時」。上片未滿 24 小時的影片沒有這個選項。
(async () => {
  if (!window.__rtc) {
    try {
      const a = new RTCPeerConnection(), b = new RTCPeerConnection();
      a.onicecandidate = e => e.candidate && b.addIceCandidate(e.candidate);
      b.onicecandidate = e => e.candidate && a.addIceCandidate(e.candidate);
      const dc = a.createDataChannel("k"); window.__rtc = { a, b, dc };
      const o = await a.createOffer(); await a.setLocalDescription(o); await b.setRemoteDescription(o);
      const an = await b.createAnswer(); await b.setLocalDescription(an); await a.setRemoteDescription(an);
    } catch (e) { /* 沒有也能跑，只是久了會變慢 */ }
  }
})();

window.__runReach = function (IDS) {
  window.__reachDone = false; window.__reachLog = []; window.__t0 = Date.now();
  (async () => {
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const txt = doc => { const out = []; (function walk(n) { if (!n) return; if (n.shadowRoot) walk(n.shadowRoot); for (const c of (n.childNodes || [])) { if (c.nodeType === 3) { const t = c.textContent.trim(); if (t) out.push(t); } else if (c.nodeType === 1 && c.tagName !== "SCRIPT" && c.tagName !== "STYLE") walk(c); } })(doc.body); return out.join("|"); };
    const findLeaf = (doc, label) => { const r = []; (function walk(n) { if (!n) return; if (n.shadowRoot) walk(n.shadowRoot); for (const c of (n.children || [])) { if (c.children.length === 0 && (c.textContent || "").trim() === label) r.push(c); walk(c); } })(doc.body); return r; };
    const up = (el, test) => { let t = el; for (let k = 0; k < 8 && t; k++) { if (test(t)) return t; t = t.parentElement || (t.getRootNode && t.getRootNode().host); } return el; };
    const head = s => {
      const k = s.indexOf("主要指標"); const h = k < 0 ? "" : s.slice(k); const m = re => { const x = h.match(re); return x ? x[1] : null; };
      return { imp: m(/縮圖曝光次數\|([\d.,]+萬?)\|/), from: m(/縮圖曝光次數\|[\d.,]+萬?\|([^|]+)\|/), views: m(/\|觀看次數\|([\d.,]+萬?)\|/), ctr: m(/縮圖點閱率\|([\d.]+)%/) };
    };
    const one = async (id, slot) => {
      const f = document.createElement("iframe");
      f.style.cssText = `position:fixed;left:${slot * 20}px;top:0;width:1400px;height:1000px;opacity:0.01;pointer-events:none;z-index:-1`;
      f.src = `https://studio.youtube.com/video/${id}/analytics/tab-reach_viewers/period-since_publish`; document.body.appendChild(f);
      const res = {};
      try {
        let s = ""; for (let i = 0; i < 30; i++) { await sleep(1000); try { s = txt(f.contentDocument); if (s.includes("觀眾如何找到這部影片") || s.includes("推薦這部影片的內容")) break; } catch (e) { } }
        await sleep(1500);
        const doc = f.contentDocument;
        const imgs = []; (function walk(n) { if (!n) return; if (n.shadowRoot) walk(n.shadowRoot); for (const c of (n.children || [])) { if (c.tagName === "IMG" && /ytCoreImageHost/.test(c.className || "")) imgs.push(c); walk(c); } })(doc.body);
        for (const im of imgs.slice(0, 3)) { try { im.scrollIntoView({ block: "center" }); } catch (e) { } }
        await sleep(1000);
        s = txt(doc);
        res.since = head(s);
        const im = s.match(/曝光次數對觀看時間的影響\|[^|]*\|縮圖曝光次數\|([^|]+)\|縮圖點閱率\|([\d.]+)%\|因曝光產生的互動觀看次數\|([^|]+)\|平均觀看時間\|([^|]+)\|/);
        if (im) res.impact = { imp: im[1], ctr: im[2], ev: im[3], avd: im[4] };
        const a = s.indexOf("A/B 測試|"), b = s.indexOf("|觀眾如何找到這部影片");
        res.ab = a >= 0 ? s.slice(a + 7, b > a ? b : a + 900).replace(/[‎⁨⁩]/g, "") : null;
        const t0 = s.indexOf("觀眾如何找到這部影片|"), t1 = s.indexOf("|外部網站或應用程式");
        res.traffic = t0 >= 0 ? s.slice(t0, t1 > t0 ? t1 : t0 + 220).split("|").slice(2).join("|") : null;
        res.abImg = imgs.map(x => x.currentSrc || x.src || "").filter(u => u.includes("/" + id + "/") && /custom_\d/.test(u));
        const more = findLeaf(doc, "更多");
        if (more.length) {
          up(more[0], t => t.tagName === "BUTTON" || (t.getAttribute && /button|tab/.test(t.getAttribute("role") || ""))).click(); await sleep(1000);
          const it = findLeaf(doc, "前 24 小時");
          if (it.length) {
            up(it[0], t => t.tagName === "BUTTON" || (t.getAttribute && /menuitem|option/.test(t.getAttribute("role") || ""))).click();
            let h = ""; for (let i = 0; i < 14; i++) { await sleep(1000); h = txt(doc); if (/主要指標\|7 天\|28 天\|自影片發布至今\|前 24 小時\|縮圖曝光次數\|[\d.,]+萬?\|/.test(h)) break; }
            await sleep(1000); h = txt(doc); res.h24 = /前 24 小時\|縮圖曝光次數/.test(h) ? head(h) : "not-switched";
          } else res.h24 = "no-menu-item";
        } else res.h24 = "no-more";
      } catch (e) { res.err = String(e); }
      try { sessionStorage.setItem("reach_" + id, JSON.stringify(res)); } catch (e) { }
      window.__reachLog.push(id);
      f.src = "about:blank"; f.remove();
    };
    const q = IDS.slice();
    await Promise.all([0, 1].map(async slot => { while (q.length) { const id = q.shift(); if (sessionStorage.getItem("reach_" + id)) continue; await one(id, slot); } }));
    window.__reachDone = true;
  })();
};
