"""Prometheus v2 – IBKR client implementation using ib_insync.

This module provides a concrete implementation of :class:`IbkrClient` using
the ``ib_insync`` library for Interactive Brokers connectivity.

Key features:
* Automatic connection management with reconnection
* Order submission with contract translation
* Real-time position and account state sync
* Fill tracking and event handling
* Error handling and logging
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ib_insync import IB, Contract, Fill as IbFill, MarketOrder, Order as IbOrder

from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger
from prometheus.execution.broker_interface import Fill, Order, OrderSide, OrderType, Position
from prometheus.execution.ibkr_client import IbkrClient, IbkrConnectionConfig
from prometheus.execution.instrument_mapper import InstrumentMapper


logger = get_logger(__name__)


class IbkrClientImpl(IbkrClient):
    """Concrete IBKR client implementation using ib_insync.
    
    This implementation:
    - Manages connection to IBKR Gateway/TWS
    - Translates Prometheus orders to IBKR contracts and orders
    - Tracks fills via event callbacks
    - Syncs positions and account state
    - Handles reconnection automatically
    """

    def __init__(self, config: IbkrConnectionConfig, mapper: Optional[InstrumentMapper] = None) -> None:
        super().__init__(config)
        self._ib = IB()
        self._connected = False
        
        # Instrument mapper for contract translation
        self._mapper = mapper or InstrumentMapper()
        
        # Local caches
        self._fills: List[Fill] = []
        self._positions: Dict[str, Position] = {}
        self._account_state: Dict = {}
        
        # Order tracking
        self._order_map: Dict[str, IbOrder] = {}  # Prometheus order_id -> IB Order
        
        # Health monitoring
        self._last_heartbeat: Optional[datetime] = None
        self._heartbeat_interval_sec = 60  # Check connection every 60 seconds
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay_sec = 10
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_running = False
        
        # Setup event handlers
        self._ib.orderStatusEvent += self._on_order_status
        self._ib.execDetailsEvent += self._on_exec_details
        self._ib.errorEvent += self._on_error
        self._ib.connectedEvent += self._on_connected
        self._ib.disconnectedEvent += self._on_disconnected

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Establish connection to IBKR Gateway/TWS."""
        if self._connected and self._ib.isConnected():
            logger.debug("IbkrClient already connected")
            return
        
        try:
            logger.info(
                "Connecting to IBKR at %s:%d (client_id=%d, account=%s)",
                self._config.host,
                self._config.port,
                self._config.client_id,
                self._config.account_id or "default",
            )
            
            self._ib.connect(
                host=self._config.host,
                port=self._config.port,
                clientId=self._config.client_id,
                readonly=self._config.readonly,
                timeout=self._config.connect_timeout_sec,
            )
            
            self._connected = True
            logger.info("Successfully connected to IBKR")
            
            # Load instruments for contract mapping
            self._mapper.load_instruments()
            
            # Initial sync
            self.sync()
            
            # Start heartbeat monitoring
            self._start_heartbeat()
            
        except Exception as e:
            logger.error("Failed to connect to IBKR: %s", e, exc_info=True)
            self._connected = False
            raise

    def disconnect(self) -> None:
        """Close the IBKR connection."""
        # Stop heartbeat monitoring
        self._stop_heartbeat()
        
        if self._ib.isConnected():
            logger.info("Disconnecting from IBKR")
            self._ib.disconnect()
        self._connected = False

    def is_connected(self) -> bool:
        """Return True if connected to IBKR."""
        return self._connected and self._ib.isConnected()

    # ------------------------------------------------------------------
    # Order and execution API
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> str:
        """Submit an order to IBKR and return order_id."""
        if not self.is_connected():
            raise RuntimeError("Not connected to IBKR. Call connect() first.")
        
        if self._config.readonly:
            logger.warning("Readonly mode enabled, order not submitted: %s", order.order_id)
            return order.order_id
        
        # Translate Prometheus order to IBKR contract and order
        contract = self._create_contract(order.instrument_id)
        ib_order = self._create_ib_order(order)
        
        logger.info(
            "Submitting order: %s %s %s x %.2f @ %s",
            order.order_id,
            order.side.value,
            order.instrument_id,
            order.quantity,
            order.order_type.value,
        )
        
        try:
            # Place order
            trade = self._ib.placeOrder(contract, ib_order)
            
            # Store mapping
            self._order_map[order.order_id] = ib_order
            
            logger.info(
                "Order submitted successfully: %s (IBKR orderId=%s)",
                order.order_id,
                trade.order.orderId if trade.order else "unknown",
            )
            
            return order.order_id
            
        except Exception as e:
            logger.error("Failed to submit order %s: %s", order.order_id, e, exc_info=True)
            raise

    def cancel_order(self, order_id: str) -> bool:
        """Attempt to cancel an order."""
        if not self.is_connected():
            raise RuntimeError("Not connected to IBKR")
        
        ib_order = self._order_map.get(order_id)
        if ib_order is None:
            logger.warning("Order %s not found in order map", order_id)
            return False
        
        try:
            logger.info("Cancelling order: %s", order_id)
            self._ib.cancelOrder(ib_order)
            return True
        except Exception as e:
            logger.error("Failed to cancel order %s: %s", order_id, e, exc_info=True)
            return False

    def get_fills(self, since: Optional[datetime] = None) -> List[Fill]:
        """Return fills since the given timestamp."""
        if since is None:
            return list(self._fills)
        return [f for f in self._fills if f.timestamp > since]

    def get_positions(self) -> Dict[str, Position]:
        """Return current positions keyed by instrument_id."""
        return dict(self._positions)

    def get_account_state(self) -> Dict:
        """Return account-level information."""
        return dict(self._account_state)

    def sync(self) -> None:
        """Synchronize positions and account state from IBKR."""
        if not self.is_connected():
            logger.warning("Cannot sync: not connected to IBKR")
            return
        
        logger.debug("Syncing positions and account state from IBKR")
        
        # Sync positions
        self._sync_positions()
        
        # Sync account values
        self._sync_account_values()
        
        logger.debug("Sync complete: %d positions", len(self._positions))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_contract(self, instrument_id: str) -> Contract:
        """Create IBKR contract from Prometheus instrument_id.
        
        Uses InstrumentMapper to translate instrument_id to IBKR contract.
        """
        # Use mapper to get contract
        contract = self._mapper.get_contract(instrument_id)
        
        # Qualify contract to ensure it's valid
        try:
            contracts = self._ib.qualifyContracts(contract)
            if not contracts:
                raise ValueError(f"Could not qualify contract for {instrument_id}")
            return contracts[0]
        except Exception as e:
            logger.error("Failed to qualify contract for %s: %s", instrument_id, e)
            # Return unqualified contract and hope for the best
            return contract

    def _create_ib_order(self, order: Order) -> IbOrder:
        """Create IBKR order from Prometheus order."""
        # Determine action (BUY or SELL)
        action = "BUY" if order.side == OrderSide.BUY else "SELL"
        
        # For now, only support MARKET orders
        # TODO: Add support for LIMIT, STOP, STOP_LIMIT
        if order.order_type != OrderType.MARKET:
            logger.warning(
                "Order type %s not yet supported, using MARKET order",
                order.order_type.value,
            )
        
        ib_order = MarketOrder(action, order.quantity)
        
        # Store Prometheus order_id in order ref for tracking
        ib_order.orderRef = order.order_id
        
        return ib_order

    def _sync_positions(self) -> None:
        """Sync positions from IBKR.

        Uses the portfolio view to obtain both quantity and valuation
        information. This avoids relying on fields that are not present on
        the ``Position`` objects returned by :meth:`IB.positions`.
        """
        try:
            # ``portfolio()`` returns a list of PortfolioItem objects with
            # position size, market value and P&L information.
            portfolio_items = self._ib.portfolio()

            self._positions.clear()

            for item in portfolio_items:
                # Respect configured account_id if provided
                if self._config.account_id and item.account != self._config.account_id:
                    continue

                instrument_id = self._contract_to_instrument_id(item.contract)

                position = Position(
                    instrument_id=instrument_id,
                    quantity=float(item.position),
                    avg_cost=float(item.averageCost),
                    market_value=float(item.marketValue),
                    unrealized_pnl=float(item.unrealizedPNL),
                )

                self._positions[instrument_id] = position

        except Exception as e:
            logger.error("Failed to sync positions: %s", e, exc_info=True)

    def _sync_account_values(self) -> None:
        """Sync account values from IBKR."""
        try:
            account_values = self._ib.accountValues(account=self._config.account_id)
            
            self._account_state.clear()
            
            # Extract key account metrics
            for av in account_values:
                # Use tag as key, convert value to float if possible
                key = av.tag
                try:
                    value = float(av.value)
                except ValueError:
                    value = av.value
                
                self._account_state[key] = value
            
            # Compute equity if not directly available
            if "NetLiquidation" in self._account_state:
                self._account_state["equity"] = self._account_state["NetLiquidation"]
            
            # Add cash
            if "TotalCashValue" in self._account_state:
                self._account_state["cash"] = self._account_state["TotalCashValue"]
                
        except Exception as e:
            logger.error("Failed to sync account values: %s", e, exc_info=True)

    def _contract_to_instrument_id(self, contract: Contract) -> str:
        """Convert IBKR contract to Prometheus instrument_id.
        
        For now, returns the symbol. In production, this should use
        proper instrument registry mapping.
        """
        return contract.symbol

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_order_status(
        self,
        trade: any,  # Trade object from ib_insync
    ) -> None:
        """Handle order status updates."""
        order = trade.order
        order_id = order.orderRef  # Our Prometheus order_id
        
        logger.debug(
            "Order status update: %s -> %s (filled=%d/%d)",
            order_id,
            trade.orderStatus.status,
            trade.orderStatus.filled,
            trade.order.totalQuantity,
        )

    def _on_exec_details(
        self,
        trade: any,  # Trade object
        fill: IbFill,  # Fill from ib_insync
    ) -> None:
        """Handle execution (fill) events."""
        execution = fill.execution
        
        # Extract order_id from order ref
        order_id = trade.order.orderRef if trade.order else None
        if not order_id:
            logger.warning("Received fill without order_id ref")
            order_id = f"unknown_{execution.execId}"
        
        # Determine side
        side = OrderSide.BUY if execution.side == "BOT" else OrderSide.SELL
        
        # Create Prometheus Fill object
        prometheus_fill = Fill(
            fill_id=execution.execId,
            order_id=order_id,
            instrument_id=trade.contract.symbol,
            side=side,
            quantity=float(execution.shares),
            price=float(execution.price),
            timestamp=datetime.fromisoformat(execution.time).replace(tzinfo=timezone.utc),
            commission=float(fill.commissionReport.commission) if fill.commissionReport else 0.0,
            metadata={
                "exchange": execution.exchange,
                "exec_id": execution.execId,
                "order_id_ibkr": str(execution.orderId),
            },
        )
        
        self._fills.append(prometheus_fill)
        
        logger.info(
            "Fill received: %s %s %s x %.2f @ %.2f (commission=%.2f)",
            prometheus_fill.fill_id,
            side.value,
            prometheus_fill.instrument_id,
            prometheus_fill.quantity,
            prometheus_fill.price,
            prometheus_fill.commission,
        )

    def _on_error(
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        contract: Optional[Contract],
    ) -> None:
        """Handle error messages from IBKR."""
        # Error codes < 1000 are system messages, not actual errors
        if errorCode < 1000:
            logger.debug("IBKR message [%d]: %s", errorCode, errorString)
        else:
            logger.warning("IBKR error [%d]: %s (reqId=%d)", errorCode, errorString, reqId)

    def _on_connected(self) -> None:
        """Handle connection established event."""
        logger.info("IBKR connection established")
        self._connected = True
        self._reconnect_attempts = 0  # Reset reconnect counter
        self._last_heartbeat = datetime.now(timezone.utc)

    def _on_disconnected(self) -> None:
        """Handle disconnection event."""
        logger.warning("IBKR connection lost")
        self._connected = False
        
        # Attempt auto-reconnection
        if self._reconnect_attempts < self._max_reconnect_attempts:
            self._attempt_reconnect()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Connection health monitoring
    # ------------------------------------------------------------------
    
    def _start_heartbeat(self) -> None:
        """Start heartbeat monitoring thread."""
        if self._heartbeat_running:
            return
        
        self._heartbeat_running = True
        self._last_heartbeat = datetime.now(timezone.utc)
        
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="IbkrClientHeartbeat",
        )
        self._heartbeat_thread.start()
        
        logger.info("Heartbeat monitoring started")
    
    def _stop_heartbeat(self) -> None:
        """Stop heartbeat monitoring thread."""
        if not self._heartbeat_running:
            return
        
        self._heartbeat_running = False
        
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=5)
        
        logger.info("Heartbeat monitoring stopped")
    
    def _heartbeat_loop(self) -> None:
        """Heartbeat monitoring loop running in background thread."""
        while self._heartbeat_running:
            try:
                time.sleep(self._heartbeat_interval_sec)
                
                if not self._heartbeat_running:
                    break
                
                # Check connection health
                if self._ib.isConnected():
                    self._last_heartbeat = datetime.now(timezone.utc)
                    logger.debug("Heartbeat: connection healthy")
                else:
                    logger.warning("Heartbeat: connection lost, attempting reconnect")
                    if self._reconnect_attempts < self._max_reconnect_attempts:
                        self._attempt_reconnect()
                
            except Exception as e:
                logger.error("Error in heartbeat loop: %s", e, exc_info=True)
    
    def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to IBKR."""
        self._reconnect_attempts += 1
        
        logger.info(
            "Attempting reconnection %d/%d in %d seconds",
            self._reconnect_attempts,
            self._max_reconnect_attempts,
            self._reconnect_delay_sec,
        )
        
        time.sleep(self._reconnect_delay_sec)
        
        try:
            self.connect()
            logger.info("Reconnection successful")
        except Exception as e:
            logger.error(
                "Reconnection attempt %d failed: %s",
                self._reconnect_attempts,
                e,
            )
            
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                logger.error(
                    "Max reconnection attempts (%d) reached. Manual intervention required.",
                    self._max_reconnect_attempts,
                )
    
    def get_connection_health(self) -> Dict:
        """Get connection health status.
        
        Returns:
            Dictionary with connection health information.
        """
        return {
            "connected": self._connected,
            "ib_connected": self._ib.isConnected(),
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "reconnect_attempts": self._reconnect_attempts,
            "max_reconnect_attempts": self._max_reconnect_attempts,
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self._stop_heartbeat()
        
        if self._ib.isConnected():
            try:
                self._ib.disconnect()
            except Exception:
                pass
