"""
Threads 發布模組
使用 Meta Threads API（Graph API）上傳圖片並發布輪播貼文
文件：https://developers.facebook.com/docs/threads
"""
import os
import time
import requests
from typing import List

THREADS_API = "https://graph.threads.net/v1.0"
ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
USER_ID = os.environ.get("THREADS_USER_ID", "")


def _api(method: str, path: str, **kwargs) -> dict:
    """通用 API 呼叫"""
    url = f"{THREADS_API}{path}"
    params = kwargs.pop("params", {})
    params["access_token"] = ACCESS_TOKEN

    resp = requests.request(method, url, params=params, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _upload_image_container(image_path: str, is_carousel_item: bool = True) -> str:
    """
    第一步：建立單張圖片的 media container。
    Threads API 要求圖片必須是公開可存取的 URL，
    所以這裡先把圖片上傳到 Imgur（免費）取得公開 URL。
    """
    # 上傳到 Imgur 取得公開 URL
    imgur_url = _upload_to_imgur(image_path)

    data = {
        "media_type": "IMAGE",
        "image_url": imgur_url,
        "is_carousel_item": str(is_carousel_item).lower()
    }
    result = _api("POST", f"/{USER_ID}/threads", data=data)
    container_id = result.get("id")
    print(f"[Threads] 圖片 container 建立：{container_id}")
    return container_id


def _upload_to_imgur(image_path: str) -> str:
    """上傳圖片到 Imgur，回傳公開 URL"""
    imgur_client_id = os.environ.get("IMGUR_CLIENT_ID", "")
    if not imgur_client_id:
        raise ValueError("需要設定 IMGUR_CLIENT_ID 環境變數（免費申請）")

    with open(image_path, "rb") as f:
        resp = requests.post(
            "https://api.imgur.com/3/image",
            headers={"Authorization": f"Client-ID {imgur_client_id}"},
            files={"image": f}
        )
        resp.raise_for_status()
        data = resp.json()
        url = data["data"]["link"]
        print(f"[Imgur] 上傳成功：{url}")
        return url


def _create_carousel_container(item_ids: List[str], caption: str) -> str:
    """第二步：建立輪播 container"""
    data = {
        "media_type": "CAROUSEL",
        "children": ",".join(item_ids),
        "text": caption
    }
    result = _api("POST", f"/{USER_ID}/threads", data=data)
    container_id = result.get("id")
    print(f"[Threads] 輪播 container 建立：{container_id}")
    return container_id


def _publish_container(container_id: str) -> str:
    """第三步：發布"""
    data = {"creation_id": container_id}
    result = _api("POST", f"/{USER_ID}/threads_publish", data=data)
    post_id = result.get("id")
    print(f"[Threads] 貼文發布成功！ID：{post_id}")
    return post_id


def publish_carousel(image_paths: List[str], caption: str) -> str:
    """
    完整發布流程：
    1. 逐張建立圖片 container
    2. 建立輪播 container
    3. 發布
    回傳 post_id
    """
    if not ACCESS_TOKEN or not USER_ID:
        raise ValueError("請在 .env 設定 THREADS_ACCESS_TOKEN 和 THREADS_USER_ID")

    # Threads 輪播最多 20 張，至少 2 張
    if len(image_paths) < 2:
        raise ValueError("輪播至少需要 2 張圖片")
    image_paths = image_paths[:20]

    print(f"[Threads] 開始上傳 {len(image_paths)} 張圖片...")
    item_ids = []
    for path in image_paths:
        container_id = _upload_image_container(path, is_carousel_item=True)
        item_ids.append(container_id)
        time.sleep(1)  # API 限流

    # 等待 container 處理完成
    print("[Threads] 等待圖片處理（30秒）...")
    time.sleep(30)

    carousel_id = _create_carousel_container(item_ids, caption)
    time.sleep(5)

    post_id = _publish_container(carousel_id)
    return post_id


def publish_single(image_path: str, caption: str) -> str:
    """發布單張圖片貼文（備用）"""
    if not ACCESS_TOKEN or not USER_ID:
        raise ValueError("請在 .env 設定 THREADS_ACCESS_TOKEN 和 THREADS_USER_ID")

    imgur_url = _upload_to_imgur(image_path)
    data = {
        "media_type": "IMAGE",
        "image_url": imgur_url,
        "text": caption
    }
    result = _api("POST", f"/{USER_ID}/threads", data=data)
    container_id = result["id"]
    time.sleep(30)

    post_id = _publish_container(container_id)
    return post_id


def publish_with_url(image_url: str, caption: str) -> str:
    """用公開圖片 URL 直接發布（不需要 Imgur）"""
    if not ACCESS_TOKEN or not USER_ID:
        raise ValueError("請在環境變數設定 THREADS_ACCESS_TOKEN 和 THREADS_USER_ID")

    data = {
        "media_type": "IMAGE",
        "image_url": image_url,
        "text": caption,
    }
    result = _api("POST", f"/{USER_ID}/threads", data=data)
    container_id = result["id"]
    print(f"[Threads] Container 建立：{container_id}")

    print("[Threads] 等待處理（30秒）...")
    time.sleep(30)

    post_id = _publish_container(container_id)
    return post_id


def post_reply(post_id: str, text: str) -> str:
    """在貼文下留言"""
    if not ACCESS_TOKEN or not USER_ID:
        raise ValueError("請在環境變數設定 THREADS_ACCESS_TOKEN 和 THREADS_USER_ID")

    data = {
        "media_type": "TEXT",
        "text": text,
        "reply_to_id": post_id,
    }
    result = _api("POST", f"/{USER_ID}/threads", data=data)
    container_id = result["id"]
    time.sleep(5)
    reply_id = _publish_container(container_id)
    return reply_id
