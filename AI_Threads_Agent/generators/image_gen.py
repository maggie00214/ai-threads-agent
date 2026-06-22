"""
Generate denser orange-blue carousel cards for Threads/Instagram-style posts.
"""
import os
import re
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1080

BG = "#07111F"
SHELL = "#0E1728"
SURFACE = "#111D33"
SURFACE_2 = "#16243C"
BORDER = "#26385A"
INNER = "#1D3154"
ORANGE = "#FF7A1A"
BLUE = "#4A94FF"
YELLOW = "#FFD247"
WHITE = "#F4F7FF"
WHITE_SOFT = "#CBD4E8"
MUTED = "#8EA1C4"
MUTED_2 = "#7386AC"
GREEN_BG = "#163424"
GREEN_LINE = "#2E8A55"
GREEN_TEXT = "#A7F1BA"

FONT_PATH = os.environ.get("FONT_PATH", "")


def _font(size: int, bold: bool = False):
    candidates = []
    if FONT_PATH:
        candidates.append(FONT_PATH)
    if bold:
        candidates += [
            "C:/Windows/Fonts/msjhbd.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ]
    candidates += [
        "C:/Windows/Fonts/msjh.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _safe_text(text: str, fallback: str = "") -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text or fallback


def _trim_chars(text: str, limit: int) -> str:
    text = _safe_text(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" ，、。；;:：,.!?") + "..."


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> List[str]:
    text = _safe_text(text)
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z0-9_.%$+\-/:]+|.", text)
    lines: List[str] = []
    current = ""
    for token in tokens:
        probe = current + token
        if draw.textbbox((0, 0), probe, font=font)[2] <= max_w or not current:
            current = probe
        else:
            lines.append(current.strip())
            current = token
    if current:
        lines.append(current.strip())
    return lines


def _ellipsize(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    text = _safe_text(text)
    if not text:
        return ""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_w:
        return text
    suffix = "..."
    allowed = max_w - draw.textbbox((0, 0), suffix, font=font)[2]
    kept = ""
    for ch in text:
        if draw.textbbox((0, 0), kept + ch, font=font)[2] > allowed:
            break
        kept += ch
    return (kept.rstrip() + suffix) if kept else suffix


def _wrap_ellipsized(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int) -> List[str]:
    lines = _wrap(draw, text, font, max_w)
    if len(lines) <= max_lines:
        return lines
    keep = lines[:max_lines]
    keep[-1] = _ellipsize(draw, "".join([keep[-1], *lines[max_lines:]]), font, max_w)
    return keep


def _line_h(draw: ImageDraw.ImageDraw, font, gap: int = 0) -> int:
    box = draw.textbbox((0, 0), "Ag測試", font=font)
    return box[3] - box[1] + gap


def _text_block_size(draw: ImageDraw.ImageDraw, lines: List[str], font, gap: int = 8) -> tuple[int, int]:
    if not lines:
        return 0, 0
    widths = []
    total_h = 0
    for idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        widths.append(bbox[2] - bbox[0])
        total_h += bbox[3] - bbox[1]
        if idx < len(lines) - 1:
            total_h += gap
    return max(widths), total_h


def _fit_lines_to_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_w: int,
    max_h: int,
    max_lines: int,
    start: int,
    minimum: int,
    bold: bool,
    gap: int = 8,
):
    fallback_font = _font(minimum, bold)
    fallback_lines = _wrap_ellipsized(draw, text, fallback_font, max_w, max_lines)
    for size in range(start, minimum - 1, -2):
        font = _font(size, bold)
        lines = _wrap(draw, text, font, max_w)
        if not lines or len(lines) > max_lines:
            continue
        _, height = _text_block_size(draw, lines, font, gap)
        if height <= max_h:
            return font, lines
    return fallback_font, fallback_lines


def _draw_lines(draw, x: int, y: int, lines: List[str], font, fill: str, gap: int = 8) -> int:
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += _line_h(draw, font, gap)
    return y


def _draw_lines_in_box(draw, box, lines: List[str], font, fill: str, gap: int = 8) -> None:
    x1, y1, x2, y2 = box
    _, block_h = _text_block_size(draw, lines, font, gap)
    y = y1 + max(0, (y2 - y1 - block_h) // 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text((x1, y - bbox[1]), line, font=font, fill=fill)
        y += bbox[3] - bbox[1] + gap


def _split_sentences(text: str) -> List[str]:
    text = _safe_text(text)
    if not text:
        return []
    parts = re.split(r"[。！？!?]\s*", text)
    out = []
    for part in parts:
        part = _safe_text(part)
        if part and part not in out:
            out.append(part)
    return out


def _merge_distinct(*parts: str, limit: int) -> str:
    merged: List[str] = []
    for part in parts:
        part = _safe_text(part)
        if not part:
            continue
        if any(part in existing or existing in part for existing in merged):
            continue
        merged.append(part)
    return _trim_chars(" ".join(merged), limit)


def _ensure_dense(primary: str, backups: List[str], min_chars: int, limit: int) -> str:
    text = _safe_text(primary)
    for part in backups:
        if len(text) >= min_chars:
            break
        text = _merge_distinct(text, part, limit=limit)
    return _trim_chars(text, limit)


def _normalize_blocks(post: Dict) -> List[Dict[str, str]]:
    blocks = []
    for item in post.get("insight_blocks", [])[:3]:
        heading = _safe_text(item.get("heading", ""), "重點")[:10]
        body = _trim_chars(item.get("body", ""), 78)
        if heading and body:
            blocks.append({"heading": heading, "body": body})
    defaults = [
        ("核心", _safe_text(post.get("subtitle_zh", ""), "這次更新和一般使用者的工作流直接有關")),
        ("影響", "它影響的不是單一功能，而是你每天怎麼用 AI 工具與資料。"),
        ("提醒", "先檢查權限、外部串接與敏感資料流向，再決定要不要開啟自動化。"),
    ]
    while len(blocks) < 3:
        heading, body = defaults[len(blocks)]
        blocks.append({"heading": heading, "body": _trim_chars(body, 78)})
    return blocks[:3]


def _build_story(post: Dict) -> Dict[str, object]:
    title = _safe_text(post.get("title_zh", ""), "這則 AI 更新別滑掉")
    subtitle = _safe_text(post.get("subtitle_zh", ""), "這次更新和你每天用工具的方式直接有關")
    hook = _safe_text(post.get("hook_line", ""), "這不是小更新，是真的會影響工作流。")
    angle = _safe_text(post.get("angle", ""), "實用提醒")
    caption = _safe_text(post.get("caption", ""))
    blocks = _normalize_blocks(post)

    sentences = _split_sentences(caption)
    if not sentences:
        sentences = [subtitle, blocks[0]["body"], blocks[1]["body"], blocks[2]["body"]]

    overview = _ensure_dense(" ".join(sentences[:2]), [subtitle, blocks[0]["body"], caption], 76, 156)
    why = _ensure_dense(
        " ".join(sentences[1:3]),
        [blocks[1]["body"], "重點不是模型聰不聰明，而是它會不會開始接手你的流程與權限。"],
        62,
        126,
    )
    risk = _ensure_dense(sentences[2] if len(sentences) > 2 else blocks[1]["body"], [blocks[1]["body"], blocks[2]["body"]], 48, 96)
    summary = _ensure_dense(sentences[0], [subtitle, blocks[0]["body"]], 58, 116)

    actions = [
        {"label": "先做 1", "body": "先確認這個工具拿得到哪些外部服務、檔案和帳號權限"},
        {"label": "先做 2", "body": "敏感資料先別直接丟進自動化流程，不用的串接也先關掉"},
        {"label": "先做 3", "body": "先用測試環境試跑，確定穩定後再放進正式工作流"},
    ]

    return {
        "title": title,
        "subtitle": subtitle,
        "hook": hook,
        "angle": angle,
        "blocks": blocks,
        "overview": overview,
        "why": why,
        "risk": risk,
        "summary": summary,
        "actions": actions,
    }


def _draw_shell(draw) -> None:
    margin = 48
    draw.rounded_rectangle([margin, margin, W - margin, H - margin], radius=30, fill=SHELL, outline=BORDER, width=2)
    draw.rounded_rectangle([margin + 14, margin + 14, W - margin - 14, H - margin - 14], radius=24, outline=INNER, width=1)
    draw.rectangle([margin, margin, W - margin, margin + 10], fill=ORANGE)


def _draw_footer(draw, source: str, date_str: str) -> None:
    y = H - 106
    font = _font(21, bold=True)
    draw.rectangle([82, y - 24, W - 82, y - 21], fill=BORDER)
    draw.text((82, y), f"SOURCE  {source.upper()[:26]}", font=font, fill=MUTED)
    date_w = draw.textbbox((0, 0), date_str, font=font)[2]
    draw.text((W - 82 - date_w, y), date_str, font=font, fill=MUTED)


def _draw_page_chip(draw, page_no: int, total_pages: int) -> None:
    text = f"{page_no}/{total_pages}"
    font = _font(20, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0] + 30
    h = bbox[3] - bbox[1] + 18
    x2 = W - 82
    y1 = 88
    draw.rounded_rectangle([x2 - w, y1, x2, y1 + h], radius=14, fill="#152746", outline="#314E81", width=1)
    draw.text((x2 - w + 15, y1 + 8), text, font=font, fill=WHITE_SOFT)


def _badge(draw, text: str, x: int, y: int, fill: str, text_fill: str) -> int:
    font = _font(24, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0] + 34
    h = bbox[3] - bbox[1] + 22
    draw.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=fill)
    draw.text((x + 17, y + 8), text, font=font, fill=text_fill)
    return x + w + 12


def _draw_info_card(draw, box, heading: str, body: str, accent: str, max_lines: int = 3) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=22, fill=SURFACE, outline="#2B4672", width=2)
    draw.rounded_rectangle([x1 + 14, y1 + 14, x2 - 14, y2 - 14], radius=16, outline="#1C2E4F", width=1)
    draw.rectangle([x1 + 22, y1 + 22, x1 + 28, y2 - 22], fill=accent)
    draw.text((x1 + 48, y1 + 20), heading, font=_font(19, bold=True), fill=accent)
    body_font = _font(25)
    lines = _wrap_ellipsized(draw, body, body_font, x2 - x1 - 72, max_lines)
    _draw_lines(draw, x1 + 48, y1 + 56, lines, body_font, WHITE, 6)


