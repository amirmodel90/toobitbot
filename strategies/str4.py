#!/usr/local/bin/python3
"""
Strategy 4 (str4) - 3-Leg ZigZag Breakout (COUNTER-TREND REVERSAL) [LIVE]
Frozen Config (2026-08-30):
- Deviation: 0.8% (0.008)
- Lookback: 200 candles
- Leg length: 5 to 20 candles each
- Volume(L3) < 80% of Volume(L2)
- L3 length > L2 length
- Post-breakout extreme within 2.5*ATR of pivot1 (SELL: max high, BUY: min low)
- Pattern:
  SELL: Leg1 up -> Pivot1(HIGH resistance) -> Leg2 down -> Pivot2(LOW) -> Leg3 up breaks Pivot1
  BUY:  Leg1 down -> Pivot1(LOW support) -> Leg2 up -> Pivot2(HIGH) -> Leg3 down breaks Pivot1
- Trigger (REVERSAL): within TRIGGER_WINDOW(5) candles after breakout,
  first OPPOSITE candle with body >= 0.7*ATR(55)
  -> SELL on UP-breakout (bearish trigger), BUY on DOWN-breakout (bullish trigger)
- SL: 1.0*ATR below/above TRIGGER candle (the reversal candle — PROMOTED from test_str4 on 2026-08-31)
- TP: 2.0R
- COOLDOWN_PER_STRUCTURE: only ONE signal per ZigZag structure (win or loss), then skip until next structure
- Backtest (5m, 100 coins, 90d, SL on trigger): n=299, WR=53.2%, PF=2.29, MaxCL=5, DD@1%=4.9%, OptRisk=4.30%, $100→$110,586
  (supersedes breakout-candle SL: n=271, WR=43.5%, PF=1.55 — same entry/filters, only SL placement differs)
"""
import numpy as np
import pandas as pd
from datetime import datetime, timezone

# ==================== CONFIGURATION ====================
ZIGZAG_DEVIATION = 0.008       # 0.8%
LOOKBACK = 110                 # candles (3-leg ZigZag needs ~60 max; 110 gives margin)
MIN_LEG_LENGTH = 5
MAX_LEG_LENGTH = 20
VOLUME_RATIO_THRESHOLD = 0.80  # L3 vol < 80% of L2 vol
TRIGGER_WINDOW = 5             # candles AFTER breakout to look for reversal trigger
TRIGGER_ATR_MIN = 0.7          # trigger candle body must be >= 0.7 * ATR(55)
ATR_PERIOD = 55                # ATR period for breakout candle size filter
BREAKOUT_EXT_ATR_MAX = 2.5     # (user 2026-09-12, replaces body<2ATR filter): SELL —
                               # highest high from breakout candle through now must not
                               # exceed pivot1 + 2.5*ATR; BUY — lowest low must not fall
                               # below pivot1 - 2.5*ATR. Don't chase run-away breaks.
SL_ATR_MULT = 1.3             # SL distance = 1.3 * ATR on breakout candle
TP_RR = 2.0                    # take-profit risk:reward
TRIG_CONFIRM_WINDOW = 0        # IDEA-1 ported from str3: trigger close must exceed
                               # the N-candle max-high (BUY) / min-low (SELL) before it.
                               # 0 = off. Synced from cfg by evaluate_strategy sweeps.
# Failed-breakout literature gates (user 2026-09-14, internet-research round):
#  TRIG_RECLAIM: trigger close must be BACK INSIDE pivot1 (SELL: close < pivot1,
#    BUY: close > pivot1) — "trade the reclaim, not the break" (SFP/stop-hunt rules).
#  TRIG_VOL_GT_BO: trigger candle volume must EXCEED the breakout candle volume —
#    "fading volume on the push, pickup on the reclaim".
#  cfg key: sl_at_sweep (handled in compute_sl_for): SL beyond the post-breakout
#    sweep extreme instead of the trigger candle alone.
TRIG_RECLAIM = 0
TRIG_VOL_GT_BO = 0
#  MIN_STRETCH_ATR: trigger close must be at least k*ATR(55) away from MA21
#  (over-extension = higher snapback value; str3's min_ma_dist inverted for str4 —
#   research 09-14: counter-trend edge dies in extended trends, thrives at extremes).
#  PINNED 0.45 (user 2026-09-14): engine n=59 PF 2.14 +22.3R MaxCL3 DD@1%3.0
#  OptR6.9->$392 (ledger a29f60074df3). PF>2 plateau 0.4-0.5, 5m-ONLY (15m PF 0.66,
#  1h dead — do not run this config on other timeframes). FIXED.
MIN_STRETCH_ATR = 0.45
COOLDOWN_PER_STRUCTURE = True  # one signal per ZigZag structure (skip until next)
# NOTE: Do NOT change COOLDOWN_PER_STRUCTURE or BREAKOUT_EXT_ATR_MAX without explicit user approval.
# ========================================================


