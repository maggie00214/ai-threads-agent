# AI Threads Agent

每天自動爬取 PTT + 科技 RSS 的 AI 熱議文章，生成懶人包圖卡，自動發布到 Threads。

---

## 專案結構

```
AI_Threads_Agent/
├── agent.py              # 主流程（入口）
├── schedule_daily.py     # 每日排程執行器
├── requirements.txt
├── .env.example          # 環境變數範本
├── scrapers/
│   ├── ptt.py            # PTT 爬蟲（ChatGPT板、AI_Agent板等）
│   └── rss.py            # RSS 爬蟲（36氪、少數派、HN、The Verge...）
├── processors/
│   └── ai_filter.py      # GPT 評分 + 文案生成
├── generators/
│   └── image_gen.py      # Pillow 懶人包圖卡生成
├── publishers/
│   └── threads.py        # Threads API 發布
└── output/
    ├── images/           # 每日圖片（自動建立）
    └── logs/             # 執行記錄 JSON
```

---

## 需要申請的帳號與 API（全部免費，除了 OpenAI）

### 1. OpenAI API（約 $1–5 / 月）

1. 前往 https://platform.openai.com/
2. 註冊帳號 → 點右上角頭像 → **API Keys**
3. 建立新 Key，複製貼到 `.env` 的 `OPENAI_API_KEY`

> 費用估算：每天執行一次，約用 GPT-4o-mini + GPT-4o，合計約 $0.03–0.10 / 天

---

### 2. Threads API（免費）

**步驟一：建立 Meta Developer App**
1. 前往 https://developers.facebook.com/
2. 登入你的 Facebook / Meta 帳號
3. 點 **My Apps** → **Create App**
4. 選 **Other** → **Business** → 填寫 App 名稱
5. 在 App Dashboard 左側找到 **Threads API** → 點 **Set up**

**步驟二：取得 Access Token**
1. 在 Threads API 設定頁，點 **Generate Token**
2. 登入你的 Threads 帳號授權
3. 複製 **Long-lived Token**（有效期 60 天，需定期更新）
4. 貼到 `.env` 的 `THREADS_ACCESS_TOKEN`

**步驟三：取得 User ID**
1. 在 Token 頁面會顯示你的 Threads User ID
2. 貼到 `.env` 的 `THREADS_USER_ID`

> Token 更新：每 60 天需重新產生，或設定自動刷新（進階）

---

### 3. Imgur API（免費，圖片中繼站）

Threads API 需要圖片的「公開 URL」，Imgur 是最簡單的解決方案。

1. 前往 https://imgur.com/ 註冊帳號
2. 前往 https://api.imgur.com/oauth2/addclient
3. 填寫：
   - Application name：任意名稱
   - Authorization type：**Anonymous usage without user authorization**
   - Email：你的 Email
4. 複製 **Client ID**，貼到 `.env` 的 `IMGUR_CLIENT_ID`

---

## 安裝步驟

```bash
# 1. 安裝 Python 3.10+（https://python.org）

# 2. 進入專案資料夾
cd AI_Threads_Agent

# 3. 安裝套件
pip install -r requirements.txt

# 4. 建立環境變數檔
cp .env.example .env
# 用任何文字編輯器開啟 .env，填入所有 Key

# 5. 測試執行（不發布，只看結果）
python agent.py --dry-run

# 6. 正式執行一次
python agent.py

# 7. 啟動每日排程（保持視窗開著）
python schedule_daily.py
```

---

## 常用指令

| 指令 | 說明 |
|------|------|
| `python agent.py --dry-run` | 完整執行但不發布，用來測試 |
| `python agent.py --skip-publish` | 生成圖片但不發布 |
| `python agent.py` | 完整執行並發布到 Threads |
| `python schedule_daily.py` | 啟動每日 8:00 自動執行 |

---

## 資料來源

| 來源 | 類型 | 說明 |
|------|------|------|
| PTT ChatGPT板 | 爬蟲 | 推文 ≥20 的 AI 文章 |
| PTT AI_Agent板 | 爬蟲 | AI 工具討論 |
| PTT Gossiping | 爬蟲 | AI 相關爆文 |
| 少數派 | RSS | 中文科技評測 |
| 36氪 | RSS | 中文新創/AI 資訊 |
| 愛范兒 | RSS | 中文科技媒體 |
| Hacker News | RSS | 英文技術社群 |
| The Verge AI | RSS | 英文科技媒體 |
| MIT Tech Review | RSS | 學術/研究導向 |
| VentureBeat AI | RSS | 英文 AI 產業 |
| Nitter (OpenAI/Anthropic) | RSS | X 帳號 RSS 替代 |

---

## 圖片設計風格

- **底色**：深黑（#0D0D0D），低 AI 感、高質感
- **強調色**：螢光黃（#E8FF3A），視覺對比強烈
- **字型**：自動偵測系統中文字型（微軟正黑、蘋方等）
- **版型**：封面圖 + N 張文章卡 + CTA 結尾圖
- **尺寸**：1080×1080（正方形，適合 Threads/IG）

---

## 常見問題

**Q: 圖片中文顯示亂碼？**
在 `.env` 設定 `FONT_PATH` 指向你系統的中文字型路徑。
- Windows：`C:/Windows/Fonts/msjh.ttc`
- macOS：`/System/Library/Fonts/PingFang.ttc`

**Q: PTT 抓不到資料？**
PTT 需要 `over18=1` Cookie，程式已自動帶入。若仍失敗，可能是 PTT 伺服器暫時下線。

**Q: Threads Token 過期了？**
重新到 Meta Developer 產生新 Token，更新 `.env` 檔案。

**Q: 想修改發文時間？**
編輯 `schedule_daily.py` 的 `RUN_TIME = "08:00"` 改成你想要的時間。

**Q: 想加入其他 RSS 來源？**
編輯 `scrapers/rss.py` 的 `RSS_FEEDS` 清單新增。
