#!/usr/local/bin/python3
"""
Chart generator module for SignalTel Scanner.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime, timezone
from pathlib import Path

def generate_chart(pos, cds, state, events, is_update=False, chart_dir=None):
    idx = pos.get("index", 0)
    sym = pos["symbol"]
    st = pos["type"]
    strategy = pos["strategy"]
    tf = pos["timeframe"]
    
    # Default window: 15 candles before entry up to event/now
    start = max(0, idx - 15)
    max_event_idx = idx
    if events:
        for e in events:
            if e["index"] > max_event_idx:
                max_event_idx = e["index"]
    else:
        max_event_idx = idx
        
    end = min(len(cds), max(max_event_idx + 10, idx + 40))
    
    # User Rule: If window > 100 candles, prioritize from exit/now backwards (show last 50 candles before exit/now)
    if end - start > 100:
        end = min(len(cds), max_event_idx + 15)
        start = max(0, end - 100)
            
    window = cds[start:end]
    
    fig = plt.figure(figsize=(12, 9), facecolor="#1e1e1e")
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1], hspace=0.05)
    ax_price = fig.add_subplot(gs[0])
    ax_vol = fig.add_subplot(gs[1], sharex=ax_price)
    ax_price.set_facecolor("#1e1e1e")
    ax_vol.set_facecolor("#1e1e1e")
    ax_price.grid(True, linestyle="--", alpha=0.3, color="#333333")
    ax_vol.grid(True, linestyle="--", alpha=0.3, color="#333333")
    
    local_idx = idx - start
    tp = pos["tp"]
    sp = pos["entry"]
    initial_sl = pos["sl"]
    
    for i, c in enumerate(window):
        col = "#26a69a" if c["close"] >= c["open"] else "#ef5350"
        ax_price.plot([i, i], [c["low"], c["high"]], color=col, linewidth=1)
        ax_price.bar(i, abs(c["close"] - c["open"]), bottom=min(c["open"], c["close"]), width=0.6, color=col)
    
    ma_vals = [c.get("ma21") for c in window]
    if any(v is not None for v in ma_vals):
        ma_x = [i for i, v in enumerate(ma_vals) if v is not None]
        ma_y = [v for v in ma_vals if v is not None]
        if ma_x: ax_price.plot(ma_x, ma_y, c="#ffaa00", linewidth=1.2, label="MA21", alpha=0.9)
    
    x_full = list(range(local_idx, len(window)))
    # RR label from the strategy's own tp_rr (per-strategy, differs by design)
    try:
        from importlib import import_module
        _mod = import_module(f"strategies.{strategy}")
        _cfg = _mod.get_config()
        rr = float(_cfg.get("tp_rr", 0.0))
    except Exception:
        rr = 0.0
    rr_txt = f" (RR={rr:g})" if rr else ""
    # TP line ALWAYS lime, drawn above other lines (never red regardless of state)
    ax_price.plot(x_full, [tp]*len(x_full), c="lime", linestyle="--", linewidth=1.5,
                  label=f"TP{rr_txt}: {tp:.4f}", zorder=4)
    # RR text at the RIGHT END of the target line — always visible, every state
    ax_price.annotate(f"RR={rr:g}" if rr else "TP",
                      xy=(len(window) - 1, tp), xytext=(-4, 6),
                      textcoords="offset points", fontsize=9, fontweight="bold",
                      color="lime", ha="right",
                      bbox=dict(boxstyle="round,pad=0.15", facecolor="#1e1e1e",
                                edgecolor="lime", alpha=0.85))
    # Mark TP touch point
    tp_touch_local = None
    for ev in events:
        if ev["type"] == "tp_hit":
            loc = ev["index"] - start
            if 0 <= loc < len(window):
                tp_touch_local = loc
            break
    if tp_touch_local is None:
        # open signal: mark first window candle whose high/low reaches tp
        for i, c in enumerate(window):
            if i <= local_idx:
                continue
            if (st == "BUY" and c["high"] >= tp) or (st == "SELL" and c["low"] <= tp):
                tp_touch_local = i
                break
    if tp_touch_local is not None and 0 <= tp_touch_local < len(window):
        ax_price.scatter([tp_touch_local], [tp], c="lime", marker="*", s=260, zorder=6, edgecolors="white")
        ax_price.annotate(f"TARGET{rr_txt}", xy=(tp_touch_local, tp), xytext=(8, 6),
                          textcoords="offset points", fontsize=9, fontweight="bold",
                          color="lime", ha="left")
    # Mark SL touch point
    sl_touch_local = None
    for ev in events:
        if ev["type"] in ("sl_hit", "be_exit"):
            loc = ev["index"] - start
            if 0 <= loc < len(window):
                sl_touch_local = loc
            break
    if sl_touch_local is None:
        for i, c in enumerate(window):
            if i <= local_idx:
                continue
            if (st == "BUY" and c["low"] <= initial_sl) or (st == "SELL" and c["high"] >= initial_sl):
                sl_touch_local = i
                break
    if sl_touch_local is not None and 0 <= sl_touch_local < len(window):
        ax_price.scatter([sl_touch_local], [initial_sl], c="red", marker="*", s=260, zorder=6, edgecolors="white")
        ax_price.annotate("STOP", xy=(sl_touch_local, initial_sl), xytext=(8, -12),
                          textcoords="offset points", fontsize=9, fontweight="bold",
                          color="red", ha="left")
    
    sl_end_idx = len(window)
    sl_hit_price = None
    be_hit_price = None
    be_start_local = None
    
    for ev in events:
        if ev["type"] in ("sl_hit", "be_exit", "ma_exit"):
            e_local = ev["index"] - start
            if 0 <= e_local < len(window):
                sl_end_idx = e_local + 1
                sl_hit_price = ev["price"]
                break
                
    for ev in events:
        if ev["type"] == "tp_hit":
            tp_local = ev["index"] - start
            if 0 <= tp_local < len(window):
                be_start_local = tp_local
                be_hit_price = sp  # Break Even price is entry
    
    # SL line: from entry up to exact SL hit candle
    if sl_hit_price is not None:
        # Draw SL line from local_idx up to the hit candle index
        hit_local_idx = None
        for ev in events:
            if ev["type"] in ("sl_hit", "be_exit", "ma_exit"):
                hit_local_idx = ev["index"] - start
        if hit_local_idx is not None and 0 <= hit_local_idx < len(window):
            x_sl = list(range(local_idx, hit_local_idx + 1))
            ax_price.plot(x_sl, [initial_sl]*len(x_sl), c="red", linestyle="-", linewidth=2, label=f"SL: {initial_sl:.4f}")
    else:
        x_sl = list(range(local_idx, len(window)))
        ax_price.plot(x_sl, [initial_sl]*len(x_sl), c="red", linestyle="--", linewidth=1.5, label=f"SL: {initial_sl:.4f}")
    
    # BE line from tp_hit index up to exit candle
    if be_start_local is not None and sl_hit_price is not None:
        hit_local_idx = None
        for ev in events:
            if ev["type"] in ("sl_hit", "be_exit", "ma_exit"):
                hit_local_idx = ev["index"] - start
        if hit_local_idx is not None and 0 <= hit_local_idx < len(window):
            x_be = list(range(be_start_local, hit_local_idx + 1))
            ax_price.plot(x_be, [be_hit_price]*len(x_be), c="orange", linestyle="-", linewidth=2, label="SL -> BE")
    
    event_desc = []
    for ev in events:
        ev_type = ev["type"]
        ev_idx = ev["index"]
        ev_price = ev["price"]
        local_ev = ev_idx - start
        
        if 0 <= local_ev < len(window):
            if ev_type == "tp_hit":
                ax_price.scatter([local_ev], [ev_price], c="lime", marker="v", s=220, zorder=6, edgecolors="white")
                ax_price.annotate("TP HIT", xy=(local_ev, ev_price), fontsize=9, fontweight="bold", color="lime", ha="center", va="bottom")
                event_desc.append(f"TP Hit @ ${ev_price:.4f} → SL→BE")
            elif ev_type == "sl_hit":
                ax_price.scatter([local_ev], [ev_price], c="red", marker="X", s=300, zorder=6, edgecolors="white")
                ax_price.annotate("SL HIT", xy=(local_ev, ev_price), fontsize=10, fontweight="bold", color="red", ha="center", va="bottom")
                event_desc.append(f"SL Hit @ ${ev_price:.4f}")
            elif ev_type == "sl_hit_remaining":
                ax_price.scatter([local_ev], [ev_price], c="red", marker="X", s=300, zorder=6, edgecolors="white")
                ax_price.annotate("SL HIT (rem)", xy=(local_ev, ev_price), fontsize=10, fontweight="bold", color="red", ha="center", va="bottom")
                event_desc.append(f"SL Hit Remaining @ ${ev_price:.4f}")
            elif ev_type == "be_exit":
                ax_price.scatter([local_ev], [ev_price], c="orange", marker="X", s=250, zorder=6, edgecolors="white")
                ax_price.annotate("BE EXIT", xy=(local_ev, ev_price), fontsize=9, fontweight="bold", color="orange", ha="center", va="bottom")
                event_desc.append(f"BE Exit @ ${ev_price:.4f}")
            elif ev_type == "ma_exit":
                ax_price.scatter([local_ev], [ev_price], c="yellow", marker="X", s=250, zorder=6, edgecolors="white")
                ax_price.annotate("MA EXIT", xy=(local_ev, ev_price), fontsize=9, fontweight="bold", color="yellow", ha="center", va="bottom")
                event_desc.append(f"MA Exit @ ${ev_price:.4f}")
            elif ev_type == "ma_half_exit":
                ax_price.scatter([local_ev], [ev_price], c="cyan", marker="D", s=200, zorder=6, edgecolors="white")
                ax_price.annotate("½ MA", xy=(local_ev, ev_price), fontsize=8, fontweight="bold", color="cyan", ha="center", va="bottom")
                event_desc.append(f"Half MA Exit @ ${ev_price:.4f}")
    
    col_e = "#26a69a" if st=="BUY" else "#ef5350"
    ax_price.scatter([local_idx], [sp], c=col_e, marker="^" if st=="BUY" else "v", s=180, zorder=5, edgecolors="white", label=f"Entry ${sp:.4f}")
    
    vol_colors = ["#26a69a" if window[i]["close"] >= window[i]["open"] else "#ef5350" for i in range(len(window))]
    ax_vol.bar(range(len(window)), [c["volume"] for c in window], width=0.6, color=vol_colors, alpha=0.7)
    ax_vol.set_ylabel("Volume", color="white", fontsize=10)
    ax_vol.tick_params(axis='y', colors='white', labelsize=8)
    
    step = max(1, len(window) // 10)
    xticks = [i for i in range(0, len(window), step)]
    xlabels = [datetime.fromtimestamp(window[i]["open_time"]/1000, tz=timezone.utc).strftime("%m-%d %H:%M") for i in xticks]
    ax_price.set_xticks(xticks)
    ax_price.set_xticklabels([])
    ax_vol.set_xticks(xticks)
    ax_vol.set_xticklabels(xlabels, rotation=45, ha="right", fontsize=8, color="white")
    
    ax_price.legend(loc="lower left", facecolor="#1e1e1e", labelcolor="white", fontsize=9)
    ax_price.tick_params(axis='y', colors='white', labelsize=9)
    ax_price.set_ylabel("Price ($)", color="white", fontsize=11)
    ax_vol.tick_params(axis='x', colors='white', labelsize=8)
    
    events_str = "\n".join([f"• {e}" for e in event_desc]) or "• OPEN (Signal Active)"
    textstr = f"{strategy} ({tf}) | {st}\nState: {state.upper()}\nEntry: ${sp:.4f}\nPath:\n{events_str}"
    props = dict(boxstyle='round', facecolor='#2d2d2d', alpha=0.9, edgecolor='#555555')
    ax_price.text(0.02, 0.95, textstr, transform=ax_price.transAxes, fontsize=8.5, verticalalignment="top", color="white", bbox=props)
    
    plt.tight_layout()
    fname = f"{sym}_{st}_{state}_#{pos['signal_id']}.png"
    if chart_dir is None:
        chart_dir = Path("/home/hermes/.venv/crypto_charts")
    cp = chart_dir / fname
    fig.savefig(str(cp), dpi=120, bbox_inches="tight", facecolor="#1e1e1e")
    plt.close(fig)
    return cp
