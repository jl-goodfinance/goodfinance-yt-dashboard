// 在「以 social@goodfinance.com（頻道擁有者）身分登入 Studio 的分頁」執行：用隱藏 iframe 開各支影片的觀眾分頁，
// 讀「觀眾（按觀看行為）→ 新觀眾 · 首次收看你的頻道 NN.N%（自影片上傳至今）」。
// 把 __IDS__ 換成 studio_newret_targets.py 的輸出。執行後輪詢 window.__nrDone，完成後讀 JSON.stringify(window.__nr)。
// 結果：{pct, jl} 有值；{na:1}＝Studio 顯示「觀眾資料不足」（太新或超過 90 天）；jl:true 代表跑到了 JL 管理員身分（該卡會報錯，數字不可信）。
// 注意：jl@ 管理員帳號下這張卡一律「系統發生錯誤」，要用 social@ 的分頁。背景分頁計時器會被節流，分頁放前景跑最快。
window.__nr = {}; window.__nrDone = false;
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
    f.src = "https://studio.youtube.com/video/" + id + "/analytics/tab-build_audience/period-since_publish";
    document.body.appendChild(f);
    let res = null; const t0 = Date.now();
    while (!res && Date.now() - t0 < 180000) {
      await sleep(2000);
      try {
        const s = txt(f.contentDocument);
        const m = s.match(/新觀眾\|首次收看你的頻道\|([\d.]+)%/);
        if (m) res = { pct: parseFloat(m[1]), jl: s.includes("JL羅申駿") };
        else if (s.includes("觀眾資料不足")) res = { na: 1 };
      } catch (e) { res = { err: String(e) }; }
    }
    window.__nr[id] = res || { fail: 1 };
    f.remove();
  };
  const queue = ids.slice();
  await Promise.all(Array.from({ length: 6 }, async () => {
    while (queue.length) await one(queue.shift());
  }));
  window.__nrDone = true;
})();
"started";
