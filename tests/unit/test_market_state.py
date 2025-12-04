"""Unit tests for prometheus.core.market_state module."""

from datetime import datetime, date, time, timezone

import pytest

from prometheus.core.market_state import (
    MarketState,
    MarketStateConfig,
    MarketSessionTimes,
    get_market_state,
    get_next_state_transition,
    get_all_market_states,
    US_EQ_CONFIG,
)
from prometheus.core.time import TradingCalendar, TradingCalendarConfig


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_calendar_us():
    """Create a TradingCalendar for US_EQ with controlled holidays."""
    # Use a calendar that treats weekends as non-trading, no holidays for simplicity
    return TradingCalendar(TradingCalendarConfig(market="US_EQ", use_db_holidays=False))


# ============================================================================
# Test: get_market_state - US_EQ
# ============================================================================


def test_market_state_us_eq_overnight_early_morning():
    """US_EQ should be OVERNIGHT at 05:00 UTC (midnight ET)."""
    now = datetime(2025, 12, 1, 5, 0, 0, tzinfo=timezone.utc)  # Monday
    state = get_market_state("US_EQ", now)
    assert state == MarketState.OVERNIGHT


def test_market_state_us_eq_preopen():
    """US_EQ should be PRE_OPEN at 13:45 UTC (8:45 ET)."""
    now = datetime(2025, 12, 1, 13, 45, 0, tzinfo=timezone.utc)  # Monday
    state = get_market_state("US_EQ", now)
    assert state == MarketState.PRE_OPEN


def test_market_state_us_eq_session_start():
    """US_EQ should be SESSION at 14:30 UTC (9:30 ET - market open)."""
    now = datetime(2025, 12, 1, 14, 30, 0, tzinfo=timezone.utc)  # Monday
    state = get_market_state("US_EQ", now)
    assert state == MarketState.SESSION


def test_market_state_us_eq_session_mid():
    """US_EQ should be SESSION at 17:00 UTC (noon ET)."""
    now = datetime(2025, 12, 1, 17, 0, 0, tzinfo=timezone.utc)  # Monday
    state = get_market_state("US_EQ", now)
    assert state == MarketState.SESSION


def test_market_state_us_eq_session_end():
    """US_EQ should be SESSION at 20:59 UTC (just before 4PM ET close)."""
    now = datetime(2025, 12, 1, 20, 59, 0, tzinfo=timezone.utc)  # Monday
    state = get_market_state("US_EQ", now)
    assert state == MarketState.SESSION


def test_market_state_us_eq_postclose():
    """US_EQ should be POST_CLOSE at 21:30 UTC (4:30 PM ET)."""
    now = datetime(2025, 12, 1, 21, 30, 0, tzinfo=timezone.utc)  # Monday
    state = get_market_state("US_EQ", now)
    assert state == MarketState.POST_CLOSE


def test_market_state_us_eq_overnight_late_evening():
    """US_EQ should be OVERNIGHT at 23:30 UTC (6:30 PM ET, after POST_CLOSE)."""
    now = datetime(2025, 12, 1, 23, 30, 0, tzinfo=timezone.utc)  # Monday
    state = get_market_state("US_EQ", now)
    assert state == MarketState.OVERNIGHT


def test_market_state_us_eq_holiday_weekend():
    """US_EQ should be HOLIDAY on Saturday."""
    now = datetime(2025, 11, 29, 15, 0, 0, tzinfo=timezone.utc)  # Saturday
    state = get_market_state("US_EQ", now)
    assert state == MarketState.HOLIDAY


def test_market_state_us_eq_holiday_sunday():
    """US_EQ should be HOLIDAY on Sunday."""
    now = datetime(2025, 11, 30, 15, 0, 0, tzinfo=timezone.utc)  # Sunday
    state = get_market_state("US_EQ", now)
    assert state == MarketState.HOLIDAY


# ============================================================================
# Test: get_market_state - Edge Cases
# ============================================================================


def test_market_state_requires_timezone_aware():
    """get_market_state should raise ValueError for naive datetime."""
    naive_dt = datetime(2025, 12, 1, 15, 0, 0)  # No timezone
    with pytest.raises(ValueError, match="timezone-aware"):
        get_market_state("US_EQ", naive_dt)


def test_market_state_unknown_market_no_config():
    """get_market_state should raise ValueError for unknown market without config."""
    now = datetime(2025, 12, 1, 15, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="Unknown market_id"):
        get_market_state("UNKNOWN_MARKET", now)


