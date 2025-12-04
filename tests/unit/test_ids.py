"""
Prometheus v2: Tests for ID Generation Utilities

Test suite for ``prometheus.core.ids``. Covers:
- UUID format and uniqueness
- Context ID structure
- Run ID prefix behaviour
"""

from __future__ import annotations

from datetime import date

from prometheus.core.ids import (
    generate_context_id,
    generate_decision_id,
    generate_run_id,
    generate_uuid,
)


class TestIDGeneration:
    """Tests for ID generation functions."""

    def test_generate_uuid_format(self) -> None:
        """Generated UUIDs should have 5 dash-separated components."""

        uuid_str = generate_uuid()
        parts = uuid_str.split("-")

        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[4]) == 12

    def test_generate_uuid_unique(self) -> None:
        """Generated UUIDs should be unique across many calls."""

        uuids = {generate_uuid() for _ in range(100)}
        assert len(uuids) == 100

    def test_generate_decision_id_is_uuid(self) -> None:
        """Decision IDs should be valid UUID strings."""

        decision_id = generate_decision_id()
        parts = decision_id.split("-")
        assert len(parts) == 5

    def test_generate_context_id_format(self) -> None:
        """Context IDs should embed date, portfolio ID, and strategy ID."""

        ctx_id = generate_context_id(
            as_of_date=date(2024, 1, 15),
            portfolio_id="port1",
            strategy_id="strat1",
        )

        assert ctx_id == "20240115_port1_strat1"

    def test_generate_run_id_with_and_without_prefix(self) -> None:
        """Run IDs should support optional prefixes."""

        plain = generate_run_id()
        prefixed = generate_run_id(prefix="backtest")

        assert len(plain.split("-")) == 5
        assert prefixed.startswith("backtest_")
        uuid_part = prefixed.split("_", 1)[1]
        assert len(uuid_part.split("-")) == 5
