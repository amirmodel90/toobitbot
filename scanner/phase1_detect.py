#!/usr/bin/env python3
"""Phase 1: Detect new signals for ToobitBot."""
import asyncio
import importlib
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .simulation import compute_sl
from .position_manager import load_pos, save_pos, next_id, apply_realized_pnl_to_equity, get_strategy_risk_pct
from .chart_gen import generate_chart
from notifications.telegram import send_to_telegram

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))

# Thread safety
_POS_LOCK = threading.Lock()
_STRAT_LOCKS = {}
_STRAT_LOCKS_GUARD = threading.Lock()


def _strategy_lock(strategy_name):
    with _STRAT_LOCKS_GUARD:
        if strategy_name not in _STRAT_LOCKS:
            _STRAT_LOCKS[strategy_name] = threading.RLock()
        return _STRAT_LOCKS[strategy_name]


async def fetch_candles_with_ma(client, symbol, interval="5m", limit=250):
    """Fetch klines from Toobit (async) and compute MA21."""
    raw = await client.get_klines(symbol=symbol, interval=interval, limit=limit)
    cds = []
    for c in raw:
        cds.append({
            "open_time": c[0],
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
        })
    # CRITICAL FIX: Toobit API returns newest-first; strategies expect oldest-first
    cds = sorted(cds, key=lambda c: c["open_time"])
    closes = [c["close"] for c in cds]
    ma21 = [sum(closes[i-20:i+1]) / 21.0 if i >= 20 else None for i in range(len(closes))]
    for i, c in enumerate(cds):
        c["ma21"] = ma21[i]
    return cds


async def fetch_candles_batch(client, symbols, interval="5m", limit=250, max_concurrent=20):
    """Fetch klines for multiple symbols concurrently using async batch."""
    # Use the client's built-in batch method
    results = await client.fetch_multiple_klines(symbols, interval, limit, max_concurrent)
    
    # Process each result: sort + MA21
    processed = {}
    for sym, raw in results.items():
        cds = []
        for c in raw:
            cds.append({
                "open_time": c[0],
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })
        cds = sorted(cds, key=lambda c: c["open_time"])
        closes = [c["close"] for c in cds]
        ma21 = [sum(closes[i-20:i+1]) / 21.0 if i >= 20 else None for i in range(len(closes))]
        for i, c in enumerate(cds):
            c["ma21"] = ma21[i]
        processed[sym] = cds
    return processed


def fetch_candles_with_ma_sync(client, symbol, interval="5m", limit=250):
    """Sync wrapper using requests directly (for multi-threaded compatibility)."""
    # Use the client's sync session directly to avoid event loop issues
    raw = client.get_klines_sync(symbol=symbol, interval=interval, limit=limit)
    cds = []
    for c in raw:
        cds.append({
            "open_time": c[0],
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
        })
    # CRITICAL FIX: Toobit API returns newest-first; strategies expect oldest-first
    cds = sorted(cds, key=lambda c: c["open_time"])
    closes = [c["close"] for c in cds]
    ma21 = [sum(closes[i-20:i+1]) / 21.0 if i >= 20 else None for i in range(len(closes))]
    for i, c in enumerate(cds):
        c["ma21"] = ma21[i]
    return cds


def load_strategy(name):
    """Load strategy module."""
    try:
        return importlib.import_module(f"strategies.{name}")
    except Exception as e:
        print(f"[STRATEGY ERROR] Failed to load {name}: {e}")
        return None


def find_by_signal_time(sym, stype, open_time):
    """Check if signal already exists."""
    for p in load_pos():
        if p["symbol"] == sym and p["type"] == stype and p.get("signal_open_time") == open_time:
            return p
    return None


def get_symbols_with_leverage(client, min_leverage=10):
    """Get USDT-M symbols with leverage > min_leverage."""
    info = client.get_exchange_info_sync()
    symbols = []
    for c in info.get("contracts", []):
        if c.get("quoteAsset") != "USDT":
            continue
        if c.get("status") != "TRADING":
            continue
        risk_limits = c.get("riskLimits", [])
        if not risk_limits:
            continue
        max_lev = max(float(r.get("maxLeverage", 0)) for r in risk_limits)
        if max_lev >= min_leverage:
            symbols.append({
                "symbol": c["symbol"],
                "max_leverage": max_lev,
                "quoteVolume": 0,  # Will be filled from ticker
            })
    return symbols