def test_market_state_custom_config():
    """get_market_state should use custom config when provided."""
    # Custom market with session 10:00-16:00 UTC
    custom_config = MarketStateConfig(
        market_id="CUSTOM",
        session_times=MarketSessionTimes(
            session_open_utc=time(10, 0),
            session_close_utc=time(16, 0),
        ),
        preopen_buffer_minutes=30,
        postclose_buffer_minutes=60,
    )
    
    # Should be SESSION at 12:00 UTC
    now = datetime(2025, 12, 1, 12, 0, 0, tzinfo=timezone.utc)
    state = get_market_state("CUSTOM", now, config=custom_config)
    assert state == MarketState.SESSION
    
    # Should be PRE_OPEN at 9:45 UTC (30min before open)
    now = datetime(2025, 12, 1, 9, 45, 0, tzinfo=timezone.utc)
    state = get_market_state("CUSTOM", now, config=custom_config)
    assert state == MarketState.PRE_OPEN


# ============================================================================
# Test: get_next_state_transition
# ============================================================================


def test_next_transition_overnight_to_preopen():
    """From OVERNIGHT, next transition should be to PRE_OPEN."""
    # 05:00 UTC on Monday (midnight ET) = OVERNIGHT
    now = datetime(2025, 12, 1, 5, 0, 0, tzinfo=timezone.utc)
    next_state, when = get_next_state_transition("US_EQ", now)
    
    assert next_state == MarketState.PRE_OPEN
    # PRE_OPEN starts at 13:30 UTC (8:30 ET)
    assert when == datetime(2025, 12, 1, 13, 30, 0, tzinfo=timezone.utc)


def test_next_transition_preopen_to_session():
    """From PRE_OPEN, next transition should be to SESSION."""
    # 13:45 UTC = PRE_OPEN
    now = datetime(2025, 12, 1, 13, 45, 0, tzinfo=timezone.utc)
    next_state, when = get_next_state_transition("US_EQ", now)
    
    assert next_state == MarketState.SESSION
    # SESSION starts at 14:30 UTC (9:30 ET)
    assert when == datetime(2025, 12, 1, 14, 30, 0, tzinfo=timezone.utc)


def test_next_transition_session_to_postclose():
    """From SESSION, next transition should be to POST_CLOSE."""
    # 17:00 UTC = SESSION
    now = datetime(2025, 12, 1, 17, 0, 0, tzinfo=timezone.utc)
    next_state, when = get_next_state_transition("US_EQ", now)
    
    assert next_state == MarketState.POST_CLOSE
    # POST_CLOSE starts at 21:00 UTC (4:00 PM ET)
    assert when == datetime(2025, 12, 1, 21, 0, 0, tzinfo=timezone.utc)


def test_next_transition_postclose_to_overnight():
    """From POST_CLOSE, next transition should be to OVERNIGHT."""
    # 21:30 UTC = POST_CLOSE
    now = datetime(2025, 12, 1, 21, 30, 0, tzinfo=timezone.utc)
    next_state, when = get_next_state_transition("US_EQ", now)
    
    assert next_state == MarketState.OVERNIGHT
    # OVERNIGHT starts at 23:00 UTC (6:00 PM ET, 120min after close)
    assert when == datetime(2025, 12, 1, 23, 0, 0, tzinfo=timezone.utc)


def test_next_transition_holiday_to_next_trading_day():
    """From HOLIDAY, next transition should jump to next trading day's PRE_OPEN."""
    # Saturday at 15:00 UTC = HOLIDAY
    now = datetime(2025, 11, 29, 15, 0, 0, tzinfo=timezone.utc)  # Saturday
    next_state, when = get_next_state_transition("US_EQ", now)
    
    assert next_state == MarketState.PRE_OPEN
    # Next trading day is Monday, PRE_OPEN at 13:30 UTC
    assert when.date() == date(2025, 12, 1)  # Monday
    assert when.time() == time(13, 30, 0)


def test_next_transition_late_overnight_to_next_day():
    """From late OVERNIGHT (after POST_CLOSE ends), should go to next trading day."""
    # 23:30 UTC Monday = late OVERNIGHT
    now = datetime(2025, 12, 1, 23, 30, 0, tzinfo=timezone.utc)
    next_state, when = get_next_state_transition("US_EQ", now)
    
    assert next_state == MarketState.PRE_OPEN
    # Next trading day is Tuesday, PRE_OPEN at 13:30 UTC
    assert when.date() == date(2025, 12, 2)  # Tuesday
    assert when.time() == time(13, 30, 0)


# ============================================================================
# Test: get_all_market_states
# ============================================================================


def test_get_all_market_states():
    """get_all_market_states should return states for all configured markets."""
    # 15:00 UTC on Monday:
    # - US_EQ: SESSION (9:30-16:00 ET = 14:30-21:00 UTC)
    # - EU_EQ: SESSION (8:00-16:30 UTC, so 15:00 is still in session)
    # - ASIA_EQ: OVERNIGHT (closed at 06:00 UTC)
    now = datetime(2025, 12, 1, 15, 0, 0, tzinfo=timezone.utc)
    states = get_all_market_states(now)
    
    assert "US_EQ" in states
    assert "EU_EQ" in states
    assert "ASIA_EQ" in states
    
    assert states["US_EQ"] == MarketState.SESSION
    assert states["EU_EQ"] == MarketState.SESSION  # 15:00 UTC is within 8:00-16:30 UTC session
    assert states["ASIA_EQ"] == MarketState.OVERNIGHT


