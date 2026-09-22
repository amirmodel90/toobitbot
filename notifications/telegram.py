"""Telegram notifications for ToobitBot."""
import requests
from pathlib import Path
from typing import Dict, List, Optional


def send_to_telegram(
    pos: Dict,
    cds: List[Dict],
    state: str,
    events: List[Dict],
    is_update: bool = False,
    bot_token: Optional[str] = None,
    channel_id: Optional[str] = None,
    chart_dir: Optional[Path] = None,
    generate_chart_fn=None
) -> bool:
    """Send chart + caption to Telegram channel (SignalTel format)."""
    if chart_dir is None:
        chart_dir = Path("/home/hermes/toobitbot/charts")
    chart_dir.mkdir(parents=True, exist_ok=True)
    
    if generate_chart_fn is None:
        from .chart_gen import generate_chart
        generate_chart_fn = generate_chart
    
    cp = generate_chart_fn(pos, cds, state, events, is_update, chart_dir=chart_dir)
    
    emoji_map = {
        "signal": "🔔", "sl_hit": "❌", "tp_hit": "🎯",
        "be_exit": "🛡️", "ma_exit": "📊", "sl_hit_remaining": "❌",
        "ma_half_exit": "🔷"
    }
    
    path_summary = "\n".join([
        f"• {e['type'].upper()} @ ${e['price']:.4f}" for e in events
    ]) or "• OPEN (Signal)"
    
    # Title logic — the closing event wins
    last_event = events[-1]["type"] if events else None
    ma_done = any(e["type"] in ("ma_half_exit", "ma_exit") for e in events)
    
    if last_event == "tp_hit":
        status_title = "🎯 TP HIT"
    elif last_event == "sl_hit":
        status_title = "❌ SL HIT"
    elif last_event == "be_exit":
        status_title = "🛡️ BE EXIT"
    elif last_event == "ma_exit":
        status_title = "📊 MA EXIT"
    elif state == "signal" and last_event == "tp_hit":
        status_title = "🎯 TP HIT — OPEN (SL→BE)"
    elif state == "signal" and ma_done:
        status_title = "🔷 MA EXIT 50% — OPEN"
    else:
        status_title = "🔔 SIGNAL"
    
    # Position sizing
    risk_usd = pos.get("risk_usd", 9.0)
    entry = pos["entry"]
    sl = pos["sl"]
    tp = pos["tp"]
    stype = pos["type"]
    risk_per_unit = abs(entry - sl)
    
    pos_summary = ""
    equity_usd = pos.get("equity", 100.0)
    if risk_per_unit > 0:
        volume = pos.get("volume", risk_usd / risk_per_unit)
        
        def pnl_usd(price):
            if stype == "BUY":
                return (price - entry) * volume
            else:
                return (entry - price) * volume
        
        tp_usd = pnl_usd(tp)
        sl_usd = pnl_usd(sl)
        ma_usd = None
        
        exit_prices = {}
        for e in events:
            exit_prices.setdefault(e["type"], e["price"])
        
        ma_price = exit_prices.get("ma_exit") or exit_prices.get("ma_half_exit")
        ma_half = any(e["type"] == "ma_half_exit" for e in events)
        if ma_price:
            ma_usd = pnl_usd(ma_price)
        
        pos_summary = (
            f"💼 Volume: <code>{volume:.2f} {pos['symbol'].replace('-SWAP-USDT','')}</code>\n"
            f"💰 Risk/Trade: <code>${risk_usd:.2f}</code>\n"
            f"📈 Equity: <code>${equity_usd:.2f}</code>\n"
            f"🎯 TP → <code>+${tp_usd:.2f}</code>\n"
            f"🛑 SL → <code>{sl_usd:+.2f}</code>\n"
            f"🛡️ BE → <code>$0.00</code>\n"
        )
        if ma_usd is not None:
            label = "MA ½ (half closed)" if ma_half else "MA"
            pos_summary += f"📊 {label} → <code>{ma_usd:+.2f}</code>\n"
    
    # Realized net PnL
    if state != "signal" and pos.get("realized_pnl_usd") is not None:
        _net = pos["realized_pnl_usd"]
        _fee = pos.get("fee_usd", 0.0)
        pos_summary += (
            f"\n<b>✅ Realized: <code>{_net:+.2f}$</code> "
            f"(fee −{_fee:.2f}$)</b>\n"
        )
    
    cap = (
        f"{emoji_map.get(state, '🔹')} <b>{status_title} | #{pos['symbol']} (#s{pos['signal_id']})</b>\n\n"
        f"📈 Strategy: <code>{pos['strategy']} ({pos['timeframe']})</code>\n"
        f"🔤 Type: <code>{stype}</code>\n"
        f"💵 Entry: <code>${entry:.4f}</code>\n"
        f"🛑 Stop Loss: <code>${sl:.4f}</code>\n"
        f"🎯 Take Profit: <code>${tp:.4f}</code>\n"
        f"📍 Status: <code>{state.upper()}</code>\n\n"
        f"<b>💰 Position & PnL ($):</b>\n{pos_summary}\n"
        f"<b>Events / Path:</b>\n{path_summary}\n\n"
        f"🕒 Time: {pos['signal_time']}"
    )
    
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    with open(cp, "rb") as f:
        r = requests.post(
            url,
            data={"chat_id": channel_id, "caption": cap, "parse_mode": "HTML"},
            files={"photo": f},
            timeout=15
        )
    try:
        res = r.json()
        if res.get("ok"):
            msg = res.get("result", {})
            print(f"[TELEGRAM OK] message_id={msg.get('message_id')} chat={msg.get('chat', {}).get('id')}")
            return True
        print(f"[TELEGRAM ERROR] {res}")
        return False
    except Exception as e:
        print(f"[TELEGRAM ERROR] HTTP {r.status_code}: {e}")
        return False


def send_text_message(bot_token: str, channel_id: str, text: str) -> bool:
    """Send plain text message to Telegram."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": channel_id,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=15)
        return r.json().get("ok", False)
    except Exception as e:
        print(f"[TELEGRAM TEXT ERROR] {e}")
        return False
