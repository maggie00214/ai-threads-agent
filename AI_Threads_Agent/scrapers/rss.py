"""
RSS 爬蟲模組
來源：台灣 PTT 生態 + 英文科技媒體（移除中國大陸媒體）
"""
import feedparser
import re
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict

RSS_FEEDS = [
    # ── 台灣中文新聞（優先）──────────────────────────────────
    {"name": "動區動趨",        "url": "https://www.blocktempo.com/feed/",                    "lang": "zh"},
    {"name": "科技新報",        "url": "https://technews.tw/feed/",                           "lang": "zh"},
    {"name": "iThome",          "url": "https://www.ithome.com.tw/rss",                       "lang": "zh"},
    {"name": "TechOrange",      "url": "https://buzzorange.com/techorange/feed/",              "lang": "zh"},
    {"name": "Google News AI",  "url": "https://news.google.com/rss/search?q=AI+人工智慧&hl=zh-TW&gl=TW&ceid=TW:zh-Hant", "lang": "zh"},
    # ── 英文主力來源（AI 討論度高）──────────────────────────
    {"name": "Hacker News",    "url": "https://hnrss.org/frontpage?q=AI&points=100",         "lang": "en"},
    {"name": "The Verge AI",   "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "lang": "en"},
    {"name": "MIT Tech Review","url": "https://www.technologyreview.com/feed/",               "lang": "en"},
    {"name": "VentureBeat AI", "url": "https://feeds.feedburner.com/venturebeat/SZYF",        "lang": "en"},
    {"name": "Ars Technica AI","url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "lang": "en"},
    {"name": "TechCrunch AI",  "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "lang": "en"},
    # ── Nitter（X 官方帳號 RSS 替代）────────────────────────
    {"name": "OpenAI",         "url": "https://nitter.privacydev.net/OpenAI/rss",             "lang": "en"},
    {"name": "AnthropicAI",    "url": "https://nitter.privacydev.net/AnthropicAI/rss",        "lang": "en"},
    {"name": "sama (Altman)",  "url": "https://nitter.privacydev.net/sama/rss",               "lang": "en"},
]

AI_KEYWORDS = [
    "AI", "artificial intelligence", "machine learning", "deep learning",
    "ChatGPT", "GPT", "Claude", "Gemini", "LLM", "language model",
    "OpenAI", "Anthropic", "Google AI", "generative", "neural",
    "Sora", "Llama", "Mistral", "diffusion", "RAG", "fine-tune",
    "automation", "AGI", "robotics", "foundation model", "multimodal",
    "人工智慧", "機器學習", "大模型", "生成式", "語言模型", "Agent",
    "AI", "聊天機器人", "自動化", "深度學習", "神經網路", "Copilot",
    "文生圖", "文生影", "算力", "GPU", "算法", "推理", "訓練",
]


def _is_ai_related(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in AI_KEYWORDS)


def _parse_entry_date(entry) -> datetime:
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_rss_feed(feed_config: Dict, days_back: int = 1) -> List[Dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    articles = []
    try:
        parsed = feedparser.parse(feed_config["url"])
        if not parsed.entries:
            return []
    except Exception as e:
        print(f"  [RSS] {feed_config['name']} 錯誤: {e}")
        return []

    for entry in parsed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        link = entry.get("link", "")

        if not _is_ai_related(title + " " + summary[:200]):
            continue
        if _parse_entry_date(entry) < cutoff:
            continue

        articles.append({
            "source": feed_config["name"],
            "title": title.strip(),
            "url": link,
            "summary": _clean_html(summary)[:500],
            "date": _parse_entry_date(entry).strftime("%Y-%m-%d %H:%M"),
            "push_count": 0,
            "lang": feed_config["lang"],
        })

    return articles


def scrape_rss(days_back: int = 1, max_per_source: int = 5) -> List[Dict]:
    all_articles = []
    seen_urls = set()

    for feed in RSS_FEEDS:
        print(f"  [RSS] 抓取 {feed['name']}...")
        articles = fetch_rss_feed(feed, days_back=days_back)
        count = 0
        for a in articles:
            if a["url"] not in seen_urls and count < max_per_source:
                seen_urls.add(a["url"])
                all_articles.append(a)
                count += 1
        time.sleep(0.5)

    print(f"[RSS] 共取得 {len(all_articles)} 篇 AI 相關文章")
    return all_articles
