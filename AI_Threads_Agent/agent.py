"""
AI Threads Agent — 主流程
每日自動：爬蟲 → 精選最熱議一篇 → 生圖 → 發布到 Threads
"""
import os
import sys
import json

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from scrapers.ptt import scrape_ptt
from scrapers.rss import scrape_rss
from processors.ai_filter import pick_top_article, generate_post_content
from generators.image_gen import generate_all_images
from publishers.threads import publish_single

# ── 設定 ──────────────────────────────────────────────────────
MIN_PUSHES = 20     # PTT 最低推文數
DAYS_BACK = 1       # 爬取幾天內的文章
DAILY_BASE = Path(__file__).parent.parent / "每日內容"


def run(dry_run: bool = False, skip_publish: bool = False):
    today = datetime.now()
    today_str = today.strftime("%Y.%m.%d")
    date_folder = DAILY_BASE / today.strftime("%Y%m%d")
    output_dir = date_folder / "images"
    date_folder.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"  AI Threads Agent 啟動  {today_str}")
    print(f"{'='*50}\n")

    # ── Step 1: 爬蟲 ──────────────────────────────────────────
    print("[Step 1] 開始爬蟲...")
    ptt_articles = scrape_ptt(min_pushes=MIN_PUSHES, days_back=DAYS_BACK)
    rss_articles = scrape_rss(days_back=DAYS_BACK)
    all_articles = ptt_articles + rss_articles
    print(f"  → 共取得 {len(all_articles)} 篇文章")

    if not all_articles:
        print("[錯誤] 沒有抓到任何文章，請檢查網路連線或爬蟲設定")
        sys.exit(1)

    # ── Step 2: 精選最熱議一篇 ────────────────────────────────
    print(f"\n[Step 2] 精選最熱議文章...")
    top = pick_top_article(all_articles)
    print(f"  → 選出：{top.get('title', '')[:50]}")
    print(f"  → 來源：{top.get('source', '')}  理由：{top.get('pick_reason', '')}")

    # ── Step 3: 生成繁中文案 ───────────────────────────────────
    print(f"\n[Step 3] 生成繁體中文發文內容...")
    post_content = generate_post_content(top, today_str)
    print(f"  圖片標題：{post_content.get('image_title')}")
    print(f"  Threads 主文預覽：\n  {post_content.get('caption', '')[:120]}...")

    if dry_run:
        print("\n[Dry Run] 完整文案：")
        print(json.dumps(post_content, ensure_ascii=False, indent=2))

    # ── Step 4: 生成圖片 ────────────────────────────────────────
    print(f"\n[Step 4] 生成圖卡...")
    image_paths = generate_all_images(
        post_content,
        source=top.get("source", ""),
        date_str=today_str,
        output_dir=str(output_dir)
    )
    print(f"  → 圖片：{image_paths[0]}")

    # ── Step 5: 發布到 Threads ─────────────────────────────────
    if skip_publish or dry_run:
        print(f"\n[Step 5] 跳過發布")
        print(f"  主文：\n{post_content.get('caption')}")
    else:
        print(f"\n[Step 5] 發布到 Threads...")
        caption = post_content.get("caption", "")
        post_id = publish_single(image_paths[0], caption)
        print(f"  → 發布成功！Post ID: {post_id}")

    # ── 儲存執行記錄 ───────────────────────────────────────────
    log_path = date_folder / "log.json"
    source_url = top.get("url", "")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump({
            "date": today_str,
            "articles_fetched": len(all_articles),
            "selected": {
                "title": top.get("title"),
                "source": top.get("source"),
                "url": source_url,
                "pick_reason": top.get("pick_reason"),
            },
            "post_content": post_content,
            "image_path": str(image_paths[0]),
            "source_url": source_url,
        }, f, ensure_ascii=False, indent=2)

    # 輸出來源 URL，供瀏覽器自動化留言使用
    print(f"\n[來源 URL] {source_url}")

    print(f"\n[記錄] 儲存至：{log_path}")
    print(f"\n{'='*50}")
    print(f"  完成！{today_str} 精選文章已就緒")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Threads Agent")
    parser.add_argument("--dry-run", action="store_true",
                        help="完整執行但不發布到 Threads")
    parser.add_argument("--skip-publish", action="store_true",
                        help="生成圖片但不發布")
    args = parser.parse_args()

    run(dry_run=args.dry_run, skip_publish=args.skip_publish)
