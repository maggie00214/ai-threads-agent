"""
GitHub Actions 發布腳本
讀取當日 log.json，用 GitHub raw URL 發布圖片到 Threads，並留言附來源連結
"""
import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))
from publishers.threads import publish_with_url, post_reply


def main():
    today = datetime.now().strftime("%Y%m%d")
    log_path = Path(__file__).parent.parent / "每日內容" / today / "log.json"

    if not log_path.exists():
        print(f"[Error] 找不到 log.json：{log_path}")
        sys.exit(1)

    with open(log_path, encoding="utf-8") as f:
        log = json.load(f)

    caption    = log["post_content"]["caption"]
    source_url = log.get("source_url", "")
    source_name = log["selected"].get("source", "")

    from urllib.parse import quote
    import posixpath
    repo       = os.environ.get("GITHUB_REPO", "maggie00214/ai-threads-agent")
    # 從 log.json 取得實際圖片檔名（含時間戳，每次唯一）
    img_path   = log.get("image_path", "").replace("\\", "/")
    img_file   = img_path.split("/")[-1] if img_path else "featured.png"
    encoded    = quote(f"每日內容/{today}/images/{img_file}", safe="/")
    image_url  = f"https://raw.githubusercontent.com/{repo}/images/{encoded}"

    print(f"[Publish] 圖片 URL：{image_url}")
    print(f"[Publish] 文案預覽：{caption[:60]}...")

    post_id = publish_with_url(image_url, caption)
    print(f"[Publish] 發布成功！Post ID: {post_id}")

    if source_url or source_name:
        time.sleep(3)
        if source_url:
            reply_text = f"📰 新聞來源：{source_name}\n{source_url}"
        else:
            reply_text = f"📰 來源：{source_name}"
        reply_id = post_reply(post_id, reply_text)
        print(f"[Publish] 留言來源成功！Reply ID: {reply_id}")


if __name__ == "__main__":
    main()
