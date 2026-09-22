#!/usr/local/bin/python3
"""
Strategy 3 (str3): Volume & Price Extremum Reversal
Frozen Config (2026-08-28):
- Structure: Extremum Reversal, Full-exit
- Entry: Volume spike, volume calm, candle-pattern quality (ideas)
- Risk: FIXED 2.90% (optimal from DD<20%, requires user approval to change)
"""
from datetime import datetime, timezone


def compute_indicators(cds, adx_len=21, adx_smooth=21):
    """Compute ADX (adx_len, adx_smooth) and MA21 arrays aligned with candle indices."""
    n = len(cds)
    closes = [c["close"] for c in cds]
    highs = [c["high"] for c in cds]
    lows = [c["low"] for c in cds]

    # ─── ADX (length=21, smoothing=21) ───
    tr = [0.0] * n
    pdm = [0.0] * n  # +DM
    mdm = [0.0] * n  # -DM
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]))
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        mdm[i] = dn if (dn > up and dn > 0) else 0.0

    p = adx_len  # ADX Length = 21
    tr_rma = [0.0] * n
    pdm_rma = [0.0] * n
    mdm_rma = [0.0] * n
    if n > p:
        tr_rma[p] = sum(tr[1:p + 1]) / p
        pdm_rma[p] = sum(pdm[1:p + 1]) / p
        mdm_rma[p] = sum(mdm[1:p + 1]) / p
        for i in range(p + 1, n):
            tr_rma[i] = (tr_rma[i - 1] * (p - 1) + tr[i]) / p
            pdm_rma[i] = (pdm_rma[i - 1] * (p - 1) + pdm[i]) / p
            mdm_rma[i] = (mdm_rma[i - 1] * (p - 1) + mdm[i]) / p

    dx = [0.0] * n
    for i in range(n):
        denom = pdm_rma[i] + mdm_rma[i]
        if denom > 0:
            dx[i] = 100.0 * abs(pdm_rma[i] - mdm_rma[i]) / denom

    s = adx_smooth  # ADX Smoothing = 21
    adx = [None] * n
    if n >= p + s:
        adx[p + s - 1] = sum(dx[p:p + s]) / s
        for i in range(p + s, n):
            adx[i] = (adx[i - 1] * (s - 1) + dx[i]) / s

    # ─── MA21 (for exit) ───
    ma21 = [None] * n
    if n >= 21:
        for i in range(20, n):
            window = closes[i - 20:i + 1]
            ma21[i] = sum(window) / 21.0

    return adx, ma21


def get_config():
    """Return strategy configuration (filters, thresholds) used by backtester & scanner."""
    return {
        # ── FIXED (do not change without user approval) ──
        "risk_pct": 0.065,  # 6.5% of equity per trade (user-set 2026-09-14; was 3.0%)
        "tp_rr": 1.5,       # Full-position TP
        # ── Entry Logic (adaptive) ──
        "sl_mode": "3candle",
        "volume_spike_mult": 1.75,
        "lookback": 10,
        "body_min": 0.3,   # reject wick-only X (user-approved 2026-08-31)
        # ── NEW FILTERS (user-approved 2026-09-07 — sweep winner: PF 1.56 net, $164) ──
        "max_vol5_ratio": 1.2,   # avg vol of 5 candles before x must be < 1.2× avg50 (volume building, not overheated)
        "min_dist_pct": 0.4,     # SL distance (risk) must be >= 0.4% of entry (fee drag control)
        "trig_confirm_window": 3, # trigger close must exceed N-candle high (BUY) / low (SELL) — idea-1 winner (PF 2.05, $251)
        # ── Indicators ──
        "adx_len": 21,
        "adx_smooth": 21,
        "min_ma_dist": 1.5,     # user-approved 2026-09-01 (ATR mode)
        "ma_dist_mode": "atr",  # 'atr' = min_ma_dist is ×ATR(55); 'pct' = % of MA (legacy)
        "ma_dist_period": 21,
        # ── Idea filters ──
        "active_ideas": {85, 74, 89, 86, 83},
        "idea_params": {},
    }


# ─── Exit params (kept for interface compatibility) ─────────────────────
HALF_TP_RR = 1.5
PART_FRAC = 0.99


