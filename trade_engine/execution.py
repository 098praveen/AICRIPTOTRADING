"""
Trade Execution Engine
Handles order placement, exchange communication, and execution logic.
"""
from datetime import datetime, timezone

class TradeExecutionEngine:
    """
    Executes trades on supported exchanges using ccxt or other APIs.
    """

    def __init__(self, exchange_clients, paper_trading=True, default_fee_bps=10.0, slippage_bps=5.0):
        """
        Initialize with exchange API clients.
        """
        self.exchange_clients = exchange_clients or {}
        self.paper_trading = paper_trading
        self.default_fee_bps = float(default_fee_bps)
        self.slippage_bps = float(slippage_bps)
        self.orders = []

    def execute_order(self, exchange_name, symbol, side, amount, order_type="market", **kwargs):
        """
        Place an order on the specified exchange.
        Returns: order confirmation or error.
        """
        if amount <= 0:
            return {"status": "rejected", "reason": "amount must be greater than zero"}

        side = side.lower()
        if side not in {"buy", "sell"}:
            return {"status": "rejected", "reason": "side must be buy or sell"}

        exchange = self.exchange_clients.get(exchange_name)
        if not self.paper_trading and exchange:
            create_order = getattr(exchange, "create_order", None)
            if not callable(create_order):
                return {"status": "rejected", "reason": "exchange client has no create_order method"}
            return create_order(symbol, order_type, side, amount, kwargs.get("price"), kwargs)

        reference_price = float(kwargs.get("price") or kwargs.get("last") or 0)
        if reference_price <= 0:
            return {"status": "rejected", "reason": "paper trading requires a reference price"}

        slippage_multiplier = 1 + (self.slippage_bps / 10000) if side == "buy" else 1 - (self.slippage_bps / 10000)
        fill_price = reference_price * slippage_multiplier
        notional = fill_price * amount
        fee = notional * (float(kwargs.get("fee_bps", self.default_fee_bps)) / 10000)
        order = {
            "id": f"paper-{len(self.orders) + 1}",
            "exchange": exchange_name,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": amount,
            "requested_price": reference_price,
            "price": fill_price,
            "fee": fee,
            "notional": notional,
            "status": "filled",
            "paper": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.orders.append(order)
        return order

    def set_exit_orders(self, exchange_name, order, stop_loss, take_profit):
        """
        Set stop loss and take profit orders for a given trade.
        """
        if not order or order.get("status") != "filled":
            return {"status": "rejected", "reason": "exit orders require a filled entry order"}

        exits = {
            "entry_order_id": order.get("id"),
            "exchange": exchange_name,
            "symbol": order.get("symbol"),
            "stop_loss": float(stop_loss) if stop_loss else None,
            "take_profit": float(take_profit) if take_profit else None,
            "status": "armed",
            "paper": order.get("paper", self.paper_trading)
        }
        order["exit_orders"] = exits
        return exits

    def execute_arbitrage(self, arbitrage_signal):
        """
        Execute arbitrage trades across multiple exchanges.
        """
        try:
            buy_price = float(arbitrage_signal.get("buy_price") or 0)
            sell_price = float(arbitrage_signal.get("sell_price") or 0)
            notional = float(arbitrage_signal.get("max_notional") or arbitrage_signal.get("notional") or 0)
        except (TypeError, ValueError):
            return {"status": "rejected", "reason": "invalid arbitrage signal"}

        if buy_price <= 0 or sell_price <= 0 or notional <= 0:
            return {"status": "rejected", "reason": "missing arbitrage prices or notional"}

        amount = notional / buy_price
        buy_order = self.execute_order(
            arbitrage_signal.get("buy_exchange"),
            arbitrage_signal.get("symbol"),
            "buy",
            amount,
            price=buy_price
        )
        sell_order = self.execute_order(
            arbitrage_signal.get("sell_exchange"),
            arbitrage_signal.get("symbol"),
            "sell",
            amount,
            price=sell_price
        )

        if buy_order.get("status") != "filled" or sell_order.get("status") != "filled":
            return {
                "status": "partial_or_rejected",
                "buy_order": buy_order,
                "sell_order": sell_order
            }

        gross = sell_order["notional"] - buy_order["notional"]
        fees = buy_order["fee"] + sell_order["fee"]
        return {
            "status": "filled",
            "buy_order": buy_order,
            "sell_order": sell_order,
            "gross_pnl": gross,
            "fees": fees,
            "net_pnl": gross - fees
        }
