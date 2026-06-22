"""
Generate stable, denser orange-blue carousel cards.
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


def _fit_lines_to_box(draw, text: str, max_w: int, max_h: int, max_lines: int, start: int, minimum: int, bold: bool, gap: int = 8):
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


def _build_story(post: Dict) -> Dict[str, object]:
    title = _safe_text(post.get("title_zh", ""), "這則 AI 更新別滑掉")
    subtitle = _safe_text(post.get("subtitle_zh", ""), "這次更新和你每天用工具的方式直接有關")
    hook = _safe_text(post.get("hook_line", ""), "這不是小更新，是真的會影響工作流。")
    angle = _safe_text(post.get("angle", ""), "實用提醒")
    caption = _safe_text(post.get("caption", ""))

    blocks = []
    for item in post.get("insight_blocks", [])[:3]:
        heading = _safe_text(item.get("heading", ""), "重點")[:10]
        body = _trim_chars(item.get("body", ""), 56)
        if heading and body:
            blocks.append({"heading": heading, "body": body})
    while len(blocks) < 3:
        defaults = [
            {"heading": "核心", "body": _trim_chars(subtitle, 56)},
            {"heading": "影響", "body": "它影響的不是單一功能，而是你每天怎麼用 AI 工具與資料。"},
            {"heading": "提醒", "body": "先看權限、串接與資料流向，再決定要不要開啟自動化。"},
        ]
        blocks.append(defaults[len(blocks)])

    sentences = _split_sentences(caption)
    if not sentences:
        sentences = [subtitle, blocks[0]["body"], blocks[1]["body"], blocks[2]["body"]]

    overview = _merge_distinct(" ".join(sentences[:2]), subtitle, blocks[0]["body"], limit=132)
    why = _merge_distinct(
        " ".join(sentences[1:3]),
        blocks[1]["body"],
        "重點不是模型聰不聰明，而是它會不會開始接手你的流程與權限。",
        limit=108,
    )
    impact = _merge_distinct(
        sentences[2] if len(sentences) > 2 else blocks[1]["body"],
        "這種變化通常不是看熱鬧就好，而是會直接影響你接下來怎麼用工具。",
        limit=74,
    )
    intro = _merge_distinct(sentences[0], subtitle, limit=96)

    actions = [
        {
            "label": "先做 1",
            "title": "先確認它能碰哪些資料",
            "detail": "包含外部服務、檔案、信箱和帳號權限，先搞清楚範圍再用。",
        },
        {
            "label": "先做 2",
            "title": "敏感資料先不要直接丟進去",
            "detail": "沒有在用的串接先關掉，自動化流程也先避開公司敏感資訊。",
        },
        {
            "label": "先做 3",
            "title": "先測試，再進正式工作流",
            "detail": "先用測試環境試跑，確定穩定和可控後，再放進每天真的會用的流程。",
        },
    ]

    return {
        "title": title,
        "subtitle": subtitle,
        "hook": hook,
        "angle": angle,
        "blocks": blocks[:3],
        "overview": overview,
        "why": why,
        "impact": impact,
        "intro": intro,
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


def _draw_info_card(draw, box, heading: str, body: str, accent: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=22, fill=SURFACE, outline="#2B4672", width=2)
    draw.rounded_rectangle([x1 + 14, y1 + 14, x2 - 14, y2 - 14], radius=16, outline="#1C2E4F", width=1)
    draw.rectangle([x1 + 22, y1 + 20, x1 + 28, y2 - 20], fill=accent)
    draw.text((x1 + 48, y1 + 18), heading, font=_font(19, bold=True), fill=accent)
    body_font = _font(22)
    lines = _wrap_ellipsized(draw, body, body_font, x2 - x1 - 72, 2)
    _draw_lines(draw, x1 + 48, y1 + 52, lines, body_font, WHITE, 5)


def _draw_paragraph_card(draw, box, title: str, body: str, accent: str, max_lines: int) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=24, fill=SURFACE, outline="#2B4672", width=2)
    draw.rounded_rectangle([x1 + 14, y1 + 14, x2 - 14, y2 - 14], radius=18, outline="#1C2E4F", width=1)
    draw.text((x1 + 28, y1 + 20), title, font=_font(20, bold=True), fill=accent)
    body_font = _font(23)
    lines = _wrap_ellipsized(draw, body, body_font, x2 - x1 - 56, max_lines)
    _draw_lines(draw, x1 + 28, y1 + 58, lines, body_font, WHITE, 7)


def _draw_action_card(draw, box, label: str, title: str, detail: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=22, fill=SURFACE, outline="#2B4672", width=2)
    draw.rounded_rectangle([x1 + 14, y1 + 14, x2 - 14, y2 - 14], radius=16, outline="#1C2E4F", width=1)
    draw.ellipse([x1 + 24, y1 + 24, x1 + 54, y1 + 54], fill=GREEN_BG, outline=GREEN_LINE, width=1)
    draw.text((x1 + 33, y1 + 24), "v", font=_font(18, bold=True), fill=GREEN_TEXT)
    draw.text((x1 + 72, y1 + 16), label, font=_font(20, bold=True), fill=WHITE_SOFT)
    title_font = _font(22, bold=True)
    detail_font = _font(20)
    title_lines = _wrap_ellipsized(draw, title, title_font, x2 - x1 - 96, 2)
    y = _draw_lines(draw, x1 + 72, y1 + 44, title_lines, title_font, WHITE, 4)
    detail_lines = _wrap_ellipsized(draw, detail, detail_font, x2 - x1 - 96, 2)
    _draw_lines(draw, x1 + 72, y + 2, detail_lines, detail_font, WHITE_SOFT, 3)


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

    _draw_info_card(draw, [82, 574, W - 82, 676], story["blocks"][0]["heading"], story["blocks"][0]["body"], BLUE)
    _draw_info_card(draw, [82, 698, W - 82, 800], story["blocks"][1]["heading"], story["blocks"][1]["body"], ORANGE)
    _draw_info_card(draw, [82, 822, W - 82, 924], "提醒", "先看權限、串接與資料流向，再決定要不要開啟。", YELLOW)

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

    _draw_paragraph_card(draw, [82, 334, W - 82, 522], "先看核心", story["overview"], WHITE_SOFT, 4)
    _draw_paragraph_card(draw, [82, 544, W - 82, 732], "為什麼值得注意", story["why"], ORANGE, 4)
    _draw_paragraph_card(draw, [82, 754, W - 82, 912], "一句話影響", story["impact"], YELLOW, 3)

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

    intro_font = _font(23, bold=True)
    intro_lines = _wrap_ellipsized(draw, story["intro"], intro_font, W - 180, 2)
    _draw_lines(draw, 82, 282, intro_lines, intro_font, WHITE_SOFT, 6)

    actions = story["actions"]
    _draw_action_card(draw, [82, 380, W - 82, 532], actions[0]["label"], actions[0]["title"], actions[0]["detail"])
    _draw_action_card(draw, [82, 548, W - 82, 700], actions[1]["label"], actions[1]["title"], actions[1]["detail"])
    _draw_action_card(draw, [82, 716, W - 82, 868], actions[2]["label"], actions[2]["title"], actions[2]["detail"])

    cta_box = [82, 886, W - 82, 956]
    draw.rounded_rectangle(cta_box, radius=22, fill=SURFACE_2, outline="#2B4672", width=2)
    draw.rounded_rectangle([cta_box[0] + 14, cta_box[1] + 14, cta_box[2] - 14, cta_box[3] - 14], radius=16, outline="#1C2E4F", width=1)
    draw.text((108, 900), "留言區延伸", font=_font(17, bold=True), fill=MUTED_2)
    cta_font = _font(21, bold=True)
    cta_lines = _wrap_ellipsized(draw, "你會先追新功能，還是先把權限收緊？", cta_font, W - 220, 2)
    _draw_lines(draw, 108, 926, cta_lines, cta_font, WHITE, 3)

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