def _atr50(cds, i, period=50):
    if i < period:
        return None
    s = 0.0
    for j in range(i - period + 1, i + 1):
        h, l = cds[j]["high"], cds[j]["low"]
        pc = cds[j - 1]["close"] if j > 0 else (h + l) / 2
        s += max(h - l, abs(h - pc), abs(l - pc))
    return s / period


def _atr(cds, i, period):
    """Generic ATR wrapper (any period) — used by ma_dist_mode='atr' (ATR55)."""
    return _atr50(cds, i, period=period)


def _ideas_pass(sig, cds, idx, cfg=None, ma21=None):
    """Quality filters for str3. T=cds[idx] trigger, X=cds[idx-1] extremum,
    M=cds[idx-2]. buy=True for BUY setup."""
    cfg = cfg or {}
    active_ideas = cfg.get("active_ideas", set())
    params = cfg.get("idea_params", {})
    if not active_ideas:
        return True
    T, X, M = cds[idx], cds[idx-1], cds[idx-2] if idx >= 2 else None
    buy = (sig == "BUY")
    atr = _atr50(cds, idx - 1)
    if not atr or atr <= 0:
        return False
    xr = max(X["high"] - X["low"], 1e-12)
    trng = max(T["high"] - T["low"], 1e-12)
    m_rng = max(M["high"] - M["low"], 1e-12) if M else 0
    xmid = (X["high"] + X["low"]) / 2
    tvol, xvol, mvol = T["volume"], X["volume"], M["volume"] if M else 0
    win50 = cds[max(0, idx - 51):idx - 1]
    avg50 = sum(c["volume"] for c in win50) / len(win50) if win50 else 0
    if avg50 <= 0:
        return False
    p3 = cds[max(0, idx - 4):idx - 1]
    avg3 = sum(c["volume"] for c in p3) / len(p3) if p3 else 0
    for n in sorted(active_ideas):
        P = params.get(n, ())
        ok = True
        # ── A) volume ──
        if n == 15:  ok = tvol <= (P[0] if P else 0.7) * xvol
        elif n == 16: ok = False  # reserved (18 handled below)
        elif n == 17: ok = False
        elif n == 18:
            lo = (P[0] if P else 1.1); hi = (P[1] if len(P) > 1 else 8.0)
            ok = lo <= (xvol / tvol if tvol > 0 else 999) <= hi
        elif n == 57: ok = bool(p3) and tvol < avg3
        elif n == 58:
            p30 = cds[max(0, idx - 31):idx - 1]
            ok = bool(p30) and xvol >= max(c["volume"] for c in p30)
        elif n == 59: ok = mvol < tvol
        elif n == 60: ok = mvol > 0 and xvol / mvol >= (P[0] if P else 1.5)
        elif n == 61: ok = tvol >= (P[0] if P else 0.3) * xvol
        elif n == 62:
            import statistics as _st
            try:
                cv = _st.pstdev([c["volume"] for c in win50]) / avg50
                ok = cv <= (P[0] if P else 1.2)
            except Exception:
                ok = False
        elif n == 63: ok = xvol >= (P[0] if P else 2.0) * mvol
        elif n == 64:
            if idx >= 288:
                yv = cds[idx - 288]["volume"]
                ok = tvol >= (P[0] if P else 0.8) * yv if yv > 0 else False
            else: ok = False
        elif n == 65:
            s3 = sum(c["volume"] for c in cds[max(0, idx - 2):idx + 1])
            ok = s3 >= (P[0] if P else 3.0) * avg50
        elif n == 66:
            s = 0.0
            for j in range(max(1, idx - 2), idx + 1):
                s += cds[j]["volume"] if cds[j]["close"] >= cds[j]["open"] else -cds[j]["volume"]
            ok = (s > 0) if buy else (s < 0)
        # ── B) ATR / volatility regime ──
        elif n == 67:
            atc = atr / T["close"] if T["close"] > 0 else 0
            ok = (P[0] if P else 0.003) <= atc <= (P[1] if len(P) > 1 else 0.02)
        elif n == 68:
            a20 = _atr50(cds, max(0, idx - 20))
            ok = a20 is not None and atr < a20
        elif n == 69: ok = xr >= (P[0] if P else 1.0) * atr
        elif n == 70: ok = m_rng <= (P[0] if P else 0.7) * atr
        elif n == 71: ok = trng >= m_rng
        elif n == 72: ok = abs(X["close"] - X["open"]) >= (P[0] if P else 0.6) * xr
        elif n == 73:
            wick = (min(X["close"], X["open"]) - X["low"]) if buy else (X["high"] - max(X["close"], X["open"]))
            ok = wick <= (P[0] if P else 0.2) * xr
        elif n == 74:
            total_move = xr + m_rng + trng
            ok = total_move >= (P[0] if P else 2.5) * atr
        elif n == 75:
            h12 = cds[max(0, idx - 11):idx + 1]
            ok = bool(h12) and ((T["high"] >= max(c["high"] for c in h12)) if buy
                                else (T["low"] <= min(c["low"] for c in h12)))
        elif n == 76:
            p50l = cds[max(0, idx - 49):idx + 1]
            if not p50l:
                ok = False
            else:
                d = T["close"] - min(c["low"] for c in p50l) if buy \
                    else max(c["high"] for c in p50l) - T["close"]
                ok = (P[0] if P else 1.0) * atr <= d <= (P[1] if len(P) > 1 else 4.0) * atr
        # ── C) time & session ──
        elif n == 77:
            hr = datetime.fromtimestamp(T["open_time"] / 1000, tz=timezone.utc).hour
            ok = hr not in (21, 22, 23)
        elif n == 78:
            hr = datetime.fromtimestamp(T["open_time"] / 1000, tz=timezone.utc).hour
            ok = 6 <= hr <= 18
        elif n == 79:
            wd = datetime.fromtimestamp(T["open_time"] / 1000, tz=timezone.utc).weekday()
            ok = wd not in (5, 6)
        elif n == 80:
            hr = datetime.fromtimestamp(T["open_time"] / 1000, tz=timezone.utc).hour
            mn = datetime.fromtimestamp(T["open_time"] / 1000, tz=timezone.utc).minute
            first_hr_candle = (mn < 12)  # 5m candles: 12 per hour
            ok = not (mn == 0 or first_hr_candle and mn < 5)
        elif n == 81:
            wd = datetime.fromtimestamp(T["open_time"] / 1000, tz=timezone.utc).weekday()
            ok = 1 <= wd <= 4
        elif n == 82:
            hr = datetime.fromtimestamp(T["open_time"] / 1000, tz=timezone.utc).hour
            ok = hr >= 0
        elif n == 83:
            hr = datetime.fromtimestamp(T["open_time"] / 1000, tz=timezone.utc).hour
            ok = 6 <= hr <= 22
        elif n == 84:
            dead = cds[max(0, idx - 5):idx]
            ok = any((c["high"] - c["low"]) > 0.3 * atr for c in dead) if dead else False
        # ── D) multi-candle structure ──
        elif n == 85:
            if M is None:
                ok = False
            else:
                mrng = max(M["high"] - M["low"], 1e-12)
                ok = ((M["close"] > M["open"] and abs(M["close"] - M["open"]) <= 0.5 * mrng) if buy
                      else (M["close"] < M["open"] and abs(M["close"] - M["open"]) <= 0.5 * mrng))
        elif n == 86:
            p20 = cds[max(0, idx - 21):idx - 1]
            ok = bool(p20) and ((X["low"] <= min(c["low"] for c in p20)) if buy
                                else (X["high"] >= max(c["high"] for c in p20)))
        elif n == 87:
            p15 = cds[max(0, idx - 16):idx - 1]
            if not p15 or idx < 10:
                ok = False
            else:
                ref = min(c["low"] for c in p15) if buy else max(c["high"] for c in p15)
                d = abs(X["low"] - ref) if buy else abs(X["high"] - ref)
                ok = d <= 0.3 * atr
        elif n == 88:
            seg = cds[max(0, idx - 4):idx - 1]
            ok = len(seg) >= 3 and all(c["close"] < c["open"] for c in seg) if buy \
                else len(seg) >= 3 and all(c["close"] > c["open"] for c in seg)
        elif n == 89:
            p10 = cds[max(0, idx - 11):idx - 1]
            if not p10:
                ok = False
            else:
                bearish = sum(1 for c in p10 if c["close"] < c["open"])
                bullish = len(p10) - bearish
                ok = bearish >= (P[0] if P else 6) if buy else bullish >= (P[0] if P else 6)
        elif n == 90:
            ma100 = sum(c["close"] for c in cds[idx - 99:idx + 1]) / 100 if idx >= 99 else None
            ok = (ma100 is not None) and ((T["close"] > ma100) if buy else (T["close"] < ma100))
        elif n == 91:
            m_now = sum(c["close"] for c in cds[idx - 20:idx + 1]) / 21 if idx >= 20 else None
            m_old = sum(c["close"] for c in cds[idx - 25:idx - 4]) / 21 if idx >= 25 else None
            ok = (m_now is not None and m_old is not None) and ((m_now > m_old) if buy else (m_now < m_old))
        elif n == 92:
            lb7x = cds[max(0, idx - 7):idx]
            if not lb7x:
                ok = False
            else:
                ok = ((X["low"] - min(c["low"] for c in lb7x)) >= (P[0] if P else 0.25) * atr) if buy \
                    else ((max(c["high"] for c in lb7x) - X["high"]) >= (P[0] if P else 0.25) * atr)
        elif n == 94:
            ma21v = ma21[idx - 1] if isinstance(ma21, list) and idx - 1 < len(ma21) else None
            ok = ma21v is not None and abs(X["close"] - ma21v) >= (P[0] if P else 1.0) * atr
        if not ok:
            return False
    return True