def _draw_paragraph_card(draw, box, title: str, body: str, accent: str, max_lines: int = 5) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=24, fill=SURFACE, outline="#2B4672", width=2)
    draw.rounded_rectangle([x1 + 14, y1 + 14, x2 - 14, y2 - 14], radius=18, outline="#1C2E4F", width=1)
    draw.text((x1 + 28, y1 + 22), title, font=_font(20, bold=True), fill=accent)
    body_font = _font(26)
    lines = _wrap_ellipsized(draw, body, body_font, x2 - x1 - 56, max_lines)
    _draw_lines(draw, x1 + 28, y1 + 60, lines, body_font, WHITE, 8)


def _draw_action_card(draw, box, label: str, body: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=22, fill=SURFACE, outline="#2B4672", width=2)
    draw.rounded_rectangle([x1 + 14, y1 + 14, x2 - 14, y2 - 14], radius=16, outline="#1C2E4F", width=1)
    draw.ellipse([x1 + 24, y1 + 24, x1 + 54, y1 + 54], fill=GREEN_BG, outline=GREEN_LINE, width=1)
    draw.text((x1 + 33, y1 + 24), "v", font=_font(18, bold=True), fill=GREEN_TEXT)
    draw.text((x1 + 72, y1 + 16), label, font=_font(20, bold=True), fill=WHITE_SOFT)
    body_font = _font(24)
    lines = _wrap_ellipsized(draw, body, body_font, x2 - x1 - 96, 3)
    _draw_lines(draw, x1 + 72, y1 + 46, lines, body_font, WHITE, 4)


