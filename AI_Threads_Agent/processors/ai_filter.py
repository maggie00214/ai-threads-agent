"""
AI 過濾與摘要模組
使用 DeepSeek API（OpenAI 相容格式）
- 精選最熱議一篇
- 生成結構化圖卡文案（category + title + 3個分段）
"""
import os
import json
import time
from typing import List, Dict
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
            return resp.choices[0].message.content.strip()
        except Exception as e:
            msg = str(e)
            if ("429" in msg or "rate" in msg.lower()) and i < retries - 1:
                wait = 30 + i * 15
                print(f"  [DeepSeek] 速率限制，等待 {wait} 秒後重試...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("DeepSeek API 重試失敗")


def _parse_json(text: str) -> any:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


def pick_top_article(articles: List[Dict]) -> Dict:
    """從所有文章中選出最值得今天報導的那一篇"""
    if not articles:
        return {}

    article_list = [
        {
            "id": i,
            "source": a.get("source", ""),
            "title": a.get("title", ""),
            "summary": a.get("summary", a.get("content", ""))[:250],
            "push_count": a.get("push_count", 0),
            # 內容字數：太短的文章不優先
            "content_len": len(a.get("summary", a.get("content", ""))),
        }
        for i, a in enumerate(articles)
    ]

    prompt = prompt.replace(
        "文章清單：",
        "文章清單（content_len 太短的文章資訊不足，請優先選 content_len > 100 的）："
    )

    prompt = f"""你是台灣科技媒體編輯。從以下文章選出「最值得今天報導的那一篇」，標準：
1. AI 核心相關
2. 討論熱度高或重大事件
3. 對台灣讀者有意義

文章清單：
{json.dumps(article_list, ensure_ascii=False)}

只回傳 JSON：{{"id": 數字, "reason": "選這篇的原因（繁體中文，20字內）"}}
不要 markdown。"""

    try:
        raw = _ask(prompt)
        result = _parse_json(raw)
        chosen = articles[result.get("id", 0)].copy()
        chosen["pick_reason"] = result.get("reason", "")
        return chosen
    except Exception as e:
        print(f"[AI Filter] 選文失敗: {e}")
        articles.sort(key=lambda x: x.get("push_count", 0), reverse=True)
        return articles[0] if articles else {}


def generate_post_content(article: Dict, today_str: str) -> Dict:
    """
    生成結構化圖卡文案，格式對應圖卡風格：
    - category: 類別標籤（2-4字英文大寫，如 AI NEWS / OPEN SOURCE / PRODUCT）
    - title_zh: 繁中主標題（有衝突感，≤18字）
    - key_stat: 最值得視覺化的關鍵數字或短語（≤10字）
    - sections: 3個分段，每段有 heading（有觀點，≤12字）+ body（≤45字）
    - caption: Threads 主文（鉤子句＋具體細節＋輕互動，130字內，不含hashtag）
    """
    raw_content = article.get('content', '') or article.get('summary', '')
    summary     = article.get('summary', '') or raw_content
    # 合併所有可用文字，餵給 DeepSeek 的上限提高到 1500 字
    full_text   = f"{summary}\n{raw_content}"[:1500].strip()
    source_text = (
        f"標題：{article.get('title', '')}\n"
        f"來源：{article.get('source', '')}\n"
        f"內容：{full_text}"
    )

    prompt = f"""你是一個在 Threads 上很有人緣的台灣科技愛好者，今天是 {today_str}。

今天精選的 AI 文章：
{source_text}

請生成以下內容：

1. category：2-4字英文大寫分類，例如 "AI NEWS"、"OPEN SOURCE"、"PRODUCT DROP"、"RESEARCH"、"INDUSTRY"

2. title_zh：圖卡主標題，要有衝突感或驚訝感，不超過 18 字，繁體中文
   好例子：「OpenAI 剛做了一個讓人看不懂的決定」、「這場 AI 大戰正式開打了」
   壞例子：「最新AI科技進展報告」（太平、太官方）

3. key_stat：這篇新聞最值得視覺化的一個數字或關鍵短語，10字以內
   例如：「$965B」、「本週就決定」、「成長 4.7 倍」、「60天後到期」

4. sections：3個分段，每段包含：
   - heading：切入角度小標，不超過 12 字，要有觀點、不只是中性標籤
     好例子：「動作快得有點可疑」、「數字說話，很不得了」
     壞例子：「最快本週談」（太平）
   - body：說明文字，不超過 45 字，要有具體細節（數字、人名、技術名詞）
     絕對禁止：「這則消息值得持續觀察」「更多細節請見原文連結」「值得關注」等空洞廢話
     如果原文資訊不足，就從標題和現有內容推理補充，不能用空洞語句敷衍

5. caption：Threads 發文文字，目標是「一個你信任的朋友，看到值得關注的事，平靜但清楚地告訴你」

   【語氣標準】
   - 不浮誇、不農場、不商業
   - 像在群組傳一則有料的訊息，不是在寫廣告也不是在發新聞稿
   - 可以有輕微的個人態度或感想，但不要用力過猛
   - 禁止：「超扯！」「有夠瘋狂！」「震驚業界！」這類誇飾詞

   【結構：三段，不標小標】

   第一段（1-2句）：
   直接說發生了什麼，要有具體細節或數字。開頭不能是「今天...」「最新...」「重磅...」
   好例子：「Meta 的 AI 客服可以被拿來駭 IG 帳號。駭客傳一個特製指令，機器人就直接把驗證碼交出去了。」
   壞例子：「欸真的假的？！這也太誇張了吧！！」

   （空一行）

   第二段（1-2句）：
   補充背景或影響範圍，繼續用具體資訊說話。

   （空一行）

   第三段（1句）：
   你自己的一個小感想或行動，然後結尾一個真的會讓人想回答的問題。
   好例子：「我還是去把雙重驗證開起來了。你的呢？」
   壞例子：「大家要注意資安喔！你覺得這樣好嗎？」

   規則：
   - 整體 120 字以內
   - 繁體中文，口語但不刻意
   - 最多 1 個 emoji，放在自然的位置
   - 絕對不能有任何 hashtag 或 # 符號

只回傳 JSON，key 為 category、title_zh、key_stat、sections、caption。不要 markdown。"""

    try:
        raw = _ask(prompt)
        data = _parse_json(raw)
        if "caption" in data:
            import re
            data["caption"] = re.sub(r"#\S+", "", data["caption"]).strip()
        data.pop("hashtags", None)
        return data
    except Exception as e:
        print(f"[AI Filter] 文案生成失敗: {e}")
        title = article.get("title", "")
        return {
            "category": "AI NEWS",
            "title_zh": title[:18],
            "key_stat": "",
            "sections": [
                {"heading": "發生了什麼事", "body": article.get("summary", "")[:45]},
                {"heading": "為什麼值得關注", "body": "這則消息值得持續觀察"},
                {"heading": "對你的影響",    "body": "更多細節請見原文連結"},
            ],
            "caption": f"這個你可能還沒看到 👀\n\n{title}\n\n你怎麼看？",
        }
