#!/usr/local/bin/python3
"""
Strategy 1 (str1): X-Candle Breakout with Dual Trigger + ADX Filter
Frozen Config (2026-08-28):
- Structure: X-Candle Breakout, Dual Trigger, Full-exit
- Entry: ADX filter, volume spike, candle-pattern quality (ideas)
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
        "risk_pct": 0.025,  # 2.5% of equity per trade (user-set 2026-08-31)
        "tp_rr": 2.65,      # Full-position TP
        # ── STRUCTURAL WINNERS (09-14 rounds, user-approved pin) ──
        # band (fee-drag floor + wide-SL cap) + t1-only + T-stretch cap:
        # n=78 WR=38.5 PF=1.32 +18.0R MaxCL=6 DD@1%6.9 OptR3.0->$154
        # (vs legacy 219-trades PF 0.77 -45.9R). Dual-TP/BE/time-stop all rejected
        # under 3-fill fees — see EXPERIMENTS 09-14 rows.
        "min_dist_pct": 0.4,
        "max_dist_pct": 0.8,
        "t1_only": 1,
        # ADX lower-bound: drop dead-chop breaks (lo=15 PF1.46, 17→1.82,
        # 18→2.06 plateau 18-19, 24→n=11 thin). Asymmetric TP: SELL side keeps
        # running further in this universe (S-R >> B-R every variant) — tp_sell
        # 3.0R vs buy 2.65R adds ~+3.5R (lo18+S3.0 = PF 2.06 ledger row; 3.4 breaks
        # the plateau). (user-approved 09-14 round 2)
        "adx_lo": 18.0,
        "tp_rr_sell": 3.0,
        # ── Entry Logic (adaptive) ──
        "adx_th": 32.0,
        "sl_mode": "3candle",
        # vol spike 2.0→1.8 (09-14 j-frontier): free count-lift, ledger 3818a364edf9
        "vol_filter": 1.8,
        # ── Indicators ──
        "adx_len": 21,
        "adx_smooth": 21,
        # ── Idea filters ──
        # idea 98 REMOVED (v4 pin 2026-09-14): redundant once band+t1_only+adx_lo
        # exist — dropping it: n 34→39, ΣR +22.2→+24.0, equity $303→$328 (ledger
        # b8a857d1a875). idea 76 kept per user choice; measured −3.2R cost (tax).
        "active_ideas": {28, 2, 3, 54, 33, 32, 18, 65, 22, 62, 76},
        "idea_params": {2: (0.25,), 18: (1.0, 6.0), 65: (1.7,), 62: (2.0,)},  # 09-14 j-pin: xvol/tvol<=6, 3-candle vol >=1.7x, cv<=2.0
    }


# ─── Exit params (kept for interface compatibility) ─────────────────────
HALF_TP_RR = 2.65

# ── Structural exit flags (2026-09-14 experiments; cfg-synced by engine) ──
DUAL_TP = 0              # 1 = enable dual-TP
DUAL_TP_RR = 0.0         # interim TP in R (e.g. 1.2)
DUAL_TP_ARM_AT_ENTRY = 0 # (unused unless BE_ARM_RR>0) arm immediately
BE_ARM_RR = 0.0          # move SL to entry after +X×R excursion (0 = off)
BE_AFTER_HALF = 0        # arm BE when the dual-TP half fills
TIME_EXIT_N = 0          # close remainder after N candles at close (0 = off)
PART_FRAC = 0.99
LB_WINDOW = 7   # X must break the extreme of the last LB_WINDOW candles (structural knob)
ADX_LO = 0.0  # lower ADX bound: skip dead chop (0 = off; 09-14 round)


def _atr50(cds, i, period=50):
    if i < period:
        return None
    s = 0.0
    for j in range(i - period + 1, i + 1):
        h, l = cds[j]["high"], cds[j]["low"]
        pc = cds[j - 1]["close"] if j > 0 else (h + l) / 2
        s += max(h - l, abs(h - pc), abs(l - pc))
    return s / period


def _ideas_pass(sig, cds, idx, x_idx, mid_idx, cfg=None):
    """Candle-pattern quality filters. T=cds[idx] (trigger), X=cds[x_idx], M=middle candle."""
    cfg = cfg or {}
    active_ideas = cfg.get("active_ideas", set())
    params = cfg.get("idea_params", {})
    if not active_ideas:
        return True
    T, X = cds[idx], cds[x_idx]
    M = cds[mid_idx] if mid_idx is not None and mid_idx >= 0 else None
    atr = _atr50(cds, idx - 1)
    if not atr or atr <= 0:
        return False
    tb = abs(T["close"] - T["open"])
    trng = max(T["high"] - T["low"], 1e-12)
    xb = abs(X["close"] - X["open"])
    xr = max(X["high"] - X["low"], 1e-12)
    tvol, xvol = T["volume"], X["volume"]
    win = cds[max(0, x_idx - 50):x_idx]
    avg50 = sum(c["volume"] for c in win) / len(win) if win else 0
    if avg50 <= 0:
        return False
    lb7 = cds[max(0, idx - 7):idx]
    buy = (sig == "BUY")
    cpos = (T["close"] - T["low"]) / trng          # 1=closed at high
    xmid = (X["high"] + X["low"]) / 2
    risk = (T["close"] - X["low"]) if buy else (X["high"] - T["close"])
    for n in sorted(active_ideas):
        P = params.get(n, ())
        ok = True
        if n == 1:    ok = (P[0] if P else 0.5) <= tb / atr <= (P[1] if len(P) > 1 else 2.0)
        elif n == 2:  ok = tb >= (P[0] if P else 0.3) * atr
        elif n == 3:  ok = tb <= (P[0] if P else 1.8) * atr
        elif n == 4:  ok = (P[0] if P else 0.8) <= trng / atr <= (P[1] if len(P) > 1 else 2.5)
        elif n == 5:  ok = tb >= (P[0] if P else 0.6) * trng
        elif n == 6:  ok = tb >= (P[0] if P else 0.5) * atr
        elif n == 7:  ok = bool(lb7) and trng >= max((c["high"] - c["low"]) for c in lb7)
        elif n == 8:  ok = xr >= 1.2 * atr
        elif n == 9:  ok = 1.0 <= xr / atr <= 3.0
        elif n == 10: ok = xb >= 0.5 * xr
        elif n == 11:
            wick = (min(X["close"], X["open"]) - X["low"]) if buy else (X["high"] - max(X["close"], X["open"]))
            ok = wick <= 0.3 * xr
        elif n == 12:
            p10 = cds[max(0, x_idx - 10):x_idx]
            ok = bool(p10) and xr >= max((c["high"] - c["low"]) for c in p10)
        elif n == 13: ok = 0.5 <= xb / atr <= 2.5
        elif n == 14: ok = 2.0 <= xvol / avg50 <= 8.0
        elif n == 15: ok = tvol <= 0.8 * xvol
        elif n == 16: ok = tvol >= 0.7 * avg50
        elif n == 17: ok = tvol <= 1.5 * avg50
        elif n == 18:
            lo = (P[0] if P else 1.3); hi = (P[1] if len(P) > 1 else 8)
            ok = lo <= (xvol / tvol if tvol > 0 else 999) <= hi
        elif n == 19:
            p10v = cds[max(0, idx - 11):idx - 1]
            ok = bool(p10v) and tvol >= sum(c["volume"] for c in p10v) / len(p10v)
        elif n == 20: ok = M is not None and M["volume"] <= 1.2 * avg50
        elif n == 21:
            p14 = cds[max(0, x_idx - 13):x_idx + 1]
            ok = bool(p14) and xvol >= max(c["volume"] for c in p14)
        elif n == 22:
            _t22 = (P[0] if P else 0.75)
            ok = (cpos >= _t22) if buy else (cpos <= 1.0 - _t22)
        elif n == 23: ok = (T["close"] >= X["high"] + 0.1 * atr) if buy else (T["close"] <= X["low"] - 0.1 * atr)
        elif n == 24: ok = (T["close"] >= xmid) if buy else (T["close"] <= xmid)
        elif n == 25: ok = (T["close"] > X["open"]) if buy else (T["close"] < X["open"])
        elif n == 26:
            c5 = [c["close"] for c in cds[max(0, idx - 4):idx + 1]]
            ok = (T["close"] >= max(c5)) if buy else (T["close"] <= min(c5))
        elif n == 27:
            uw = T["high"] - max(T["close"], T["open"])
            dw = min(T["close"], T["open"]) - T["low"]
            ok = (uw <= 0.3 * trng) if buy else (dw <= 0.3 * trng)
        elif n == 28: ok = (T["low"] > X["low"]) if buy else (T["high"] < X["high"])
        elif n == 29:
            off = 0.1 * (X["high"] - X["low"])
            ok = (T["close"] > xmid + off) if buy else (T["close"] < xmid - off)
        elif n == 30:
            if buy:
                d = T["high"] - X["high"]
                ok = d > 0 and (T["close"] - X["high"]) / d >= 0.5
            else:
                d = X["low"] - T["low"]
                ok = d > 0 and (X["low"] - T["close"]) / d >= 0.5
        elif n == 31:
            xhi, xlo = max(X["open"], X["close"]), min(X["open"], X["close"])
            ok = (T["low"] >= xlo and T["close"] >= xhi) if buy else (T["high"] <= xhi and T["close"] <= xlo)
        elif n == 32:
            xhi, xlo = max(X["open"], X["close"]), min(X["open"], X["close"])
            frac = (P[0] if P else 1.0)
            span = (xhi - xlo) * frac
            ok = (T["open"] <= xlo and T["close"] >= xlo + span) if buy else (T["open"] >= xhi and T["close"] <= xhi - span)
        elif n == 33:
            # no-retrace-into-X-body gate; P[0]=f allows retrace of f×X-body (0=strict)
            _f33 = (P[0] if P else 0.0)
            _xb33 = abs(X["open"] - X["close"])
            ok = (T["low"] >= X["close"] - _f33 * _xb33) if buy \
                 else (T["high"] <= X["close"] + _f33 * _xb33)
        elif n == 34:
            d = (T["close"] - X["high"]) if buy else (X["low"] - T["close"])
            ok = 0.05 * atr <= d <= 0.5 * atr
        elif n == 35: ok = M is not None and (M["high"] - M["low"]) <= 0.8 * atr
        elif n == 36: ok = (T["open"] >= xmid) if buy else (T["open"] <= xmid)
        elif n == 37: ok = M is not None and xr >= atr and (M["high"] - M["low"]) <= 0.6 * atr and tb >= xb
        elif n == 38: ok = 0.4 * atr <= risk <= 2.0 * atr
        elif n == 39: ok = 1.8 * risk <= 4.0 * atr
        elif n == 40:
            lb7x = cds[max(0, x_idx - 7):x_idx]
            if lb7x:
                ok = ((X["low"] - min(c["low"] for c in lb7x)) >= 0.3 * atr) if buy \
                    else ((max(c["high"] for c in lb7x) - X["high"]) >= 0.3 * atr)
            else:
                ok = False
        elif n == 41: ok = risk >= 0.6 * trng
        elif n == 42: ok = xvol >= 2 * avg50 and tb >= 0.6 * atr
        elif n == 43: ok = xr >= 1.5 * atr and (cpos >= 0.8 if buy else cpos <= 0.2)
        elif n == 44:
            ok = (xvol >= 2 * avg50 and tb >= 0.5 * atr) and (cpos >= 0.6 if buy else cpos <= 0.4)
        elif n == 45: ok = tb >= 0.8 * xb
        elif n == 46: ok = 0.5 <= (tb / xb if xb > 0 else 999) <= 3
        elif n == 47:
            if M is None:
                ok = False
            elif buy:
                ok = M["close"] > M["open"] and (M["high"] - M["low"]) <= 0.8 * atr
            else:
                ok = M["close"] < M["open"] and (M["high"] - M["low"]) <= 0.8 * atr
        elif n == 48:
            p20 = cds[max(0, x_idx - 19):x_idx + 1]
            ok = (X["low"] <= min(c["low"] for c in p20)) if buy else (X["high"] >= max(c["high"] for c in p20))
        elif n == 49: ok = (T["close"] >= X["high"] + 0.2 * atr) if buy else (T["close"] <= X["low"] - 0.2 * atr)
        elif n == 50:
            hr = datetime.fromtimestamp(T["open_time"] / 1000, tz=timezone.utc).hour
            ok = hr not in (0, 1, 2, 3, 23)
        elif n == 51: ok = 0.6 * atr <= risk <= 1.5 * atr
        elif n == 52: ok = 0.8 * atr <= risk <= 1.5 * atr
        elif n == 53: ok = 0.5 * atr <= risk <= 1.2 * atr
        elif n == 54:
            _lo54 = (P[0] if P else 0.7); _hi54 = (P[1] if len(P) > 1 else 1.8)
            ok = _lo54 * atr <= risk <= _hi54 * atr
        elif n == 55:
            # Semi-engulf: T closes beyond X body by frac, T opens inside X body
            xhi, xlo = max(X["open"], X["close"]), min(X["open"], X["close"])
            frac = (P[0] if P else 0.5)
            ok = (T["close"] >= xlo + (xhi - xlo) * frac and T["open"] <= xhi) if buy \
                else (T["close"] <= xhi - (xhi - xlo) * frac and T["open"] >= xlo)
        elif n == 56:
            # Body cross: T body spans X close (stronger than 33, weaker than 32)
            ok = ((T["low"] <= X["close"] <= T["high"]) and (T["close"] > T["open"])) if buy \
                else ((T["low"] <= X["close"] <= T["high"]) and (T["close"] < T["open"]))
        elif n == 57:
            # Volume decay into trigger: T.vol < avg vol of last 3 candles before T
            p3 = cds[max(0, idx - 4):idx - 1]
            ok = bool(p3) and tvol < sum(c["volume"] for c in p3) / len(p3)
        elif n == 58:
            # X volume = highest since previous signal region (last 30 candles before X)
            p30 = cds[max(0, x_idx - 29):x_idx]
            ok = bool(p30) and xvol >= max(c["volume"] for c in p30)
        elif n == 59:
            # Progressive quieting toward trigger: T.vol < M.vol
            ok = M is not None and tvol < M["volume"]
        elif n == 60:
            # Spike only on extremum vs middle: X.vol / M.vol >= ratio
            if M is None or M["volume"] <= 0:
                ok = False
            else:
                r = (P[0] if P else 1.5)
                ok = xvol / M["volume"] >= r
        elif n == 61:
            # Trigger not bone-dry: T.vol >= frac of X.vol
            f = (P[0] if P else 0.3)
            ok = tvol >= f * xvol
        elif n == 62:
            # Stable market: coefficient of variation of last-50 vols <= thr
            import statistics as _st
            try:
                cv = _st.pstdev([c["volume"] for c in win]) / avg50
                ok = cv <= (P[0] if P else 1.2)
            except Exception:
                ok = False
        elif n == 63:
            # Extremum spike double the middle candle: X.vol >= mult * M.vol
            if M is None or M["volume"] <= 0:
                ok = False
            else:
                ok = xvol >= (P[0] if P else 2.0) * M["volume"]
        elif n == 64:
            # Same-hour yesterday volume comparison (approx via 288 candles back)
            if idx >= 288:
                yv = cds[idx - 288]["volume"]
                ok = tvol >= (P[0] if P else 0.8) * yv if yv > 0 else False
            else:
                ok = False
        elif n == 65:
            # Sum of last-3 candles volume (X+M+T) >= mult × avg50 (per-candle basis ×3)
            s3 = sum(c["volume"] for c in cds[max(0, idx - 2):idx + 1])
            ok = s3 >= (P[0] if P else 1.5) * avg50 * 3
        elif n == 66:
            # Directional net volume over last 3 candles agrees with trade side
            s = 0.0
            for j in range(max(1, idx - 2), idx + 1):
                s += cds[j]["volume"] if cds[j]["close"] >= cds[j]["open"] else -cds[j]["volume"]
            ok = (s > 0) if buy else (s < 0)
        # ── Wave 3: regime / depth / management (no time filters) ──
        elif n == 67:
            # Balanced volatility: ATR50/close between lo% and hi%
            atc = atr / T["close"] if T["close"] > 0 else 0
            ok = (P[0] if P else 0.003) <= atc <= (P[1] if len(P) > 1 else 0.02)
        elif n == 68:
            # Squeeze: current ATR50 below ATR50 measured ~20 candles ago
            a20 = _atr50(cds, max(0, idx - 20))
            ok = a20 is not None and atr < a20
        elif n == 71:
            # Intensification: trigger range >= middle range
            ok = M is not None and trng >= (M["high"] - M["low"])
        elif n == 72: ok = xb >= 0.6 * xr
        elif n == 73:
            wick = (min(X["close"], X["open"]) - X["low"]) if buy else (X["high"] - max(X["close"], X["open"]))
            ok = wick <= (P[0] if P else 0.2) * xr
        elif n == 74:
            total_move = xr + (M["high"] - M["low"] if M else 0) + trng
            ok = total_move >= (P[0] if P else 2.5) * atr
        elif n == 75:
            h12 = cds[max(0, idx - 11):idx + 1]
            ok = bool(h12) and T["high"] >= max(c["high"] for c in h12)
        elif n == 76:
            p50l = cds[max(0, idx - 49):idx + 1]
            if not p50l:
                ok = False
            else:
                d = T["close"] - min(c["low"] for c in p50l) if buy \
                    else max(c["high"] for c in p50l) - T["close"]
                ok = (P[0] if P else 1.0) * atr <= d <= (P[1] if len(P) > 1 else 4.0) * atr
        elif n == 85:
            # Confirming middle candle (small same-direction)
            if M is None:
                ok = False
            else:
                mrng = max(M["high"] - M["low"], 1e-12)
                ok = ((M["close"] > M["open"] and abs(M["close"] - M["open"]) <= 0.5 * mrng) if buy
                      else (M["close"] < M["open"] and abs(M["close"] - M["open"]) <= 0.5 * mrng))
        elif n == 86:
            p20x = cds[max(0, x_idx - 19):x_idx + 1]
            ok = (X["low"] <= min(c["low"] for c in p20x)) if buy else (X["high"] >= max(c["high"] for c in p20x))
        elif n == 87:
            p15 = cds[max(0, x_idx - 14):x_idx - 9]
            if not p15 or x_idx < 10:
                ok = False
            else:
                ref = min(c["low"] for c in p15) if buy else max(c["high"] for c in p15)
                d = abs(X["low"] - ref) if buy else abs(X["high"] - ref)
                ok = d <= 0.3 * atr
        elif n == 88:
            seg = cds[max(0, x_idx - 3):x_idx]
            if len(seg) < 3:
                ok = False
            elif buy:
                ok = all(c["close"] < c["open"] for c in seg)
            else:
                ok = all(c["close"] > c["open"] for c in seg)
        elif n == 89:
            p10 = cds[max(0, idx - 11):idx - 1]
            if not p10:
                ok = False
            else:
                bearish = sum(1 for c in p10 if c["close"] < c["open"])
                bullish = len(p10) - bearish
                ok = bearish >= (P[0] if P else 6) if buy else bullish >= (P[0] if P else 6)
        elif n == 90:
            ma100 = sum(c["close"] for c in cds[idx-99:idx+1]) / 100 if idx >= 99 else None
            ok = (ma100 is not None) and ((T["close"] > ma100) if buy else (T["close"] < ma100))
        elif n == 91:
            m_now = sum(c["close"] for c in cds[idx - 20:idx + 1]) / 21 if idx >= 20 else None
            m_old = sum(c["close"] for c in cds[idx - 25:idx - 4]) / 21 if idx >= 25 else None
            ok = (m_now is not None and m_old is not None) and ((m_now > m_old) if buy else (m_now < m_old))
        elif n == 92:
            lb7x = cds[max(0, x_idx - 7):x_idx]
            if not lb7x:
                ok = False
            else:
                ok = ((X["low"] - min(c["low"] for c in lb7x)) >= (P[0] if P else 0.25) * atr) if buy \
                    else ((max(c["high"] for c in lb7x) - X["high"]) >= (P[0] if P else 0.25) * atr)
        elif n == 94:
            # MA21 computed locally (ma21 series is not passed into _ideas_pass)
            ma21v = (sum(c["close"] for c in cds[x_idx - 20:x_idx + 1]) / 21) if x_idx >= 20 else None
            ok = ma21v is not None and abs(X["close"] - ma21v) >= (P[0] if P else 1.0) * atr
        elif n == 95:
            # directional MA21 over-extension of X (str4 stretch-gate transfer, 09-14):
            # BUY wants X close stretched BELOW MA21 (oversold flush), SELL mirrored.
            ma21v = (sum(c["close"] for c in cds[x_idx - 20:x_idx + 1]) / 21) if x_idx >= 20 else None
            if ma21v is None:
                ok = False
            else:
                ext = (ma21v - X["close"]) if buy else (X["close"] - ma21v)
                ok = ext >= (P[0] if P else 0.45) * atr
        elif n == 96:
            # decisive-break quality (idea 6): X close beyond ALL closes of the prev
            # 7 candles AND dominant body (>=60% of range) — not a stop-wick break.
            p7c = [c["close"] for c in cds[max(0, x_idx - 7):x_idx]]
            deep = (X["close"] < min(p7c)) if buy else (X["close"] > max(p7c))
            ok = bool(p7c) and deep and xb >= 0.6 * xr
        elif n == 97:
            # reclaim-volume: trigger candle volume >= mult × X volume (idea 5,
            # "pickup on reclaim" from failed-breakout literature).
            ok = tvol >= (P[0] if P else 1.0) * xvol
        elif n == 98:
            # T-stretch CAP (09-14 structural round): trigger close must not run
            # more than k×ATR beyond X's extreme — no chasing; entry stays near the
            # flush level so R stays cheap and dist fee-drag stays inside the band.
            cap = (P[0] if P else 0.3) * atr
            ok = (T["close"] - X["high"] <= cap) if buy else (X["low"] - T["close"] <= cap)
        elif n == 99:
            # regime width gate: range of last 20 candles ≤ k×ATR — str1 is a
            # RANGE mean-reversion pattern; skip expansion/regime-shift candles.
            w20 = cds[max(0, x_idx - 19):x_idx + 1]
            hi20 = max(c["high"] for c in w20); lo20 = min(c["low"] for c in w20)
            ok = (hi20 - lo20) <= (P[0] if P else 3.0) * atr
        elif n == 100:
            # snap-back-through-MA gate: T close must already be on the far side of
            # MA21 from X (reversal in progress, not just a pause mid-drop).
            ma21v = (sum(c["close"] for c in cds[idx - 20:idx + 1]) / 21) if idx >= 20 else None
            if ma21v is None:
                ok = False
            else:
                ok = (T["close"] > ma21v) if buy else (T["close"] < ma21v)
        if not ok:
            return False
    return True


def detect(cds, idx, cfg=None, ind=None):
    """Unified signal entry point."""
    cfg = cfg or {}
    # LIVE-PARITY FIX (09-15 cfg-coverage audit): the scanner calls detect()
    # directly — without the engine's run_backtest cfg->global sync — so the
    # ADX floor gate (reads module global ADX_LO) never saw cfg["adx_lo"]=18
    # live and leaked dead-chop signals (proved: 4 signals in ADX 10-18 zone).
    # Sync from cfg here so EVERY caller gets backtest-exact behavior.
    global ADX_LO
    ADX_LO = float(cfg.get("adx_lo", 0.0) or 0.0)
    if ind is None:
        ind = compute_indicators(
            cds,
            adx_len=cfg.get("adx_len", 21),
            adx_smooth=cfg.get("adx_smooth", 21),
        )
    adx, ma21 = ind
    adx_th = cfg.get("adx_th", 26.0)
    vol_filter = cfg.get("vol_filter", 2.0)
    if cfg.get("t1_only"):
        # idea 2 (09-14): drop the delayed Trigger-2 fallback entirely
        return check_signal_t1(cds, idx, adx, ma21, cfg, adx_th=adx_th, vol_filter=vol_filter)
    sig = check_signal(cds, idx, adx, ma21, cfg, adx_th=adx_th, vol_filter=vol_filter)
    if not sig:
        sig = check_signal_t1(cds, idx, adx, ma21, cfg, adx_th=adx_th, vol_filter=vol_filter)
    return sig


def check_signal(cds, idx, adx, ma21, cfg, adx_th=26.0, vol_filter=2.0):
    """
    Trigger 2 fallback check (idx is Trigger2 candle, X is at idx-2).
    Lookback = 7 candles.
    """
    if idx < 52 or idx >= len(cds):
        return None

    trigger2 = cds[idx]
    trigger1 = cds[idx - 1]
    X = cds[idx - 2]
    x_idx = idx - 2

    lb = LB_WINDOW
    prev_lb = cds[idx - 2 - lb: idx - 2]
    if len(prev_lb) < lb:
        return None
    min_low_lb = min(c["low"] for c in prev_lb)
    max_high_lb = max(c["high"] for c in prev_lb)

    prev50 = cds[idx - 52: idx - 2]
    avg_vol_50 = sum(c["volume"] for c in prev50) / len(prev50) if prev50 else 0

    adx_val = adx[x_idx] if x_idx < len(adx) else None

    trig1_bull = trigger1["close"] > trigger1["open"] and trigger1["close"] > X["high"]
    trig1_bear = trigger1["close"] < trigger1["open"] and trigger1["close"] < X["low"]

    # ---------- BUY ----------
    x_bear = X["close"] < X["open"]
    if x_bear:
        cond1 = X["low"] < min_low_lb
        cond2 = avg_vol_50 > 0 and X["volume"] >= vol_filter * avg_vol_50
        cond3 = adx_val is not None and adx_val <= adx_th and (not ADX_LO or adx_val >= ADX_LO)
        cond4 = trigger2["close"] > trigger2["open"] and trigger2["close"] > X["high"]
        cond5 = not trig1_bull
        if cond1 and cond2 and cond3 and cond4 and cond5:
            if _ideas_pass("BUY", cds, idx, x_idx, idx - 1, cfg):
                return "BUY"

    # ---------- SELL ----------
    x_bull = X["close"] > X["open"]
    if x_bull:
        cond1 = X["high"] > max_high_lb
        cond2 = avg_vol_50 > 0 and X["volume"] >= vol_filter * avg_vol_50
        cond3 = adx_val is not None and adx_val <= adx_th and (not ADX_LO or adx_val >= ADX_LO)
        cond4 = trigger2["close"] < trigger2["open"] and trigger2["close"] < X["low"]
        cond5 = not trig1_bear
        if cond1 and cond2 and cond3 and cond4 and cond5:
            if _ideas_pass("SELL", cds, idx, x_idx, idx - 1, cfg):
                return "SELL"

    return None


def check_signal_t1(cds, idx, adx, ma21, cfg, adx_th=26.0, vol_filter=2.0):
    """
    Trigger 1 check (idx is Trigger1 candle, X is at idx-1).
    Lookback = 7 candles.
    """
    if idx < 52 or idx >= len(cds):
        return None

    trigger1 = cds[idx]
    X = cds[idx - 1]
    x_idx = idx - 1

    lb = LB_WINDOW
    prev_lb = cds[idx - 1 - lb: idx - 1]
    if len(prev_lb) < lb:
        return None
    min_low_lb = min(c["low"] for c in prev_lb)
    max_high_lb = max(c["high"] for c in prev_lb)

    prev50 = cds[idx - 51: idx - 1]
    avg_vol_50 = sum(c["volume"] for c in prev50) / len(prev50) if prev50 else 0

    adx_val = adx[x_idx] if x_idx < len(adx) else None

    # ---------- BUY ----------
    x_bear = X["close"] < X["open"]
    if x_bear:
        cond1 = X["low"] < min_low_lb
        cond2 = avg_vol_50 > 0 and X["volume"] >= vol_filter * avg_vol_50
        cond3 = adx_val is not None and adx_val <= adx_th and (not ADX_LO or adx_val >= ADX_LO)
        cond4 = trigger1["close"] > trigger1["open"] and trigger1["close"] > X["high"]
        if cond1 and cond2 and cond3 and cond4:
            if _ideas_pass("BUY", cds, idx, x_idx, None, cfg):
                return "BUY"

    # ---------- SELL ----------
    x_bull = X["close"] > X["open"]
    if x_bull:
        cond1 = X["high"] > max_high_lb
        cond2 = avg_vol_50 > 0 and X["volume"] >= vol_filter * avg_vol_50
        cond3 = adx_val is not None and adx_val <= adx_th and (not ADX_LO or adx_val >= ADX_LO)
        cond4 = trigger1["close"] < trigger1["open"] and trigger1["close"] < X["low"]
        if cond1 and cond2 and cond3 and cond4:
            if _ideas_pass("SELL", cds, idx, x_idx, None, cfg):
                return "SELL"

    return None


def simulate_exit(cds, idx, stype, entry, sl, tp, ma21):
    """
    FROZEN EXIT (2026-08-24) — FULL close at TP (2.5R). No BE, no trail:
    sweep showed trailing never beat full exit on 3mo backtest.
    Returns (final_state, exit_price, exit_idx, half_done, events)
      final_state ∈ {'tp_hit','sl_hit','signal'}
    pnl computed by evaluate_strategy from events.

    2026-09-07 FT/live parity fix: within-candle resolution changed TP-first → SL-first
    (freqtrade checks STOP_LOSS before ROI on same-candle ties) + SL gap-fill at candle
    OPEN when the open is already beyond the stop (FT _get_close_rate_for_stoploss).

    2026-09-14 structural experiments (user: structural changes, not filters):
    module flags (cfg-synced by evaluate_strategy):
      DUAL_TP + DUAL_TP_RR=X — half position closes at X×R (ma_half_exit event →
        engine blend + 3rd-fill fee), remainder runs to full TP/SL.
      BE_ARM_RR=X — move SL to entry once +X×R excursion reached ("be_exit").
      BE_AFTER_HALF — treat the dual-TP fill as the BE arming trigger.
      TIME_EXIT_N=N — close remainder at candle close after N candles ("ma_exit").
    Retested under 3-fill fees + SL-first parity (old "half hurts str1" note predates
    both).
    """
    events = []
    _risk = abs(entry - sl)
    dtp = None
    if DUAL_TP and DUAL_TP_RR and DUAL_TP_RR > 0:
        dtp = entry + DUAL_TP_RR * _risk if stype == "BUY" else entry - DUAL_TP_RR * _risk
    half_done = False
    armed = bool(BE_ARM_RR and BE_ARM_RR > 0 and DUAL_TP_ARM_AT_ENTRY)  # opt. arm at once
    be_on = (BE_ARM_RR and BE_ARM_RR > 0) or BE_AFTER_HALF
    te = TIME_EXIT_N if (TIME_EXIT_N and TIME_EXIT_N > 0) else None

    def _gap_fill(price, candle, is_short):
        # FT: stop beyond the candle range → fill at OPEN (long: stop > high; short: stop < low)
        if is_short:
            if price < candle["low"]:
                return candle["open"]
        else:
            if price > candle["high"]:
                return candle["open"]
        return price

    for i in range(idx + 1, len(cds)):
        c = cds[i]
        is_short = (stype == "SELL")
        # effective stop: BE price once armed (after half or after excursion)
        eff_sl = entry if (be_on and armed) else sl
        if stype == "BUY":
            hit_tp = c["high"] >= tp
            hit_sl = c["low"] <= eff_sl
            hit_dtp = dtp is not None and c["high"] >= dtp
        else:
            hit_tp = c["low"] <= tp
            hit_sl = c["high"] >= eff_sl
            hit_dtp = dtp is not None and c["low"] <= dtp
        # Within-candle: SL first (freqtrade parity — stoploss outranks ROI on ties)
        if hit_sl:
            fill = _gap_fill(eff_sl, c, is_short=is_short)
            if armed:
                # closed at breakeven
                if half_done:
                    # remaining half at entry: blend via ma_exit semantics
                    events.append({"type": "be_exit", "price": fill, "index": i})
                    return "ma_exit", entry, i, True, events
                events.append({"type": "be_exit", "price": fill, "index": i})
                return "be_exit", fill, i, False, events
            events.append({"type": "sl_hit", "price": fill, "index": i})
            return "sl_hit", fill, i, half_done, events
        # full TP takes precedence over the interim dual-TP level on the same candle
        if hit_tp:
            events.append({"type": "tp_hit", "price": tp, "index": i})
            return "tp_hit", tp, i, True, events
        if hit_dtp and not half_done:
            events.append({"type": "ma_half_exit", "price": dtp, "index": i})
            half_done = True
            if BE_AFTER_HALF:
                armed = True
        # arm BE on favorable excursion (checked AFTER exits — no same-candle arming)
        if BE_ARM_RR and BE_ARM_RR > 0 and not armed:
            fav = (c["high"] - entry) if stype == "BUY" else (entry - c["low"])
            if fav >= BE_ARM_RR * _risk:
                armed = True
        # time stop: close remainder at this candle's close
        if te is not None and i - idx >= te:
            px = c["close"]
            events.append({"type": "ma_exit", "price": px, "index": i})
            return "ma_exit", px, i, half_done, events
    return "signal", cds[-1]["close"], len(cds) - 1, half_done, events
