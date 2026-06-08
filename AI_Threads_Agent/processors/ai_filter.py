"""
Pick practical AI news and turn it into useful, shareable Threads copy.
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


PRACTICAL_KEYWORDS = [
    "price", "pricing", "subscription", "plus", "plan", "free",
    "limit", "usage", "quota", "cowork", "credit",
    "feature", "mode", "update", "launch", "rollout",
    "prompt", "workflow", "email", "meeting", "summary",
    "security", "hack", "account", "privacy", "data",
    "chatgpt", "claude", "gemini", "openai", "anthropic", "meta",
    "tips", "guide", "how to", "use case", "creator", "productivity",
]


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


def _clean_short_text(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _clean_caption(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text

    sentences = re.split(r"(?<=[。！？!?])\s*", text)
    kept = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{kept} {sentence}".strip() if kept else sentence
        if len(candidate) <= limit:
            kept = candidate
        else:
            break
    if kept:
        return kept

    shortened = text[:limit].rstrip()
    cut_points = [shortened.rfind(mark) for mark in ("。", "？", "！", ".", "?", "!", "，", ",")]
    best_cut = max(cut_points)
    if best_cut >= max(18, limit // 3):
        return shortened[: best_cut + 1].strip()
    return shortened


def pick_top_article(articles: List[Dict]) -> Dict:
    if not articles:
        return {}

    article_list = [
        {
            "id": i,
            "source": a.get("source", ""),
            "title": a.get("title", ""),
            "summary": _clean_short_text(a.get("summary") or a.get("content") or "", 260),
            "push_count": a.get("push_count", 0),
            "content_len": len(a.get("summary") or a.get("content") or ""),
        }
        for i, a in enumerate(articles)
    ]

    prompt = f"""
你是台灣社群內容總監。請從候選文章中選出一篇最適合發成「接地氣、實用型、像創作者真人分享的 AI Threads 貼文」。

優先標準：
1. 對一般人或上班族有直接幫助，例如價格、訂閱、額度、功能更新、工作效率、安全風險
2. 看完之後能回答「這對我有什麼用」
3. 題目本身有實際行動價值，例如可以提醒、可以省錢、可以避坑、可以提升效率
4. 若都差不多，優先資訊完整、較新、較容易講清楚的文章
5. 少選太偏投資、太偏政商角力、太抽象的產業新聞
6. 如果一篇內容可以被改寫成「我剛發現一個很好用/要注意的 AI 資訊」，就加分

候選文章：
{json.dumps(article_list, ensure_ascii=False)}

請只回傳 JSON：
{{"id": 文章 id, "reason": "40字內，說明為什麼這篇對大家有用"}}
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
            key=lambda x: (
                any(
                    keyword in (x.get("title", "") + " " + (x.get("summary", "") or "")).lower()
                    for keyword in PRACTICAL_KEYWORDS
                ),
                x.get("push_count", 0),
                len(x.get("summary") or x.get("content") or ""),
            ),
            reverse=True,
        )
        fallback = ranked[0].copy()
        fallback["pick_reason"] = "Fallback: practical relevance, visibility, and content depth."
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
你是高互動 Threads 編輯，風格像「把 AI 新聞翻成一般人看得懂、用得到的資訊」。
語氣請參考真人創作者分享：像在提醒朋友、補充限制、順手幫大家省時間，不要像新聞台。
今天日期：{today_str}

新聞資料：
{source_text}

請把這則新聞整理成一篇：
- 接地氣
- 能立刻看懂
- 有實用價值
- 讀完會覺得「這資訊對我有用」
- 像真人整理重點，不像官宣摘要
- 可以接近下面幾種貼文型態：
  1. 我剛發現一個實用更新
  2. 這個限制很多人會搞錯
  3. 如果你有在用某工具，這則先記起來
  4. 這不是大新聞，但對常用的人很重要

請只輸出 JSON，包含以下 keys：
- category: 從 "AI NEWS"、"TOOLS"、"SECURITY"、"WORKFLOW"、"PRICING"、"TIPS" 中選一個
- title_zh: 16 字內，直接點出重點
- subtitle_zh: 22 字內，補上影響或適用對象
- hook_line: 14 字內，一句最值得停下來看的話
- insight_blocks: 1 到 2 個，每個包含 heading 與 body
  - heading: 8 字內
  - body: 32 字內
  - 至少其中一個 block 要偏「你可以怎麼看 / 怎麼用 / 要注意什麼」
- caption: 100 字內，2 到 4 句
- angle: 16 字內，說這篇貼文的切角，例如「省錢資訊」、「上班族實用」、「帳號安全」

caption 規則：
1. 第一段先講發生什麼事，用白話翻譯
2. 第二段直接翻成對讀者有什麼用，或誰最該注意
3. 如果有條件、限制、到期日、適用範圍，請明講
4. 最後一句可以是提醒、建議，或自然提問
5. 不要 hashtag
6. 不要新聞稿口吻
7. 用繁體中文
8. 如果這篇偏功能更新，請寫出怎麼用
9. 如果這篇偏安全風險，請寫出該注意什麼
10. 如果這篇偏價格或額度，請寫出誰受益、要不要現在做
11. 優先用「你 / 如果你 / 記得 / 可以先 / 我覺得」這種口吻
12. 可以像真人補充一句「很多人可能沒注意到…」「如果你平常有在用…」
13. 不能只寫一行短句；要有資訊密度，但整體不要超過 100 字
14. 優先寫成 3 句：發生什麼事、對誰有用、現在該注意什麼
""".strip()

    try:
        raw = _ask(prompt)
        data = _parse_json(raw)
        data["title_zh"] = _clean_short_text(data.get("title_zh", ""), 16)
        data["subtitle_zh"] = _clean_short_text(data.get("subtitle_zh", ""), 22)
        data["hook_line"] = _clean_short_text(data.get("hook_line", ""), 14)
        data["angle"] = _clean_short_text(data.get("angle", ""), 16)

        blocks = data.get("insight_blocks", [])
        cleaned_blocks = []
        for block in blocks[:2]:
            cleaned_blocks.append(
                {
                    "heading": _clean_short_text(block.get("heading", ""), 8),
                    "body": _clean_short_text(block.get("body", ""), 32),
                }
            )
        data["insight_blocks"] = cleaned_blocks

        if "caption" in data:
            caption = re.sub(r"#\S+", "", data["caption"]).strip()
            data["caption"] = _clean_caption(caption, 100)
        return data
    except Exception as e:
        print(f"[AI Filter] generate_post_content failed: {e}")
        title = article.get("title", "").strip()
        summary_text = _clean_short_text(article.get("summary", "") or raw_content, 140)
        return {
            "category": "AI NEWS",
            "title_zh": _clean_short_text(title, 16) or "今日 AI 焦點",
            "subtitle_zh": "這則更新和一般使用者直接有關",
            "hook_line": "",
            "angle": "實用資訊",
            "insight_blocks": [
                {"heading": "重點", "body": _clean_short_text(summary_text, 32) or "今天有一則和 AI 使用直接相關的消息。"},
                {"heading": "你該看", "body": "如果你平常有在用 AI 工具，這則值得先記下來。"},
            ],
            "caption": _clean_caption(
                f"{title}。如果你平常有在用 AI 工具，這則資訊和你的使用方式直接有關。建議先記起來。",
                100,
            ),
        }
