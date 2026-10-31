"""Regression: continuity history + engine-synced karaoke + one-word highlight steps.

Standard library only:
    python test_karaoke.py        # exit 0 = pass, exit 1 = fail
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

# 1. Continuation history carries recent turns and strips markers.
_h = [{"speaker": "Host2" if i % 2 == 0 else "Host1",
       "chinese": "**w%d** text" % i, "english": "line%d" % i} for i in range(8)]
_b = pg._format_history_block(_h)
if "**" in _b or "line7" not in _b or "line0" in _b or "line1" in _b:
    FAILURES.append("history-window: %r" % (_b,))

# 2. Engine boundaries give exact per-token timings summing to the duration.
SAMPLE = "你好世界今天很好"
_sw = [b["text"] for b in [{"text": "你好", "offset": 0.0, "duration": 0.3}, {"text": "世界", "offset": 0.5, "duration": 0.3}, {"text": "今天", "offset": 1.0, "duration": 0.3}, {"text": "很好", "offset": 1.5, "duration": 0.3}]]
_t0 = pg.karaoke_tokens_for_text(SAMPLE)
_t = pg.karaoke_tokens_for_text(SAMPLE, [{"text": "你好", "offset": 0.0, "duration": 0.3}, {"text": "世界", "offset": 0.5, "duration": 0.3}, {"text": "今天", "offset": 1.0, "duration": 0.3}, {"text": "很好", "offset": 1.5, "duration": 0.3}])
_d = pg.karaoke_step_durations(_t or _t0, 1.9, [{"text": "你好", "offset": 0.0, "duration": 0.3}, {"text": "世界", "offset": 0.5, "duration": 0.3}, {"text": "今天", "offset": 1.0, "duration": 0.3}, {"text": "很好", "offset": 1.5, "duration": 0.3}], SAMPLE)
if not (_t or _t0) or abs(sum(_d) - 1.9) > 0.05 or len(_d) != len(_t or _t0):
    FAILURES.append("engine-sync: %r stepped %r" % (_t, _d))

# 3. Exactly one non-space word highlighted per step; spacing kept.
_mt = _t0 or _t
_mp = SAMPLE.replace("**", "").strip()
for _k in range(len(_mt)):
    _m = pg._karaoke_marked(_mt, _k)
    if _m.count("**") != 2:
        FAILURES.append("mark-one: step %d markers %r" % (_k, _m))
        break
    if _m.split("**")[1].strip() == "":
        FAILURES.append("mark-space: step %d highlights blank %r" % (_k, _m))
        break
    if _m.replace("**", "") != _mp:
        FAILURES.append("mark-spacing: step %d moved text %r" % (_k, _m))
        break

if FAILURES:
    print("FAIL (%d):" % len(FAILURES))
    for f in FAILURES:
        print("  - " + f)
    sys.exit(1)
print("PASS: karaoke regression (3 checks)")