def detect(cds, idx, cfg=None, ind=None):
    """Unified signal entry point."""
    cfg = cfg or {}
    sig = check_signal(
        cds, idx, cfg,
        volume_spike_mult=cfg.get("volume_spike_mult", 1.75),
        lookback=cfg.get("lookback", 10),
        body_min=cfg.get("body_min", 0.0),
    )
    if sig is None:
        return None
    # Apply idea quality filters
    if not _ideas_pass(sig, cds, idx, cfg):
        return None
    return sig


def check_signal(cds, idx, cfg, volume_spike_mult=3.0, lookback=10, body_min=0.0):
    """
    Check if Strategy 3 signal exists at index idx.
    """
    if idx < 150 or idx >= len(cds):
        return None
       
    trigger = cds[idx]
    extrema = cds[idx-1]
    prior = cds[idx-2]
    
    # MA Distance Filter: extremum close vs MA{ma_dist_period} at idx-1
    # MODE: 'pct' = min_ma_dist is % of MA (legacy) | 'atr' = min_ma_dist is × ATR(55)
    ma_dist_period = cfg.get("ma_dist_period", 21)
    min_ma_dist = cfg.get("min_ma_dist", 0.01)
    ma_dist_mode = cfg.get("ma_dist_mode", "pct")
    ma_val = None
    if len(cds) > ma_dist_period:
        closes_for_ma = [c["close"] for c in cds[idx-ma_dist_period:idx]]
        if len(closes_for_ma) == ma_dist_period:
            ma_val = sum(closes_for_ma) / ma_dist_period

    if ma_val is not None:
        if ma_dist_mode == "atr":
            atr55 = _atr(cds, idx - 1, 55)
            if atr55 is None or atr55 <= 0:
                return None
            dist = abs(extrema["close"] - ma_val) / atr55
        else:
            dist = abs(extrema["close"] - ma_val) / ma_val
        if dist < min_ma_dist:
            return None
    
    # Volume filter
    prev_50_vols = [c["volume"] for c in cds[idx-51:idx-1]]
    avg_vol_50 = sum(prev_50_vols) / len(prev_50_vols) if prev_50_vols else 0
    if avg_vol_50 == 0: return None

    # Calm-market filter (restored 2026-08-31): spike must be ISOLATED, not the
    # continuation of broader excitement — avg of last 10 candles must be calm.
    volume_calm_mult = cfg.get("volume_calm_mult", 1.3)
    prev_10_vols = [c["volume"] for c in cds[idx-11:idx-1]]
    avg_vol_10 = sum(prev_10_vols) / len(prev_10_vols)
    if avg_vol_10 > volume_calm_mult * avg_vol_50: return None

    # Extremum candle volume spike (ONLY extremum)
    if extrema["volume"] < volume_spike_mult * avg_vol_50: return None

    # NEW FILTER (user-approved 2026-09-07): volume building — avg of the 5 candles
    # before x must NOT exceed 1.2× avg50 (overheated micro-background kills edge).
    max_vol5_ratio = cfg.get("max_vol5_ratio")
    if max_vol5_ratio is not None:
        prev_5_vols = [c["volume"] for c in cds[idx-6:idx-1]]
        if len(prev_5_vols) == 5:
            avg_vol_5 = sum(prev_5_vols) / 5.0
            if avg_vol_5 > max_vol5_ratio * avg_vol_50: return None
    
    # Body filter: reject if body too small relative to range (wick-heavy candles)
    ext_range = abs(extrema["high"] - extrema["low"])
    ext_body = abs(extrema["close"] - extrema["open"])
    if ext_range > 0 and (ext_body / ext_range) < body_min: return None
    
    preceding_closes = [c["close"] for c in cds[idx-lookback:idx-1]]

    # IDEA-1 trigger confirmation (user-approved 2026-09-07): trigger close beyond
    # the extreme HIGH/LOW of the previous N candles (N = trig_confirm_window; 0=off).
    tw = cfg.get("trig_confirm_window", 0)
    if tw and tw > 0:
        prev_highs = [c["high"] for c in cds[idx-tw:idx]]
        prev_lows = [c["low"] for c in cds[idx-tw:idx]]
        hi_n = max(prev_highs) if len(prev_highs) == tw else None
        lo_n = min(prev_lows) if len(prev_lows) == tw else None
    else:
        hi_n = lo_n = None

    # BUY (کف)
    if extrema["close"] < extrema["open"]:
        cond1 = all(extrema["close"] < c for c in preceding_closes)
        prior_mid = (prior["open"] + prior["close"]) / 2
        cond3 = (trigger["close"] > prior_mid and trigger["close"] > extrema["high"] and trigger["close"] > trigger["open"])
        if hi_n is not None:
            cond3 = cond3 and trigger["close"] > hi_n
        if cond1 and cond3:
            return "BUY"

    # SELL (سقف)
    elif extrema["close"] > extrema["open"]:
        cond1 = all(extrema["close"] > c for c in preceding_closes)
        prior_mid = (prior["open"] + prior["close"]) / 2
        cond3 = (trigger["close"] < prior_mid and trigger["close"] < extrema["low"] and trigger["close"] < trigger["open"])
        if lo_n is not None:
            cond3 = cond3 and trigger["close"] < lo_n
        if cond1 and cond3:
            return "SELL"

    return None


