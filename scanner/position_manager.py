#!/usr/local/bin/python3
"""
Position manager module for SignalTel Scanner.
"""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
DATA_DIR = SCRIPT_DIR / "data"
POS_FILE = DATA_DIR / "positions.json"
ID_FILE = DATA_DIR / "next_id.txt"
EQUITY_FILE = DATA_DIR / "equity.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_pos():
    try:
        data = json.loads(POS_FILE.read_text()) if POS_FILE.exists() else []
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_pos(positions):
    POS_FILE.write_text(json.dumps(positions, indent=4))


def next_id():
    try:
        n = int(ID_FILE.read_text().strip())
    except Exception:
        n = 1
    ID_FILE.write_text(str(n + 1))
    return n


def update_position(signal_id, updates):
    positions = load_pos()
    for p in positions:
        if p.get("signal_id") == signal_id:
            p.update(updates)
            save_pos(positions)
            return p
    return None


# ---------------------------------------------------------------------------
# Equity tracking
# ---------------------------------------------------------------------------
DEFAULT_START_EQUITY = 100.0

# Fee model (user 2026-09-12): 0.045% charged on EVERY fill's notional —
# entry fill + each exit fill. str4's MA half-exit closes TWO legs (half at
# the MA-cross price, the rest at the final exit price) → 3 fills total.
FEE_RATE = 0.00045


def position_fee_usd(pos):
    """Total round-trip fee ($) for a position under the 0.045%-per-fill model."""
    entry = pos.get("entry")
    if entry is None:
        return 0.0
    # Same volume basis as position_equity_pnl (risk_usd / risk-per-unit) so
    # fee and PnL can never diverge on inconsistent data; stored volume is
    # only a fallback for legacy rows without risk_usd/sl.
    volume = None
    sl = pos.get("sl")
    rpu = abs(entry - sl) if sl else 0
    if rpu > 0 and pos.get("risk_usd"):
        volume = pos["risk_usd"] / rpu
    if not volume:
        volume = pos.get("volume")
    if not volume:
        return 0.0
    exit_price = pos.get("exit_price")
    if exit_price is None:
        return 0.0
    half_price = next((e["price"] for e in pos.get("events", [])
                       if e.get("type") == "ma_half_exit"), None)
    if half_price is not None:
        fills = [(entry, volume),
                 (half_price, volume * 0.5),
                 (exit_price, volume * 0.5)]
    else:
        fills = [(entry, volume), (exit_price, volume)]
    return FEE_RATE * sum(abs(price) * qty for price, qty in fills)


def get_strategy_risk_pct(strategy_name):
    """
    Read per-strategy risk_pct (fraction of equity risked per trade) from the
    strategy module's get_config(). Falls back to DEFAULT_RISK_PCT if the
    module/config doesn't define one.
    """
    try:
        mod = __import__(f"strategies.{strategy_name}", fromlist=["get_config"])
        cfg = mod.get_config() if hasattr(mod, "get_config") else {}
        return float(cfg.get("risk_pct", DEFAULT_RISK_PCT))
    except Exception:
        return DEFAULT_RISK_PCT


DEFAULT_RISK_PCT = 0.09  # legacy fallback (9%)


def load_equity():
    """Load equity state: {'equity': float, 'risk_usd': float, 'start': float}"""
    try:
        data = json.loads(EQUITY_FILE.read_text()) if EQUITY_FILE.exists() else {}
        return {
            "equity": float(data.get("equity", DEFAULT_START_EQUITY)),
            "risk_pct": float(data.get("risk_pct", DEFAULT_RISK_PCT)),
            "risk_usd": float(data.get("risk_usd",
                                       DEFAULT_START_EQUITY * data.get("risk_pct", DEFAULT_RISK_PCT))),
            "start": float(data.get("start", DEFAULT_START_EQUITY)),
        }
    except Exception:
        return {
            "equity": DEFAULT_START_EQUITY,
            "risk_pct": DEFAULT_RISK_PCT,
            "risk_usd": DEFAULT_START_EQUITY * DEFAULT_RISK_PCT,
            "start": DEFAULT_START_EQUITY,
        }


def save_equity(equity_state):
    EQUITY_FILE.write_text(json.dumps(equity_state, indent=4))


def get_current_equity():
    """Return current equity balance."""
    return load_equity()["equity"]


