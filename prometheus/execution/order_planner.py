"""Prometheus v2 – Order planning utilities.

This module provides a small helper to convert desired target positions
into executable :class:`~prometheus.execution.broker_interface.Order`
objects. It is deliberately simple for Iteration 1 and only supports
single-account, single-currency books.
"""

from __future__ import annotations

from typing import Dict, List

from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger

from prometheus.execution.broker_interface import Order, OrderSide, OrderType, Position


logger = get_logger(__name__)


# Minimum absolute quantity before an order is emitted. This helps avoid
# generating dust orders from tiny rounding differences when rebalancing.
MIN_ABS_QUANTITY: float = 1e-6


def plan_orders(
    current_positions: Dict[str, Position],
    target_positions: Dict[str, float],
    order_type: OrderType = OrderType.MARKET,
    min_abs_quantity: float = MIN_ABS_QUANTITY,
) -> List[Order]:
    """Compute orders required to move from current to target positions.

    Args:
        current_positions: Mapping from instrument_id to current
            :class:`Position` objects.
        target_positions: Mapping from instrument_id to desired absolute
            quantities (same units as ``Position.quantity``).
        order_type: Order type to use for all generated orders. For this
            iteration only ``MARKET`` is exercised in tests.
        min_abs_quantity: Minimum absolute quantity change required before
            emitting an order.

    Returns:
        A list of :class:`Order` objects representing the required trades.
    """

    orders: List[Order] = []

    # Instruments present in either the current or target state.
    all_instruments = set(current_positions.keys()) | set(target_positions.keys())

    for instrument_id in sorted(all_instruments):
        current = current_positions.get(
            instrument_id,
            Position(
                instrument_id=instrument_id,
                quantity=0.0,
                avg_cost=0.0,
                market_value=0.0,
                unrealized_pnl=0.0,
            ),
        )
        target_qty = float(target_positions.get(instrument_id, 0.0))
        delta = target_qty - float(current.quantity)

        if abs(delta) < min_abs_quantity:
            continue

        side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        order = Order(
            order_id=generate_uuid(),
            instrument_id=instrument_id,
            side=side,
            order_type=order_type,
            quantity=abs(delta),
        )
        orders.append(order)

    if orders:
        logger.info(
            "OrderPlanner.plan_orders: generated %d orders for %d instruments",
            len(orders),
            len(all_instruments),
        )

    return orders