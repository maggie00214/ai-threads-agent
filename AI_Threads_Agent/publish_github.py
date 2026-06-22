"""
Publish generated images from GitHub Actions, then reply with the source link.
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).parent
load_dotenv(APP_DIR / ".env")
sys.path.insert(0, str(APP_DIR))

from publishers.threads import post_reply, publish_carousel, publish_single


def _resolve_image_paths(log: dict) -> list[str]:
    paths = log.get("image_paths") or [log.get("image_path", "")]
    resolved = []
    for path in paths:
        if not path:
            continue
        img_path = Path(path)
        if not img_path.is_absolute():
            img_path = (APP_DIR.parent / img_path).resolve()
        resolved.append(str(img_path))
    return resolved


def main():
    today = datetime.now().strftime("%Y%m%d")
    log_path = APP_DIR.parent / "每日內容" / today / "log.json"

    if not log_path.exists():
        print(f"[Error] missing log.json: {log_path}")
        sys.exit(1)

    with open(log_path, encoding="utf-8") as f:
        log = json.load(f)

    caption = log["post_content"]["caption"]
    source_url = log.get("source_url", "")
    source_name = log["selected"].get("source", "")
    image_paths = _resolve_image_paths(log)

    if not image_paths:
        print("[Error] no images found in log.json")
        sys.exit(1)

    print(f"[Publish] image count: {len(image_paths)}")
    print(f"[Publish] caption preview: {caption[:60]}...")

    if len(image_paths) > 1:
        post_id = publish_carousel(image_paths, caption)
    else:
        post_id = publish_single(image_paths[0], caption)
    print(f"[Publish] post ID: {post_id}")

    reply_id = ""
    if source_url or source_name:
        time.sleep(3)
        reply_lines = []
        if source_name:
            reply_lines.append(f"來源：{source_name}")
        if source_url:
            reply_lines.append(source_url)
        reply_text = "\n".join(reply_lines)
        reply_id = post_reply(post_id, reply_text)
        print(f"[Publish] reply ID: {reply_id}")

    log["post_id"] = post_id
    log["reply_id"] = reply_id
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
