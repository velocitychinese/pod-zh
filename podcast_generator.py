"""VELOCITY CHINESE PODCAST
15-min bilingual Mandarin Chinese/English podcast at A2 level with pinyin
2 hosts: Mei & Wei
"""
import os, sys, json, asyncio, subprocess, random, requests, re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter

load_dotenv()

try:
    from pypinyin import pinyin as _pinyin_fn, Style as _PinyinStyle
    _has_pypinyin = True
except Exception:
    _pinyin_fn = None
    _PinyinStyle = None
    _has_pypinyin = False
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL") or "openai/gpt-5.4-nano"

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
FONTS_DIR = BASE_DIR / "fonts"

HOST1_VOICE = "zh-CN-YunyangNeural"
HOST2_VOICE = "zh-CN-XiaoxiaoNeural"

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30

TOPICS = [
    "去新国家旅行 - Traveling to a new country",
    "传统美食 - Traditional food",
    "日常习惯 - Daily routine",
    "节日和庆祝 - Holidays and celebrations",
    "天气和季节 - Weather and seasons",
    "家人和朋友 - Family and friends",
    "音乐和电影 - Music and movies",
    "运动和锻炼 - Sports and exercise",
    "理想的城市 - The ideal city",
    "学习语言 - Learning languages",
    "周末 - The weekend",
    "购物和衣服 - Shopping and clothes",
    "公共交通 - Public transport",
    "在餐馆 - At the restaurant",
    "健康和幸福 - Health and wellness",
]

YELLOW = (247, 202, 0)
DARK_BG = (11, 14, 27)
WHITE = (255, 255, 255)
LIGHT_GRAY = (170, 180, 205)
DARK_LINE = (50, 55, 75)

def load_font(size, bold=False, italic=False):
    fonts_to_try = []
    if italic and bold:
        fonts_to_try.extend([
            "C:/Windows/Fonts/segoeuiz.ttf", "C:/Windows/Fonts/arialbi.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
            str(FONTS_DIR / "DejaVuSans-BoldOblique.ttf"),
        ])
    elif italic:
        fonts_to_try.extend([
            "C:/Windows/Fonts/segoeuii.ttf", "C:/Windows/Fonts/ariali.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            str(FONTS_DIR / "DejaVuSans-Oblique.ttf"),
        ])
    elif bold:
        fonts_to_try.extend([
            "C:/Windows/Fonts/Inter-Bold-slnt=0.ttf", "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            str(FONTS_DIR / "DejaVuSans-Bold.ttf"),
        ])
    else:
        fonts_to_try.extend([
            "C:/Windows/Fonts/Inter-Regular-slnt=0.ttf", "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            str(FONTS_DIR / "DejaVuSans.ttf"),
        ])

    for fp in fonts_to_try:
        if Path(fp).exists():
            try: return ImageFont.truetype(fp, size)
            except: continue
    return ImageFont.load_default()

def load_chinese_font(size, bold=False):
    """Load a font that supports Chinese characters."""
    p = FONTS_DIR / "NotoSansSC.ttf"
    if p.exists():
        try:
            f = ImageFont.truetype(str(p), size)
            try:
                names = [n.decode() if isinstance(n, bytes) else n for n in f.get_variation_names()]
                if bold and "Bold" in names:
                    f.set_variation_by_name("Bold")
                elif not bold and "Regular" in names:
                    f.set_variation_by_name("Regular")
            except Exception:
                pass
            return f
        except Exception:
            pass
    if bold:
        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ]
    for fp in candidates:
        if Path(fp).exists():
            try: return ImageFont.truetype(fp, size)
            except: continue
    # fallback to the bundled DejaVu (will show boxes but not crash)
    return load_font(size, bold=bold)

