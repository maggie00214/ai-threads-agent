"""
Select a top article and generate Threads-ready post content via DeepSeek.
"""
import json
import os
import re
import time
from typing import Any, Dict, List

from openai import OpenAI

_client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com",
)
MODEL = "deepseek-chat"


def _ask(prompt: str, retries: int = 3) -> str:
    for i in range(retries):
        try:
            resp = _client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.7,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            msg = str(e)
            if ("429" in msg or "rate" in msg.lower()) and i < retries - 1:
                wait = 30 + i * 15
                print(f"  [DeepSeek] rate limited, wait {wait}s and retry...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("DeepSeek API request failed after retries")


def _parse_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    return json.loads(text)


def pick_top_article(articles: List[Dict]) -> Dict:
    if not articles:
        return {}

    article_list = [
        {
            "id": i,
            "source": a.get("source", ""),
            "title": a.get("title", ""),
            "summary": (a.get("summary") or a.get("content") or "")[:250],
            "push_count": a.get("push_count", 0),
            "content_len": len(a.get("summary") or a.get("content") or ""),
        }
        for i, a in enumerate(articles)
    ]

    prompt = f"""
你是科技媒體編輯，請從候選文章中選出最適合今天 Threads 發文的一篇。

優先條件：
1. AI 相關性高
2. 有新意、討論度或實際影響
3. 標題清楚，內文資訊量足夠
4. 若條件接近，優先選 content_len > 100 的文章

候選文章：
{json.dumps(article_list, ensure_ascii=False)}

請只回傳 JSON：
{{"id": 文章 id, "reason": "50字內挑選原因"}}
不要輸出 markdown。
""".strip()

    try:
        raw = _ask(prompt)
        result = _parse_json(raw)
        chosen = articles[result.get("id", 0)].copy()
        chosen["pick_reason"] = result.get("reason", "")
        return chosen
    except Exception as e:
        print(f"[AI Filter] pick_top_article failed: {e}")
        ranked = sorted(
            articles,
            key=lambda x: (x.get("push_count", 0), len(x.get("summary") or x.get("content") or "")),
            reverse=True,
        )
        fallback = ranked[0].copy()
        fallback["pick_reason"] = "Fallback: sorted by popularity and content length."
        return fallback


def generate_post_content(article: Dict, today_str: str) -> Dict:
    raw_content = article.get("content", "") or article.get("summary", "")
    summary = article.get("summary", "") or raw_content
    full_text = f"{summary}\n{raw_content}"[:1500].strip()
    source_text = (
        f"標題：{article.get('title', '')}\n"
        f"來源：{article.get('source', '')}\n"
        f"內容：{full_text}"
    )

    prompt = f"""
你是繁體中文科技內容編輯，請把以下 AI 新聞整理成適合 Threads 的貼文素材，日期是 {today_str}。

新聞資料：
{source_text}

請只輸出 JSON，包含以下 keys：
- category: 從 "AI NEWS"、"OPEN SOURCE"、"PRODUCT DROP"、"RESEARCH"、"INDUSTRY" 中選一個
- title_zh: 18 字內繁中標題
- key_stat: 若有數字亮點就寫一句，沒有則留空字串
- sections: 長度為 3 的陣列，每項包含 heading 與 body
  - heading: 12 字內
  - body: 45 字內
- caption: 120 字內，不要 hashtag，最多 1 個 emoji

要求：
1. 用自然、俐落、可讀的繁體中文
2. 不要捏造原文沒有的數據
3. 不要輸出 markdown
4. 若原文資訊不足，就保守整理
""".strip()

    try:
        raw = _ask(prompt)
        data = _parse_json(raw)
        if "caption" in data:
            data["caption"] = re.sub(r"#\S+", "", data["caption"]).strip()
        data.pop("hashtags", None)
        return data
    except Exception as e:
        print(f"[AI Filter] generate_post_content failed: {e}")
        title = article.get("title", "").strip()
        summary_text = (article.get("summary", "") or raw_content).strip()
        return {
            "category": "AI NEWS",
            "title_zh": title[:18] or "今日 AI 焦點",
            "key_stat": "",
            "sections": [
                {"heading": "事件重點", "body": summary_text[:45] or "今日整理一則 AI 焦點新聞。"},
                {"heading": "為何值得看", "body": "它反映了 AI 產品與產業節奏正在持續加快。"},
                {"heading": "接下來", "body": "後續可觀察產品落地、使用者反應與市場擴散。"},
            ],
            "caption": f"今天看到一則值得注意的 AI 新聞：{title}".strip(),
        }
