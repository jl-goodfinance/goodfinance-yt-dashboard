# 美好證券 YouTube 節目數據 Dashboard

- **Dashboard**：`docs/index.html`（GitHub Pages 自動部署）
- **每小時**：GitHub Actions 跑 `fetch_data.py`（Analytics＋Data API，憑證在 repo Secrets）→ `fetch_comments.py`（innertube 留言）→ `fetch_thumbs.py`（縮圖快取）→ `apply_data.py docs/index.html`
- **每週一**：本機 Claude 排程 `yt-weekly-advisor` 更新 Studio 曝光/CTR（`studio_scrape_raw.txt` → `build_studio.py`）、重寫 `advice.json`（顧問建議）與 `analysis.json`（留言洞察），commit push 並重發 Claude artifact
- 憑證：`YT_CLIENT_ID` / `YT_CLIENT_SECRET` / `YT_REFRESH_TOKEN`（Actions Secrets；本機讀 `~/.config/goodfinance-yt/`）
- 注意：CTR／曝光／新觀眾比為 YouTube Studio 專屬（API 不提供），僅每週更新
