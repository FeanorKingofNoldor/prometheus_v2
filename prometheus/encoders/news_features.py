"""Issuer×day news feature helper.

This module provides a small helper to pull **issuer×day** news features
from the historical DB, built on top of the article-level NEWS
embeddings and issuer×day aggregates populated elsewhere.

Given an ``issuer_id`` and ``as_of_date``, it returns:

- The aggregated issuer×day NEWS embedding from ``text_embeddings`` with
  ``source_type = 'NEWS_ISSUER_DAY'`` and a given ``model_id``.
- The number of raw news articles for that issuer on that date.
- The number of days since the issuer last had any news at or before
  ``as_of_date``.

This is intentionally a lightweight, query-only helper that can be used
by regimes, profiles, universes, or joint encoders when news context is
needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.logging import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class IssuerNewsFeatures:
    """Issuer×day news features.

    Attributes:
        issuer_id: Issuer identifier as stored in the runtime DB.
        as_of_date: Date for which features are requested.
        model_id: Text embedding model identifier (e.g. ``"text-fin-general-v1"``).
        embedding: Aggregated issuer×day NEWS embedding vector, or ``None``
            if no such embedding exists for this issuer/date.
        n_articles: Number of distinct news articles for this issuer on
            ``as_of_date``.
        days_since_last_news: Number of days since the most recent news
            article for this issuer on or before ``as_of_date``. ``None`` if
            the issuer has never had any news up to that date.
    """

    issuer_id: str
    as_of_date: date
    model_id: str
    embedding: Optional[NDArray[np.float_]]
    n_articles: int
    days_since_last_news: Optional[int]


def load_issuer_news_features(
    issuer_id: str,
    as_of_date: date,
    *,
    db_manager: DatabaseManager | None = None,
    model_id: str = "text-fin-general-v1",
    source_type: str = "NEWS_ISSUER_DAY",
) -> IssuerNewsFeatures:
    """Load issuer×day news features for a single issuer/date.

    The helper assumes that issuer×day embeddings have been populated in
    ``text_embeddings`` by a separate backfill (e.g.
    ``backfill_issuer_news_embeddings``) using the same ``model_id`` and
    ``source_type``.
    """

    db = db_manager or get_db_manager()

    embedding: Optional[NDArray[np.float_]] = None
    n_articles: int = 0
    days_since_last_news: Optional[int] = None

    with db.get_historical_connection() as conn:
        cursor = conn.cursor()
        try:
            # -----------------------------------------------------------------
            # 1) Aggregated issuer×day embedding from text_embeddings.
            # -----------------------------------------------------------------
            source_id = f"{issuer_id}:{as_of_date.isoformat()}"
            cursor.execute(
                """
                SELECT vector
                FROM text_embeddings
                WHERE source_type = %s
                  AND model_id = %s
                  AND source_id = %s
                LIMIT 1
                """,
                (source_type, model_id, source_id),
            )
            row = cursor.fetchone()
            if row is not None and row[0] is not None:
                vec_bytes = row[0]
                embedding = np.frombuffer(vec_bytes, dtype=np.float32).copy()

            # -----------------------------------------------------------------
            # 2) Same-day article count for this issuer.
            # -----------------------------------------------------------------
            cursor.execute(
                """
                SELECT COUNT(DISTINCT na.article_id)
                FROM news_links nl
                JOIN news_articles na ON na.article_id = nl.article_id
                WHERE nl.issuer_id = %s
                  AND DATE(na.timestamp) = %s
                """,
                (issuer_id, as_of_date),
            )
            n_articles_row = cursor.fetchone()
            if n_articles_row is not None and n_articles_row[0] is not None:
                n_articles = int(n_articles_row[0])

            # -----------------------------------------------------------------
            # 3) Days since last news (on or before as_of_date).
            # -----------------------------------------------------------------
            cursor.execute(
                """
                SELECT MAX(DATE(na.timestamp))
                FROM news_links nl
                JOIN news_articles na ON na.article_id = nl.article_id
                WHERE nl.issuer_id = %s
                  AND DATE(na.timestamp) <= %s
                """,
                (issuer_id, as_of_date),
            )
            last_date_row = cursor.fetchone()
            last_date = last_date_row[0] if last_date_row is not None else None
            if last_date is not None:
                days_since_last_news = (as_of_date - last_date).days
        finally:
            cursor.close()

    return IssuerNewsFeatures(
        issuer_id=issuer_id,
        as_of_date=as_of_date,
        model_id=model_id,
        embedding=embedding,
        n_articles=n_articles,
        days_since_last_news=days_since_last_news,
    )
