"""
AI Threads Agent entrypoint.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(Path(__file__).with_name(".env"))

from generators.image_gen import generate_all_images
from processors.ai_filter import generate_post_content, pick_top_article
from publishers.threads import post_reply, publish_carousel, publish_single
from scrapers.ptt import scrape_ptt
from scrapers.rss import scrape_rss

MIN_PUSHES = 20
DAYS_BACK = 1
DAILY_BASE = Path(__file__).parent.parent / "每日內容"


def _load_seen_urls(log_path: Path) -> list[str]:
    if not log_path.exists():
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            log = json.load(f)
        seen_urls = log.get("seen_urls", [])
        previous_source_url = log.get("source_url", "") or log.get("selected", {}).get("url", "")
        if previous_source_url and previous_source_url not in seen_urls:
            seen_urls.append(previous_source_url)
        return [url for url in seen_urls if url]
    except Exception:
        return []


def run(dry_run: bool = False, skip_publish: bool = False):
    today = datetime.now()
    today_str = today.strftime("%Y.%m.%d")
    date_folder = DAILY_BASE / today.strftime("%Y%m%d")
    output_dir = date_folder / "images"
    date_folder.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 50}")
    print(f"  AI Threads Agent 啟動  {today_str}")
    print(f"{'=' * 50}\n")

    print("[Step 1] 開始爬蟲...")
    all_articles = scrape_ptt(min_pushes=MIN_PUSHES, days_back=DAYS_BACK) + scrape_rss(days_back=DAYS_BACK)

    log_path = date_folder / "log.json"
    seen_urls = _load_seen_urls(log_path)
    if seen_urls:
        filtered_articles = [article for article in all_articles if article.get("url", "") not in seen_urls]
        if filtered_articles:
            print(f"  → 排除本日已選文章 {len(seen_urls)} 篇")
            all_articles = filtered_articles

    print(f"  → 共取得 {len(all_articles)} 篇文章")
    if not all_articles:
        print("[錯誤] 找不到可用文章，請稍後再試。")
        sys.exit(1)

    print("\n[Step 2] 精選文章...")
    top = pick_top_article(all_articles)
    source_url = top.get("url", "")
    source_name = top.get("source", "")
    print(f"  → 選出：{top.get('title', '')[:60]}")
    print(f"  → 來源：{source_name}  理由：{top.get('pick_reason', '')}")

    print("\n[Step 3] 生成貼文內容...")
    post_content = generate_post_content(top, today_str)
    print(f"  → Caption 預覽：{post_content.get('caption', '')[:120]}...")
    if dry_run:
        print("\n[Dry Run] 完整文案：")
        print(json.dumps(post_content, ensure_ascii=False, indent=2))

    print("\n[Step 4] 生成圖卡...")
    image_paths = generate_all_images(
        post_content,
        source=source_name,
        date_str=today_str,
        output_dir=str(output_dir),
    )
    print(f"  → 圖片：{len(image_paths)} 張")

    post_id = ""
    reply_id = ""
    if skip_publish or dry_run:
        print("\n[Step 5] 跳過發布")
        print(f"  主文：\n{post_content.get('caption', '')}")
    else:
        print("\n[Step 5] 發布到 Threads...")
        caption = post_content.get("caption", "")
        if len(image_paths) > 1:
            post_id = publish_carousel(image_paths, caption)
        else:
            post_id = publish_single(image_paths[0], caption)
        print(f"  → 發布成功！Post ID: {post_id}")
        if source_url or source_name:
            reply_lines = []
            if source_name:
                reply_lines.append(f"來源：{source_name}")
            if source_url:
                reply_lines.append(source_url)
            reply_text = "\n".join(reply_lines)
            reply_id = post_reply(post_id, reply_text)
            print(f"  → 來源留言成功！Reply ID: {reply_id}")

    updated_seen_urls = []
    for url in seen_urls + [source_url]:
        if url and url not in updated_seen_urls:
            updated_seen_urls.append(url)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": today_str,
                "articles_fetched": len(all_articles),
                "selected": {
                    "title": top.get("title"),
                    "source": source_name,
                    "url": source_url,
                    "pick_reason": top.get("pick_reason"),
                },
                "post_content": post_content,
                "image_path": str(image_paths[0]),
                "image_paths": [str(path) for path in image_paths],
                "source_url": source_url,
                "seen_urls": updated_seen_urls,
                "post_id": post_id,
                "reply_id": reply_id,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n[來源 URL] {source_url}")
    print(f"\n[記錄] 儲存至：{log_path}")
    print(f"\n{'=' * 50}")
    print(f"  完成！{today_str} 精選文章已就緒")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Threads Agent")
    parser.add_argument("--dry-run", action="store_true", help="產生內容但不發布")
    parser.add_argument("--skip-publish", action="store_true", help="只生成圖文，不發布")
    args = parser.parse_args()
    run(dry_run=args.dry_run, skip_publish=args.skip_publish)