# ============================================================================
# Test: State Boundaries
# ============================================================================


def test_state_boundary_preopen_to_session():
    """Test exact boundary between PRE_OPEN and SESSION."""
    # 14:29:59 UTC should be PRE_OPEN
    now = datetime(2025, 12, 1, 14, 29, 59, tzinfo=timezone.utc)
    state = get_market_state("US_EQ", now)
    assert state == MarketState.PRE_OPEN
    
    # 14:30:00 UTC should be SESSION
    now = datetime(2025, 12, 1, 14, 30, 0, tzinfo=timezone.utc)
    state = get_market_state("US_EQ", now)
    assert state == MarketState.SESSION


def test_state_boundary_session_to_postclose():
    """Test exact boundary between SESSION and POST_CLOSE."""
    # 20:59:59 UTC should be SESSION
    now = datetime(2025, 12, 1, 20, 59, 59, tzinfo=timezone.utc)
    state = get_market_state("US_EQ", now)
    assert state == MarketState.SESSION
    
    # 21:00:00 UTC should be POST_CLOSE
    now = datetime(2025, 12, 1, 21, 0, 0, tzinfo=timezone.utc)
    state = get_market_state("US_EQ", now)
    assert state == MarketState.POST_CLOSE


def test_state_boundary_postclose_to_overnight():
    """Test exact boundary between POST_CLOSE and OVERNIGHT."""
    # 22:59:59 UTC should be POST_CLOSE (ends at 23:00)
    now = datetime(2025, 12, 1, 22, 59, 59, tzinfo=timezone.utc)
    state = get_market_state("US_EQ", now)
    assert state == MarketState.POST_CLOSE
    
    # 23:00:00 UTC should be OVERNIGHT
    now = datetime(2025, 12, 1, 23, 0, 0, tzinfo=timezone.utc)
    state = get_market_state("US_EQ", now)
    assert state == MarketState.OVERNIGHT


# ============================================================================
# Test: Integration with TradingCalendar
# ============================================================================


def test_market_state_uses_calendar_for_holidays():
    """Market state should respect TradingCalendar holidays."""
    # If we have a proper calendar with holidays loaded, check it works
    # For now, just verify weekends are treated as HOLIDAY
    
    # Saturday
    now = datetime(2025, 11, 29, 17, 0, 0, tzinfo=timezone.utc)
    state = get_market_state("US_EQ", now)
    assert state == MarketState.HOLIDAY
    
    # Sunday
    now = datetime(2025, 11, 30, 17, 0, 0, tzinfo=timezone.utc)
    state = get_market_state("US_EQ", now)
    assert state == MarketState.HOLIDAY
    
    # Monday should not be HOLIDAY
    now = datetime(2025, 12, 1, 17, 0, 0, tzinfo=timezone.utc)
    state = get_market_state("US_EQ", now)
    assert state != MarketState.HOLIDAY


# ============================================================================
# Test: Multi-Market Scenarios
# ============================================================================


def test_eu_market_state_session():
    """EU_EQ should have correct session times (8:00-16:30 UTC)."""
    # 10:00 UTC = SESSION for EU_EQ
    now = datetime(2025, 12, 1, 10, 0, 0, tzinfo=timezone.utc)  # Monday
    state = get_market_state("EU_EQ", now)
    assert state == MarketState.SESSION


def test_asia_market_state_session():
    """ASIA_EQ should have correct session times (0:00-6:00 UTC)."""
    # 03:00 UTC = SESSION for ASIA_EQ
    now = datetime(2025, 12, 1, 3, 0, 0, tzinfo=timezone.utc)  # Monday
    state = get_market_state("ASIA_EQ", now)
    assert state == MarketState.SESSION


def test_follow_the_sun_scenario():
    """Test that markets transition through states in follow-the-sun pattern."""
    # At 07:00 UTC:
    # - ASIA: POST_CLOSE (closed at 6:00)
    # - EU: PRE_OPEN (opens at 8:00)
    # - US: OVERNIGHT (opens at 14:30)
    now = datetime(2025, 12, 1, 7, 0, 0, tzinfo=timezone.utc)
    
    asia_state = get_market_state("ASIA_EQ", now)
    eu_state = get_market_state("EU_EQ", now)
    us_state = get_market_state("US_EQ", now)
    
    assert asia_state == MarketState.POST_CLOSE
    assert eu_state == MarketState.PRE_OPEN
    assert us_state == MarketState.OVERNIGHT
