"""Derived data computations for Prometheus v2 data ingestion.

This package contains helpers that derive secondary data sets from
primary market data. For Iteration 2 we focus on:

- Daily returns in ``returns_daily`` derived from ``prices_daily``.
- Rolling realised volatility in ``volatility_daily`` derived from
  ``prices_daily``.

These modules are designed to be idempotent at the instrument level:
callers may safely recompute derived data for an instrument by first
clearing existing rows for that instrument/date range.
"""