def generate_featured_card(post: Dict, source: str, date_str: str, output_path: str) -> str:
    story = _build_story(post)
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_shell(draw)

    x = 82
    y = 88
    x = _badge(draw, _safe_text(post.get("category", "AI NEWS"), "AI NEWS").upper()[:12], x, y, ORANGE, WHITE)
    _badge(draw, story["angle"][:16], x, y, "#152746", BLUE)
    _draw_page_chip(draw, 1, 3)

    title_box = [82, 166, W - 96, 320]
    title_font, title_lines = _fit_lines_to_box(draw, story["title"], title_box[2] - title_box[0], title_box[3] - title_box[1], 3, 58, 30, True, 8)
    _draw_lines_in_box(draw, title_box, title_lines, title_font, WHITE, 8)

    subtitle_box = [82, 326, W - 96, 386]
    subtitle_font, subtitle_lines = _fit_lines_to_box(draw, story["subtitle"], subtitle_box[2] - subtitle_box[0], subtitle_box[3] - subtitle_box[1], 2, 28, 22, True, 6)
    _draw_lines_in_box(draw, subtitle_box, subtitle_lines, subtitle_font, WHITE_SOFT, 6)

    hook_box = [82, 416, W - 82, 548]
    draw.rounded_rectangle(hook_box, radius=24, fill=SURFACE_2, outline="#2F4A7A", width=2)
    draw.rounded_rectangle([hook_box[0] + 14, hook_box[1] + 14, hook_box[2] - 14, hook_box[3] - 14], radius=18, outline="#20345A", width=1)
    draw.rectangle([hook_box[0] + 24, hook_box[1] + 24, hook_box[0] + 31, hook_box[3] - 24], fill=YELLOW)
    draw.text((hook_box[0] + 48, hook_box[1] + 22), "別只看新聞標題", font=_font(20, bold=True), fill=YELLOW)
    hook_font, hook_lines = _fit_lines_to_box(draw, story["hook"], hook_box[2] - hook_box[0] - 80, 68, 2, 40, 28, True, 8)
    _draw_lines_in_box(draw, [hook_box[0] + 48, hook_box[1] + 54, hook_box[2] - 24, hook_box[3] - 18], hook_lines, hook_font, WHITE, 8)

    blocks = story["blocks"]
    _draw_info_card(draw, [82, 570, W - 82, 680], blocks[0]["heading"], _trim_chars(_ensure_dense(blocks[0]["body"], [story["summary"]], 34, 68), 68), BLUE, 2)
    _draw_info_card(draw, [82, 700, W - 82, 810], blocks[1]["heading"], _trim_chars(_ensure_dense(blocks[1]["body"], [story["risk"]], 34, 68), 68), ORANGE, 2)
    _draw_info_card(draw, [82, 830, W - 82, 940], blocks[2]["heading"], _trim_chars(_ensure_dense(blocks[2]["body"], ["先看權限、串接與資料流向。"], 34, 68), 68), YELLOW, 2)

    _draw_footer(draw, source, date_str)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"[Image] saved: {output_path}")
    return output_path


