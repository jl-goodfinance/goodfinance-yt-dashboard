# 美好證券 YouTube 節目數據 Dashboard

- **Dashboard**：`docs/index.html`（GitHub Pages 自動部署）
- **每小時**：GitHub Actions 跑 `fetch_data.py`（Analytics＋Data API，憑證在 repo Secrets）→ `fetch_comments.py`（innertube 留言）→ `fetch_thumbs.py`（縮圖快取）→ `apply_data.py docs/index.html`
- **每週一**：本機 Claude 排程 `yt-weekly-advisor` 更新 Studio 曝光/CTR（`studio_scrape_raw.txt` → `build_studio.py`）、重寫 `advice.json`（顧問建議）與 `analysis.json`（留言洞察），commit push 並重發 Claude artifact
- 憑證：`YT_CLIENT_ID` / `YT_CLIENT_SECRET` / `YT_REFRESH_TOKEN`（Actions Secrets；本機讀 `~/.config/goodfinance-yt/`）
- 注意：CTR／曝光／新觀眾比為 YouTube Studio 專屬（API 不提供），僅每週更新
- **逐日 CTR**：`fetch_reach.py` 用 YouTube Reporting API 報表 `channel_reach_basic_a1` 抓逐日、逐支的縮圖曝光與 CTR，存進 `ctr_daily.json`，節目專頁畫成「上片第 N 天」對齊的折線圖。首次需在 Google Cloud 專案啟用 YouTube Reporting API，再執行一次 `python3 fetch_reach.py --create-job`；之後 Actions 每輪自動下載新報表。報表日期為美西時間，約晚 2 天產出。
