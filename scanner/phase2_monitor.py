#!/usr/bin/env python3
"""Phase 2: Monitor existing positions for ToobitBot."""
import time
import importlib
import sys
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent))

from .simulation import simulate_forward_from
from .phase1_detect import fetch_candles_with_ma_sync
from .position_manager import load_pos, update_position, apply_realized_pnl_to_equity
from notifications.telegram import send_to_telegram


def _tp_rr_for(pos):
    """Get per-strategy TP multiple from get_config()['tp_rr'].""" 
    try:
        mod = importlib.import_module(f"strategies.{pos.get('strategy', 'str3')}")
        cfg = mod.get_config() if hasattr(mod, "get_config") else {}
        return float(cfg["tp_rr"])
    except Exception:
        return 2.0


def _monitor_symbol(sym, positions, client, bot_token, channel_id):
    """Monitor all open positions for a single symbol."""
    open_positions = [p for p in positions if p["symbol"] == sym and p["state"] == "signal"]
    if not open_positions:
        return
    
    tf = open_positions[0].get("timeframe", "5m")
    
    # Fetch candles using shared sync wrapper function
    cds_full = fetch_candles_with_ma_sync(client, sym, interval=tf, limit=250)
    if len(cds_full) < 75:
        return
    
    cds = cds_full  # Already has ma21 computed
    
    for pos in open_positions:
        open_time = pos.get("signal_open_time")
        idx = None
        for i, c in enumerate(cds):
            if c["open_time"] == open_time:
                idx = i
                break
        
        if idx is None:
            # STALE check: unresolved > 48 hours
            if pos.get("signal_open_time") and \
               time.time() * 1000 - pos["signal_open_time"] > 48 * 86400_000:
                update_position(pos["signal_id"], {
                    "state": "expired", "status": "EXPIRED",
                    "exit_price": pos["entry"], "realized_pnl_usd": 0.0
                })
                print(f"[STALE] {pos['strategy']} {pos['symbol']} expired at 0R")
            continue
        
        stype = pos["type"]
        entry = pos["entry"]
        sl = pos["sl"]
        
        # Validate SL direction
        if stype == "BUY" and sl >= entry:
            sl = entry * 0.999
        elif stype == "SELL" and sl <= entry:
            sl = entry * 1.001
        
        # Recalculate TP
        risk = abs(entry - sl)
        tp_rr = _tp_rr_for(pos)
        tp = entry + (risk * tp_rr) if stype == "BUY" else entry - (risk * tp_rr)
        
        half_done = pos.get("half_vol_done", False)
        events = pos.get("events", [])
        ma21_arr = [c.get("ma21") for c in cds]
        
        # Use strategy's simulate_exit if available
        strat_mod = importlib.import_module(f"strategies.{pos.get('strategy', 'str3')}")
        if hasattr(strat_mod, "simulate_exit"):
            cds_from_entry = cds[idx:-1]
            new_state, exit_price, rel_exit_idx, new_tp_hit, new_events = \
                strat_mod.simulate_exit(
                    cds_from_entry, 0, stype, entry, sl, tp, ma21_arr[idx:])
            exit_idx = idx + rel_exit_idx
            last_check = exit_idx if new_state != "signal" else len(cds) - 1
            for ev in new_events:
                ev["index"] = idx + ev["index"]
        else:
            current_sl = entry if half_done else sl
            tp_hit = half_done
            sim_start = pos.get("last_check_idx", idx + 1)
            if sim_start <= idx:
                sim_start = idx + 1
            new_state, exit_price, exit_idx, new_tp_hit, new_events = simulate_forward_from(
                cds[:-1], sim_start, stype, entry, sl, tp, ma21_arr[:-1],
                idx, tp_hit, current_sl)
            last_check = exit_idx if new_state != "signal" else sim_start
        
        if new_state != "signal" or new_events:
            all_events = new_events if new_events else events
            
            def _sig_events(evs):
                return [e["type"] for e in (evs or [])]
            
            already_has_half = any(
                e["type"] in ("ma_half_exit", "ma_exit")
                for e in (events or []))
            
            if new_state != "signal" and pos.get("state") == new_state:
                continue
            if (new_state == "signal" and pos.get("state") == "signal"
                    and already_has_half
                    and _sig_events(all_events) == _sig_events(events)):
                continue
            
            updates = {
                "state": new_state,
                "status": new_state.upper(),
                "half_vol_done": new_tp_hit,
                "events": all_events,
                "exit_price": exit_price,
                "index": idx,
                "last_check_idx": last_check
            }
            
            updated_pos = update_position(pos["signal_id"], updates)
            if updated_pos:
                updated_pos["index"] = idx
                if new_state != "signal" and pos.get("state") == "signal":
                    eq_state = apply_realized_pnl_to_equity()
                    updated_pos["equity"] = eq_state["equity"]
                send_to_telegram(updated_pos, cds, new_state, all_events,
                                 is_update=True, bot_token=bot_token, channel_id=channel_id)
                print(f"[UPDATE] #{pos['signal_id']} {sym} {stype} -> {new_state}")


def monitor_positions(bot_token, channel_id, client):
    """Monitor all open positions and update on state changes."""
    positions = load_pos()
    if not positions:
        return
    
    # Get symbols with open positions
    symbols_to_check = set(p["symbol"] for p in positions if p["state"] == "signal")
    if not symbols_to_check:
        return
    
    print(f"[MONITOR] open={len([p for p in positions if p['state'] == 'signal'])} syms={len(symbols_to_check)}")
    
    # Parallel fetch for multiple symbols (usually <10, but safe to parallelize)
    max_workers = min(8, len(symbols_to_check))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(_monitor_symbol, sym, positions, client, bot_token, channel_id): sym 
                for sym in symbols_to_check}
        for fut in futs:
            try:
                fut.result()
            except Exception as e:
                sym = futs[fut]
                print(f"[MONITOR ERROR] {sym}: {e}")