"""scanner_log.py — compact rolling log for the SignalTel scanner.

Design goals (user: "log، ولی حجم نگیره"):
- ONE small file: data/scanner.log
- Size-capped via rotation: scanner.log (current) + scanner.log.1, each <= 256 KB
  (~512 KB total worst case — a few MB of disk is never used).
- One SUMMARY line per scan tick (strategy -> symbol counts + timings), plus
  per-signal lines. No per-symbol chatter: 100 symbols x 4 strategies would be
  400 lines/tick = ~500k lines/day. A tick summary is 1 line.
- Verification use-case: "are all 4 strategies scanning correctly?" -> check
  strategies_scanned=4 in the tick line + per-strategy fetch/error counts.
"""
import os
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_LOG_PATH = os.path.join(_LOG_DIR, "scanner.log")
ROTATE_BYTES = 256 * 1024   # 256 KB per file
_KEEP = 1                   # keep scanner.log + scanner.log.1

_lock = threading.Lock()
def _rotate_if_needed():
    try:
        if os.path.exists(_LOG_PATH) and os.path.getsize(_LOG_PATH) > ROTATE_BYTES:
            shifted = _LOG_PATH + ".1"
            if os.path.exists(shifted):
                os.remove(shifted)
            os.replace(_LOG_PATH, shifted)
    except OSError:
        pass  # never let logging break the scan


def log(msg: str):
    """Append one timestamped line; rotates when > 256 KB (keeps 1 old file)."""
    ts = datetime.now(timezone.utc).strftime("%m-%d %H:%M:%S")
    line = f"{ts} {msg}\n"
    with _lock:
        try:
            os.makedirs(_LOG_DIR, exist_ok=True)
            _rotate_if_needed()
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass


def signal(symbol: str, strategy: str, sig_type: str, state: str, signal_id=None):
    tag = f"#s{signal_id}" if signal_id is not None else "-"
    log(f"SIGNAL {tag} {symbol} {strategy} {sig_type} -> {state}")


def error(where: str, detail: str):
    log(f"ERROR {where}: {detail}")


class TickSummary:
    """Accumulates per-strategy stats during one scan tick; call .flush() at end.

    One compact line per tick, e.g.:
      TICK str1:100/0 str2:100/0 str3:100/0 str4:100/2 | fetch=803 err=0 sig=2 50.3s
    meaning strategy:scanned/errors per strategy, total fetches, errors, signals, seconds.
    """
    def __init__(self):
        self.t0 = time.time()
        self._per = OrderedDict()
        self.fetches = 0
        self.errors = 0
        self.signals = 0

    def strategy(self, name: str, scanned: int, errors: int):
        self._per[name] = (scanned, errors)
        self.errors += errors

    def fetch(self):
        self.fetches += 1

    def signal(self):
        self.signals += 1

    def flush(self):
        if not self._per:
            return
        parts = " ".join(f"{k}:{v[0]}/{v[1]}" for k, v in self._per.items())
        dur = time.time() - self.t0
        log(f"TICK {parts} | fetch={self.fetches} err={self.errors} "
            f"sig={self.signals} {dur:.1f}s")