def compute_zigzag(cds, deviation=ZIGZAG_DEVIATION):
    n = len(cds)
    if n < 10: return []
    pivots = []
    last_high_idx = 0; last_low_idx = 0
    last_high_val = cds[0]["high"]; last_low_val = cds[0]["low"]
    trend = 0
    for i in range(1, n):
        h = cds[i]["high"]; l = cds[i]["low"]
        if trend == 0:
            if h > last_high_val * (1 + deviation):
                trend = 1; last_high_idx = i; last_high_val = h
                pivots.append({"index": 0, "price": last_low_val, "type": "LOW"})
            elif l < last_low_val * (1 - deviation):
                trend = -1; last_low_idx = i; last_low_val = l
                pivots.append({"index": 0, "price": last_high_val, "type": "HIGH"})
        elif trend == 1:
            if h >= last_high_val:
                last_high_idx = i; last_high_val = h
            elif l <= last_high_val * (1 - deviation):
                pivots.append({"index": last_high_idx, "price": last_high_val, "type": "HIGH"})
                trend = -1; last_low_idx = i; last_low_val = l
        elif trend == -1:
            if l <= last_low_val:
                last_low_idx = i; last_low_val = l
            elif h >= last_low_val * (1 + deviation):
                pivots.append({"index": last_low_idx, "price": last_low_val, "type": "LOW"})
                trend = 1; last_high_idx = i; last_high_val = h
    return pivots