def generate_detail_card(post: Dict, source: str, date_str: str, output_path: str) -> str:
    story = _build_story(post)
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_shell(draw)

    x = 82
    y = 88
    x = _badge(draw, "AI NEWS", x, y, ORANGE, WHITE)
    _badge(draw, "重點拆解", x, y, "#152746", BLUE)
    _draw_page_chip(draw, 2, 3)

    draw.text((82, 168), "這則更新在說什麼", font=_font(22, bold=True), fill=YELLOW)
    title_box = [82, 198, W - 96, 300]
    title_font, title_lines = _fit_lines_to_box(draw, story["title"], title_box[2] - title_box[0], title_box[3] - title_box[1], 2, 50, 30, True, 8)
    _draw_lines_in_box(draw, title_box, title_lines, title_font, WHITE, 8)

    _draw_paragraph_card(draw, [82, 334, W - 82, 544], "先看核心", story["overview"], WHITE_SOFT, 5)
    _draw_paragraph_card(draw, [82, 564, W - 82, 774], "為什麼值得注意", _merge_distinct(story["why"], story["blocks"][1]["body"], limit=132), ORANGE, 5)
    _draw_paragraph_card(draw, [82, 794, W - 82, 942], "一句話影響", _merge_distinct(story["risk"], "這種變化通常不是看熱鬧就好，而是會直接影響你接下來怎麼用工具。", limit=96), YELLOW, 3)

    _draw_footer(draw, source, date_str)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"[Image] saved: {output_path}")
    return output_path


