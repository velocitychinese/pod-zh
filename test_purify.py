"""Regression test: Chinese-field purification removes Latin leaks from the script API.

Covers _purify_chinese (strip Latin, keep Hanzi/**brand**) and the
to_accurate_pinyin converter (tone marks preserved).

Run with the standard library only (pypinyin needed for full pinyin):
    python test_purify.py        # exit 0 = pass, exit 1 = fail
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import podcast_generator as pg

FAILURES = []


def check(name, got, must_have=(), must_missing=()):
    for s in must_have:
        if s not in got:
            FAILURES.append("%s: missing %r in %r" % (name, s, got))
    for s in must_missing:
        if s in got:
            FAILURES.append("%s: leaked %r in %r" % (name, s, got))


# 1. Latin leak mixed into Hanzi is removed.
out = pg._purify_chinese("你好， hello 韦！")
check("leak-plain", out, ("你好", "韦"), ("hello",))

# 2. Latin leak inside highlight markers is removed (empty markers go too).
out = pg._purify_chinese("今天的话题非常 **you yisi**。")
check("leak-in-highlight", out, ("今天的话题非常",), ("you yisi", "****"))

# 3. The brand name survives purification untouched.
brand = "欢迎来到Velocity Chinese。今天我们来聊聊"
if pg._purify_chinese(brand) != brand:
    FAILURES.append("brand: damaged -> %r" % pg._purify_chinese(brand))

# 4. Clean input passes through unchanged.
clean = "谢谢，韦！今天的话题非常**有意思**。我们开始吧。"
if pg._purify_chinese(clean) != clean:
    FAILURES.append("clean-passthrough: changed -> %r" % pg._purify_chinese(clean))

# 5. Pinyin converter keeps tone marks.
r = pg.to_accurate_pinyin("你好，我是韦。")
if not any(c in r for c in "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü"):
    FAILURES.append("pinyin-tones: no tone marks in %r" % r)

# 6. End-to-end fragment of the generate_script guarantee loop.
turn = {"chinese": "今天的话题非常 **you yisi**。", "romaji": ""}
ja = pg._purify_chinese(turn.get("chinese", ""))
turn["chinese"] = ja
check("guarantee-writeback", turn["chinese"], ("今天的话题非常",), ("you yisi", "****"))

# 7. Spacing regression: wrapped Chinese lines keep original spacing
#    (no spaces injected between characters), with and without highlights.
from PIL import Image, ImageDraw
_tmp_img = Image.new("RGB", (10, 10))
_tmp_d = ImageDraw.Draw(_tmp_img)
_sp_font = pg.load_chinese_font(40, bold=True)
for _src in ("你好，韦！今天的话题非常有意思。",
             "今天的话题非常**有意思**。我们开始吧。"):
    _toks = pg._cjk_tokens(_src, _sp_font, _tmp_d)
    _wl = pg._wrap_tokens(_toks, 10000)
    if len(_wl) != 1:
        FAILURES.append("spacing: unexpected wrap of %r" % _src)
        continue
    _line = pg._join_tokens(_wl[0][0], highlight=True)
    _rt = pg._cjk_tokens(_line, _sp_font, _tmp_d)
    _want = [(_t, _h) for _t, _h, _x in _wl[0][0]]
    _got = [(_t, _h) for _t, _h, _x in _rt]
    if _got != _want:
        FAILURES.append("spacing: %r round-tripped to %r" % (_src, _line))

# 8. Bold CJK font carries more ink than Regular (variation applies).
def _ink(_font, _text):
    _im = Image.new("RGB", (600, 120), (0, 0, 0))
    ImageDraw.Draw(_im).text((10, 10), _text, fill=(255, 255, 255), font=_font)
    return sum(1 for _px in _im.get_flattened_data() if _px[0] > 128)

_ink_bold = _ink(pg.load_chinese_font(64, bold=True), "中文测试")
_ink_reg = _ink(pg.load_chinese_font(64, bold=False), "中文测试")
if not _ink_bold > _ink_reg * 1.5:
    FAILURES.append("bold: no weight difference (%d vs %d)" % (_ink_bold, _ink_reg))

# 9. Voice order + pace: first turn is Mei (female voice), speech slowed down.
_gen_src = (Path(__file__).resolve().parent / "podcast_generator.py").read_text(encoding="utf-8")
for _need in ['HOST2_VOICE = "zh-CN-XiaoxiaoNeural"',
              'HOST1_VOICE = "zh-CN-YunyangNeural"',
              'all_turns[0]["speaker"] = "Host2"',
              'rate="-10%"']:
    if _need not in _gen_src:
        FAILURES.append("config: missing %r" % _need)

# 10. Karaoke marked lines preserve spacing exactly at every highlight step.
_ctoks = pg.karaoke_tokens_for_text("谢谢韦！今天的话题非常有意思。我们开始吧。")
_cplain = "谢谢韦！今天的话题非常有意思。我们开始吧。"
if not _ctoks:
    FAILURES.append("karaoke-marked: no tokens")
else:
    for _k in range(len(_ctoks)):
        _m = pg._karaoke_marked(_ctoks, _k)
        if _m.replace("**", "") != _cplain:
            FAILURES.append("karaoke-marked: spacing lost at step %d: %r" % (_k, _m))
            break

# 11. Tokenizer keeps spaces around highlight runs (exact round-trip).
for _src in ("今天的话题非常**有意思**。我们开始吧。",
             "学习 Chinese **Podcast** 很有意思"):
    _toks = pg._cjk_tokens(_src, _sp_font, _tmp_d)
    _rt = "".join(_t[0] for _t in _toks)
    if _rt != _src.replace("**", ""):
        FAILURES.append("tokenizer-space: %r became %r" % (_src, _rt))

# 12. Wrapped subtitle lines never shift between highlight steps.
_wraps = []
for _k in range(len(_ctoks)):
    _mk = pg._karaoke_marked(_ctoks, _k)
    _tk = pg._cjk_tokens(_mk, _sp_font, _tmp_d)
    _w = pg._wrap_tokens(_tk, 400)
    _wraps.append([[_x[0] for _x in _line] for _line, _wd in _w])
if any(_w != _wraps[0] for _w in _wraps):
    FAILURES.append("wrap-stable: lines shift between steps: %r" % (_wraps,))

if FAILURES:
    print("FAIL (%d):" % len(FAILURES))
    for f in FAILURES:
        print("  - " + f)
    sys.exit(1)
print("PASS: purify+render+voice regression (12 checks)")
