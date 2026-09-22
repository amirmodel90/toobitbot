"""Toobit REST API client."""
import time
import hmac
import hashlib
import requests
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode


class ToobitClient:
    """REST API client for Toobit USDT-M futures."""

    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://api.toobit.com"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"X-BB-APIKEY": self.api_key})

    def _sign(self, query_string: str) -> str:
        """HMAC-SHA256 signature."""
        return hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, path: str, params: Optional[Dict] = None, signed: bool = False) -> Any:
        """Make API request."""
        url = f"{self.base_url}{path}"
        if params is None:
            params = {}
        
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 60000
            query = urlencode(sorted(params.items()))
            params["signature"] = self._sign(query)
        
        resp = self.session.request(method, url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # === Public Endpoints (No signature) ===

    def get_server_time(self) -> int:
        """GET /api/v1/time"""
        return self._request("GET", "/api/v1/time")

    def get_exchange_info(self) -> Dict:
        """GET /api/v1/exchangeInfo - All trading rules and symbol info."""
        return self._request("GET", "/api/v1/exchangeInfo")

    def get_klines(self, symbol: str, interval: str, limit: int = 250) -> List[List]:
        """GET /quote/v1/klines - OHLCV candlestick data."""
        return self._request("GET", "/quote/v1/klines", params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        })

    def get_depth(self, symbol: str, limit: int = 100) -> Dict:
        """GET /quote/v1/depth - Order book."""
        return self._request("GET", "/quote/v1/depth", params={
            "symbol": symbol,
            "limit": limit
        })

    def get_24hr_ticker(self, symbol: Optional[str] = None) -> Any:
        """GET /quote/v1/contract/ticker/24hr"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/quote/v1/contract/ticker/24hr", params=params or None)

    def get_symbol_price(self, symbol: str) -> Dict:
        """GET /quote/v1/contract/ticker/price - Latest price."""
        return self._request("GET", "/quote/v1/contract/ticker/price", params={"symbol": symbol})

    def get_index_price(self, symbol: Optional[str] = None) -> Dict:
        """GET /quote/v1/index - Index price."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/quote/v1/index", params=params or None)

    def get_risk_limits(self, symbol: str) -> List[Dict]:
        """GET /api/v1/futures/riskLimits - Risk limits for a symbol."""
        return self._request("GET", "/api/v1/futures/riskLimits", params={"symbol": symbol})

    # === Private Endpoints (Signed) ===

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

    # === Trading Endpoints ===

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

    # === Leverage & Margin ===

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

    # === ListenKey (WebSocket) ===

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
