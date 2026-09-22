#!/usr/local/bin/python3
"""
Simulation module for SignalTel Scanner.
Shared exit primitives (compute_sl, simulate_outcome_full, simulate_forward_from).
SL model and TP multiple are ALWAYS supplied by the calling strategy's
get_config() — this module defines no strategy values of its own.
"""
def compute_sl(cds, i, sig_type, mode, atr_arr=None, sl_atr_mult=2.0):
    """Per-strategy stop-loss placement (shared by backtester & live scanner).
      '3candle'      : extreme low/high of the last 3 candles (original backtest mode)
      'trigger'      : entry candle low/high, clamped 0.1% beyond entry (live scanner mode)
      'trigger_open' : the OPEN of the trigger candle (direction-guarded)
      'atr'          : ATR-based SL (requires atr_arr and sl_atr_mult)
    mode comes from the strategy's get_config()['sl_mode'] — no default here:
    every strategy must declare its own SL model."""
    entry = cds[i]["close"]
    if mode == "atr" and atr_arr is not None:
        atr_val = atr_arr[i] if i < len(atr_arr) else None
        if atr_val and atr_val > 0:
            if sig_type == "BUY":
                return entry - atr_val * sl_atr_mult
            else:
                return entry + atr_val * sl_atr_mult
    if mode == "trigger_open":
        sl = cds[i]["open"]
        if sig_type == "BUY" and sl >= entry:
            sl = entry * 0.999
        if sig_type == "SELL" and sl <= entry:
            sl = entry * 1.001
        return sl
    if mode == "trigger":
        if sig_type == "BUY":
            sl = min(cds[i]["low"], entry * 0.999)
            if sl >= entry:
                sl = entry * 0.999
        else:
            sl = max(cds[i]["high"], entry * 1.001)
            if sl <= entry:
                sl = entry * 1.001
        return sl
    # 3candle
    if sig_type == "BUY":
        return min(cds[max(0, i-2)]["low"], cds[i-1]["low"], cds[i]["low"])
    else:
        return max(cds[max(0, i-2)]["high"], cds[i-1]["high"], cds[i]["high"])


def simulate_outcome_full(cds, idx, stype, entry, sl, tp, ma21):
    max_idx = len(cds) - 1
    tp_hit = False
    current_sl = sl
    events = []

    for i in range(idx + 1, max_idx + 1):
        c = cds[i]
        ma = ma21[i] if i < len(ma21) else None

        def _gap_fill_sl(price, candle):
            # FT parity: stop beyond the candle range → fill at OPEN
            if stype == "SELL" and price < candle["low"]:
                return candle["open"]
            if stype == "BUY" and price > candle["high"]:
                return candle["open"]
            return price

        if stype == "BUY":
            hit_tp = c["high"] >= tp
            hit_sl = c["low"] <= current_sl
            # SL first (freqtrade parity — stoploss outranks ROI on same-candle ties)
            if hit_sl:
                fill = _gap_fill_sl(current_sl, c)
                if not tp_hit:
                    events.append({"type": "sl_hit", "price": fill, "index": i})
                    return "sl_hit", fill, i, False, events
                else:
                    events.append({"type": "be_exit", "price": fill, "index": i})
                    return "be_exit", fill, i, True, events
            if not tp_hit and hit_tp:
                tp_hit = True
                current_sl = entry  # SL→BE
                events.append({"type": "tp_hit", "price": tp, "index": i})
                continue
            # MA trail ONLY after TP hit
            if tp_hit and ma is not None and c["open"] > ma and c["close"] < ma:
                events.append({"type": "ma_exit", "price": c["close"], "index": i})
                return "ma_exit", c["close"], i, True, events
        else:
            hit_tp = c["low"] <= tp
            hit_sl = c["high"] >= current_sl
            # SL first (freqtrade parity)
            if hit_sl:
                fill = _gap_fill_sl(current_sl, c)
                if not tp_hit:
                    events.append({"type": "sl_hit", "price": fill, "index": i})
                    return "sl_hit", fill, i, False, events
                else:
                    events.append({"type": "be_exit", "price": fill, "index": i})
                    return "be_exit", fill, i, True, events
            if not tp_hit and hit_tp:
                tp_hit = True
                current_sl = entry
                events.append({"type": "tp_hit", "price": tp, "index": i})
                continue
            if tp_hit and ma is not None and c["open"] < ma and c["close"] > ma:
                events.append({"type": "ma_exit", "price": c["close"], "index": i})
                return "ma_exit", c["close"], i, True, events

    if tp_hit:
        return "tp_hit", tp, max_idx, True, events
    return "signal", cds[-1]["close"], max_idx, False, events


def simulate_forward_from(cds, start_idx, stype, entry, sl, tp, ma21, prev_idx, tp_hit, current_sl):
    """Monitor existing position forward from a checkpoint (Mode 1, LIVE).

    IMPORTANT: When TP is hit, the position does NOT close. SL moves to BE and
    the position trails with MA21. So a TP hit at end-of-data means the position
    is still OPEN — return "signal" (open), not "tp_hit" (closed).
    """
    max_idx = len(cds) - 1
    events = []

    for i in range(start_idx, max_idx + 1):
        c = cds[i]
        ma = ma21[i] if i < len(ma21) else None

        def _gap_fill_sl(price, candle):
            # FT parity: stop beyond the candle range → fill at OPEN
            if stype == "SELL" and price < candle["low"]:
                return candle["open"]
            if stype == "BUY" and price > candle["high"]:
                return candle["open"]
            return price

        if stype == "BUY":
            hit_tp = c["high"] >= tp
            hit_sl = c["low"] <= current_sl
            # SL first (freqtrade parity — stoploss outranks ROI on same-candle ties)
            if hit_sl:
                fill = _gap_fill_sl(current_sl, c)
                if not tp_hit:
                    events.append({"type": "sl_hit", "price": fill, "index": i})
                    return "sl_hit", fill, i, False, events
                else:
                    events.append({"type": "be_exit", "price": fill, "index": i})
                    return "be_exit", fill, i, True, events
            if not tp_hit and hit_tp:
                tp_hit = True
                current_sl = entry
                events.append({"type": "tp_hit", "price": tp, "index": i})
                continue
            if tp_hit and ma is not None and c["open"] > ma and c["close"] < ma:
                events.append({"type": "ma_exit", "price": c["close"], "index": i})
                return "ma_exit", c["close"], i, True, events
        else:
            hit_tp = c["low"] <= tp
            hit_sl = c["high"] >= current_sl
            # SL first (freqtrade parity)
            if hit_sl:
                fill = _gap_fill_sl(current_sl, c)
                if not tp_hit:
                    events.append({"type": "sl_hit", "price": fill, "index": i})
                    return "sl_hit", fill, i, False, events
                else:
                    events.append({"type": "be_exit", "price": fill, "index": i})
                    return "be_exit", fill, i, True, events
            if not tp_hit and hit_tp:
                tp_hit = True
                current_sl = entry
                events.append({"type": "tp_hit", "price": tp, "index": i})
                continue
            if tp_hit and ma is not None and c["open"] < ma and c["close"] > ma:
                events.append({"type": "ma_exit", "price": c["close"], "index": i})
                return "ma_exit", c["close"], i, True, events

    # End of data: TP hit means position is STILL OPEN (SL→BE, trailing). Not closed.
    if tp_hit:
        return "signal", cds[-1]["close"], max_idx, True, events
    return "signal", cds[-1]["close"], max_idx, False, events
