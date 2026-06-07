"""
圖卡生成模組 v3 — 雜誌封面式排版
風格：深海軍藍底 + 橘色主調 + 電藍點綴
核心邏輯：大標題 + 關鍵數字/短語 + 一段描述，留白多、人味強
"""
import os
import re
from pathlib import Path
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1080

BG          = "#08091C"
ORANGE      = "#FF6B2B"
BLUE        = "#4A9EFF"
WHITE       = "#F2F4FF"
WHITE_DIM   = "#BCC5E0"
GRAY        = "#5A6A90"
GHOST_BG    = "#0D1020"
DIVIDER     = "#1C2347"

FONT_PATH = os.environ.get("FONT_PATH", "")


def _font(size: int) -> ImageFont.FreeTypeFont:
    candidates = []
    if FONT_PATH:
        candidates.append(FONT_PATH)
    candidates += [
        "C:/Windows/Fonts/msjhbd.ttc",
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/mingliu.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9_.%$+\-]+|.", text)
    lines, cur = [], ""
    for token in tokens:
        test = cur + token
        if draw.textbbox((0, 0), test, font=font)[2] > max_w and cur:
            lines.append(cur)
            cur = token
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def _text_h(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _draw_rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.ellipse([x0, y0, x0 + radius*2, y0 + radius*2], fill=fill)
    draw.ellipse([x1 - radius*2, y0, x1, y0 + radius*2], fill=fill)
    draw.ellipse([x0, y1 - radius*2, x0 + radius*2, y1], fill=fill)
    draw.ellipse([x1 - radius*2, y1 - radius*2, x1, y1], fill=fill)


def _draw_glow(img: Image.Image, cx: int, cy: int, color_hex: str, radius: int, strength: float):
    """在指定位置畫一個柔和的光暈"""
    r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
    bg_r, bg_g, bg_b = int(BG[1:3], 16), int(BG[3:5], 16), int(BG[5:7], 16)
    glow_layer = img.copy()
    draw = ImageDraw.Draw(glow_layer)
    steps = 30
    for i in range(steps, 0, -1):
        t = (i / steps) ** 2
        alpha = int(strength * t * 255)
        cr = int(bg_r + (r - bg_r) * alpha / 255)
        cg = int(bg_g + (g - bg_g) * alpha / 255)
        cb = int(bg_b + (b - bg_b) * alpha / 255)
        r_cur = int(radius * i / steps)
        draw.ellipse([cx - r_cur, cy - r_cur, cx + r_cur, cy + r_cur], fill=(cr, cg, cb))
    return Image.blend(img, glow_layer, 0.55)


def generate_featured_card(post: Dict, source: str, date_str: str, output_path: str) -> str:
    """
    雜誌封面式圖卡：
    - 上區：類別膠囊 + 日期
    - 中上：超大主標題（留白呼吸感）
    - 中：橘色分隔線
    - 中下：key_stat 大數字（如有）
    - 下：核心描述段落（寬鬆行距）
    - 底：來源 + handle
    """
    img = Image.new("RGB", (W, H), BG)

    # 左下橘色光暈
    img = _draw_glow(img, cx=0, cy=H, color_hex=ORANGE, radius=520, strength=0.18)
    # 右上藍色光暈（輕）
    img = _draw_glow(img, cx=W, cy=0, color_hex=BLUE, radius=380, strength=0.10)

    draw = ImageDraw.Draw(img)
    PAD = 72

    # ── 頂部橘線 ─────────────────────────────────────────────
    draw.rectangle([0, 0, W, 6], fill=ORANGE)

    # ── 字型 ─────────────────────────────────────────────────
    f_tag    = _font(22)
    f_date   = _font(20)
    f_title  = _font(80)    # 主標題：超大
    f_stat   = _font(110)   # 關鍵數字：巨大
    f_stat_label = _font(26)
    f_body   = _font(34)    # 正文：舒服閱讀大小
    f_footer = _font(22)

    # ── 類別標籤（橘色圓角膠囊）────────────────────────────
    category = post.get("category", "AI NEWS").upper()
    tag_pad_x, tag_pad_y = 18, 9
    tag_w = draw.textbbox((0, 0), category, font=f_tag)[2] + tag_pad_x * 2
    tag_h = draw.textbbox((0, 0), category, font=f_tag)[3] + tag_pad_y * 2 + 4
    tag_y = 36
    _draw_rounded_rect(draw, [PAD, tag_y, PAD + tag_w, tag_y + tag_h], radius=12, fill=ORANGE)
    draw.text((PAD + tag_pad_x, tag_y + tag_pad_y), category, font=f_tag, fill=WHITE)

    # 日期（右上，藍色）
    date_w = draw.textbbox((0, 0), date_str, font=f_date)[2]
    draw.text((W - PAD - date_w, tag_y + tag_pad_y + 2), date_str, font=f_date, fill=BLUE)

    # ── 主標題（優先一行；超過則縮字體，最多兩行）──────────
    title = post.get("title_zh", "")
    title_max_w = W - PAD * 2
    # 從 76px 往下縮到 42px，找到能單行顯示的最大字體
    f_title = _font(42)  # 預設最小
    for font_size in range(76, 40, -2):
        f_title_try = _font(font_size)
        if draw.textbbox((0, 0), title, font=f_title_try)[2] <= title_max_w:
            f_title = f_title_try
            break

    ty = tag_y + tag_h + 56
    title_lines = _wrap(draw, title, f_title, title_max_w)
    for line in title_lines[:2]:  # 最多 2 行
        draw.text((PAD, ty), line, font=f_title, fill=WHITE)
        ty += _text_h(draw, line, f_title) + 8
    ty += 36  # 標題下方空白

    # ── 橘色分隔線 ───────────────────────────────────────────
    draw.rectangle([PAD, ty, W - PAD, ty + 3], fill=ORANGE)
    ty += 56  # 分隔線下方也留空

    # ── 關鍵數字/短語（如果有 key_stat）────────────────────
    key_stat = post.get("key_stat", "")
    if key_stat:
        stat_lines = _wrap(draw, key_stat, f_stat, W - PAD * 2)
        for line in stat_lines[:1]:
            draw.text((PAD, ty), line, font=f_stat, fill=ORANGE)
            ty += _text_h(draw, line, f_stat) + 8
        ty += 44  # 數字下方留大空白再接正文

    # ── 核心描述段落 ─────────────────────────────────────────
    # 取三個 section 合併成一段流暢敘述，或直接用 sections[0].body
    sections = post.get("sections", [])

    # 組合敘述：heading 白色 + body 灰藍色，各段之間有行距
    available_h = H - 90 - ty   # 底部留給 footer
    for i, sec in enumerate(sections[:3]):
        heading = sec.get("heading", "")
        body    = sec.get("body", "")

        if not heading and not body:
            continue

        # 藍色左側細條（4px）
        block_start = ty

        # Heading（白色，較大）
        if heading:
            h_lines = _wrap(draw, heading, f_body, W - PAD * 2 - 20)
            draw.rectangle([PAD, ty, PAD + 4, ty + _text_h(draw, h_lines[0], f_body) + 6], fill=BLUE)
            for line in h_lines[:1]:
                draw.text((PAD + 18, ty), line, font=f_body, fill=WHITE)
                ty += _text_h(draw, line, f_body) + 6

        # Body（藍灰色，縮進）
        if body:
            b_lines = _wrap(draw, body, f_body, W - PAD * 2 - 20)
            for line in b_lines[:2]:
                draw.text((PAD + 18, ty), line, font=f_body, fill=WHITE_DIM)
                ty += _text_h(draw, line, f_body) + 6

        # 更新左側條高度
        draw.rectangle([PAD, block_start, PAD + 4, ty], fill=BLUE)

        ty += 30   # 段落間距（寬鬆）

        # 不要超出底部
        if ty > H - 120:
            break

    # ── 底部 footer ──────────────────────────────────────────
    footer_y = H - 68
    draw.rectangle([0, footer_y, W, footer_y + 2], fill=DIVIDER)

    # 左：來源
    draw.text((PAD, footer_y + 16), f"來源：{source}", font=f_footer, fill=GRAY)
    # 右：handle（橘色）
    handle = "@metaspax"
    handle_w = draw.textbbox((0, 0), handle, font=f_footer)[2]
    draw.text((W - PAD - handle_w, footer_y + 16), handle, font=f_footer, fill=ORANGE)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"[Image] 圖卡已儲存：{output_path}")
    return output_path


def generate_all_images(post_content: Dict, source: str, date_str: str, output_dir: str) -> List[str]:
    from datetime import datetime
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    card_path = str(Path(output_dir) / f"featured_{ts}.png")
    generate_featured_card(post_content, source, date_str, card_path)
    return [card_path]