def compute_atr(cds, period=ATR_PERIOD):
    """Compute ATR(period) aligned with candle indices."""
    n = len(cds)
    tr = [0.0] * n
    for i in range(1, n):
        tr[i] = max(cds[i]["high"] - cds[i]["low"],
                    abs(cds[i]["high"] - cds[i - 1]["close"]),
                    abs(cds[i]["low"] - cds[i - 1]["close"]))
    atr = [None] * n
    if n > period:
        atr[period] = sum(tr[1:period + 1]) / period
        for i in range(period + 1, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def compute_indicators(cds, adx_len=21, adx_smooth=21):
    n = len(cds)
    closes = [c["close"] for c in cds]
    ma21 = [None] * n
    if n >= 21:
        for i in range(20, n):
            ma21[i] = sum(closes[i-20:i+1]) / 21.0
    atr55 = compute_atr(cds, ATR_PERIOD)
    return None, ma21, atr55


def is_valid_trigger(cds, trigger_idx, sig_type):
    """Check trigger candle direction only."""
    if trigger_idx < 1:
        return False
    curr = cds[trigger_idx]
    if sig_type == "BUY":
        return curr["close"] > curr["open"]
    else:
        return curr["close"] < curr["open"]


# Module-level cache: patterns that already produced a LOSING trade are skipped
_broken_patterns = set()


# ── Alternative entry triggers (user experiment 2026-09-12) ──────────────────
# TRIGGER_MODE selects which reversal-trigger matcher the post-breakout window
# uses. "body" = current live rule. cfg-synced by evaluate_strategy sweeps.
TRIGGER_MODE = "body"
# Body-trigger extras (user 2026-09-12 round 2):
#  TRIG_CLOSE_BEHIND: trigger close must sit BEHIND the previous candle entirely
#    (SELL: close < prev low | BUY: close > prev high). 0=off, 1=on.
#  TRIG_VOL_MULT / TRIG_VOL_WINDOW: trigger volume must exceed
#    mult × SMA(volume, window) — confirmation by high volume. None=off.
TRIG_CLOSE_BEHIND = 0
TRIG_VOL_MULT = None
TRIG_VOL_WINDOW = 20


def _vol_ok(cds, t):
    if TRIG_VOL_MULT is None:
        return True
    lo = max(0, t - TRIG_VOL_WINDOW)
    vols = [c["volume"] for c in cds[lo:t]]  # previous candles, no lookahead
    if not vols:
        return False
    return cds[t]["volume"] > TRIG_VOL_MULT * (sum(vols) / len(vols))


def _cand_stats(c):
    body = abs(c["close"] - c["open"])
    rng = c["high"] - c["low"]
    up_w = c["high"] - max(c["close"], c["open"])
    lo_w = min(c["close"], c["open"]) - c["low"]
    return body, rng, up_w, lo_w


def _is_star(c, atr, sell):
    """Shooting star (SELL) / inverted-hammer (BUY): big rejection wick, small body."""
    body, rng, up_w, lo_w = _cand_stats(c)
    if sell:
        return up_w >= 2.0 * body and up_w >= 0.7 * atr and c["close"] <= c["open"]
    return lo_w >= 2.0 * body and lo_w >= 0.7 * atr and c["close"] >= c["open"]


def _is_pinbar(c, atr, sell):
    """Pin bar: wick >= 2/3 of range, body <= 1/5 of range, range >= 0.7 ATR."""
    body, rng, up_w, lo_w = _cand_stats(c)
    if rng < 0.7 * atr or rng <= 0:
        return False
    if sell:
        return up_w >= 0.66 * rng and body <= 0.2 * rng and c["close"] <= c["open"]
    return lo_w >= 0.66 * rng and body <= 0.2 * rng and c["close"] >= c["open"]


def match_trigger(cds, t, sig_type, atr_arr, mode, lo_idx):
    """Return True if candle t is a valid entry trigger under `mode`.
    `mode` may be a comma-separated OR of modes (e.g. "body,engulf").
    SELL signal = bearish reversal after an UP-breakout; BUY mirrors it.
    Only past candles are used (no lookahead)."""
    if "," in mode:
        return any(match_trigger(cds, t, sig_type, atr_arr, m.strip(), lo_idx)
                   for m in mode.split(","))
    sell = (sig_type == "SELL")
    c = cds[t]
    body, rng, up_w, lo_w = _cand_stats(c)
    atr_t = atr_arr[t] if t < len(atr_arr) else None
    if atr_t is None or atr_t <= 0:
        return False
    if mode == "body":
        if sell:
            ok = c["close"] < c["open"] and body >= TRIGGER_ATR_MIN * atr_t
        else:
            ok = c["close"] > c["open"] and body >= TRIGGER_ATR_MIN * atr_t
        if not ok:
            return False
        # close-behind-prev-candle: SELL close below prev LOW | BUY close above prev HIGH
        # (prev may be the breakout candle itself — it is a real closed candle)
        if TRIG_CLOSE_BEHIND:
            p = cds[t - 1]
            if sell and c["close"] >= p["low"]:
                return False
            if (not sell) and c["close"] <= p["high"]:
                return False
        # volume confirmation: trigger candle volume > mult × avg(prev window)
        if not _vol_ok(cds, t):
            return False
        return True
    if mode == "star":
        return _is_star(c, atr_t, sell)
    if mode == "pinbar":
        return _is_pinbar(c, atr_t, sell)
    if mode == "engulf":
        p = cds[t - 1]
        pb = abs(p["close"] - p["open"])
        if sell:  # bearish body engulfing a prior bullish body
            return (c["close"] < c["open"] and p["close"] > p["open"]
                    and c["open"] >= p["close"] and c["close"] <= p["open"]
                    and body >= max(0.5 * atr_t, 1.0 * pb))
        return (c["close"] > c["open"] and p["close"] < p["open"]
                and c["open"] <= p["close"] and c["close"] >= p["open"]
                and body >= max(0.5 * atr_t, 1.0 * pb))
    if mode == "3candle":
        a, b = cds[t - 2], cds[t - 1]
        if sell:
            return (a["close"] < a["open"] and b["close"] < b["open"]
                    and c["close"] < c["open"]
                    and c["close"] < b["close"] < a["close"]
                    and a["open"] - c["close"] >= 0.7 * atr_t)
        return (a["close"] > a["open"] and b["close"] > b["open"]
                and c["close"] > c["open"]
                and c["close"] > b["close"] > a["close"]
                and c["close"] - a["open"] >= 0.7 * atr_t)
    if mode == "hammer_break":
        # a rejection candle j (star) formed after the breakout, and candle t is
        # the FIRST close beyond its extreme — the break itself is the trigger.
        for j in range(max(lo_idx, t - 3), t):
            cj, cn = cds[j], cds[t]
            atr_j = atr_arr[j] if j < len(atr_arr) else None
            if not atr_j or atr_j <= 0:
                continue
            if _is_star(cj, atr_j, sell):
                if sell:
                    if cn["close"] < cj["low"] and cds[t - 1]["close"] >= cj["low"]:
                        return True
                else:
                    if cn["close"] > cj["high"] and cds[t - 1]["close"] <= cj["high"]:
                        return True
        return False
    raise ValueError(f"unknown trigger mode: {mode}")

# Last detected breakout candle index (set by check_signal, read by compute_sl_for)
_last_breakout_idx = None
# Last detected trigger candle index (set by detect, read by scanner for entry timing)
_last_trigger_idx = None
# SL computed for the LAST detected signal (set by detect, read by scanner —
# scanner must not re-derive SL from a different idx than the strategy used)
_last_pattern_key = None
_last_sl = None
# post-breakout sweep extreme captured at trigger time (for SL-at-sweep experiments)
_last_sweep_ext = None


def reset_caches():
    """Clear per-run caches (call once per symbol)."""
    _broken_patterns.clear()
    global _last_breakout_idx, _last_trigger_idx, _last_sl, _last_pattern_key, _last_sweep_ext
    _last_breakout_idx = None
    _last_trigger_idx = None
    _last_sl = None
    _last_pattern_key = None
    _last_sweep_ext = None


def detect(cds, idx, cfg=None, ind=None, zigzag_pivots=None):
    """Unified signal entry point (scanner-compatible).

    Returns "BUY" / "SELL" / None — never a tuple (scanner expects a pure
    signal type, and uses `idx` directly as the signal candle).
    `zigzag_pivots` can be precomputed once per symbol for speed.

    ENTRY TIMING: signal is detected on candle `idx` (the reversal trigger),
    but the actual ENTRY is taken on the NEXT candle (`idx+1`) after it closes.
    We return idx+1 so the scanner enters on the close of the post-trigger candle.
    """
    cfg = cfg or {}
    # LIVE-PARITY (09-15 cfg-coverage audit): mirror the engine's cfg->global sync
    # for knobs this module reads as module globals. Current defaults already
    # equal cfg values, so behavior is unchanged — this drift-proofing ensures a
    # future cfg-only change can never diverge between backtest and live scanner.
    global TRIGGER_WINDOW, BREAKOUT_EXT_ATR_MAX, SL_ATR_MULT, MIN_STRETCH_ATR
    if cfg.get("trigger_window") is not None: TRIGGER_WINDOW = int(cfg["trigger_window"])
    if cfg.get("breakout_ext_atr_max") is not None: BREAKOUT_EXT_ATR_MAX = float(cfg["breakout_ext_atr_max"])
    if cfg.get("sl_atr_mult") is not None: SL_ATR_MULT = float(cfg["sl_atr_mult"])
    if cfg.get("min_stretch_atr") is not None: MIN_STRETCH_ATR = float(cfg["min_stretch_atr"])
    tf = cfg.get("timeframe", "5m")
    atr_arr = ind[2] if isinstance(ind, tuple) and len(ind) > 2 and ind[2] is not None \
        else compute_atr(cds, ATR_PERIOD)
    sig = check_signal(cds, idx, tf, atr_arr=atr_arr, zigzag_pivots=zigzag_pivots)
    if sig is None:
        return None
    # mark structure as used (cooldown until next fresh structure)
    pattern_key = sig[2]
    _broken_patterns.add(pattern_key)
    global _last_pattern_key
    _last_pattern_key = pattern_key
    # signal candle = idx; TRIGGER candle = sig[1]; ENTRY = trigger_idx + 1 (next candle)
    global _last_trigger_idx, _last_sl
    _last_trigger_idx = sig[1]
    # SL for THIS signal as computed during detection (trigger candle ± SL_ATR_MULT*ATR).
    # The scanner reads _last_sl so it never has to re-derive SL from a different idx —
    # mirrors the backtest exactly (same candle, same ATR value).
    _sig_type = sig[0]
    _t_atr = atr_arr[sig[1]] if sig[1] < len(atr_arr) else None
    if _t_atr and _t_atr > 0:
        if _sig_type == "BUY":
            _last_sl = cds[sig[1]]["low"] - SL_ATR_MULT * _t_atr
            if _last_sl >= cds[sig[1]]["close"]:
                _last_sl = None
        else:
            _last_sl = cds[sig[1]]["high"] + SL_ATR_MULT * _t_atr
            if _last_sl <= cds[sig[1]]["close"]:
                _last_sl = None
    else:
        _last_sl = None
    return sig[0]  # sig_type only


def check_signal(cds, idx, timeframe="5m", atr_arr=None, zigzag_pivots=None):
    global _last_breakout_idx, _last_sweep_ext
    if idx < LOOKBACK or idx >= len(cds):
        return None

    if atr_arr is None:
        atr_arr = compute_atr(cds, ATR_PERIOD)

    # Use precomputed pivots if provided (speed), else compute locally
    if zigzag_pivots is not None:
        pivots = zigzag_pivots
    else:
        window_cds = cds[idx-LOOKBACK : idx+1]
        pivots = compute_zigzag(window_cds)
    if len(pivots) < 3:
        return None

    if zigzag_pivots is None:
        global_pivots = [{"index": p["index"] + (idx - LOOKBACK), "price": p["price"], "type": p["type"]} for p in pivots]
    else:
        global_pivots = pivots  # already in global coords
    if len(global_pivots) < 3:
        return None

    p2 = global_pivots[-1]
    p1 = global_pivots[-2]
    p0 = global_pivots[-3]

    # Unique pattern key (pivot indices + types define the structure)
    pattern_key = (p0["index"], p0["type"], p1["index"], p1["type"], p2["index"], p2["type"])

    # If this structure already produced a LOSS, skip it entirely
    if pattern_key in _broken_patterns:
        return None

    l1_len = p1["index"] - p0["index"]
    l2_len = p2["index"] - p1["index"]
    if not (MIN_LEG_LENGTH <= l1_len <= MAX_LEG_LENGTH and
            MIN_LEG_LENGTH <= l2_len <= MAX_LEG_LENGTH):
        return None

    l2_vol = sum(c["volume"] for c in cds[p1["index"]:p2["index"] + 1])
    if l2_vol <= 0:
        return None

    # Ensure pivot1 was NOT broken during leg2
    for k in range(p1["index"] + 1, p2["index"] + 1):
        if p0["type"] == "LOW" and p1["type"] == "HIGH" and cds[k]["close"] > p1["price"]:
            return None
        if p0["type"] == "HIGH" and p1["type"] == "LOW" and cds[k]["close"] < p1["price"]:
            return None

    # ---------- SELL pattern: p0 LOW, p1 HIGH (resistance), p2 LOW ----------
    if p0["type"] == "LOW" and p1["type"] == "HIGH" and p2["type"] == "LOW":
        pivot1_price = p1["price"]
        breakout_idx = None
        for k in range(p2["index"] + 1, idx + 1):
            if cds[k]["close"] > pivot1_price:
                breakout_idx = k
                break
        if breakout_idx is None:
            return None

        l3_len = breakout_idx - p2["index"]
        if not (MIN_LEG_LENGTH <= l3_len <= MAX_LEG_LENGTH):
            return None
        if l3_len <= l2_len:
            return None

        l3_vol = sum(c["volume"] for c in cds[p2["index"]:breakout_idx + 1])
        if l3_vol >= VOLUME_RATIO_THRESHOLD * l2_vol:
            return None

        # (user 2026-09-12) Extreme-overshoot filter REPLACES the old body<2.0*ATR
        # filter: SELL (up-breakout) — the highest high from the breakout candle
        # through the scan candle must not exceed pivot1 + BREAKOUT_EXT_ATR_MAX * ATR(55).
        atr_b = atr_arr[breakout_idx] if breakout_idx < len(atr_arr) else None
        if atr_b is None or atr_b <= 0:
            return None
        post_high = max(c["high"] for c in cds[breakout_idx:idx + 1])
        if post_high > pivot1_price + BREAKOUT_EXT_ATR_MAX * atr_b:
            return None

        # SL = SL_ATR_MULT * ATR(55) below TRIGGER candle (not breakout candle)
        # Trigger search is BOUNDED by idx (user 2026-09-12): the signal may only fire
        # once the trigger candle has CLOSED — entry = that candle's close. (The old
        # len(cds) bound let the scan match a future trigger = lookahead, entering
        # 1-4 candles BEFORE the reversal candle.)
        for t in range(breakout_idx + 1, min(breakout_idx + 1 + TRIGGER_WINDOW, idx + 1)):
            c = cds[t]
            atr_t = atr_arr[t] if t < len(atr_arr) else None
            if atr_t is None or atr_t <= 0:
                continue
            if match_trigger(cds, t, "SELL", atr_arr, TRIGGER_MODE, breakout_idx + 1):
                # SFP/stop-hunt gates (2026-09-14 research round):
                if TRIG_RECLAIM and c["close"] >= pivot1_price:
                    continue   # reclaim required: close back INSIDE pivot1
                if TRIG_VOL_GT_BO and c["volume"] <= cds[breakout_idx]["volume"]:
                    continue   # reclaim volume must exceed breakout volume
                if MIN_STRETCH_ATR > 0:
                    _cl = [x["close"] for x in cds[max(0, t - 20):t + 1]]
                    if len(_cl) >= 21:
                        _ma = sum(_cl) / 21.0
                        if (c["close"] - _ma) < MIN_STRETCH_ATR * atr_t:
                            continue   # SELL needs price stretched ABOVE MA21
                # IDEA-1 (ported from str3): trigger close must break the LOW of the
                # previous TRIG_CONFIRM_WINDOW candles — real reversal, not noise.
                tw = TRIG_CONFIRM_WINDOW
                if tw and tw > 0:
                    prev_lows = [c["low"] for c in cds[max(0, t - tw):t]]
                    if len(prev_lows) < tw or c["close"] >= min(prev_lows):
                        continue
                _last_sweep_ext = max(cc["high"] for cc in cds[breakout_idx:t + 1])
                sl = c["low"] - SL_ATR_MULT * atr_t
                entry = c["close"]
                if entry <= sl:
                    continue
                risk = abs(entry - sl)
                if risk <= entry * 1e-4:
                    continue
                _last_breakout_idx = breakout_idx
                return ("SELL", t, pattern_key)

        return None

    # ---------- BUY pattern: p0 HIGH, p1 LOW (support), p2 HIGH ----------
    if p0["type"] == "HIGH" and p1["type"] == "LOW" and p2["type"] == "HIGH":
        pivot1_price = p1["price"]
        breakout_idx = None
        for k in range(p2["index"] + 1, idx + 1):
            if cds[k]["close"] < pivot1_price:
                breakout_idx = k
                break
        if breakout_idx is None:
            return None

        l3_len = breakout_idx - p2["index"]
        if not (MIN_LEG_LENGTH <= l3_len <= MAX_LEG_LENGTH):
            return None
        if l3_len <= l2_len:
            return None

        l3_vol = sum(c["volume"] for c in cds[p2["index"]:breakout_idx + 1])
        if l3_vol >= VOLUME_RATIO_THRESHOLD * l2_vol:
            return None

        # (user 2026-09-12) Extreme-overshoot filter (mirror of SELL branch):
        # BUY (down-breakout) — the lowest low from the breakout candle through the
        # scan candle must not fall below pivot1 - BREAKOUT_EXT_ATR_MAX * ATR(55).
        atr_b = atr_arr[breakout_idx] if breakout_idx < len(atr_arr) else None
        if atr_b is None or atr_b <= 0:
            return None
        post_low = min(c["low"] for c in cds[breakout_idx:idx + 1])
        if post_low < pivot1_price - BREAKOUT_EXT_ATR_MAX * atr_b:
            return None

        # SL = SL_ATR_MULT * ATR(55) above TRIGGER candle (not breakout candle)
        # Trigger search bounded by idx — same no-lookahead rule as SELL branch.
        for t in range(breakout_idx + 1, min(breakout_idx + 1 + TRIGGER_WINDOW, idx + 1)):
            c = cds[t]
            atr_t = atr_arr[t] if t < len(atr_arr) else None
            if atr_t is None or atr_t <= 0:
                continue
            if match_trigger(cds, t, "BUY", atr_arr, TRIGGER_MODE, breakout_idx + 1):
                # SFP/stop-hunt gates (2026-09-14 research round, mirrored):
                if TRIG_RECLAIM and c["close"] <= pivot1_price:
                    continue
                if TRIG_VOL_GT_BO and c["volume"] <= cds[breakout_idx]["volume"]:
                    continue
                if MIN_STRETCH_ATR > 0:
                    _cl = [x["close"] for x in cds[max(0, t - 20):t + 1]]
                    if len(_cl) >= 21:
                        _ma = sum(_cl) / 21.0
                        if (_ma - c["close"]) < MIN_STRETCH_ATR * atr_t:
                            continue   # BUY needs price stretched BELOW MA21
                # IDEA-1 (ported from str3): trigger close must break the HIGH of
                # the previous TRIG_CONFIRM_WINDOW candles — real reversal, not noise.
                tw = TRIG_CONFIRM_WINDOW
                if tw and tw > 0:
                    prev_highs = [c["high"] for c in cds[max(0, t - tw):t]]
                    if len(prev_highs) < tw or c["close"] <= max(prev_highs):
                        continue
                _last_sweep_ext = min(cc["low"] for cc in cds[breakout_idx:t + 1])
                sl = c["high"] + SL_ATR_MULT * atr_t
                entry = c["close"]
                if entry >= sl:
                    continue
                risk = abs(sl - entry)
                if risk <= entry * 1e-4:
                    continue
                _last_breakout_idx = breakout_idx
                return ("BUY", t, pattern_key)

        return None

    return None


def compute_sl_for(cds, idx, sig_type, cfg, atr_arr=None):
    """Strategy-specific SL: place N*ATR below/above the TRIGGER candle.

    Called by evaluate_strategy / scanner when present; falls back to shared
    compute_sl() when absent. Returns (sl_price, trigger_idx).
    `idx` is the ENTRY candle (= trigger_idx + 1); trigger is idx-1.
    The trigger index is captured by detect() into _last_trigger_idx.
    """
    global _last_trigger_idx
    t_idx = _last_trigger_idx if _last_trigger_idx is not None else (idx - 1)
    if t_idx < 0 or t_idx >= len(cds):
        return None, None
    if atr_arr is None:
        atr_arr = compute_atr(cds, ATR_PERIOD)
    atr_t = atr_arr[t_idx] if t_idx < len(atr_arr) else None
    if atr_t is None or atr_t <= 0:
        return None, None
    if sig_type == "BUY":
        anchor_lo = cds[t_idx]["low"]
        if cfg.get("sl_at_sweep") and _last_sweep_ext is not None:
            anchor_lo = min(anchor_lo, _last_sweep_ext)  # SFP: stop below sweep wick
        sl = anchor_lo - SL_ATR_MULT * atr_t
        # Reject if SL ends up above entry (invalid structure)
        if sl >= cds[idx]["close"]:
            return None, t_idx
    else:
        anchor_hi = cds[t_idx]["high"]
        if cfg.get("sl_at_sweep") and _last_sweep_ext is not None:
            anchor_hi = max(anchor_hi, _last_sweep_ext)  # SFP: stop above sweep wick
        sl = anchor_hi + SL_ATR_MULT * atr_t
        # Reject if SL ends up below entry (invalid structure)
        if sl <= cds[idx]["close"]:
            return None, t_idx
    return sl, t_idx


def get_config():
    return {
        "zigzag_deviation": ZIGZAG_DEVIATION,
        "lookback": LOOKBACK,
        "min_leg_length": MIN_LEG_LENGTH,
        "max_leg_length": MAX_LEG_LENGTH,
        "volume_ratio_threshold": VOLUME_RATIO_THRESHOLD,
        "trigger_window": TRIGGER_WINDOW,
        "atr_period": ATR_PERIOD,
        "breakout_ext_atr_max": BREAKOUT_EXT_ATR_MAX,
        "sl_atr_mult": SL_ATR_MULT,
        "tp_rr": TP_RR,
        "sl_mode": "atr",  # use ATR-based SL on breakout candle
        "risk_pct": 0.065,  # 6.5% of equity per trade (user-set 2026-09-14; was 4.0%)
        # str3-inspired fee-drag filter (user-approved 2026-09-12 — sweep winner
        # md=0.8: n=55 PF 1.23 +5.4R under the 3-fill 0.045% fee model; ledger d829567a3303).
        # SL distance must be >= 0.8% of entry or the signal is dropped. FIXED — do not
        # change without explicit user approval.
        "min_dist_pct": 0.8,
        # ATR-knob tuning (user 2026-09-12, ledger 50b1269d764f): SL = 1.3×ATR(55)
        # behind the trigger — widens SL so fewer structures trip the 0.8% floor AND
        # gives price room to breathe: n=87 WR 47.1 PF 1.44 ΣR+15.1 MaxCL6 OptR3.7→$164.
        "sl_atr_mult": 1.3,
        # MA21 over-extension gate (user 2026-09-14, ledger a29f60074df3): trigger close
        # ≥ 0.45×ATR(55) away from MA21 — PF 2.14 n=59 +22.3R $392 @6.9% (5m ONLY).
        # Fixed — do not change without user approval.
        "min_stretch_atr": MIN_STRETCH_ATR,
    }


def simulate_exit(cds, idx, stype, entry, sl, tp, ma21):
    """FROZEN EXIT v2 (2026-09-01, user-approved): 50% partial exit on MA-cross.

    BUY:  candle opens ABOVE MA21 and closes BELOW it → close 50% once.
    SELL: candle opens BELOW MA21 and closes ABOVE it → close 50% once.
    Remaining 50% runs to TP/SL. Only str4 uses this — str1/str2/str3 stay full-close
    (tested: partial exit only improved str4 and str2; hurt str1/str3).

    2026-09-07 FT/live parity fix: within-candle resolution changed TP-first → SL-first
    (freqtrade checks STOP_LOSS before ROI on same-candle ties) + SL gap-fill at candle
    OPEN when the open is already beyond the stop. MA-cross stays last.
    States: tp_hit / sl_hit / ma_half_exit / signal.
    Returns (final_state, exit_price, exit_idx, half_done, events)
    """
    events = []
    half_done = False
    for i in range(idx + 1, len(cds)):
        c = cds[i]
        ma = ma21[i] if ma21 is not None and i < len(ma21) else None

        if stype == "BUY":
            hit_tp = c["high"] >= tp
            hit_sl = c["low"] <= sl
        else:
            hit_tp = c["low"] <= tp
            hit_sl = c["high"] >= sl
        # 1) SL first (freqtrade parity — stoploss outranks ROI on ties)
        if hit_sl:
            fill = sl
            if stype == "SELL" and sl < c["low"]:
                fill = c["open"]          # short SL gapped below the candle low
            elif stype == "BUY" and sl > c["high"]:
                fill = c["open"]          # long SL gapped above the candle high
            events.append({"type": "sl_hit", "price": fill, "index": i})
            return "sl_hit", fill, i, half_done, events
        # 2) TP second
        if hit_tp:
            events.append({"type": "tp_hit", "price": tp, "index": i})
            # final_state = tp_hit even after a partial MA exit — the position IS
            # closed at TP (the ma_half_exit leg is recorded in events for the blend)
            return "tp_hit", tp, i, half_done, events
        # 3) MA-cross 50% partial exit (once per position)
        if not half_done and ma is not None:
            if (stype == "BUY" and c["open"] > ma and c["close"] < ma) or \
               (stype == "SELL" and c["open"] < ma and c["close"] > ma):
                half_done = True
                events.append({"type": "ma_half_exit", "price": c["close"], "index": i})
    return "signal", cds[-1]["close"], len(cds) - 1, half_done, events
