"""Prometheus v2 – External data ingestion package.

This package contains modules responsible for fetching external data
(e.g. prices, fundamentals, macro series, news) from third‑party
providers and writing it into the historical database using the
canonical schemas defined in :mod:`prometheus.data`.

For Iteration 2 we start with a minimal EODHD client and a concrete
price ingestion helper that populates ``prices_daily`` for US equities.
"""