def update_equity_from_position(pos):
    """
    After a position closes (state != 'signal'), update equity by its realized PnL.
    Also recompute risk_usd for the NEXT trade = 9% of current equity.
    Returns the updated equity state.
    """
    eq = load_equity()

    # Ignore positions with no realized PnL (open signals)
    if pos.get("state") in ("signal", None):
        return eq

    # Use stored realized_pnl_usd if present, else compute from exit vs entry
    pnl_usd = pos.get("realized_pnl_usd")
    if pnl_usd is None:
        entry = pos.get("entry")
        exit_price = pos.get("exit_price")
        if entry is None or exit_price is None:
            return eq
        volume = pos.get("volume")
        if volume is None:
            # Recompute from stored risk amount if available
            risk_usd = pos.get("risk_usd", eq["risk_usd"])
            risk_per_unit = abs(entry - pos.get("sl", entry))
            volume = risk_usd / risk_per_unit if risk_per_unit > 0 else 0
        stype = pos.get("type")
        if stype == "BUY":
            pnl_usd = (exit_price - entry) * volume
        else:
            pnl_usd = (entry - exit_price) * volume

    pnl_usd -= position_fee_usd(pos)  # NET of 0.045%-per-fill fees (user 09-12)
    eq["equity"] += pnl_usd
    # Risk for next trade = risk_pct (per-strategy) of current equity
    eq["risk_usd"] = eq["equity"] * get_strategy_risk_pct(pos.get("strategy", ""))
    save_equity(eq)
    return eq


def position_equity_pnl(pos):
    """
    Compute the realized PnL ($) for a position based on its exit state.
    Handles states: sl_hit, be_exit, ma_exit, tp_hit, ma_half_exit.
    For ma_half_exit (str4 50% partial exit): realized = 50% closed at the
    ma_half_exit price + 50% still open (counts only when the position CLOSES —
    the open half's PnL is added at final close via the remaining-half logic).
    """
    entry = pos.get("entry")
    exit_price = pos.get("exit_price")
    state = pos.get("state")
    if entry is None or exit_price is None:
        return 0.0

    risk_usd = pos.get("risk_usd", load_equity()["risk_usd"])
    sl = pos.get("sl")
    risk_per_unit = abs(entry - sl) if sl else abs(entry - exit_price)
    if risk_per_unit <= 1e-12:
        return 0.0
    volume = risk_usd / risk_per_unit

    stype = pos.get("type")

    def dir_pnl(price):
        if stype == "BUY":
            return (price - entry) * volume
        return (entry - price) * volume

    events = pos.get("events", [])
    half_price = next((e["price"] for e in events
                       if e.get("type") == "ma_half_exit"), None)
    half_frac = 0.5 if half_price is not None else 0.0
    rem_frac = 1.0 - half_frac

    if state == "sl_hit":
        # str4 MA-half: 50% was closed at the MA-cross price, remaining 50% at SL.
        # Realized = half*dir_pnl(ma_price) + rem*(-risk_usd). Mirrors engine blend.
        if half_price is not None:
            pnl = half_frac * dir_pnl(half_price) + rem_frac * (-risk_usd)
        else:
            pnl = -risk_usd  # exact -R
    elif state == "be_exit":
        pnl = 0.0
    elif state == "ma_half_exit":
        # str4 50% partial exit: half realized at the MA-cross price NOW,
        # the other half realized at the final close price (exit_price).
        pnl = 0.5 * dir_pnl(half_price or exit_price) + 0.5 * dir_pnl(exit_price)
    elif state == "ma_exit":
        pnl = dir_pnl(exit_price)
    elif state == "tp_hit":
        # str4 MA-half: half at MA-cross price, remaining at TP.
        if half_price is not None:
            pnl = half_frac * dir_pnl(half_price) + rem_frac * dir_pnl(exit_price)
        else:
            pnl = dir_pnl(exit_price)
    else:
        pnl = 0.0
    return pnl


def apply_realized_pnl_to_equity():
    """
    Scan all positions; for any CLOSED position not yet flagged (equity_applied != True),
    apply its realized PnL to equity and mark it.
    Called once per scan tick.
    """
    positions = load_pos()
    eq = load_equity()
    changed = False

    for p in positions:
        if p.get("state") == "signal":
            continue
        if p.get("equity_applied"):
            continue

        pnl = position_equity_pnl(p)
        fee = position_fee_usd(p)
        pnl_net = pnl - fee
        eq["equity"] += pnl_net
        # Next-trade risk follows the strategy that just closed this position
        eq["risk_pct"] = get_strategy_risk_pct(p.get("strategy", ""))
        eq["risk_usd"] = eq["equity"] * eq["risk_pct"]

        # Store realized PnL (NET of fees) + the fee itself + volume on the position
        p["fee_usd"] = round(fee, 2)
        p["realized_pnl_gross_usd"] = round(pnl, 2)
        p["realized_pnl_usd"] = round(pnl_net, 2)
        p["equity_applied"] = True

        # Also stamp the volume/risk used for this trade
        if "volume" not in p:
            sl = p.get("sl")
            entry = p.get("entry")
            risk_per_unit = abs(entry - sl) if sl and entry else 0
            p["volume"] = round(eq["risk_usd"] / risk_per_unit, 6) if risk_per_unit > 0 else 0
        if "risk_usd" not in p:
            p["risk_usd"] = round(eq["risk_usd"], 2)

        changed = True

    if changed:
        save_pos(positions)
        save_equity(eq)

    return eq