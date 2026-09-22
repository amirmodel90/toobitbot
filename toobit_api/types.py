"""Toobit API type definitions."""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    ma21: Optional[float] = None


@dataclass
class SymbolInfo:
    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    contract_multiplier: float
    max_leverage: float
    risk_limits: List[Dict[str, Any]]


@dataclass
class Position:
    signal_id: int
    symbol: str
    type: str  # BUY or SELL
    strategy: str
    timeframe: str
    entry: float
    sl: float
    tp: float
    signal_time: str
    signal_open_time: int
    status: str
    state: str
    exit_price: Optional[float]
    half_vol_done: bool
    events: List[Dict]
    index: int
    last_check_idx: int
    equity: float
    risk_pct: float
    risk_usd: float
    volume: float


@dataclass
class OrderResult:
    order_id: str
    client_order_id: str
    symbol: str
    price: float
    leverage: float
    orig_qty: float
    executed_qty: float
    avg_price: float
    margin_locked: float
    type: str
    side: str
    time_in_force: str
    status: str


@dataclass
class Balance:
    asset: str
    free: float
    locked: float
