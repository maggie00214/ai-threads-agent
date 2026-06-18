"""
Generate orange-blue social news cards with fixed layout zones.
"""
import os
import re
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1080

BG = "#07111F"
PANEL = "#0E1728"
PANEL_2 = "#111D33"
LINE = "#26385A"
ORANGE = "#FF7A1A"
BLUE = "#4A94FF"
ACCENT = "#FFD247"
WHITE = "#F5F7FF"
WHITE_SOFT = "#C8D2E6"
MUTED = "#8FA0C1"

FONT_PATH = os.environ.get("FONT_PATH", "")


def _font(size: int, bold: bool = False):
    candidates = []
    if FONT_PATH:
        candidates.append(FONT_PATH)
    if bold:
        candidates += [
            "C:/Windows/Fonts/msjhbd.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
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


def _wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z0-9_.%$+\-/:]+|.", text)
    lines, current = [], ""
    for token in tokens:
        test = current + token
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_w or not current:
            current = test
        else:
            lines.append(current.strip())
            current = token
    if current:
        lines.append(current.strip())
    return lines


def _line_h(draw: ImageDraw.ImageDraw, fnt, gap: int = 0) -> int:
    box = draw.textbbox((0, 0), "測試Ag", font=fnt)
    return box[3] - box[1] + gap


def _fit_lines(draw: ImageDraw.ImageDraw, text: str, max_w: int, max_lines: int, start: int, minimum: int, bold: bool):
    fallback_font = _font(minimum, bold)
    fallback_lines = _wrap(draw, text, fallback_font, max_w)[:max_lines]
    for size in range(start, minimum - 1, -2):
        fnt = _font(size, bold)
        lines = _wrap(draw, text, fnt, max_w)
        if lines and len(lines) <= max_lines:
            return fnt, lines
    return fallback_font, fallback_lines


def _draw_lines(draw, x: int, y: int, lines: List[str], fnt, fill: str, gap: int = 8) -> int:
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += _line_h(draw, fnt, gap)
    return y


def _text_block_size(draw: ImageDraw.ImageDraw, lines: List[str], fnt, gap: int = 8) -> tuple[int, int]:
    if not lines:
        return 0, 0
    widths = []
    total_h = 0
    for idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=fnt)
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
    fallback_lines = _wrap(draw, text, fallback_font, max_w)[:max_lines]
    for size in range(start, minimum - 1, -2):
        fnt = _font(size, bold)
        lines = _wrap(draw, text, fnt, max_w)
        if not lines or len(lines) > max_lines:
            continue
        _, block_h = _text_block_size(draw, lines, fnt, gap)
        if block_h <= max_h:
            return fnt, lines
    return fallback_font, fallback_lines