def generate_action_card(post: Dict, source: str, date_str: str, output_path: str) -> str:
    story = _build_story(post)
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_shell(draw)

    x = 82
    y = 88
    x = _badge(draw, "AI NEWS", x, y, ORANGE, WHITE)
    _badge(draw, "你可以怎麼做", x, y, "#152746", BLUE)
    _draw_page_chip(draw, 3, 3)

    title_box = [82, 166, W - 96, 266]
    title_font, title_lines = _fit_lines_to_box(draw, "看到這類 AI 更新，先做這 3 件事", title_box[2] - title_box[0], title_box[3] - title_box[1], 2, 48, 28, True, 8)
    _draw_lines_in_box(draw, title_box, title_lines, title_font, WHITE, 8)

    intro_font = _font(24, bold=True)
    intro_lines = _wrap_ellipsized(draw, story["summary"], intro_font, W - 180, 3)
    _draw_lines(draw, 82, 282, intro_lines, intro_font, WHITE_SOFT, 6)

    actions = story["actions"]
    _draw_action_card(draw, [82, 392, W - 82, 534], actions[0]["label"], actions[0]["body"])
    _draw_action_card(draw, [82, 554, W - 82, 696], actions[1]["label"], actions[1]["body"])
    _draw_action_card(draw, [82, 716, W - 82, 858], actions[2]["label"], actions[2]["body"])

    cta_box = [82, 878, W - 82, 964]
    draw.rounded_rectangle(cta_box, radius=22, fill=SURFACE_2, outline="#2B4672", width=2)
    draw.rounded_rectangle([cta_box[0] + 14, cta_box[1] + 14, cta_box[2] - 14, cta_box[3] - 14], radius=16, outline="#1C2E4F", width=1)
    draw.text((108, 894), "留言區延伸", font=_font(18, bold=True), fill=MUTED_2)
    cta_font = _font(23, bold=True)
    cta_lines = _wrap_ellipsized(draw, "你會先追新功能，還是先把權限收緊？", cta_font, W - 220, 2)
    _draw_lines(draw, 108, 922, cta_lines, cta_font, WHITE, 4)

    _draw_footer(draw, source, date_str)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"[Image] saved: {output_path}")
    return output_path


def generate_all_images(post_content: Dict, source: str, date_str: str, output_dir: str) -> List[str]:
    from datetime import datetime

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    paths = [
        str(Path(output_dir) / f"featured_{ts}_01.png"),
        str(Path(output_dir) / f"featured_{ts}_02.png"),
        str(Path(output_dir) / f"featured_{ts}_03.png"),
    ]
    generate_featured_card(post_content, source, date_str, paths[0])
    generate_detail_card(post_content, source, date_str, paths[1])
    generate_action_card(post_content, source, date_str, paths[2])
    return paths
