"""Prometheus v2 – Market State Machine

This module implements market state detection for orchestration. Each market
(US_EQ, EU_EQ, etc.) transitions through distinct states during the trading
day based on its calendar and session times:

- HOLIDAY: Trading day is a holiday
- OVERNIGHT: Outside market hours, before pre-open
- PRE_OPEN: Pre-market buffer before session open
- SESSION: Market is open for trading
- POST_CLOSE: Post-market buffer after session close

State transitions are based on:
1. Trading calendar (from TradingCalendar)
2. Session times (hardcoded per market for v2)
3. Configurable buffer periods

This is used by the orchestration layer to schedule jobs at appropriate times
(e.g., run ingestion in POST_CLOSE, run engines after POST_CLOSE completes).

Author: Prometheus Team
Created: 2025-12-01
Status: Development
Version: v1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from enum import Enum

from prometheus.core.logging import get_logger
from prometheus.core.time import TradingCalendar, TradingCalendarConfig

logger = get_logger(__name__)


# ============================================================================
# Market State Enum
# ============================================================================


class MarketState(str, Enum):
    """Discrete states for a market during the trading day.
    
    States follow this daily cycle:
    OVERNIGHT → PRE_OPEN → SESSION → POST_CLOSE → OVERNIGHT
    
    HOLIDAY is returned when the date is not a trading day.
    """
    
    HOLIDAY = "HOLIDAY"
    OVERNIGHT = "OVERNIGHT"
    PRE_OPEN = "PRE_OPEN"
    SESSION = "SESSION"
    POST_CLOSE = "POST_CLOSE"


# ============================================================================
# Configuration
# ============================================================================


@dataclass(frozen=True)
class MarketSessionTimes:
    """Session times for a market in UTC.
    
    Attributes:
        session_open_utc: Session open time (e.g., 14:30 UTC for US_EQ = 9:30 ET)
        session_close_utc: Session close time (e.g., 21:00 UTC for US_EQ = 16:00 ET)
    """
    
    session_open_utc: time
    session_close_utc: time


@dataclass(frozen=True)
class MarketStateConfig:
    """Configuration for market state detection.
    
    Attributes:
        market_id: Market identifier (e.g., "US_EQ")
        session_times: Session open/close times in UTC
        preopen_buffer_minutes: Minutes before session_open for PRE_OPEN state
        postclose_buffer_minutes: Minutes after session_close for POST_CLOSE state
    """
    
    market_id: str
    session_times: MarketSessionTimes
    preopen_buffer_minutes: int = 60
    postclose_buffer_minutes: int = 120


# ============================================================================
# Default Configurations
# ============================================================================


# US Equity markets: NYSE/NASDAQ
# Regular hours: 9:30 AM - 4:00 PM ET
# ET to UTC: ET + 4h (EDT) or ET + 5h (EST)
# Using EST (UTC-5) for simplicity: 9:30 ET = 14:30 UTC, 16:00 ET = 21:00 UTC
US_EQ_CONFIG = MarketStateConfig(
    market_id="US_EQ",
    session_times=MarketSessionTimes(
        session_open_utc=time(14, 30),   # 9:30 AM ET
        session_close_utc=time(21, 0),   # 4:00 PM ET
    ),
    preopen_buffer_minutes=60,   # PRE_OPEN starts at 13:30 UTC (8:30 ET)
    postclose_buffer_minutes=120,  # POST_CLOSE ends at 23:00 UTC (18:00 ET)
)

# European markets: Euronext, LSE, XETRA
# Regular hours: 9:00 AM - 5:30 PM CET (approximate)
# CET to UTC: CET - 1h
EU_EQ_CONFIG = MarketStateConfig(
    market_id="EU_EQ",
    session_times=MarketSessionTimes(
        session_open_utc=time(8, 0),    # 9:00 AM CET
        session_close_utc=time(16, 30),  # 5:30 PM CET
    ),
    preopen_buffer_minutes=60,
    postclose_buffer_minutes=120,
)

# Asian markets: Tokyo, Hong Kong, Shanghai
# TSE hours: 9:00 AM - 3:00 PM JST
# JST to UTC: UTC = JST - 9h, so 9:00 JST = 0:00 UTC, 15:00 JST = 6:00 UTC
# BUT we want next day: if 9:00 JST Dec 2 = 0:00 UTC Dec 2, then we're in overnight from previous day
# Correction: JST is UTC+9, so UTC = JST - 9. Example: 9:00 JST = 0:00 UTC same day.
ASIA_EQ_CONFIG = MarketStateConfig(
    market_id="ASIA_EQ",
    session_times=MarketSessionTimes(
        session_open_utc=time(0, 0),    # 9:00 AM JST = 0:00 UTC
        session_close_utc=time(6, 0),   # 3:00 PM JST = 6:00 UTC  
    ),
    preopen_buffer_minutes=60,
    postclose_buffer_minutes=120,
)

DEFAULT_CONFIGS: dict[str, MarketStateConfig] = {
    "US_EQ": US_EQ_CONFIG,
    "EU_EQ": EU_EQ_CONFIG,
    "ASIA_EQ": ASIA_EQ_CONFIG,
}


# ============================================================================
# State Detection
# ============================================================================


def get_market_state(
    market_id: str,
    now_utc: datetime,
    config: MarketStateConfig | None = None,
    calendar: TradingCalendar | None = None,
) -> MarketState:
    """Determine the current market state for a given market and time.
    
    Args:
        market_id: Market identifier (e.g., "US_EQ")
        now_utc: Current time in UTC (must be timezone-aware)
        config: Optional market state config. If None, uses default for market_id.
        calendar: Optional TradingCalendar. If None, creates one for the market.
    
    Returns:
        Current MarketState for the market
        
    Raises:
        ValueError: If market_id not recognized and no config provided
        ValueError: If now_utc is not timezone-aware
    """
    
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware (use datetime.now(timezone.utc))")
    
    # Get config
    if config is None:
        if market_id not in DEFAULT_CONFIGS:
            raise ValueError(
                f"Unknown market_id {market_id!r}. Provide config explicitly or add to DEFAULT_CONFIGS."
            )
        config = DEFAULT_CONFIGS[market_id]
    
    # Get calendar
    if calendar is None:
        calendar = TradingCalendar(TradingCalendarConfig(market=market_id))
    
    # Extract date in UTC
    current_date = now_utc.date()
    
    # Check if today is a trading day
    if not calendar.is_trading_day(current_date):
        return MarketState.HOLIDAY
    
    # Get current time of day
    current_time = now_utc.time()
    
    # Calculate state boundaries
    session_open = config.session_times.session_open_utc
    session_close = config.session_times.session_close_utc
    
    # PRE_OPEN starts preopen_buffer_minutes before session_open
    preopen_start = _subtract_minutes(session_open, config.preopen_buffer_minutes)
    
    # POST_CLOSE ends postclose_buffer_minutes after session_close
    postclose_end = _add_minutes(session_close, config.postclose_buffer_minutes)
    
    # Determine state based on current time
    # Handle cases where times might wrap around midnight
    
    # Check if preopen_start wraps to previous day (e.g., 00:00 - 60min = 23:00)
    preopen_wraps = preopen_start > session_open
    
    if session_open < session_close:
        # Normal case: session within same day (e.g., US: 14:30 - 21:00, ASIA: 00:00 - 06:00)
        if preopen_wraps:
            # PRE_OPEN wraps midnight (e.g., session at 00:00, PRE_OPEN at 23:00)
            # Times 23:00-23:59 = PRE_OPEN
            # Times 00:00-session_open = also PRE_OPEN (continuation from previous day)
            # Times session_open-session_close = SESSION
            # After session_close = POST_CLOSE then OVERNIGHT
            if current_time >= preopen_start:  # After 23:00 = PRE_OPEN
                return MarketState.PRE_OPEN
            elif current_time < session_open:  # 00:00-00:00 is instant, but 00:00-xx:xx = could be PRE_OPEN or OVERNIGHT
                # If session_open is 00:00, we're right at the boundary
                # Since we're in this branch, current_time < session_open, so if session_open=00:00, this is impossible
                # Actually, if session starts at 00:00 and we're at 00:00, we're AT session start = SESSION
                # But if we're at 00:01 and open is 00:00, then current_time (00:01) > session_open (00:00)
                # So this branch means we're in the range [00:00, session_open) which for 00:00 start doesn't exist
                # So: we're actually in late night before PRE_OPEN starts at 23:00
                return MarketState.OVERNIGHT
            elif current_time < session_close:
                return MarketState.SESSION
            elif current_time < postclose_end:
                return MarketState.POST_CLOSE
            else:
                return MarketState.OVERNIGHT
        else:
            # Standard case: no wraparound
            if current_time < preopen_start:
                return MarketState.OVERNIGHT
            elif current_time < session_open:
                return MarketState.PRE_OPEN
            elif current_time < session_close:
                return MarketState.SESSION
            elif current_time < postclose_end:
                return MarketState.POST_CLOSE
            else:
                return MarketState.OVERNIGHT
    else:
        # Edge case: session wraps midnight (unlikely but handle it)
        # e.g., 22:00 - 02:00 (10PM to 2AM next day)
        if preopen_start < session_open:
            # PRE_OPEN before midnight
            if current_time >= preopen_start or current_time < session_close:
                if current_time >= session_open or current_time < session_close:
                    return MarketState.SESSION
                else:
                    return MarketState.PRE_OPEN
        
        # Fallback logic for complex wrapping cases
        if current_time >= session_open or current_time < session_close:
            return MarketState.SESSION
        elif current_time < postclose_end:
            return MarketState.POST_CLOSE
        else:
            return MarketState.OVERNIGHT


def get_next_state_transition(
    market_id: str,
    now_utc: datetime,
    config: MarketStateConfig | None = None,
    calendar: TradingCalendar | None = None,
) -> tuple[MarketState, datetime]:
    """Calculate when the market will next transition to a different state.
    
    Args:
        market_id: Market identifier
        now_utc: Current time in UTC (must be timezone-aware)
        config: Optional market state config
        calendar: Optional TradingCalendar
    
    Returns:
        Tuple of (next_state, transition_time_utc)
        
    Example:
        >>> # Current state is OVERNIGHT at 13:00 UTC
        >>> next_state, when = get_next_state_transition("US_EQ", datetime(...))
        >>> # Returns (MarketState.PRE_OPEN, datetime(... 13:30 UTC))
    """
    
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    
    current_state = get_market_state(market_id, now_utc, config, calendar)
    
    # Get config
    if config is None:
        config = DEFAULT_CONFIGS.get(market_id)
        if config is None:
            raise ValueError(f"Unknown market_id {market_id!r}")
    
    # Get calendar
    if calendar is None:
        calendar = TradingCalendar(TradingCalendarConfig(market=market_id))
    
    current_date = now_utc.date()
    current_time = now_utc.time()
    
    session_open = config.session_times.session_open_utc
    session_close = config.session_times.session_close_utc
    preopen_start = _subtract_minutes(session_open, config.preopen_buffer_minutes)
    postclose_end = _add_minutes(session_close, config.postclose_buffer_minutes)
    
    # If HOLIDAY, next transition is to next trading day's OVERNIGHT→PRE_OPEN
    if current_state == MarketState.HOLIDAY:
        next_trading_day = calendar.get_next_trading_day(current_date)
        transition_time = datetime.combine(next_trading_day, preopen_start, tzinfo=timezone.utc)
        return (MarketState.PRE_OPEN, transition_time)
    
    # For trading days, determine next transition
    if current_state == MarketState.OVERNIGHT:
        # Next is PRE_OPEN
        if current_time < preopen_start:
            # PRE_OPEN is later today
            transition_time = datetime.combine(current_date, preopen_start, tzinfo=timezone.utc)
        else:
            # PRE_OPEN is tomorrow (we're in late OVERNIGHT)
            next_trading_day = calendar.get_next_trading_day(current_date)
            transition_time = datetime.combine(next_trading_day, preopen_start, tzinfo=timezone.utc)
        return (MarketState.PRE_OPEN, transition_time)
    
    elif current_state == MarketState.PRE_OPEN:
        # Next is SESSION
        transition_time = datetime.combine(current_date, session_open, tzinfo=timezone.utc)
        return (MarketState.SESSION, transition_time)
    
    elif current_state == MarketState.SESSION:
        # Next is POST_CLOSE
        transition_time = datetime.combine(current_date, session_close, tzinfo=timezone.utc)
        return (MarketState.POST_CLOSE, transition_time)
    
    elif current_state == MarketState.POST_CLOSE:
        # Next is OVERNIGHT
        transition_time = datetime.combine(current_date, postclose_end, tzinfo=timezone.utc)
        return (MarketState.OVERNIGHT, transition_time)
    
    # Should never reach here
    raise RuntimeError(f"Unexpected state: {current_state}")  # pragma: no cover


# ============================================================================
# Utilities
# ============================================================================


def _add_minutes(t: time, minutes: int) -> time:
    """Add minutes to a time object, handling day wraparound.
    
    Returns the new time. If it would go past midnight, wraps to next day.
    """
    dt = datetime.combine(datetime.today(), t)
    dt += timedelta(minutes=minutes)
    return dt.time()


def _subtract_minutes(t: time, minutes: int) -> time:
    """Subtract minutes from a time object, handling day wraparound."""
    dt = datetime.combine(datetime.today(), t)
    dt -= timedelta(minutes=minutes)
    return dt.time()


def get_all_market_states(now_utc: datetime) -> dict[str, MarketState]:
    """Get current state for all configured markets.
    
    Args:
        now_utc: Current time in UTC (timezone-aware)
    
    Returns:
        Dict mapping market_id to its current MarketState
        
    Example:
        >>> states = get_all_market_states(datetime.now(timezone.utc))
        >>> # {'US_EQ': MarketState.SESSION, 'EU_EQ': MarketState.POST_CLOSE, ...}
    """
    return {
        market_id: get_market_state(market_id, now_utc)
        for market_id in DEFAULT_CONFIGS.keys()
    }
