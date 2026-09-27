"""Toobit REST API client with async support for public endpoints."""
import time
import hmac
import hashlib
import asyncio
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

import aiohttp
import requests


class ToobitClient:
    """REST API client for Toobit USDT-M futures.
    
    Uses aiohttp for public endpoints (async, high concurrency)
    and requests for private endpoints (sync, low frequency).
    """
    
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://api.toobit.com"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        
        # Sync session for private/signed endpoints (low frequency)
        self._sync_session = requests.Session()
        self._sync_session.headers.update({"X-BB-APIKEY": self.api_key})
        
        # Async session for public endpoints (high frequency)
        self._async_session: Optional[aiohttp.ClientSession] = None
        self._async_connector: Optional[aiohttp.TCPConnector] = None
        self._async_lock = asyncio.Lock()
    
    # ===== Sync Methods (Private/Signed) =====
    
    def _sign(self, query_string: str) -> str:
        """HMAC-SHA256 signature."""
        return hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
    
    def _request(self, method: str, path: str, params: Optional[Dict] = None, signed: bool = False) -> Any:
        """Make synchronous API request."""
        url = f"{self.base_url}{path}"
        if params is None:
            params = {}
        
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 60000
            query = urlencode(sorted(params.items()))
            params["signature"] = self._sign(query)
        
        resp = self._sync_session.request(method, url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    
    # --- Private Endpoints (Signed) ---
    
    def get_account_info(self) -> Dict:
        """GET /api/v1/account/info - Account balance."""
        return self._request("GET", "/api/v1/account/info", signed=True)
    
    def get_position(self, symbol: Optional[str] = None) -> List[Dict]:
        """GET /api/v1/futures/position - Open positions."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v1/futures/position", params=params or None, signed=True)
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """GET /api/v1/futures/openOrders - All open orders."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v1/futures/openOrders", params=params or None, signed=True)
    
    def get_all_orders(self, symbol: str, **kwargs) -> List[Dict]:
        """GET /api/v1/futures/allOrders - Historical orders."""
        params = {"symbol": symbol, **kwargs}
        return self._request("GET", "/api/v1/futures/allOrders", params=params, signed=True)
    
    def get_balance_flow(self, **kwargs) -> List[Dict]:
        """GET /api/v1/account/balanceFlow - Fund transfer history."""
        return self._request("GET", "/api/v1/account/balanceFlow", params=kwargs or None, signed=True)
    
    def get_commission_rate(self, symbol: str) -> Dict:
        """GET /api/v1/futures/commissionRate - Trade fee rate."""
        return self._request("GET", "/api/v1/futures/commissionRate", params={"symbol": symbol}, signed=True)
    
    def get_today_pnl(self) -> Dict:
        """GET /api/v1/futures/todayPnl - Today's PnL (UTC+0)."""
        return self._request("GET", "/api/v1/futures/todayPnl", signed=True)
    
    def get_my_trades(self, symbol: str, **kwargs) -> List[Dict]:
        """GET /api/v1/futures/myTrades - User's trade history."""
        params = {"symbol": symbol, **kwargs}
        return self._request("GET", "/api/v1/futures/myTrades", params=params, signed=True)
    
    # --- Trading Endpoints ---
    
    def new_order(self, symbol: str, side: str, order_type: str, quantity: float,
                  price: Optional[float] = None, price_type: str = "INPUT",
                  stop_price: Optional[float] = None, time_in_force: str = "GTC",
                  new_client_order_id: Optional[str] = None,
                  take_profit: Optional[float] = None, stop_loss: Optional[float] = None,
                  tp_trigger_by: str = "CONTRACT_PRICE", sl_trigger_by: str = "CONTRACT_PRICE",
                  tp_order_type: str = "MARKET", sl_order_type: str = "MARKET",
                  tp_limit_price: Optional[float] = None, sl_limit_price: Optional[float] = None) -> Dict:
        """POST /api/v1/futures/order - Place new order."""
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "priceType": price_type,
            "timeInForce": time_in_force,
            "newClientOrderId": new_client_order_id or f"tbb_{int(time.time()*1000)}",
        }
        if price is not None:
            params["price"] = price
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if take_profit is not None:
            params["takeProfit"] = take_profit
        if stop_loss is not None:
            params["stopLoss"] = stop_loss
        params["tpTriggerBy"] = tp_trigger_by
        params["slTriggerBy"] = sl_trigger_by
        params["tpOrderType"] = tp_order_type
        params["slOrderType"] = sl_order_type
        if tp_limit_price is not None:
            params["tpLimitPrice"] = tp_limit_price
        if sl_limit_price is not None:
            params["slLimitPrice"] = sl_limit_price
        return self._request("POST", "/api/v1/futures/order", params=params, signed=True)
    
    def cancel_order(self, symbol: str, order_id: Optional[str] = None,
                     orig_client_order_id: Optional[str] = None) -> Dict:
        """POST /api/v1/futures/order/cancel - Cancel order."""
        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        return self._request("POST", "/api/v1/futures/order/cancel", params=params, signed=True)
    
    def cancel_all_orders(self, symbol: str) -> Dict:
        """POST /api/v1/futures/order/cancelAll - Cancel all orders for symbol."""
        return self._request("POST", "/api/v1/futures/order/cancelAll", params={"symbol": symbol}, signed=True)
    
    def query_order(self, symbol: str, order_id: Optional[str] = None,
                    orig_client_order_id: Optional[str] = None) -> Dict:
        """GET /api/v1/futures/order - Query order."""
        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        return self._request("GET", "/api/v1/futures/order", params=params, signed=True)
    
    def modify_order(self, **kwargs) -> Dict:
        """POST /api/v1/futures/order/update - Modify order."""
        return self._request("POST", "/api/v1/futures/order/update", params=kwargs, signed=True)
    
    # --- Leverage & Margin ---
    
    def change_leverage(self, symbol: str, leverage: int) -> Dict:
        """POST /api/v1/futures/leverage - Adjust leverage."""
        return self._request("POST", "/api/v1/futures/leverage", params={
            "symbol": symbol,
            "leverage": leverage
        }, signed=True)
    
    def change_margin_type(self, symbol: str, margin_type: str) -> Dict:
        """POST /api/v1/futures/marginType - Change margin mode (CROSS/ISOLATED)."""
        return self._request("POST", "/api/v1/futures/marginType", params={
            "symbol": symbol,
            "marginType": margin_type
        }, signed=True)
    
    def get_leverage_and_margin_type(self, symbol: str) -> List[Dict]:
        """GET /api/v1/futures/accountLeverage - Get leverage and margin mode."""
        return self._request("GET", "/api/v1/futures/accountLeverage", params={"symbol": symbol}, signed=True)
    
    # --- ListenKey (WebSocket) ---
    
    def create_listen_key(self) -> str:
        """POST /api/v1/listenKey - Start user data stream."""
        result = self._request("POST", "/api/v1/listenKey", signed=True)
        return result.get("listenKey", "")
    
    def keepalive_listen_key(self, listen_key: str) -> Dict:
        """PUT /api/v1/listenKey - Keepalive user data stream."""
        return self._request("PUT", "/api/v1/listenKey", params={"listenKey": listen_key}, signed=True)
    
    def close_listen_key(self, listen_key: str) -> Dict:
        """DELETE /api/v1/listenKey - Close user data stream."""
        return self._request("DELETE", "/api/v1/listenKey", params={"listenKey": listen_key}, signed=True)
    
    # ===== Async Methods (Public Endpoints) =====
    
    async def _get_async_session(self) -> aiohttp.ClientSession:
        """Get or create async session with connection pooling."""
        if self._async_session is None or self._async_session.closed:
            async with self._async_lock:
                if self._async_session is None or self._async_session.closed:
                    self._async_connector = aiohttp.TCPConnector(
                        limit=20,           # Max concurrent connections
                        limit_per_host=20,  # Per-host limit
                        ttl_dns_cache=300,  # DNS cache TTL
                        keepalive_timeout=30,
                        enable_cleanup_closed=True
                    )
                    self._async_session = aiohttp.ClientSession(
                        connector=self._async_connector,
                        headers={"X-BB-APIKEY": self.api_key},
                        timeout=aiohttp.ClientTimeout(total=15, connect=5)
                    )
        return self._async_session
    
    async def _async_request(self, method: str, path: str, params: Optional[Dict] = None) -> Any:
        """Make asynchronous API request (public endpoints only, no signature)."""
        session = await self._get_async_session()
        url = f"{self.base_url}{path}"
        if params is None:
            params = {}
        
        async with session.request(method, url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    # --- Public Endpoints (Async) ---
    
    async def get_server_time(self) -> int:
        """GET /api/v1/time"""
        return await self._async_request("GET", "/api/v1/time")
    
    async def get_exchange_info(self) -> Dict:
        """GET /api/v1/exchangeInfo - All trading rules and symbol info."""
        return await self._async_request("GET", "/api/v1/exchangeInfo")
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 250) -> List[List]:
        """GET /quote/v1/klines - OHLCV candlestick data."""
        return await self._async_request("GET", "/quote/v1/klines", params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        })
    
    async def get_depth(self, symbol: str, limit: int = 100) -> Dict:
        """GET /quote/v1/depth - Order book."""
        return await self._async_request("GET", "/quote/v1/depth", params={
            "symbol": symbol,
            "limit": limit
        })
    
    async def get_24hr_ticker(self, symbol: Optional[str] = None) -> Any:
        """GET /quote/v1/contract/ticker/24hr"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._async_request("GET", "/quote/v1/contract/ticker/24hr", params=params or None)
    
    async def get_symbol_price(self, symbol: str) -> Dict:
        """GET /quote/v1/contract/ticker/price - Latest price."""
        return await self._async_request("GET", "/quote/v1/contract/ticker/price", params={"symbol": symbol})
    
    async def get_index_price(self, symbol: Optional[str] = None) -> Dict:
        """GET /quote/v1/index - Index price."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._async_request("GET", "/quote/v1/index", params=params or None)
    
    async def get_risk_limits(self, symbol: str) -> List[Dict]:
        """GET /api/v1/futures/riskLimits - Risk limits for a symbol."""
        return await self._async_request("GET", "/api/v1/futures/riskLimits", params={"symbol": symbol})
    
    # ===== Batch Operations (Async) =====
    
    async def fetch_multiple_klines(self, symbols: List[str], interval: str = "5m", limit: int = 250,
                                    max_concurrent: int = 20) -> Dict[str, List[List]]:
        """Fetch klines for multiple symbols concurrently with semaphore limiting."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_one(sym: str):
            async with semaphore:
                try:
                    data = await self.get_klines(sym, interval, limit)
                    return sym, data
                except Exception as e:
                    return sym, e
        
        tasks = [fetch_one(sym) for sym in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        output = {}
        for r in results:
            if isinstance(r, Exception):
                continue
            sym, data = r
            if isinstance(data, Exception):
                continue
            output[sym] = data
        return output
    
    async def close(self):
        """Close async session and connector."""
        if self._async_session and not self._async_session.closed:
            await self._async_session.close()
        if self._async_connector and not self._async_connector.closed:
            await self._async_connector.close()
        self._async_session = None
        self._async_connector = None
    
    def close_sync(self):
        """Sync wrapper for close()."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            # Can't run_until_complete on running loop, schedule instead
            import warnings
            warnings.warn("close_sync called on running loop, cleanup may be incomplete")
            return
        loop.run_until_complete(self.close())
    
    def __del__(self):
        # Cleanup sync session
        if hasattr(self, '_sync_session'):
            self._sync_session.close()