def simulate_exit(cds, idx, stype, entry, sl, tp, ma21):
    """
    FROZEN EXIT (2026-08-25) — FULL close at TP (1.5R). No BE, no trail.
    States: tp_hit / sl_hit / signal.
    Returns (final_state, exit_price, exit_idx, half_done, events)

    2026-09-06 FT/live parity fix: within-candle resolution order changed from
    TP-first to SL-first — freqtrade checks STOP_LOSS before ROI when both trigger
    on the same candle (interface.py should_exit: stoplossflag appended before
    roi_reached; _get_exit_for_signal takes the first). SL gap-fill: when the candle
    OPEN is already beyond the stop, FT fills at the OPEN (not at the stop price) —
    replicated here via _gap_fill.
    """
    events = []

    def _gap_fill(price, candle, is_sl, is_short):
        # FT _get_close_rate_for_stoploss: stop beyond the candle range -> fill at OPEN.
        # (Applies to SL fills; ROI fills at the roi price.)
        if is_short:
            # short SL is above; gap when stop < candle low
            if is_sl and price < candle["low"]:
                return candle["open"]
        else:
            # long SL is below; gap when stop > candle high
            if is_sl and price > candle["high"]:
                return candle["open"]
        return price

    for i in range(idx + 1, len(cds)):
        c = cds[i]
        if stype == "BUY":
            hit_tp = c["high"] >= tp
            hit_sl = c["low"] <= sl
        else:
            hit_tp = c["low"] <= tp
            hit_sl = c["high"] >= sl
        # Within-candle: SL-first (freqtrade/live parity — SL outranks ROI on ties)
        if hit_sl:
            fill = _gap_fill(sl, c, is_sl=True, is_short=(stype == "SELL"))
            events.append({"type": "sl_hit", "price": fill, "index": i})
            return "sl_hit", fill, i, False, events
        if hit_tp:
            events.append({"type": "tp_hit", "price": tp, "index": i})
            return "tp_hit", tp, i, True, events
    return "signal", cds[-1]["close"], len(cds) - 1, False, events
