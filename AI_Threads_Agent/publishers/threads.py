"""
Threads publishing helpers.
"""
import os
import time
from typing import List

import requests

THREADS_API = "https://graph.threads.net/v1.0"
ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
USER_ID = os.environ.get("THREADS_USER_ID", "")


def _api(method: str, path: str, **kwargs) -> dict:
    url = f"{THREADS_API}{path}"
    params = kwargs.pop("params", {})
    params["access_token"] = ACCESS_TOKEN

    resp = requests.request(method, url, params=params, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _upload_to_imgur(image_path: str) -> str:
    imgur_client_id = os.environ.get("IMGUR_CLIENT_ID", "")
    if not imgur_client_id:
        raise ValueError("IMGUR_CLIENT_ID is not configured")

    with open(image_path, "rb") as f:
        resp = requests.post(
            "https://api.imgur.com/3/image",
            headers={"Authorization": f"Client-ID {imgur_client_id}"},
            files={"image": f},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        url = data["data"]["link"]
        print(f"[Imgur] uploaded: {url}")
        return url


def _upload_to_catbox(image_path: str) -> str:
    with open(image_path, "rb") as f:
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": f},
            timeout=60,
        )
        resp.raise_for_status()
        url = resp.text.strip()
        if not url.startswith("http"):
            raise ValueError(f"Catbox upload failed: {url}")
        print(f"[Catbox] uploaded: {url}")
        return url


def _upload_to_public_url(image_path: str) -> str:
    try:
        return _upload_to_imgur(image_path)
    except Exception as imgur_error:
        print(f"[Upload] Imgur unavailable, fallback to Catbox: {imgur_error}")
        return _upload_to_catbox(image_path)


def _upload_image_container(image_path: str, is_carousel_item: bool = True) -> str:
    public_url = _upload_to_public_url(image_path)
    data = {
        "media_type": "IMAGE",
        "image_url": public_url,
        "is_carousel_item": str(is_carousel_item).lower(),
    }
    result = _api("POST", f"/{USER_ID}/threads", data=data)
    container_id = result.get("id")
    print(f"[Threads] image container created: {container_id}")
    return container_id


def _create_carousel_container(item_ids: List[str], caption: str) -> str:
    data = {
        "media_type": "CAROUSEL",
        "children": ",".join(item_ids),
        "text": caption,
    }
    result = _api("POST", f"/{USER_ID}/threads", data=data)
    container_id = result.get("id")
    print(f"[Threads] carousel container created: {container_id}")
    return container_id


def _publish_container(container_id: str) -> str:
    data = {"creation_id": container_id}
    result = _api("POST", f"/{USER_ID}/threads_publish", data=data)
    post_id = result.get("id")
    print(f"[Threads] published: {post_id}")
    return post_id


def publish_carousel(image_paths: List[str], caption: str) -> str:
    if not ACCESS_TOKEN or not USER_ID:
        raise ValueError("THREADS_ACCESS_TOKEN or THREADS_USER_ID is missing")
    if len(image_paths) < 2:
        raise ValueError("Carousel publishing requires at least 2 images")

    image_paths = image_paths[:20]
    print(f"[Threads] uploading {len(image_paths)} images...")
    item_ids = []
    for path in image_paths:
        container_id = _upload_image_container(path, is_carousel_item=True)
        item_ids.append(container_id)
        time.sleep(1)

    print("[Threads] waiting 30s before creating carousel...")
    time.sleep(30)

    carousel_id = _create_carousel_container(item_ids, caption)
    time.sleep(5)
    return _publish_container(carousel_id)


def publish_single(image_path: str, caption: str) -> str:
    if not ACCESS_TOKEN or not USER_ID:
        raise ValueError("THREADS_ACCESS_TOKEN or THREADS_USER_ID is missing")

    public_url = _upload_to_public_url(image_path)
    data = {
        "media_type": "IMAGE",
        "image_url": public_url,
        "text": caption,
    }
    result = _api("POST", f"/{USER_ID}/threads", data=data)
    container_id = result["id"]
    print(f"[Threads] single post container created: {container_id}")
    time.sleep(30)
    return _publish_container(container_id)


def publish_with_url(image_url: str, caption: str) -> str:
    if not ACCESS_TOKEN or not USER_ID:
        raise ValueError("THREADS_ACCESS_TOKEN or THREADS_USER_ID is missing")

    data = {
        "media_type": "IMAGE",
        "image_url": image_url,
        "text": caption,
    }
    result = _api("POST", f"/{USER_ID}/threads", data=data)
    container_id = result["id"]
    print(f"[Threads] container created: {container_id}")
    print("[Threads] waiting 30s before publish...")
    time.sleep(30)
    return _publish_container(container_id)


def post_reply(post_id: str, text: str) -> str:
    if not ACCESS_TOKEN or not USER_ID:
        raise ValueError("THREADS_ACCESS_TOKEN or THREADS_USER_ID is missing")

    data = {
        "media_type": "TEXT",
        "text": text,
        "reply_to_id": post_id,
    }
    result = _api("POST", f"/{USER_ID}/threads", data=data)
    container_id = result["id"]
    time.sleep(5)
    return _publish_container(container_id)