def _draw_lines_in_box(draw, box, lines: List[str], fnt, fill: str, gap: int = 8, align: str = "left") -> None:
    x1, y1, x2, y2 = box
    _, block_h = _text_block_size(draw, lines, fnt, gap)
    y = y1 + max(0, (y2 - y1 - block_h) // 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=fnt)
        line_w = bbox[2] - bbox[0]
        x = x1 if align == "left" else x1 + max(0, (x2 - x1 - line_w) // 2)
        draw.text((x - bbox[0], y - bbox[1]), line, font=fnt, fill=fill)
        y += bbox[3] - bbox[1] + gap


def _draw_centered_lines(draw, box, lines: List[str], fnt, fill: str, gap: int = 8) -> None:
    x1, y1, x2, y2 = box
    total_h = len(lines) * _line_h(draw, fnt, gap) - gap if lines else 0
    y = y1 + max(0, (y2 - y1 - total_h) // 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=fnt)
        x = x1 + max(0, (x2 - x1 - (bbox[2] - bbox[0])) // 2)
        draw.text((x, y), line, font=fnt, fill=fill)
        y += _line_h(draw, fnt, gap)


def _badge(draw, text: str, x: int, y: int, fill: str, text_fill: str) -> int:
    text = (text or "").strip()
    fnt = _font(24, bold=True)
    bbox = draw.textbbox((0, 0), text, font=fnt)
    w = bbox[2] - bbox[0] + 34
    h = bbox[3] - bbox[1] + 22
    draw.rounded_rectangle([x, y, x + w, y + h], radius=14, fill=fill)
    draw.text((x + 17, y + 8), text, font=fnt, fill=text_fill)
    return x + w + 12


def _draw_glow(img: Image.Image, cx: int, cy: int, color_hex: str, radius: int, strength: float):
    r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
    layer = img.copy()
    draw = ImageDraw.Draw(layer)
    for i in range(18, 0, -1):
        alpha = int(255 * strength * (i / 18) ** 2)
        rr = int(radius * i / 18)
        color = (r, g, b)
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=color)
    return Image.blend(img, layer, 0.10)


def _safe_text(value: str, fallback: str) -> str:
    value = re.sub(r"\s+", " ", (value or "")).strip()
    return value or fallback


def _dedupe_repeated_fragments(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return text

    for _ in range(3):
        out = []
        i = 0
        changed = False
        while i < len(text):
            max_unit = min(36, (len(text) - i) // 2)
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


def _card_body(text: str, limit: int = 32) -> str:
    text = _dedupe_repeated_fragments(_safe_text(text, "這則更新值得先記下來。"))
    for mark in ("；", "。", "，", "、"):
        idx = text.find(mark)
        if 10 <= idx <= limit:
            return text[:idx].strip()
    return text[:limit].strip()


def _ellipsize(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if draw.textbbox((0, 0), text, font=fnt)[2] <= max_w:
        return text

    suffix = "..."
    available = max_w - draw.textbbox((0, 0), suffix, font=fnt)[2]
    kept = ""
    for ch in text:
        candidate = kept + ch
        if draw.textbbox((0, 0), candidate, font=fnt)[2] > available:
            break
        kept = candidate
    return (kept.rstrip() + suffix) if kept else suffix


def _wrap_ellipsized(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int, max_lines: int) -> List[str]:
    lines = _wrap(draw, text, fnt, max_w)
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    kept[-1] = _ellipsize(draw, "".join([kept[-1], *lines[max_lines:]]), fnt, max_w)
    return kept


def _draw_info_card(draw, box, heading: str, body: str, accent: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=18, fill=PANEL_2, outline=LINE, width=2)
    draw.rectangle([x1 + 22, y1 + 24, x1 + 28, y2 - 24], fill=accent)

    heading_font, heading_lines = _fit_lines(draw, heading, x2 - x1 - 74, 1, 24, 20, True)
    body_font = _font(25)
    body_lines = _wrap_ellipsized(draw, body, body_font, x2 - x1 - 74, 2)
    heading_gap = 5
    body_gap = 2
    total_h = len(heading_lines) * _line_h(draw, heading_font, 0)
    total_h += heading_gap
    total_h += len(body_lines) * _line_h(draw, body_font, body_gap) - body_gap
    y = y1 + max(14, (y2 - y1 - total_h) // 2)
    y = _draw_lines(draw, x1 + 46, y, heading_lines, heading_font, accent, 0)
    _draw_lines(draw, x1 + 46, y + heading_gap, body_lines, body_font, WHITE, body_gap)


def generate_featured_card(post: Dict, source: str, date_str: str, output_path: str) -> str:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    margin = 48
    draw.rounded_rectangle([margin, margin, W - margin, H - margin], radius=30, fill=PANEL, outline=LINE, width=2)
    draw.rectangle([margin, margin, W - margin, margin + 12], fill=ORANGE)

    category = _safe_text(post.get("category", "AI NEWS"), "AI NEWS").upper()[:12]
    angle = _safe_text(post.get("angle", ""), "")
    title = _safe_text(post.get("title_zh", ""), "今日 AI 重點")
    subtitle = _safe_text(post.get("subtitle_zh", ""), "這則更新和一般使用者有關")
    hook = _safe_text(post.get("hook_line", ""), "")
    blocks = post.get("insight_blocks", [])[:3]

    x = 82
    y = 86
    x = _badge(draw, category, x, y, ORANGE, WHITE)
    if angle:
        _badge(draw, angle[:16], x, y, "#152746", BLUE)

    title_box = [82, 158, W - 82, 292]
    title_font, title_lines = _fit_lines_to_box(
        draw, title, title_box[2] - title_box[0], title_box[3] - title_box[1], 2, 66, 38, True, 8
    )
    _draw_lines_in_box(draw, title_box, title_lines, title_font, WHITE, 8)

    subtitle_box = [84, 312, W - 84, 382]
    subtitle_font, subtitle_lines = _fit_lines_to_box(
        draw, subtitle, subtitle_box[2] - subtitle_box[0], subtitle_box[3] - subtitle_box[1], 2, 34, 23, True, 6
    )
    _draw_lines_in_box(draw, subtitle_box, subtitle_lines, subtitle_font, WHITE_SOFT, 6)

    hook_text = hook or "這次重點先看懂"
    hook_font, hook_lines = _fit_lines(draw, hook_text, W - 210, 2, 44, 30, True)
    hook_box = [82, 428, W - 82, 548]
    draw.rounded_rectangle(hook_box, radius=24, fill="#18243A", outline=LINE, width=2)
    draw.rectangle([hook_box[0] + 26, hook_box[1] + 28, hook_box[0] + 34, hook_box[3] - 28], fill=ACCENT)
    _draw_centered_lines(draw, [hook_box[0] + 48, hook_box[1], hook_box[2] - 28, hook_box[3]], hook_lines, hook_font, ACCENT, 8)

    if not blocks:
        blocks = [
            {"heading": "核心", "body": subtitle},
            {"heading": "影響", "body": "這會改變工具成本、資料風險或工作流程。"},
            {"heading": "提醒", "body": "先看限制，再決定要不要跟進。"},
        ]

    while len(blocks) < 3:
        blocks.append({"heading": "提醒", "body": "常用 AI 工具的人可以先注意這次變動。"})

    card_y = 570
    accents = [BLUE, ORANGE, ACCENT]
    defaults = ["核心", "影響", "提醒"]
    fallback_bodies = [
        "先看它改變了哪個日常流程",
        "影響會出現在成本、安全或效率",
        "可以立刻檢查自己的使用方式",
    ]
    seen_bodies = set()
    for idx, block in enumerate(blocks[:3]):
        body = _card_body(block.get("body", ""), 54)
        body_key = re.sub(r"\W+", "", body).lower()
        if body_key and body_key in seen_bodies:
            body = fallback_bodies[idx]
            body_key = re.sub(r"\W+", "", body).lower()
        if body_key:
            seen_bodies.add(body_key)
        _draw_info_card(
            draw,
            [82, card_y + idx * 124, W - 82, card_y + idx * 124 + 112],
            _safe_text(block.get("heading", ""), defaults[idx])[:10],
            body,
            accents[idx],
        )

    footer_y = H - 112
    draw.rectangle([82, footer_y - 20, W - 82, footer_y - 18], fill=LINE)
    small = _font(22, bold=True)
    source_text = f"SOURCE  {source.upper()[:26]}"
    draw.text((82, footer_y), source_text, font=small, fill=MUTED)
    date_w = draw.textbbox((0, 0), date_str, font=small)[2]
    draw.text((W - 82 - date_w, footer_y), date_str, font=small, fill=MUTED)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"[Image] saved: {output_path}")
    return output_path


def generate_all_images(post_content: Dict, source: str, date_str: str, output_dir: str) -> List[str]:
    from datetime import datetime

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    card_path = str(Path(output_dir) / f"featured_{ts}.png")
    generate_featured_card(post_content, source, date_str, card_path)
    return [card_path]