def clean_text(text):
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'\b(mm+|um+|uh+|ah+|äh+)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _purify_chinese(text):
    """Remove stray Latin/English letters that leaked into the Chinese field.
    Keeps Simplified Chinese characters, Chinese punctuation, the **bold**
    markers and the 'Velocity Chinese' brand name."""
    if not text:
        return text
    text = clean_text(text)
    text = text.replace('**', chr(1))  # protect highlight markers
    text = text.replace('Velocity Chinese', chr(2))  # protect brand
    text = re.sub('[A-Za-z' + chr(0xC0) + '-' + chr(0x24F) + ']+', '', text)
    text = text.replace(chr(1), '**')
    text = text.replace(chr(2), 'Velocity Chinese')
    text = _clean_empty_hl(text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return ""
    return text

def _clean_empty_hl(text):
    """Drop highlight markers left empty after purification ('****')."""
    if not text or '**' not in text:
        return text
    text = re.sub(r'\*\*\s*\*\*', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def to_accurate_pinyin(chinese):
    """Simplified Chinese -> Hanyu Pinyin WITH tone marks (per character).
    Uses pypinyin; falls back to empty string when unavailable."""
    if not chinese:
        return ""
    clean_cn = re.sub(r'\*\*(.*?)\*\*', r'\1', chinese)
    if _has_pypinyin:
        try:
            syls = _pinyin_fn(clean_cn, style=_PinyinStyle.TONE)
            parts = [(s[0] if s else "") for s in syls]
            pinyin = ' '.join(p for p in parts if p)
            pinyin = re.sub(r'\s+([,!?.])', r'\1', pinyin)
            pinyin = pinyin.replace('，', ', ').replace('。', '. ').replace('！', '! ').replace('？', '? ')
            pinyin = pinyin.replace(' ,', ',').replace(' .', '.').replace(' !', '!').replace(' ?', '?')
            pinyin = re.sub(r'\s+', ' ', pinyin).strip()
            sentences = re.split(r'([.!?]\s*)', pinyin)
            cap_s = ''
            for s in sentences:
                if s and not s.isspace():
                    if not cap_s or cap_s.endswith('. ') or cap_s.endswith('! ') or cap_s.endswith('? '):
                        cap_s += s[0].upper() + s[1:] if len(s) > 1 else s.upper()
                    else:
                        cap_s += s
                else:
                    cap_s += s
            if re.search(r'[a-zA-Z]{2,}', cap_s):
                return cap_s.strip()
        except Exception as e:
            print(f"  pypinyin error: {e}")
    return _pinyin_fallback(clean_cn)

def _pinyin_fallback(chinese):
    """No dictionary-free way to romanize Han characters: return empty so the
    caller falls back to the English line instead of printing boxes."""
    return ""

def sanitize_latin(text):
    """Convert leaked non-Latin characters to font-safe Latin equivalents so
    romaji/English never show tofu glyphs. Handles macrons, full-width forms
    and Chinese punctuation."""
    if not text:
        return text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2026', '...').replace('\u2014', ' - ').replace('\u2013', ' - ')
    text = text.replace('\u3001', ', ').replace('\u3002', '.').replace('\u30fb', ' ')
    text = text.replace('\uff0c', ',').replace('\uff0e', '.').replace('\uff01', '!')
    text = text.replace('\uff1f', '?').replace('\uff20', '@')
    _EXTRA_LATIN = {
        '\u00e6': 'ae', '\u00c6': 'AE',
        '\u00f8': 'o', '\u00d8': 'O',
        '\u0153': 'oe', '\u0152': 'OE',
        '\u00df': 'ss', '\u1e9e': 'SS',
        '\u0142': 'l', '\u0141': 'L',
        '\u0131': 'i',
        '\u0111': 'd', '\u0110': 'D',
        '\u00f0': 'd', '\u00d0': 'D',
        '\u00fe': 'th', '\u00de': 'TH',
    }
    def norm_letter(m):
        ch = m.group(0)
        if ch == '\u0101': return 'a'
        if ch == '\u014d': return 'o'
        if ch == '\u016b': return 'u'
        if ch == '\u012b': return 'i'
        if ch == '\u0113': return 'e'
        if ch == '\u0100': return 'A'
        if ch == '\u014c': return 'O'
        if ch == '\u016a': return 'U'
        if ch == '\u012a': return 'I'
        if ch == '\u0112': return 'E'
        if ch == '\u00e9': return 'e'
        if ch == '\u00e8': return 'e'
        if ch == '\u00ea': return 'e'
        if ch == '\u00ef': return 'i'
        if ch == '\u00f1': return 'n'
        if ch == '\u00fc': return 'u'
        if ch == '\u00f6': return 'o'
        if ch == '\u00e4': return 'a'
        if ch in _EXTRA_LATIN:
            return _EXTRA_LATIN[ch]
        import unicodedata as _ud
        _base = ''.join(
            c for c in _ud.normalize('NFKD', ch)
            if not _ud.combining(c))
        if _base and all(ord(c) < 128 for c in _base):
            return _base
        return ch
    text = re.sub(r'[\u00c0-\u024f\u0100-\u017f\u1e00-\u1eff]', norm_letter, text)
    text = re.sub(r'[\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef\u3000-\u303f]', ' ', text)
    # final safety net: map remaining symbols to ASCII, else drop (prevents any tofu glyph)
    text = text.replace('\u2192', ' -> ').replace('\u2190', ' <- ').replace('\u2194', ' -- ')
    text = text.replace('\u2022', '-').replace('\u25cf', '-').replace('\u2605', '*').replace('\u2606', '*')
    out = []
    for ch in text:
        o = ord(ch)
        if 0x20 <= o <= 0x7E:
            out.append(ch)
        elif o in (0x0A, 0x0D):
            out.append(' ')
        else:
            out.append(' ')
    text = ''.join(out)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def sanitize_translit(text):
    """Latin + Hanyu Pinyin tone-mark vowels kept; CJK stripped.
    Mirrors sanitize_latin but preserves ā á ǎ à ē é ě è ī í ǐ ì
    ō ó ǒ ò ū ú ǔ ù ǖ ǘ ǚ ǜ ü ê so pinyin never loses its tones."""
    if not text:
        return text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2026', '...').replace('\u2014', ' - ').replace('\u2013', ' - ')
    text = text.replace('\u3001', ', ').replace('\u3002', '.').replace('\u30fb', ' ')
    text = text.replace('\uff0c', ',').replace('\uff0e', '.').replace('\uff01', '!')
    text = text.replace('\uff1f', '?').replace('\uff20', '@')
    text = re.sub(r'[\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef\u3000-\u303f]', ' ', text)
    text = text.replace('\u2192', ' -> ').replace('\u2190', ' <- ').replace('\u2194', ' -- ')
    text = text.replace('\u2022', '-').replace('\u25cf', '-').replace('\u2605', '*').replace('\u2606', '*')
    out = []
    for ch in text:
        o = ord(ch)
        if 0x20 <= o <= 0x7E or 0xC0 <= o <= 0x2AF:
            out.append(ch)
        elif o in (0x0A, 0x0D):
            out.append(' ')
        else:
            out.append(' ')
    text = ''.join(out)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def auto_highlight_chinese(text):
    if '**' in text:
        return text
    stopwords = {'的', '是', '在', '和', '有', '我', '你', '他', '她', '我们', '你们', '他们',
                 '这', '那', '不', '很', '也', '都', '要', '会', '能', '可以', '吗', '呢',
                 '吧', '啊', '了', '着', '过', '就', '才', '跟', '说', '对'}
    words = text.split()
    if len(words) <= 1:
        t = text.strip()
        if len(t) >= 2 and t not in stopwords:
            return t[:1] + '**' + t[1:3] + '**' + t[3:]
        return text
    candidates = []
    for idx, w in enumerate(words):
        clean_w = re.sub(r'[^\w]', '', w, flags=re.UNICODE)
        if clean_w not in stopwords and len(clean_w) >= 2:
            candidates.append((len(clean_w), idx, w, clean_w))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_idx = candidates[0][1]
        raw_w = words[best_idx]
        clean_w = candidates[0][3]
        highlighted = raw_w.replace(clean_w, f"**{clean_w}**")
        words[best_idx] = highlighted
        return " ".join(words)
    return text

def draw_microphone_icon(draw, center_x, center_y, radius=24):
    draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                 outline=YELLOW, width=3)
    w, h = 10, 18
    draw.rounded_rectangle([center_x - w//2, center_y - 12, center_x + w//2, center_y - 12 + h],
                           radius=4, fill=YELLOW)
    draw.arc([center_x - 10, center_y - 4, center_x + 10, center_y + 12],
             start=0, end=180, fill=YELLOW, width=3)
    draw.line([(center_x, center_y + 12), (center_x, center_y + 17)], fill=YELLOW, width=3)
    draw.line([(center_x - 7, center_y + 17), (center_x + 7, center_y + 17)], fill=YELLOW, width=3)

def draw_person_icon(draw, center_x, center_y):
    draw.ellipse([center_x - 6, center_y - 12, center_x + 6, center_y], fill=YELLOW)
    draw.chord([center_x - 12, center_y + 2, center_x + 12, center_y + 20],
               start=180, end=360, fill=YELLOW)

def draw_chinese_flag(img, draw, center_x, center_y, radius=22):
    import math
    flag_img = Image.new('RGBA', (radius*2, radius*2), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(flag_img)
    # Chinese flag: red background with yellow stars
    fdraw.rectangle([(0, 0), (radius*2, radius*2)], fill=(222, 41, 16, 255))

    def star(cx, cy, r):
        pts = []
        for k in range(10):
            ang = -math.pi / 2 + k * math.pi / 5
            rr = r if k % 2 == 0 else r * 0.382
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        return pts

    R = radius * 2
    fdraw.polygon(star(R * 0.28, R * 0.30, R * 0.16), fill=(255, 222, 0, 255))
    for (sx, sy) in [(R * 0.55, R * 0.12), (R * 0.68, R * 0.25),
                     (R * 0.68, R * 0.48), (R * 0.55, R * 0.60)]:
        fdraw.polygon(star(sx, sy, R * 0.055), fill=(255, 222, 0, 255))

    mask = Image.new('L', (radius*2, radius*2), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse([0, 0, radius*2, radius*2], fill=255)
    img.paste(flag_img, (center_x - radius, center_y - radius), mask)

def draw_headphones_icon(draw, center_x, center_y):
    draw.arc([center_x - 14, center_y - 14, center_x + 14, center_y + 6],
             start=180, end=360, fill=YELLOW, width=3)
    draw.rounded_rectangle([center_x - 16, center_y - 3, center_x - 10, center_y + 11], radius=2, fill=YELLOW)
    draw.rounded_rectangle([center_x + 10, center_y - 3, center_x + 16, center_y + 11], radius=2, fill=YELLOW)

_CJK_RE = re.compile('[' + chr(0x3000) + '-' + chr(0x30ff) + chr(0x4e00) + '-' + chr(0x9fff) + chr(0xac00) + '-' + chr(0xd7a3) + ']')


def _cjk_tokens(text, font, draw):
    """Split text into drawable tokens (char-level for CJK, word-level for
    Latin). Tokens from a highlighted (**) run are split exactly like plain
    text and carry the highlight flag, so every highlight step wraps the
    same way and only the color changes."""
    pattern = r'(\*\*.*?\*\*)'
    raw_parts = re.split(pattern, text)
    tokens = []
    for part in raw_parts:
        if part.startswith('**') and part.endswith('**'):
            is_hl = True
            part = part[2:-2]
            if not part:
                continue
        elif part:
            is_hl = False
        else:
            continue
        if _CJK_RE.search(part):
            for ch in part:
                bb = draw.textbbox((0, 0), ch, font=font)
                tokens.append((ch, is_hl, bb[2] - bb[0]))
        else:
            # Keep every space exactly (incl. around ** runs): split while
            # retaining separators so no gap is ever dropped or shifted.
            for w in re.split(r'( +)', part):
                if not w:
                    continue
                if w.strip() == '':
                    _sp = draw.textbbox((0, 0), ' ', font=font)[2]
                    for _ch in w:
                        tokens.append((' ', False, _sp))
                else:
                    bb = draw.textbbox((0, 0), w, font=font)
                    tokens.append((w, is_hl, bb[2] - bb[0]))
    return tokens

def _wrap_tokens(tokens, max_w):
    """Greedy wrap tokens into visual lines that each fit max_w."""
    lines = []
    current_line = []
    current_line_width = 0

    for word, is_hl, w_width in tokens:
        if current_line_width + w_width <= max_w:
            current_line.append((word, is_hl, w_width))
            current_line_width += w_width
        else:
            if current_line:
                if current_line[-1][0] == ' ':
                    current_line_width -= current_line[-1][2]
                    current_line.pop()
                lines.append((current_line, current_line_width))
            if word == ' ':
                current_line = []
                current_line_width = 0
            else:
                current_line = [(word, is_hl, w_width)]
                current_line_width = w_width

    if current_line:
        if current_line[-1][0] == ' ':
            current_line_width -= current_line[-1][2]
            current_line.pop()
        lines.append((current_line, current_line_width))
    return lines

def _join_tokens(line, highlight=False):
    """Rebuild a wrapped line with its original spacing (never add spaces)."""
    return ''.join(f"**{w}**" if (highlight and hl and w != ' ') else w
                   for w, hl, _ww in line).strip()


def draw_lines_centered(draw, lines, center_y, font, line_height):
    """Draw pre-wrapped lines centered without re-wrapping, so karaoke
    highlighting can never shift the layout. Returns (ink_top, ink_bottom)."""
    ink_min_top = None
    ink_max = None
    total_height = len(lines) * line_height
    start_y = center_y - total_height // 2
    for idx, line in enumerate(lines):
        tokens = _cjk_tokens(line, font, draw)
        line_w = sum(tw for _tw, _th, tw in tokens)
        curr_x = (VIDEO_WIDTH - line_w) // 2
        curr_y = start_y + idx * line_height
        for word, is_yellow, w_w in tokens:
            if word == ' ':
                curr_x += w_w
                continue
            color = YELLOW if is_yellow else WHITE
            draw.text((curr_x, curr_y), word, fill=color, font=font)
            bb = draw.textbbox((curr_x, curr_y), word, font=font)
            if ink_min_top is None:
                ink_min_top, ink_max = bb[1], bb[3]
            else:
                ink_min_top = min(ink_min_top, bb[1])
                ink_max = max(ink_max, bb[3])
            curr_x += w_w
    if ink_min_top is None:
        ink_min_top = start_y
        ink_max = start_y + total_height
    return ink_min_top, ink_max

def _ro_ink_height(font, lines, max_w=1350):
    """Return the measured ink height of the given (already-wrapped) latin lines."""
    from PIL import Image, ImageDraw
    if not lines:
        return 0
    tmp = Image.new('RGB', (max_w, 200), (0, 0, 0))
    td = ImageDraw.Draw(tmp)
    probe = lines[0]
    bb = td.textbbox((0, 0), probe, font=font)
    h = bb[3] - bb[1]
    if len(lines) > 1:
        h += (len(lines) - 1) * int(font.size * 1.3)
    return h

def draw_english_translation(draw, text, center_y, font, max_w=1350, line_height=52):
    words = text.split()
    lines = []
    current_line = []
    
    for w in words:
        test_line = ' '.join(current_line + [w])
        bb = draw.textbbox((0, 0), test_line, font=font)
        if bb[2] - bb[0] <= max_w:
            current_line.append(w)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [w]
    if current_line:
        lines.append(' '.join(current_line))
        
    total_h = len(lines) * line_height
    start_y = center_y - total_h // 2

    ink_min_top = None
    ink_max = None
    for idx, line in enumerate(lines):
        lx = VIDEO_WIDTH // 2
        ly = start_y + idx * line_height + line_height // 2
        draw.text((lx, ly), line, fill=LIGHT_GRAY, font=font, anchor="mm")
        bb = draw.textbbox((lx, ly), line, font=font, anchor="mm")
        ink_min_top = bb[1] if ink_min_top is None else min(ink_min_top, bb[1])
        ink_max = bb[3] if ink_max is None else max(ink_max, bb[3])
    if ink_min_top is None:
        ink_min_top = start_y
        ink_max = start_y + total_h
    return ink_min_top, ink_max

def create_frame(turn, output_path, frame_num=0, preserve_highlights=False):
    img = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), DARK_BG)
    draw = ImageDraw.Draw(img)

    glow = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([(-200, VIDEO_HEIGHT-600), (600, VIDEO_HEIGHT+200)], fill=(30, 20, 60, 40))
    gdraw.ellipse([(VIDEO_WIDTH-500, -200), (VIDEO_WIDTH+300, 600)], fill=(30, 20, 60, 40))
    img.paste(glow, (0, 0), glow)

    f_title_white = load_font(36, bold=True)
    f_title_sub = load_font(18, bold=False)
    f_title_sub_muted = load_font(15, bold=False)
    f_ep = load_font(22, bold=True)
    f_speaker = load_font(26, bold=True)
    f_hablando = load_font(24, bold=False)
    f_target = load_chinese_font(64, bold=True)
    f_english = load_font(42, bold=False, italic=True)
    f_footer = load_font(22, bold=False)

    # === TOP HEADER ===
    header_y = 68
    draw_microphone_icon(draw, center_x=70, center_y=header_y, radius=24)

    draw.text((110, header_y), "VELOCITY", fill=WHITE, font=f_title_white, anchor="lm")
    v_bbox = draw.textbbox((110, header_y), "VELOCITY", font=f_title_white, anchor="lm")
    
    draw.text((v_bbox[2] + 8, header_y), "CHINESE", fill=YELLOW, font=f_title_white, anchor="lm")
    s_bbox = draw.textbbox((v_bbox[2] + 8, header_y), "CHINESE", font=f_title_white, anchor="lm")

    draw.text((s_bbox[2] + 8, header_y), "PODCAST", fill=WHITE, font=f_title_white, anchor="lm")
    p_bbox = draw.textbbox((s_bbox[2] + 8, header_y), "PODCAST", font=f_title_white, anchor="lm")

    draw.line([(p_bbox[2] + 20, 48), (p_bbox[2] + 20, 88)], fill=DARK_LINE, width=2)

    sub_x = p_bbox[2] + 35
    draw.text((sub_x, header_y - 12), "Chinese Podcast", fill=WHITE, font=f_title_sub, anchor="lm")
    draw.text((sub_x, header_y + 12), "Learn Through Conversations", fill=LIGHT_GRAY, font=f_title_sub_muted, anchor="lm")

    ep_num = (frame_num // 150) + 1 if isinstance(frame_num, int) else 1
    ep_str = f"EP {ep_num:02d}"
    draw.rounded_rectangle([(1640, 46), (1750, 90)], radius=8, fill=YELLOW)
    draw.text((1695, header_y), ep_str, fill=DARK_BG, font=f_ep, anchor="mm")

    draw_chinese_flag(img, draw, center_x=1810, center_y=header_y, radius=22)

    draw.line([(0, 130), (VIDEO_WIDTH, 130)], fill=YELLOW, width=2)

    # === SPEAKER STATUS SECTION ===
    is_host1 = turn.get("speaker") == "Host1"
    speaker_name = "WEI" if is_host1 else "MEI"
    pill_x, pill_y = 120, 210
    pill_w, pill_h = 220, 52

    draw.rounded_rectangle([(pill_x, pill_y), (pill_x + pill_w, pill_y + pill_h)],
                           radius=26, outline=YELLOW, width=2)
    draw_person_icon(draw, center_x=pill_x + 36, center_y=pill_y + 26)
    draw.text((pill_x + 60, pill_y + 26), speaker_name, fill=YELLOW, font=f_speaker, anchor="lm")

    draw.text((pill_x + pill_w + 25, pill_y + 26), "zhèngzài shuōhuà", fill=LIGHT_GRAY, font=f_hablando, anchor="lm")

    # === MAIN TEXT ZONE: Chinese + Romaji, must BOTH fit above the center divider ===
    ZONE_TOP = 300
    DIV_Y = 615
    ZONE_BOTTOM = DIV_Y - 30
    ZONE_H = ZONE_BOTTOM - ZONE_TOP
    target_text = turn.get("chinese", turn.get("spanish", ""))
    if '**' not in target_text:
        target_text = auto_highlight_chinese(target_text)
    romaji_text = sanitize_translit(turn.get("romaji", ""))
    if not re.search(r'[a-zA-Z]{2,}', romaji_text):
        romaji_text = to_accurate_pinyin(target_text)
    if not re.search(r'[a-zA-Z]{2,}', romaji_text):
        romaji_text = sanitize_latin(turn.get("english", ""))

    def _wrap(text, font, max_w):
        tokens = _cjk_tokens(text, font, draw)
        wrapped = _wrap_tokens(tokens, max_w)
        return [_join_tokens(line, highlight=True) for line, wd in wrapped]

    # 1) choose the largest Chinese font that wraps into <= 3 lines
    ja_font = None
    ja_size = 64
    final_lines = []
    for test_size in [64, 56, 48, 40, 34, 28, 24, 20]:
        tf = load_chinese_font(test_size, bold=True)
        tl = _wrap(target_text, tf, 1550)
        if len(tl) <= 3:
            ja_font, ja_size, final_lines = tf, test_size, tl
            break
    if ja_font is None:
        ja_font, ja_size = load_chinese_font(20, bold=True), 20
        all_lines = _wrap(target_text, ja_font, 1550)
        final_lines = all_lines[:3]
        if len(all_lines) > 3 and target_text:
            final_lines[-1] = final_lines[-1].rstrip() + "..."
    n_ja = len(final_lines)

    # 2) wrap romaji at the starting italic size
    ro_size = 40
    ro_font = load_font(ro_size, bold=True, italic=True)
    ro_lines = _wrap(romaji_text, ro_font, 1350) if romaji_text else []
    n_ro = len(ro_lines)

    JA_RO_GAP = 58
    SAFE_BOTTOM = ZONE_BOTTOM - 6

    def _measure_block():
        """Render ja+ro to a temp canvas and return (ja_center, ro_center, ink_bottom).
        Mirrors the real draw path so measured ink is exactly what appears."""
        tmp = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), DARK_BG)
        td = ImageDraw.Draw(tmp)
        ja_lh_ = int(ja_size * 1.4)
        ja_center = ZONE_TOP + len(final_lines) * ja_lh_ // 2
        _, ja_ib = draw_lines_centered(td, final_lines, center_y=ja_center,
                                       font=ja_font, line_height=ja_lh_)
        if not n_ro:
            return ja_center, None, ja_ib
        ih = _ro_ink_height(ro_font, ro_lines)
        target_top = ja_ib + JA_RO_GAP
        ly0 = target_top + ih / 2
        ro_center = ly0 - ro_lh // 2 + (n_ro * ro_lh) // 2
        _, ro_ib = draw_english_translation(td, " ".join(ro_lines), center_y=ro_center,
                                            font=ro_font, max_w=1350, line_height=ro_lh)
        return ja_center, ro_center, ro_ib

    # 3) dynamically shrink BOTH fonts until the MEASURED ink block stays
    #    clear of the center divider (real ink, not just estimated line-h).
    ja_lh = int(ja_size * 1.4)
    ro_lh = int(ro_size * 1.3)
    while True:
        ja_center, ro_center, ink_bottom = _measure_block()
        if ink_bottom <= SAFE_BOTTOM or ja_size <= 20:
            break
        ja_size = max(20, ja_size - 2)
        ro_size = max(18, ro_size - 1)
        ja_font = load_chinese_font(ja_size, bold=True)
        ro_font = load_font(ro_size, bold=True, italic=True)
        final_lines = _wrap(target_text, ja_font, 1550)
        n_ja = len(final_lines)
        ro_lines = _wrap(romaji_text, ro_font, 1350) if romaji_text else []
        n_ro = len(ro_lines)
        ja_lh = int(ja_size * 1.4)
        ro_lh = int(ro_size * 1.3)

    ja_center, ro_center, _ = _measure_block()
    draw_lines_centered(draw, final_lines, center_y=ja_center,
                        font=ja_font, line_height=ja_lh)
    if n_ro and ro_center is not None:
        draw_english_translation(draw, " ".join(ro_lines), center_y=ro_center,
                                 font=ro_font, max_w=1350, line_height=ro_lh)

    # === CENTER DIVIDER WITH DOT ===
    div_y = 615
    draw.line([(VIDEO_WIDTH//2 - 300, div_y), (VIDEO_WIDTH//2 + 300, div_y)], fill=YELLOW, width=2)
    draw.ellipse([(VIDEO_WIDTH//2 - 8, div_y - 8), (VIDEO_WIDTH//2 + 8, div_y + 8)], fill=YELLOW)

    # === ENGLISH TRANSLATION (ITALIC, WRAPPED) ===
    english_text = sanitize_latin(turn.get("english", ""))
    draw_english_translation(draw, english_text, center_y=715, font=f_english, max_w=1350, line_height=48)

    # === BOTTOM FOOTER ===
    draw.line([(0, 975), (VIDEO_WIDTH, 975)], fill=YELLOW, width=2)

    footer_y = 1025
    draw_headphones_icon(draw, center_x=VIDEO_WIDTH//2 - 270, center_y=footer_y)
    draw.text((VIDEO_WIDTH//2 - 240, footer_y), "Learn Chinese Naturally", fill=WHITE, font=f_footer, anchor="lm")
    
    fn_bbox = draw.textbbox((VIDEO_WIDTH//2 - 240, footer_y), "Learn Chinese Naturally", font=f_footer, anchor="lm")
    draw.line([(fn_bbox[2] + 20, footer_y - 12), (fn_bbox[2] + 20, footer_y + 12)], fill=DARK_LINE, width=2)
    
    draw.text((fn_bbox[2] + 40, footer_y), "velocitychinese.com", fill=WHITE, font=f_footer, anchor="lm")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=92)


def parse_turns_json(content, target_key="chinese"):
    """Robustly parse JSON array of turns from LLM output, handling unescaped control chars, code fences, and partial json."""
    clean = content.strip()
    if "```json" in clean:
        clean = clean.split("```json")[1].split("```")[0].strip()
    elif "```" in clean:
        clean = clean.split("```")[1].split("```")[0].strip()

    try:
        obj = json.loads(clean, strict=False)
        if isinstance(obj, list):
            return obj
    except Exception:
        pass

    fixed = re.sub(r'(?<!\\)\n', r'\\n', clean)
    try:
        obj = json.loads(fixed, strict=False)
        if isinstance(obj, list):
            return obj
    except Exception:
        pass

    recovered = []
    start = None
    depth = 0
    for ci, ch in enumerate(clean):
        if ch == '{':
            if depth == 0:
                start = ci
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                chunk = clean[start:ci + 1]
                try:
                    t = json.loads(chunk, strict=False)
                    if isinstance(t, dict):
                        recovered.append(t)
                except Exception:
                    try:
                        chunk_fixed = re.sub(r'(?<!\\)\n', r'\\n', chunk)
                        t = json.loads(chunk_fixed, strict=False)
                        if isinstance(t, dict):
                            recovered.append(t)
                    except Exception:
                        pass
                start = None
    if recovered:
        return recovered

    regex = re.compile(
        r'\{\s*"speaker"\s*:\s*"(?P<speaker>[^"]+)"\s*,\s*'
        r'(?:"(?:' + target_key + r'|text|content|spanish)"\s*:\s*"(?P<tgt>.*?)"\s*,\s*)?'
        r'(?:"(?:romaji|translit|transliteration)"\s*:\s*"(?P<ro>.*?)"\s*,\s*)?'
        r'(?:"english"\s*:\s*"(?P<en>.*?)"\s*)?'
        r'\}', re.DOTALL
    )
    for m in regex.finditer(clean):
        spk = m.group("speaker") or "Host1"
        tgt = m.group("tgt") or ""
        ro = m.group("ro") or ""
        en = m.group("en") or ""
        if tgt:
            recovered.append({"speaker": spk, target_key: tgt, "romaji": ro, "english": en})

    return recovered

def _format_history_block(history, max_turns=6):
    """Compact recent turns for the batch prompt (speaker + English + target text)."""
    lines = []
    for turn in (history or [])[-max_turns:]:
        if not isinstance(turn, dict):
            continue
        speaker = turn.get("speaker", "?")
        role = "Mei" if speaker == "Host2" else "Wei"
        en = clean_text(turn.get("english", ""))
        tx = clean_text(re.sub(r'\*\*(.*?)\*\*', r'\1', turn.get("chinese", "")))
        lines.append(f"{role} ({speaker}): EN: {en} / TX: {tx}")
    return "\n".join(lines)


def _fetch_turns_batch(topic, topic_cn, topic_en, start_turn, batch_size=10, history=None):
    """Fetch one small batch of turns with multi-model fallback and robust parsing."""
    current_host = "Host2" if start_turn % 2 == 0 else "Host1"
    next_host = "Host1" if current_host == "Host2" else "Host2"
    host_role = "Mei" if current_host == "Host2" else "Wei"

    history_block = _format_history_block(history)
    intro_instruction = ""
    if start_turn == 0:
        intro_instruction = ("IMPORTANT: This is the FIRST batch. Keep the introduction SHORT - just 2 lines total "
                             "(one from Mei/Host2, one from Wei/Host1), then immediately dive into the topic. "
                             "No long welcome speeches.\n")
    elif history_block:
        intro_instruction = ("IMPORTANT: This is a CONTINUATION. The conversation below is already in progress. "
                             "The first new turn MUST directly respond to the last line above: answer its question, "
                             "react with an opinion or feeling, then ask a follow-up question. "
                             "Do NOT greet, introduce yourself, welcome anyone, or restate the topic. "
                             "Keep ONE evolving thread: every turn answers or reacts to the previous turn, "
                             "never two disconnected monologues.\n")
    else:
        intro_instruction = "Continue naturally into the topic conversation. No new introductions.\n"

    history_section = ""
    if history_block:
        history_section = (f"Previous conversation (respond directly to the LAST line):\n{history_block}\n\n")

    prompt = f"""You are writing a Mandarin Chinese/English learning podcast at A2 level with pinyin.
Topic: {topic}

{history_section}The dialogue so far is at turn {start_turn}. The current speaker is {host_role} ({current_host}).
Write the NEXT {batch_size} turns. Speakers STRICTLY alternate starting with {current_host}.

{intro_instruction}Each turn: 3-4 SHORT sentences (6-10 words each) with PERIODS for natural TTS pauses. 20-30 seconds spoken.
Simple present tense. A2 vocabulary. Natural Mandarin Chinese. Include pinyin (Mandarin transliteration in Latin letters WITH tone marks) for every Chinese line. NO filler sounds.
IMPORTANT: The "chinese" field MUST be written 100% in Simplified Chinese characters.
IMPORTANT: The "romaji" field MUST be written 100% in Latin letters as Hanyu Pinyin WITH tone marks (e.g. ni hao, xuexi, Zhongwen).
IMPORTANT: Highlight exactly 1 key A2 target vocabulary word in each turn's Chinese text using double asterisks, for example: "私たちは**未来**を見ます。"
IMPORTANT: Format as a single compact JSON array without unescaped line breaks inside string values.

Return EXACTLY {batch_size} turns as a JSON array (no markdown):
[{{"speaker": "{current_host}", "chinese": "...", "romaji": "...", "english": "..."}},
 {{"speaker": "{next_host}", "chinese": "...", "romaji": "...", "english": "..."}}]"""

    candidate_models = [AI_MODEL, "openai/gpt-5.4-nano", "mistral", "qwen"]
    models_to_try = []
    for mod in candidate_models:
        if mod and mod not in models_to_try:
            models_to_try.append(mod)

    for attempt, model_name in enumerate(models_to_try):
        try:
            resp = requests.post("https://gen.pollinations.ai/v1/chat/completions", json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You write natural A2-level Mandarin Chinese podcast scripts with VERY clear punctuation. Every sentence must have at least 2 commas for natural TTS pauses. Mei and Wei strictly alternate. Highlight 1 key target word per turn in double asterisks like **xuexi**. No filler sounds. CRITICAL: the chinese field must contain ONLY Simplified Chinese characters. The romaji field must contain ONLY Latin letters: Hanyu Pinyin with tone marks. English belongs only in the english field. Output single compact JSON array without unescaped newlines inside strings."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8
            }, headers={"Authorization": f"Bearer {POLLINATIONS_API_KEY}"} if POLLINATIONS_API_KEY else {}, timeout=45)
            if resp.status_code != 200:
                print(f"  Batch attempt {attempt+1} ({model_name}) returned HTTP {resp.status_code}", flush=True)
                continue
            content = resp.json()["choices"][0]["message"]["content"].strip()
            script = parse_turns_json(content, "chinese")
            valid = []
            for i, turn in enumerate(script):
                if not isinstance(turn, dict):
                    continue
                ja = turn.get("chinese") or turn.get("text") or turn.get("content") or turn.get("spanish") or ""
                en = turn.get("english") or turn.get("translation") or ""
                ro = sanitize_translit(turn.get("romaji") or turn.get("translit") or turn.get("romanji") or "")
                ja = _purify_chinese(ja)
                if not ja:
                    continue
                if not re.search(r'[a-zA-Z]{2,}', ro):
                    ro = to_accurate_pinyin(ja)
                valid.append({
                    "speaker": current_host if i % 2 == 0 else next_host,
                    "chinese": clean_text(ja),
                    "romaji": ro,
                    "english": clean_text(en) if en else "Translation unavailable"
                })
            if len(valid) >= 4:
                return valid
            else:
                print(f"  Batch attempt {attempt+1} ({model_name}) parsed only {len(valid)} turns, trying next model...", flush=True)
        except Exception as e:
            print(f"  Batch attempt {attempt+1} ({model_name}) failed: {e}", flush=True)
            import time
            time.sleep(1)
    return None


def _generate_topic():
    """Have the AI invent a brand-new random topic (unlimited variety).
    Returns '<topic - English>' or None on failure (caller falls back to TOPICS)."""
    seed = random.randint(100000, 999999)
    candidate_models = [AI_MODEL, "openai/gpt-5.4-nano", "mistral"]
    for m in candidate_models:
        if not m:
            continue
        try:
            resp = requests.post("https://gen.pollinations.ai/v1/chat/completions", json={
                "model": m,
                "messages": [
                    {"role": "system", "content": "You invent fresh, interesting, everyday topics for a Chinese/English A2 learning podcast. Always pick something new and varied from all areas of daily life, as a SHORT noun phrase (2-5 words), NOT a full sentence."},
                    {"role": "user", "content": f"Create EXACTLY ONE brand-new topic (uniqueness seed {seed}) for a Chinese/English A2 podcast. Return ONLY one line in this exact format: <topic in Chinese> - <topic in English>. The first part must be a short noun phrase in Simplified Chinese. No numbering, no bullets, no extra text."}
                ],
                "temperature": 1.1,
            }, headers={"Authorization": f"Bearer {POLLINATIONS_API_KEY}"} if POLLINATIONS_API_KEY else {}, timeout=45)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip().strip('"').strip()
                if content and " - " in content:
                    return content
        except Exception as e:
            print(f"  Topic gen ({m}) failed: {e}", flush=True)
    return None


def _fallback_script(topic_cn, topic_en, target=150):
    """Generate 150 unique, educational, progressive dialogue turns in Mandarin
    Chinese with pinyin covering diverse conversation phases."""
    topic_translit = to_accurate_pinyin(topic_cn)
    phases = [
        # Phase 1: Greetings & Introduction
        [
            ("Host2", f"大家好，我是梅。欢迎来到Velocity Chinese！今天我们来聊聊**{topic_cn}**。",
                      f"Hello everyone. I'm Mei. Welcome to Velocity Chinese! Today we talk about {topic_en}."),
            ("Host1", f"你好，梅！听众朋友们，欢迎你们！这个话题对学中文非常**重要**。",
                      f"Hello Mei! Welcome listeners! This topic is very important for learning Chinese."),
            ("Host2", f"没错，韦。在日常生活中很常见，可是很多人不知道怎么用中文**表达**。",
                      f"That's right, Wei. It is common in daily life, but many people don't know how to express it in Chinese."),
            ("Host1", f"所以今天我们用简单的句子和清楚的词语，开心地**学习**吧。",
                      f"So today let's happily learn with simple sentences and clear words."),
            ("Host2", f"太好了！第一个问题，韦，对你来说**{topic_cn}**意味着什么？",
                      f"Wonderful! First question, Wei, what does {topic_en} mean to you?"),
            ("Host1", f"对我来说，它是让每天更开心的生活中**重要**的一部分。",
                      f"For me, it's an important part of life that makes every day happier."),
            ("Host2", f"我完全同意。用心去体会，一天会变得更加**丰富**。",
                      f"I completely agree. Experiencing it mindfully makes the day richer."),
            ("Host1", f"是的，记住需要的词语，自然的**对话**会越来越容易。",
                      f"Yes, once you remember the words you need, natural conversation gets easier and easier."),
        ],
        # Phase 2: Morning routine & habits
        [
            ("Host2", f"韦，你平时早上会想到**{topic_cn}**吗？",
                      f"Wei, on a normal morning do you think about {topic_en}?"),
            ("Host1", f"会的，早起让我心情平静，还会有很好的**想法**。",
                      f"Yes, getting up early calms me and gives me good ideas."),
            ("Host2", f"安静的早晨很特别。可以不着急，享受自己的**时间**。",
                      f"Quiet mornings are special. You can enjoy your own time without rushing."),
            ("Host1", f"忙乱的生活很累人。好的晨间**习惯**让一整天都舒服。",
                      f"A hectic life is tiring. A good morning habit makes the whole day comfortable."),
            ("Host2", f"也有很多人喜欢在晚上或者下班以后享受**{topic_cn}**。",
                      f"Many people also enjoy {topic_en} in the evening or after work."),
            ("Host1", f"每个人生活方式不同，找到适合自己的**平衡**最重要。",
                      f"Everyone's lifestyle differs; finding your own balance matters most."),
            ("Host2", f"说得对。了解自己的节奏，生活会更**舒服**。",
                      f"Well said. Knowing your own rhythm makes life more comfortable."),
            ("Host1", f"学中文也一样，每天一点点的积累会变成真正的**能力**。",
                      f"Learning Chinese is the same: a little accumulation every day becomes real ability."),
        ],
        # Phase 3: Friends, curiosity & wrap-up
        [
            ("Host2", f"韦，你的朋友们聊到**{topic_cn}**时会有什么反应？",
                      f"Wei, how do your friends react when talking about {topic_en}?"),
            ("Host1", f"他们都很感兴趣，还会问我很多**问题**。",
                      f"They are very interested and ask me many questions."),
            ("Host2", f"好奇心是最好的老师。多问，多听，进步会很**快**。",
                      f"Curiosity is the best teacher. Ask more, listen more, progress fast."),
            ("Host1", f"听众朋友也可以跟着我们大声**练习**今天的关键词。",
                      f"Listeners can also practice today's keywords out loud with us."),
            ("Host2", f"对了，**{topic_cn}**在不同的地方，人们的看法一样吗？",
                      f"By the way, do people in different places see {topic_en} the same way?"),
            ("Host1", f"不太一样。每个地方都有自己的**特色**，很有意思。",
                      f"Not quite the same. Every place has its own character, very interesting."),
            ("Host2", f"学语言就是这样，越比较，理解越**深刻**。",
                      f"That is language learning: the more you compare, the deeper you understand."),
            ("Host1", f"今天的**{topic_cn}**就聊到这里，明天我们继续加油！",
                      f"That is {topic_en} for today. Let's keep going tomorrow!"),
        ],
    ]

    all_templates = []
    for ph in phases:
        all_templates.extend(ph)
    turns = []
    for i in range(target):
        _, t_cn, t_en = all_templates[i % len(all_templates)]
        spk = "Host2" if i % 2 == 0 else "Host1"
        turns.append({
            "speaker": spk,
            "chinese": t_cn,
            "romaji": to_accurate_pinyin(t_cn),
            "english": t_en
        })
    return turns

def _extend_script(existing_turns, topic_cn, topic_en, target=150):
    fallback_pool = _fallback_script(topic_cn, topic_en, target)
    idx = 0
    cur_speaker = existing_turns[-1]["speaker"] if existing_turns else "Host1"
    while len(existing_turns) < target:
        cand = fallback_pool[idx % len(fallback_pool)]
        idx += 1
        needed_spk = "Host1" if cur_speaker == "Host2" else "Host2"
        existing_turns.append({
            "speaker": needed_spk,
            "chinese": cand["chinese"],
            "romaji": cand["romaji"],
            "english": cand["english"]
        })
        cur_speaker = needed_spk
    return existing_turns[:target]


def generate_script():
    topic = _generate_topic() or random.choice(TOPICS)
    topic_cn = topic.split(" - ")[0]
    topic_en = topic.split(" - ")[1]

    TARGET = int(os.getenv("SAMPLE_TURNS", "150") or 150)
    BATCH = 10
    all_turns = []
    consecutive_empty = 0
    import time as _time
    _deadline = _time.time() + 600  # generous 10 min cap

    while len(all_turns) < TARGET and consecutive_empty < 12 and _time.time() < _deadline:
        batch = _fetch_turns_batch(topic, topic_cn, topic_en, len(all_turns), BATCH, history=all_turns)
        if not batch:
            consecutive_empty += 1
            wait_s = min(15, 3 + consecutive_empty * 2)
            print(f"  API busy (consecutive fails: {consecutive_empty}) - waiting {wait_s}s before retrying...", flush=True)
            _time.sleep(wait_s)
            continue
        all_turns.extend(batch)
        consecutive_empty = 0
        print(f"  Script progress: {len(all_turns)}/{TARGET} turns", flush=True)
        if len(all_turns) < TARGET:
            _time.sleep(1)

    all_turns = all_turns[:TARGET]

    if not all_turns:
        print("  Using structured fallback script (150 unique turns)...", flush=True)
        all_turns = _fallback_script(topic_cn, topic_en, TARGET)
    elif len(all_turns) < TARGET:
        print(f"  Extending {len(all_turns)} turns to {TARGET} with topic conversation...", flush=True)
        all_turns = _extend_script(all_turns, topic_cn, topic_en, TARGET)

    # Short 2-line intro: Mei (Host2) first, then Wei (Host1), then topic
    topic_translit = to_accurate_pinyin(topic_cn)
    all_turns[0]["speaker"] = "Host2"
    all_turns[0]["chinese"] = f"你好，我是梅。欢迎来到Velocity Chinese。今天我们来聊聊**{topic_cn}**。"
    all_turns[0]["romaji"] = f"Nǐ hǎo, wǒ shì Méi. Huānyíng láidào Velocity Chinese. Jīntiān wǒmen lái liáoliao {topic_translit}."
    all_turns[0]["english"] = f"Hi, I'm Mei. Welcome to Velocity Chinese Podcast. Today we talk about {topic_en}."
    if len(all_turns) > 1:
        all_turns[1]["speaker"] = "Host1"
        all_turns[1]["chinese"] = f"谢谢，梅！今天的话题非常**有意思**。我们开始吧。"
        all_turns[1]["romaji"] = f"Xièxie, Méi! Jīntiān de huàtí fēicháng yǒu yìsi. Wǒmen kāishǐ ba."
        all_turns[1]["english"] = f"Thanks, Mei. Today's topic is very interesting. Let's start."

    # Final guarantee across ALL turns: ensure valid Latin romaji exists for every single turn
    for turn in all_turns:
        ja = turn.get("chinese", "")
        ja = _purify_chinese(ja)
        turn["chinese"] = ja
        ro = sanitize_translit(turn.get("romaji", ""))
        if not re.search(r'[a-zA-Z]{2,}', ro):
            turn["romaji"] = to_accurate_pinyin(ja)
        else:
            turn["romaji"] = ro

    print(f"  Script: {len(all_turns)} turns, topic: {topic_cn}", flush=True)
    return all_turns, topic_cn, topic_en


def configure_edge_tts():
    """Stock edge-tts endpoint only: forcing api.msedgeservices.com breaks runners."""
    return None




async def generate_audio(turns, target_dir=None):
    configure_edge_tts()
    import edge_tts
    audio_files = []
    audio_dir = Path(target_dir) if target_dir else OUTPUT_DIR
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i, turn in enumerate(turns):
        voice = HOST1_VOICE if turn["speaker"] == "Host1" else HOST2_VOICE
        filename = audio_dir / f"audio_{i:03d}.mp3"
        spoken_text = re.sub(r'\*\*(.*?)\*\*', r'\1', turn.get("chinese", turn.get("spanish", "")))
        success = False
        word_boundaries = []
        engine = "edge"
        for attempt in range(3):
            try:
                configure_edge_tts()
                communicate = edge_tts.Communicate(spoken_text, voice, rate="-10%", boundary="WordBoundary")
                _bounds = []
                _chunks = bytearray()
                async for _c in communicate.stream():
                    _t = _c.get("type")
                    if _t == "audio":
                        _chunks.extend(_c.get("data", b""))
                    elif _t == "WordBoundary":
                        _bounds.append({"offset": _c["offset"] / 10_000_000, "duration": _c["duration"] / 10_000_000, "text": _c.get("text", "")})
                if _chunks:
                    with open(str(filename), "wb") as _f:
                        _f.write(_chunks)
                word_boundaries = list(_bounds)
                if Path(filename).exists() and Path(filename).stat().st_size > 100:
                    success = True
                    break
            except Exception as e:
                print(f"  Audio {i} attempt {attempt+1}/3 failed: {e}")
                if attempt == 0:
                    print(f"  Audio {i} waiting 15s before retry...")
                    await asyncio.sleep(15.0)
                elif attempt == 1:
                    print(f"  Audio {i} waiting 45s before final retry...")
                    await asyncio.sleep(45.0)
        if not success:
            raise RuntimeError(f"Edge TTS failed for turn {i} after 3 attempts; no fallback allowed")
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(filename)], capture_output=True, text=True)
            duration = float(r.stdout.strip()) if r.stdout else 3.0
        except:
            duration = 3.0
        audio_files.append({"path": str(filename), "duration": duration, "speaker": turn["speaker"], "voice": voice, "engine": engine, "word_boundaries": word_boundaries})
        if (i + 1) % 25 == 0 or i == 0:
            print(f"  Audio {i} [{turn['speaker']}/{voice}] via {engine}: {duration:.1f}s, {len(word_boundaries)} bounds")
    return audio_files

_KARAOKE_SEP = ""
# Joiner that rebuilds the exact original spacing from karaoke tokens.
# Word languages use " "; char/cluster languages use "".


def _karaoke_marked(tokens, k):
    """Step k highlighted; a pure-space step keeps the nearest real
    word highlighted (backward first), so no step is marker-free."""
    kk = k
    if 0 <= kk < len(tokens) and tokens[kk].strip() == "":
        j = kk
        while j >= 0 and tokens[j].strip() == "":
            j -= 1
        if j < 0:
            j = kk
            while j < len(tokens) and tokens[j].strip() == "":
                j += 1
        if j < len(tokens):
            kk = j
    return _KARAOKE_SEP.join(
        f"**{x}**" if (j == kk and x.strip() != "") else x
        for j, x in enumerate(tokens))



def _boundary_tokens_and_spans(clean, boundaries):
    """Align Edge TTS word boundaries to the text: (token texts, spans).

    Returns (None, None) when alignment fails. Skipped characters between
    boundaries (punctuation or spaces the engine does not emit) attach to
    the preceding token, so joining the tokens rebuilds the text exactly.
    """
    items = [(b.get("text", ""), b) for b in (boundaries or []) if b.get("text")]
    if not items or not clean:
        return None, None
    out, spans, pos = [], [], 0
    for t, b in items:
        raw = t
        i = clean.find(raw, pos)
        if i < 0:
            return None, None
        if i > pos:
            gap = clean[pos:i]
            if out:
                out[-1] += gap
            else:
                t = gap + raw
        try:
            start = float(b.get("offset", 0))
            end = start + float(b.get("duration", 0))
        except (TypeError, ValueError):
            return None, None
        out.append(t)
        spans.append([start, end])
        pos = i + len(raw)
    if pos < len(clean):
        if not out:
            return None, None
        out[-1] += clean[pos:]
    return out, spans


def _spans_for_tokens(tokens, aligned, spans):
    """Map display tokens back onto aligned boundary spans.

    Matching tolerates whitespace attached to boundary pieces (spaces the
    engine skips attach to the neighboring piece); returns None on any
    surprise (caller falls back to even split).
    """
    res, j = [], 0
    for tok in tokens:
        rest, s, e = tok, None, None
        while rest:
            if j >= len(aligned):
                return None
            p, (ps, pe) = aligned[j], spans[j]
            pm = p.strip()
            if not pm:
                j += 1
                continue
            if rest == pm or rest.startswith(pm):
                s = ps if s is None else s
                e = pe
                rest = rest[len(pm):]
                j += 1
            else:
                return None
        res.append([s, e])
    return res


def _karaoke_marked(tokens, k):
    """Rebuild the karaoke line with token k highlighted, preserving spacing.

    The highlighted token keeps its exact position, so the wrapped subtitle
    lines are identical at every step: only the color changes, the layout
    never shifts. A pure-space step keeps the nearest real word highlighted
    (looking backward first), so no step is ever marker-free.
    """
    kk = k
    if 0 <= kk < len(tokens) and tokens[kk].strip() == "":
        j = kk
        while j >= 0 and tokens[j].strip() == "":
            j -= 1
        if j < 0:
            j = kk
            while j < len(tokens) and tokens[j].strip() == "":
                j += 1
        if j < len(tokens):
            kk = j
    return _KARAOKE_SEP.join(
        f"**{x}**" if (j == kk and x.strip() != "") else x
        for j, x in enumerate(tokens))


def karaoke_tokens_for_text(chinese_text, boundaries=None):
    """Engine-word highlight tokens when boundaries rebuild the text,
    else per-character tokens for spaceless script."""
    clean = re.sub(r'\*\*(.*?)\*\*', r'\1', chinese_text or "").strip()
    if not clean:
        return []
    if boundaries:
        aligned, _spans = _boundary_tokens_and_spans(clean, boundaries)
        if aligned is not None and "".join(aligned) == clean:
            return [a.strip() for a in aligned if a.strip()]
    return list(clean)

def karaoke_step_durations(tokens, duration, boundaries, text=None):
    """Per-token seconds: exact Edge spans when they map to tokens, else split."""
    n = len(tokens)
    if n == 0:
        return []
    if boundaries and text:
        clean = re.sub(r'\*\*(.*?)\*\*', r'\1', text or "").strip()
        aligned, spans = _boundary_tokens_and_spans(clean, boundaries)
        if (aligned is not None and "".join(aligned) == clean
                and "".join(tokens).replace(" ", "") == clean.replace(" ", "")):
            mapped = _spans_for_tokens(tokens, aligned, spans)
            if mapped is not None:
                total = sum(e - s for s, e in mapped) or duration
                durs = [(e - s) * duration / total for s, e in mapped]
                durs = [max(0.12, d) for d in durs]
                scale = duration / sum(durs)
                return [d * scale for d in durs]
    if boundaries and len(boundaries) == n:
        total = sum(b["duration"] for b in boundaries) or duration
        durs = [b["duration"] * duration / total for b in boundaries]
    else:
        durs = [duration / n] * n
    durs = [max(0.12, d) for d in durs]
    scale = duration / sum(durs)
    return [d * scale for d in durs]


def _ass_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_karaoke_files(turns, audio_files, out_dir):
    """Write word_timings.json + karaoke ASS subtitle data for the episode."""
    out_dir = Path(out_dir)
    t = 0.0
    events = []
    timings = []
    for turn, audio in zip(turns, audio_files):
        dur = audio["duration"]
        tokens = karaoke_tokens_for_text(turn.get("chinese", ""), audio.get("word_boundaries", []))
        steps = karaoke_step_durations(tokens, dur, audio.get("word_boundaries", []), turn.get("chinese", ""))
        cursor = t
        cells = []
        for tok, d in zip(tokens, steps):
            cells.append({"token": tok, "start": round(cursor, 3), "end": round(cursor + d, 3)})
            cursor += d
        timings.append({"speaker": turn["speaker"], "tokens": cells})
        if tokens:
            k_line = _KARAOKE_SEP.join("{\\k%d}%s" % (max(1, int(round(d * 100))), tok) for tok, d in zip(tokens, steps))
            events.append(f"Dialogue: 0,{_ass_timestamp(t)},{_ass_timestamp(t + dur)},CN,,0,0,0,,{k_line}")
        romaji = sanitize_translit(turn.get("romaji", ""))
        if romaji:
            events.append(f"Dialogue: 0,{_ass_timestamp(t)},{_ass_timestamp(t + dur)},Pinyin,,0,0,0,,{romaji}")
        t += dur
    with open(out_dir / "word_timings.json", "w", encoding="utf-8") as f:
        json.dump(timings, f, indent=1, ensure_ascii=False)
    header = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n"
              "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Alignment, MarginV\n"
              "Style: CN,Noto Sans SC,64,&H0000CAF7,&H80000000,&H80000000,1,8,180\n"
              "Style: Pinyin,Arial,40,&H00CDB4AA,&H80000000,&H80000000,0,8,120\n\n"
              "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    with open(out_dir / "podcast_karaoke.ass", "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")
    return out_dir / "podcast_karaoke.ass"


def render_karaoke_preview(turns, audio_files, out_dir, max_turns=3):
    """Burnt-in per-word highlight preview for the first turns (local check)."""
    out_dir = Path(out_dir)
    prev_dir = out_dir / "karaoke_preview"
    prev_dir.mkdir(parents=True, exist_ok=True)
    segments = []
    for ti in range(min(max_turns, len(turns))):
        turn = turns[ti]
        audio = audio_files[ti]
        tokens = karaoke_tokens_for_text(turn.get("chinese", ""), audio.get("word_boundaries", []))
        if not tokens:
            continue
        steps = karaoke_step_durations(tokens, audio["duration"], audio.get("word_boundaries", []), turn.get("chinese", ""))
        parts = []
        for k in range(len(tokens)):
            marked = _karaoke_marked(tokens, k)
            step_turn = dict(turn)
            step_turn["chinese"] = marked
            img = prev_dir / f"t{ti:02d}_w{k:03d}.png"
            create_frame(step_turn, str(img), ti, preserve_highlights=True)
            part = prev_dir / f"t{ti:02d}_w{k:03d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(img),
                            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={FPS}",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-t", f"{steps[k]:.3f}", str(part)],
                           check=True, capture_output=True)
            parts.append(part)
        seg = prev_dir / f"seg_{ti:02d}.mp4"
        lst = prev_dir / f"seg_{ti:02d}.txt"
        with open(lst, "w") as f:
            for p in parts:
                f.write(f"file '{p.resolve().as_posix()}'\n")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-i", audio["path"], "-c:v", "copy", "-c:a", "aac",
                        "-shortest", str(seg)], check=True, capture_output=True)
        segments.append(seg)
    preview = out_dir / "karaoke_preview.mp4"
    lst = prev_dir / "all.txt"
    with open(lst, "w") as f:
        for s in segments:
            f.write(f"file '{s.resolve().as_posix()}'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(preview)], check=True)
    return preview


def _render_turn_segment(turn, audio, video_dir, i):
    """One video segment per turn with burnt-in per-word karaoke highlight."""
    video_dir = Path(video_dir)
    tokens = karaoke_tokens_for_text(turn.get("chinese", ""), audio.get("word_boundaries", []))
    steps = karaoke_step_durations(tokens, audio["duration"], audio.get("word_boundaries", []), turn.get("chinese", ""))
    if not tokens:
        img = video_dir / f"f_{i:04d}.png"
        create_frame(turn, str(img), i)
        parts = [(img, audio["duration"])]
    else:
        parts = []
        for k in range(len(tokens)):
            marked = _karaoke_marked(tokens, k)
            step_turn = dict(turn)
            step_turn["chinese"] = marked
            img = video_dir / f"f_{i:04d}_w{k:03d}.png"
            create_frame(step_turn, str(img), i, preserve_highlights=True)
            parts.append((img, steps[k]))
    if len(parts) == 1:
        img, dur = parts[0]
        clip = video_dir / f"c_{i:04d}.mp4"
        fade_start = max(0.0, dur - 0.3)
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", audio["path"],
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={FPS}",
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-t", str(dur), "-af", f"afade=t=out:st={fade_start:.2f}:d=0.3",
            str(clip)
        ], check=True, capture_output=True)
        return clip
    word_clips = []
    for j, (img, d) in enumerate(parts):
        part = video_dir / f"c_{i:04d}_w{j:03d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(img),
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={FPS}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-t", f"{d:.3f}", str(part)], check=True, capture_output=True)
        word_clips.append(part)
    lst = video_dir / f"seg_{i:04d}.txt"
    with open(lst, "w") as f:
        for p in word_clips:
            f.write(f"file '{p.resolve().as_posix()}'\n")
    clip = video_dir / f"c_{i:04d}.mp4"
    fade_start = max(0.0, audio["duration"] - 0.3)
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-i", audio["path"], "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-af", f"afade=t=out:st={fade_start:.2f}:d=0.3",
        "-shortest", str(clip)], check=True, capture_output=True)
    for p in word_clips:
        p.unlink(missing_ok=True)
    lst.unlink(missing_ok=True)
    return clip


def create_video(turns, audio_files, video_dir=None):
    if video_dir is None:
        video_dir = OUTPUT_DIR / f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    video_dir = Path(video_dir)
    video_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    total_dur = 0

    for i, (turn, audio) in enumerate(zip(turns, audio_files)):
        clip = _render_turn_segment(turn, audio, video_dir, i)
        clips.append(clip)

        total_dur += audio["duration"]
        if (i + 1) % 25 == 0:
            print(f"  Frame {i+1}/{len(turns)}")

    concat = video_dir / "list.txt"
    with open(concat, "w") as f:
        for c in clips:
            f.write(f"file '{c.resolve().as_posix()}'\n")

    out = video_dir / "podcast_final.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-movflags", "+faststart", str(out)], check=True)

    for c in clips:
        c.unlink(missing_ok=True)
    for a in audio_files:
        try:
            Path(a["path"]).unlink(missing_ok=True)
        except Exception:
            pass
    if concat.exists():
        concat.unlink(missing_ok=True)

    return out, total_dur