def detect_new_signals(config, bot_token, channel_id, client, scanner_cfg):
    """Main detection loop."""
    # Get symbols with leverage > min_leverage
    symbols = get_symbols_with_leverage(client, scanner_cfg.get("min_leverage", 10))
    
    # Get 24hr tickers for volume sorting (async)
    try:
        tickers = client.get_24hr_ticker_sync()
        ticker_map = {t["s"]: float(t.get("qv", 0)) for t in tickers}
        for s in symbols:
            s["quoteVolume"] = ticker_map.get(s["symbol"], 0)
    except Exception as e:
        print(f"[ERROR] ticker fetch: {e}")
    
    # Sort by volume, take top N
    symbols = sorted(symbols, key=lambda x: x["quoteVolume"], reverse=True)
    limit = config.get("symbols_limit", 655)
    symbols = symbols[:limit]
    
    strategy_list = config.get("strategies", ["str1", "str2", "str3", "str4"])
    timeframes = config.get("timeframes", ["5m"])
    candles_limit = config.get("candles_limit", 250)
    monitor_limit = config.get("monitor_candles_limit", 250)
    max_workers = config.get("max_workers", 8)
    
    eq_state = apply_realized_pnl_to_equity()
    
    # ===== CANDLE CACHING: Async batch fetch for all symbols =====
    symbol_names = [s["symbol"] for s in symbols]
    print(f"[CACHE] Fetching candles for {len(symbol_names)} symbols (async)...")
    
    # Run async fetch in event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    cds_cache = loop.run_until_complete(
        fetch_candles_batch(client, symbol_names, "5m", monitor_limit, max_concurrent=20)
    )
    
    # Filter out symbols with insufficient data
    cds_cache = {sym: cds for sym, cds in cds_cache.items() if len(cds) >= 75}
    print(f"[CACHE] Cached {len(cds_cache)} symbols")
    
    for strategy_name in strategy_list:
        # Read risk from config.yaml (source of truth), fallback to strategy module
        strat_risk_pct = config.get("strategies_dict", {}).get(strategy_name, {}).get("risk_pct")
        if strat_risk_pct is None:
            strat_risk_pct = get_strategy_risk_pct(strategy_name)
        strat_risk_pct = float(strat_risk_pct)
        strat_risk_usd = eq_state["equity"] * strat_risk_pct
        
        mod = load_strategy(strategy_name)
        if not mod:
            continue
        
        for tf in timeframes:
            interval = tf
            
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futs = []
                for sym_info in symbols:
                    sym = sym_info["symbol"]
                    if sym not in cds_cache:
                        continue
                    futs.append(pool.submit(
                        _scan_symbol, mod, config, strategy_name, tf, interval,
                        candles_limit, monitor_limit, sym,
                        eq_state, strat_risk_pct, strat_risk_usd,
                        bot_token, channel_id, cds_cache[sym]
                    ))
                for f in futs:
                    try:
                        f.result()
                    except Exception as e:
                        print(f"[SCAN ERROR] {e}")


