// 在「已登入 Studio 的分頁」（studio.youtube.com 網域）執行：用隱藏 iframe 開各支影片的觸及分頁，讀「縮圖曝光次數／縮圖點閱率（自發布至今）」。
// 把 __IDS__ 換成 studio_ctr_targets.py 的輸出。執行後輪詢 window.__ctrDone，完成後讀 JSON.stringify(window.__ctr)。
// 背景分頁的計時器會被 Chrome 降到約每分鐘一次，所以 6 支並行；38 支約 10–15 分鐘。
// 影片層新觀眾卡在 JL 管理員帳號下會報「系統發生錯誤」，但觸及卡可讀。
window.__ctr = {}; window.__ctrDone = false;
(async () => {
  const ids = "__IDS__".split(" ").filter(Boolean);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const txt = doc => {
    const out = [];
    (function walk(n) {
      if (!n) return;
      if (n.shadowRoot) walk(n.shadowRoot);
      for (const c of (n.childNodes || [])) {
        if (c.nodeType === 3) { const t = c.textContent.trim(); if (t) out.push(t); }
        else if (c.nodeType === 1 && c.tagName !== "SCRIPT" && c.tagName !== "STYLE") walk(c);
      }
    })(doc.body);
    return out.join("|");
  };
  const one = async id => {
    const f = document.createElement("iframe");
    f.style.cssText = "position:fixed;left:-3000px;width:1400px;height:1000px";
    f.src = "https://studio.youtube.com/video/" + id + "/analytics/tab-reach_viewers/period-since_publish";
    document.body.appendChild(f);
    let res = null; const t0 = Date.now();
    while (!res && Date.now() - t0 < 240000) {
      await sleep(2000);
      try {
        const m = txt(f.contentDocument).match(/縮圖曝光次數\|縮圖曝光次數\|([\d.,]+萬?)\|[\s\S]*?縮圖點閱率\|([\d.]+)%/);
        if (m) res = { impr: m[1], ctr: m[2] };
      } catch (e) { res = { err: String(e) }; }
    }
    window.__ctr[id] = res || { fail: 1 };
    f.remove();
  };
  const queue = ids.slice();
  await Promise.all(Array.from({ length: 6 }, async () => {
    while (queue.length) await one(queue.shift());
  }));
  window.__ctrDone = true;
})();
"started";
