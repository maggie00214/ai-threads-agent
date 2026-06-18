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


def _dedupe_repeated_fragments(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", (text or "")).strip()
    if not text:
        return text

    for _ in range(3):
        out = []
        i = 0
        changed = False
        while i < len(text):
            max_unit = min(48, (len(text) - i) // 2)
            matched = False
            for size in range(max_unit, 3, -1):
                unit = text[i : i + size]
                if not unit.strip() or not text.startswith(unit, i + size):
                    continue
                out.append(unit)
                i += size
                while text.startswith(unit, i):
                    i += size
                    changed = True
                matched = True
                break
            if not matched:
                out.append(text[i])
                i += 1
        next_text = "".join(out)
        if not changed or next_text == text:
            return next_text
        text = next_text
    return text


def _clean_short_text(text: str, limit: int) -> str:
    text = _dedupe_repeated_fragments(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _clean_title_text(text: str, limit: int = 22) -> str:
    text = _dedupe_repeated_fragments(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text

    clipped = text[:limit].rstrip(" ，、：:；;。！？!?-—｜|")
    for mark in ("：", ":", "，", "、", "；", ";", "。", "！", "？", "!", "?"):
        idx = clipped.rfind(mark)
        if idx >= 8:
            clipped = clipped[:idx].strip()
            break

    dangling = ("把", "給", "讓", "在", "是", "的", "和", "與", "及", "或", "到", "向", "對")
    while clipped.endswith(dangling):
        clipped = clipped[:-1].rstrip()
    return clipped or text[:limit].rstrip()


def _fallback_title_from_article(title: str) -> str:
    title = re.split(r"[：:｜|]", title or "", maxsplit=1)[0].strip()
    if not title:
        return "今日 AI 焦點"

    match = re.search(r"(.+?)把(.+?)交給(.+)", title)
    if match:
        subject = match.group(1).strip()
        target = match.group(2).strip()
        agent = match.group(3).strip()
        if "AI" in agent.upper():
            rewritten = f"{subject} 用 AI 接手{target}"
        else:
            rewritten = f"{agent}接手{target}"
        return _clean_title_text(rewritten, 22)

    return _clean_title_text(title, 22)


def _clean_caption(text: str, limit: int = 520) -> str:
    text = _dedupe_repeated_fragments(text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) <= limit:
        return text

    clipped = text[:limit].rstrip()
    cut_points = [clipped.rfind(mark) for mark in ("。", "？", "！", "?", "!", "\n")]
    best_cut = max(cut_points)
    if best_cut >= max(120, limit // 2):
        return clipped[: best_cut + 1].strip()
    return clipped.strip()


def _make_blocks_distinct(blocks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    fallback_bodies = [
        "先看它改變了哪個日常流程，不要只看產品名字。",
        "影響會落在成本、安全或效率，取決於你怎麼用。",
        "可以立刻檢查自己的工具權限、資料流向與工作流程。",
    ]
    seen = set()
    result = []
    for idx, block in enumerate(blocks[:3]):
        body = _dedupe_repeated_fragments(block.get("body", ""))
        key = re.sub(r"\W+", "", body).lower()
        if key and key in seen:
            body = fallback_bodies[min(idx, len(fallback_bodies) - 1)]
            key = re.sub(r"\W+", "", body).lower()
        if key:
            seen.add(key)
        result.append({"heading": block.get("heading", ""), "body": body})
    action_words = ("檢查", "關閉", "限制", "避免", "設定", "權限", "取消", "不要", "先把")
    if result and not any(any(word in block.get("body", "") for word in action_words) for block in result):
        result[-1] = {
            "heading": "避坑",
            "body": "先檢查權限、關掉不用的串接，敏感資料不要直接丟進 AI。",
        }
    return result


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
- title_zh: 22 字內，必須像爆文封面標題，直擊痛點或反直覺，而且語意必須完整，不可以停在「把、給、讓、的」
- subtitle_zh: 24 字內，補上影響、對象或趨勢
- hook_line: 24 字內，語不驚人死不休；可用痛點、反直覺觀點或強烈提問
- insight_blocks: 必須剛好 3 個，每個包含 heading 與 body
  - heading: 8 字內
  - body: 54 字內
  - 三個段落分別要講「核心事實 / 為什麼重要 / 如何影響或怎麼做」
- caption: 260 到 520 字，必須多換行，像專家朋友在分享
- angle: 16 字內，說這篇貼文的切角，例如「省錢資訊」、「上班族實用」、「帳號安全」

caption 規則：
1. 黃金前三秒：第一句必須很有衝擊，讓人停下來；不要平鋪直敘
2. 第二段開始用 3 個條列段落，每段都要講清楚「為什麼」或「如何影響」
3. 條列格式請用「1.」「2.」「3.」，每點 1 到 2 句
4. 語氣像專家朋友，不要新聞稿，不要官腔
5. 多換行，讓 Threads 好讀
6. 適度加入 2 到 3 個 emoji，但不要塞滿
7. 最後必須丟出一個有爭議、能逼大家表態的問題
8. 不要 hashtag
9. 用繁體中文
10. 不要捏造原文沒有的數據；如果原文沒數字，就講趨勢和影響
""".strip()

    prompt += """

硬性補充規則：
- 三個 insight_blocks 必須依序是「發生什麼事 / 為什麼重要 / 大家怎麼避免或注意」。
- 第三個 insight_blocks 的 heading 優先用「避坑」「做法」「提醒」其中之一。
- 第三個 insight_blocks 的 body 一定要有具體動作，例如：檢查權限、關閉不用的串接、不要把敏感資料丟進 AI、分開公司與個人帳號、確認帳單/額度/設定。
- caption 的第 3 點必須是「怎麼做」，至少給 2 個可立即執行的檢查或避免方法，不要只寫「大家要注意」。
""".strip()

    try:
        raw = _ask(prompt)
        data = _parse_json(raw)
        data["title_zh"] = _clean_title_text(data.get("title_zh", ""), 22)
        data["subtitle_zh"] = _clean_short_text(data.get("subtitle_zh", ""), 24)
        data["hook_line"] = _clean_short_text(data.get("hook_line", ""), 24)
        data["angle"] = _clean_short_text(data.get("angle", ""), 16)

        blocks = data.get("insight_blocks", [])
        cleaned_blocks = []
        for block in blocks[:3]:
            cleaned_blocks.append(
                {
                    "heading": _clean_short_text(block.get("heading", ""), 8),
                    "body": _clean_short_text(block.get("body", ""), 54),
                }
            )
        data["insight_blocks"] = _make_blocks_distinct(cleaned_blocks)

        if "caption" in data:
            caption = re.sub(r"#\S+", "", data["caption"]).strip()
            data["caption"] = _clean_caption(caption)
        return data
    except Exception as e:
        print(f"[AI Filter] generate_post_content failed: {e}")
        title = article.get("title", "").strip()
        fallback_title = _fallback_title_from_article(title)
        summary_text = _clean_short_text(article.get("summary", "") or raw_content, 140)
        return {
            "category": "AI NEWS",
            "title_zh": fallback_title,
            "subtitle_zh": "這則更新和一般使用者直接有關",
            "hook_line": "別只看新聞標題",
            "angle": "實用資訊",
            "insight_blocks": [
                {"heading": "核心", "body": _clean_short_text(summary_text, 54) or "今天有一則和 AI 使用直接相關的消息。"},
                {"heading": "影響", "body": "如果你平常有在用 AI 工具，這會改變你的使用成本或工作方式。"},
                {"heading": "避坑", "body": "先查設定與權限，關掉不用的串接，敏感資料不要直接丟。"},
            ],
            "caption": _clean_caption(
                f"這則 AI 消息不要只滑過，後面可能會影響你每天怎麼用工具。\n\n"
                f"1. 核心重點：{title}。\n\n"
                f"2. 為什麼重要：如果你平常有在用 AI 工具，這可能會改變你的成本、效率或資料風險。\n\n"
                f"3. 你可以怎麼做：先檢查設定、權限和帳單；不用的外掛或串接先關掉，敏感資料不要直接丟進 AI。\n\n"
                f"你覺得 AI 工具現在是在幫大家省時間，還是在把大家綁進更貴的工作流程？",
            ),
        }