def _scan_symbol(mod, config, strategy_name, tf, interval, limit, monitor_limit,
                 sym, eq_state, strat_risk_pct, strat_risk_usd,
                 bot_token, channel_id, cds_full):
    """Scan single symbol for signals using pre-fetched candles."""
    strat_lock = _strategy_lock(strategy_name)
    
    try:
        if len(cds_full) < 75:
            return
        
        cds = cds_full[-limit:] if len(cds_full) > limit else cds_full
        offset = len(cds_full) - len(cds)
        
        last_closed_idx = len(cds) - 2
        pending_signals = []
        _sl_for_idx = {}
        
        cfg = mod.get_config() if hasattr(mod, "get_config") else {}
        lb = int(cfg.get("lookback", 10))
        scan_start = int(cfg.get("scan_start_idx", max(50, lb)))
        
        # Precompute indicators
        ind_cache = None
        if hasattr(mod, "compute_indicators"):
            try:
                c4 = mod.compute_indicators(cds)
                ind_cache = c4 if isinstance(c4, tuple) else None
            except Exception:
                ind_cache = None
        
        with strat_lock:
            if hasattr(mod, "reset_caches"):
                mod.reset_caches()
            
            for check_idx in range(scan_start, last_closed_idx + 1):
                sig_type = mod.detect(cds, check_idx, cfg, ind=ind_cache) if hasattr(mod, "detect") \
                    else mod.check_signal(cds, check_idx, cfg=cfg)
                if not sig_type:
                    continue
                
                entry_idx = check_idx
                if hasattr(mod, "_last_trigger_idx") and mod._last_trigger_idx is not None:
                    entry_idx = mod._last_trigger_idx + 1
                    _sl_for_idx[entry_idx] = getattr(mod, "_last_sl", None)
                
                if entry_idx >= len(cds) - 1:
                    continue
                
                pending_signals.append((entry_idx, sig_type))
        
        if not pending_signals:
            return
        
        for full_idx_scan, stype in pending_signals:
            try:
                full_idx = full_idx_scan
                e_candle = cds[full_idx]
                entry = cds[full_idx]["close"]
                
                # SL placement
                sl = None
                if hasattr(mod, "compute_sl_for"):
                    sl = _sl_for_idx.get(full_idx_scan)
                    if sl is None:
                        try:
                            atr_arr = ind_cache[2] if isinstance(ind_cache, tuple) and len(ind_cache) > 2 else None
                            sl_calc = mod.compute_sl_for(cds, full_idx, stype, cfg, atr_arr=atr_arr)
                            if isinstance(sl_calc, tuple):
                                sl = sl_calc[0]
                        except Exception:
                            sl = None
                if sl is None:
                    sl = compute_sl(cds, full_idx, stype, mode=cfg.get("sl_mode", "3candle"),
                                    atr_arr=ind_cache[2] if isinstance(ind_cache, tuple) and len(ind_cache) > 2 else None)
                
                # Direction guards
                if stype == "BUY" and sl >= entry:
                    sl = entry * 0.999
                if stype == "SELL" and sl <= entry:
                    sl = entry * 1.001
                
                risk = abs(entry - sl)
                
                # Distance filters
                min_dist_pct = cfg.get("min_dist_pct")
                if min_dist_pct is not None and risk / entry * 100 < min_dist_pct:
                    continue
                max_dist_pct = cfg.get("max_dist_pct")
                if max_dist_pct is not None and risk / entry * 100 > max_dist_pct:
                    continue
                
                # TP
                _rr_side = cfg.get("tp_rr_buy") if stype == "BUY" else cfg.get("tp_rr_sell")
                tp_rr = float(_rr_side if _rr_side is not None else cfg.get("tp_rr", 2.0))
                tp = entry + (risk * tp_rr) if stype == "BUY" else entry - (risk * tp_rr)
                open_time = cds[full_idx]["open_time"]
                
                with _POS_LOCK:
                    if find_by_signal_time(sym, stype, open_time):
                        continue
                
                # Result-first replay
                full_idx = full_idx_scan + offset
                strat_mod = importlib.import_module(f"strategies.{strategy_name}")
                if hasattr(strat_mod, "simulate_exit"):
                    rel_closed = cds_full[full_idx:-1]
                    final_state, exit_price, rel_exit_idx, half_done, events = \
                        strat_mod.simulate_exit(rel_closed, 0, stype, entry, sl, tp,
                                                [c.get("ma21") for c in rel_closed])
                    exit_idx = full_idx + rel_exit_idx
                    for ev in events:
                        ev["index"] = full_idx + ev["index"]
                else:
                    from .simulation import simulate_outcome_full as _sof
                    final_state, exit_price, exit_idx, half_done, events = _sof(
                        cds_full[:-1], full_idx, stype, entry, sl, tp,
                        [c.get("ma21") for c in cds_full[:-1]])
                
                with _POS_LOCK:
                    if find_by_signal_time(sym, stype, open_time):
                        continue
                    
                    # ===== MARGIN CHECK: Ensure position fits in available balance =====
                    # Get max leverage for this symbol
                    sym_info = next((s for s in symbols if s["symbol"] == sym), None)
                    max_leverage = sym_info.get("max_leverage", 20) if sym_info else 20
                    
                    # Calculate required margin (Cross Margin: notional / leverage)
                    notional = volume * entry
                    margin_required = notional / max_leverage
                    
                    # Available equity for margin (conservative: 90% of current equity)
                    available_margin = eq_state["equity"] * 0.9
                    
                    if margin_required > available_margin:
                        # Reduce volume to fit margin
                        max_volume = (available_margin * max_leverage) / entry
                        volume = min(volume, max_volume)
                        # Recalculate risk_usd with adjusted volume
                        strat_risk_usd = volume * risk
                        print(f"[MARGIN ADJUST] {sym} volume reduced to {volume:.6f} (margin: ${margin_required:.2f} > ${available_margin:.2f})")
                    
                    signal_id = next_id()
                    pos = {
                        "signal_id": signal_id, "symbol": sym, "type": stype,
                        "strategy": strategy_name, "timeframe": tf,
                        "entry": entry, "sl": round(sl, 8), "tp": round(tp, 8),
                        "signal_time": datetime.fromtimestamp(open_time/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                        "signal_open_time": open_time,
                        "status": final_state.upper(), "state": final_state,
                        "exit_price": exit_price, "half_vol_done": half_done,
                        "events": events, "index": full_idx,
                        "last_check_idx": exit_idx,
                        "equity": round(eq_state["equity"], 2),
                        "risk_pct": round(strat_risk_pct, 4),
                        "risk_usd": round(strat_risk_usd, 2),
                        "volume": round(volume, 6) if risk > 0 else 0,
                        "leverage_used": max_leverage,
                        "margin_required": round(margin_required, 2)
                    }
                    positions = load_pos()
                    positions.append(pos)
                    save_pos(positions)
                    
                    if final_state != "signal":
                        eq_state = apply_realized_pnl_to_equity()
                        pos["equity"] = round(eq_state["equity"], 2)
                        for p in positions:
                            if p["signal_id"] == signal_id:
                                p["equity"] = pos["equity"]
                                if "realized_pnl_usd" in p:
                                    pos["realized_pnl_usd"] = p["realized_pnl_usd"]
                                break
                        save_pos(positions)
                
                send_to_telegram(pos, cds_full, final_state, events, is_update=False,
                                 bot_token=bot_token, channel_id=channel_id)
                print(f"[SIGNAL] #{signal_id} {sym} {stype} -> {final_state}")
                
            except Exception as e:
                print(f"[SCAN ERROR] {sym} signal@{full_idx_scan}: {e}")
    
    except Exception as e:
        print(f"[SCAN ERROR] {sym} {tf}: {e}")


# ===== Async Version (for candle-aligned main loop) =====

async def detect_new_signals_async(config, bot_token, channel_id, client, scanner_cfg):
    """Async main detection loop - uses async batch fetch."""
    # Get symbols with leverage > min_leverage (sync, uses requests)
    symbols = get_symbols_with_leverage(client, scanner_cfg.get("min_leverage", 10))

    # Get 24hr tickers for volume sorting (sync)
    try:
        tickers = client.get_24hr_ticker_sync()
        ticker_map = {t["s"]: float(t.get("qv", 0)) for t in tickers}
        for s in symbols:
            s["quoteVolume"] = ticker_map.get(s["symbol"], 0)
    except Exception as e:
        print(f"[ERROR] ticker fetch: {e}")

    # Sort by volume, take top N
    symbols = sorted(symbols, key=lambda x: x["quoteVolume"], reverse=True)
    limit = config.get("symbols_limit", 655)
    symbols = symbols[:limit]

    strategy_list = config.get("strategies", ["str1", "str2", "str3", "str4"])
    timeframes = config.get("timeframes", ["5m"])
    candles_limit = config.get("candles_limit", 250)
    monitor_limit = config.get("monitor_candles_limit", 250)
    max_workers = config.get("max_workers", 8)

    eq_state = apply_realized_pnl_to_equity()

    # ===== CANDLE CACHING: Async batch fetch for all symbols =====
    symbol_names = [s["symbol"] for s in symbols]
    print(f"[CACHE] Fetching candles for {len(symbol_names)} symbols (async)...")

    cds_cache = await fetch_candles_batch(
        client, symbol_names, "5m", monitor_limit, max_concurrent=20
    )

    # Filter out symbols with insufficient data
    cds_cache = {sym: cds for sym, cds in cds_cache.items() if len(cds) >= 75}
    print(f"[CACHE] Cached {len(cds_cache)} symbols")

    for strategy_name in strategy_list:
        # Read risk from config.yaml (source of truth), fallback to strategy module
        strat_risk_pct = config.get("strategies_dict", {}).get(strategy_name, {}).get("risk_pct")
        if strat_risk_pct is None:
            strat_risk_pct = get_strategy_risk_pct(strategy_name)
        strat_risk_pct = float(strat_risk_pct)
        strat_risk_usd = eq_state["equity"] * strat_risk_pct

        mod = load_strategy(strategy_name)
        if not mod:
            continue

        for tf in timeframes:
            interval = tf

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futs = []
                for sym_info in symbols:
                    sym = sym_info["symbol"]
                    if sym not in cds_cache:
                        continue
                    futs.append(pool.submit(
                        _scan_symbol, mod, config, strategy_name, tf, interval,
                        candles_limit, monitor_limit, sym,
                        eq_state, strat_risk_pct, strat_risk_usd,
                        bot_token, channel_id, cds_cache[sym]
                    ))
                for f in futs:
                    try:
                        f.result()
                    except Exception as e:
                        print(f"[SCAN ERROR] {e}")
