"""
PTT 爬蟲模組
爬取 AI、科技相關版面，依推文數篩選熱議文章
"""
import requests
import time
import re
from datetime import datetime, timedelta
from typing import List, Dict

# 實際存在且有 AI 討論的版面
PTT_BOARDS = []  # PTT JSON API 目前無法連線，暫時停用
PTT_BASE = "https://www.ptt.cc"
AI_KEYWORDS = [
    "AI", "人工智慧", "機器學習", "深度學習", "ChatGPT", "GPT", "Claude",
    "Gemini", "Llama", "語言模型", "LLM", "生成式", "Sora", "OpenAI",
    "Anthropic", "Copilot", "神經網路", "大模型", "文生圖", "自動化",
    "Agent", "RAG", "微調", "fine-tune", "cursor", "vibe coding"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.ptt.cc/bbs/index.html",
    "Cookie": "over18=1",
}


def _is_ai_related(title: str) -> bool:
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in AI_KEYWORDS)


def _parse_push_count(push_str: str) -> int:
    if not push_str:
        return 0
    push_str = push_str.strip()
    if push_str == "爆":
        return 100
    if push_str.startswith("X"):
        return -int(push_str[1:]) if push_str[1:].isdigit() else -1
    try:
        return int(push_str)
    except ValueError:
        return 0


def _get_json(url: str, retries: int = 3) -> dict | None:
    """帶 retry 的 JSON 請求"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            time.sleep(3)
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 404:
                return None  # 版面不存在，不重試
            time.sleep(2)
        except Exception as e:
            time.sleep(2)
    return None


def fetch_board(board: str, min_pushes: int = 20, days_back: int = 1) -> List[Dict]:
    articles = []
    cutoff = datetime.now() - timedelta(days=days_back)

    # 取得最新頁碼
    index_data = _get_json(f"{PTT_BASE}/bbs/{board}/index.json")
    if not index_data:
        return []

    current_page = index_data.get("current_page", 1)

    for page_offset in range(0, 3):
        page_num = current_page - page_offset
        if page_num < 1:
            break

        url = f"{PTT_BASE}/bbs/{board}/index{page_num}.json"
        items = _get_json(url)
        if not items:
            continue

        for item in items:
            title = item.get("title", "")
            if title.startswith("[置頂]") or not title:
                continue

            push_count = _parse_push_count(item.get("push_count", "0"))
            if push_count < min_pushes:
                continue

            if not _is_ai_related(title):
                continue

            # 日期篩選
            date_str = item.get("date", "")
            try:
                now = datetime.now()
                month, day = map(int, date_str.strip().split("/"))
                article_date = datetime(now.year, month, day)
                if article_date < cutoff:
                    continue
            except Exception:
                pass

            articles.append({
                "source": f"PTT/{board}",
                "title": title,
                "url": PTT_BASE + item.get("href", ""),
                "push_count": push_count,
                "author": item.get("author", ""),
                "date": date_str,
                "summary": "",
            })

        time.sleep(0.8)  # 避免被封

    return articles


def scrape_ptt(min_pushes: int = 20, days_back: int = 1) -> List[Dict]:
    all_articles = []
    seen_urls = set()

    for board in PTT_BOARDS:
        articles = fetch_board(board, min_pushes=min_pushes, days_back=days_back)
        for a in articles:
            if a["url"] not in seen_urls:
                seen_urls.add(a["url"])
                all_articles.append(a)

    all_articles.sort(key=lambda x: x["push_count"], reverse=True)
    print(f"[PTT] 找到 {len(all_articles)} 篇熱門 AI 文章")
    return all_articles