async def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("=" * 60)
    print("  VELOCITY CHINESE PODCAST")
    print("=" * 60)

    print("\n[1/4] Generating script...")
    turns, topic_cn, topic_en = generate_script()

    video_dir = OUTPUT_DIR / f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    video_dir.mkdir(parents=True, exist_ok=True)

    with open(video_dir / "script.json", "w", encoding="utf-8") as f:
        json.dump({"topic": topic_cn, "topic_en": topic_en, "turns": turns}, f, indent=2, ensure_ascii=False)

    print(f"\n[2/4] Generating audio ({len(turns)} turns)...")
    audio_files = await generate_audio(turns, video_dir)
    total_audio = sum(a["duration"] for a in audio_files)
    print(f"  Total audio: {total_audio/60:.1f} min")

    print(f"\n[2b/4] Writing karaoke subtitle data...")
    write_karaoke_files(turns, audio_files, video_dir)
    if os.getenv("KARAOKE_PREVIEW_TURNS"):
        try:
            preview = render_karaoke_preview(turns, audio_files, video_dir, max_turns=int(os.getenv("KARAOKE_PREVIEW_TURNS", "3")))
            print(f"  Karaoke preview: {preview}")
        except Exception as e:
            print(f"  Karaoke preview warn: {e}")
    print(f"\n[3/4] Creating video...")
    video_path, duration = create_video(turns, audio_files, video_dir)

    print(f"\n[4/4] Saving...")
    first_frame = video_dir / "f_0000.png"
    thumbnail_path = video_dir / "thumbnail.jpg"
    try:
        from PIL import Image as _Img
        if first_frame.exists():
            _Img.open(str(first_frame)).convert("RGB").save(str(thumbnail_path), quality=92)
    except Exception as e:
        print(f"  Thumbnail warn: {e}")

    title = build_podcast_title(topic_cn, topic_en)
    description = build_podcast_description(topic_cn, topic_en, len(turns), round(duration / 60, 1))
    tags = ["Learn Chinese", "Chinese", "Chinese Podcast", "Learn Chinese Naturally",
            "Chinese for Beginners", "Bilingual", "Chinese Listening", "Chinese Conversation",
            "HSK 3", "HSK 4", "Chinese Pinyin", "Velocity Chinese", topic_cn, topic_en]

    meta_out = {
        "title": title,
        "description": description,
        "tags": tags,
        "category_english": topic_cn,
        "language": "Chinese",
        "duration_minutes": round(duration / 60, 1),
        "turns_count": len(turns),
        "video_path": str(video_path),
        "thumbnail_path": str(thumbnail_path),
        "generated_at": datetime.now().isoformat(),
    }
    (OUTPUT_DIR).mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "latest_video.json", "w", encoding="utf-8") as f:
        json.dump(meta_out, f, indent=2, ensure_ascii=False)
    with open(OUTPUT_DIR / "latest_upload_info.json", "w", encoding="utf-8") as f:
        json.dump({"title": title, "description": description,
                   "category": topic_cn, "turns_count": len(turns)}, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print("  PODCAST COMPLETE!")
    print(f"  Topic: {topic_cn}")
    print(f"  Duration: {duration/60:.1f} min ({len(turns)} turns)")
    print(f"  Video: {video_path.name}")
    print("=" * 60)


def build_podcast_title(topic_cn, topic_en):
    titles = [
        f"Learn Chinese: {topic_cn} ({topic_en}) | Bilingual Chinese Podcast | Velocity Chinese",
        f"Chinese Conversation for Beginners: {topic_cn} | Mei & Wei | Velocity Chinese",
        f"Chinese Podcast: {topic_cn} ({topic_en}) | A2 Listening Practice with Pinyin",
        f"{topic_cn} | Speak Chinese Naturally with Mei & Wei | Velocity Chinese",
    ]
    return random.choice(titles)


def build_podcast_description(topic_cn, topic_en, turns_count, duration_min):
    description = (
        f"🎙️ Velocity Chinese 欢迎你。Huānyíng láidào Podcast!\n"
        f"👉 Free Chinese Guides & Vocabulary Blog: https://velocitychinese.com/\n"
        f"📖 Read our latest Chinese Articles: https://velocitychinese.com/blog/\n\n"

        f"这一期，Mei 和 Wei 会用中文聊聊：{topic_cn} ({topic_en}).\n"
        f"A2级别的轻松双语对话，带拼音，帮你自然地学会中文。\n\n"

        f"✨ WHAT'S INSIDE THIS EPISODE:\n"
        f"• {turns_count} 个实用的中文短语和表达 (Practical Chinese phrases)\n"
        f"• 日常交流的实用词汇 (Everyday conversational vocabulary)\n"
        f"• 自然的母语发音 (Natural native pronunciation)\n"
        f"• 每一句都有英文翻译和拼音 (English translation and pinyin on every line)\n\n"

        f"🔍 POPULAR SEARCH QUERIES:\n"
        f"learn chinese, chinese podcast for beginners, hsk listening practice, chinese conversation a2, learn chinese with pinyin, {topic_en.lower()} in chinese, velocity chinese podcast\n\n"

        f"📌 HOW TO USE THIS PODCAST:\n"
        f"1️⃣ 先听中文，试着理解意思 (Listen to Chinese)\n"
        f"2️⃣ 看拼音，跟读发音 (Read the pinyin)\n"
        f"3️⃣ 对照英文翻译确认意思 (Check English meaning)\n"
        f"4️⃣ 大声重复短语 (Repeat out loud)\n"
        f"5️⃣ 明天再听一次 - 每天都会更简单! (Practice daily!)\n\n"

        f"🌐 OFFICIAL WEBSITE & BLOG:\n"
        f"• Website: https://velocitychinese.com/\n"
        f"• Blog: https://velocitychinese.com/blog/\n\n"

        f"🔔 请订阅，每天都有新课程。\n\n"

        f"📅 时长: {duration_min} 分钟\n\n"

        f"#LearnChinese #ChinesePodcast #Bilingual #LanguageLearning #ChineseForBeginners #HSK #VelocityChinese #SpeakChinese"
    )
    return description

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('  Cancelled.')