# ===== Backward Compatibility Sync Wrappers (using requests directly) =====

    # These sync versions use requests directly for thread-safety
    # Used by legacy code that hasn't been migrated yet
    
    def get_exchange_info_sync(self) -> Dict:
        """Sync version using requests directly."""
        return self._request("GET", "/api/v1/exchangeInfo")
    
    def get_klines_sync(self, symbol: str, interval: str, limit: int = 250) -> List[List]:
        """Sync version using requests directly."""
        return self._request("GET", "/quote/v1/klines", params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        })
    
    def get_24hr_ticker_sync(self, symbol: Optional[str] = None) -> Any:
        """Sync version using requests directly."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/quote/v1/contract/ticker/24hr", params=params or None)
    
    def get_symbol_price_sync(self, symbol: str) -> Dict:
        """Sync version using requests directly."""
        return self._request("GET", "/quote/v1/contract/ticker/price", params={"symbol": symbol})
    
    def get_index_price_sync(self, symbol: Optional[str] = None) -> Dict:
        """Sync version using requests directly."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/quote/v1/index", params=params or None)
    
    def get_risk_limits_sync(self, symbol: str) -> List[Dict]:
        """Sync version using requests directly."""
        return self._request("GET", "/api/v1/futures/riskLimits", params={"symbol": symbol})
    
    # For backward compatibility - alias old method names to sync wrappers
    # NOTE: async methods keep their original names (get_exchange_info, get_klines, get_24hr_ticker)
    # These aliases are for external code that expects the old sync interface
    get_exchange_info_legacy = get_exchange_info_sync
    get_klines_legacy = get_klines_sync
    get_24hr_ticker_legacy = get_24hr_ticker_sync