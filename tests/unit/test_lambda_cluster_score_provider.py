from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from prometheus.opportunity.lambda_provider import CsvLambdaClusterScoreProvider


class TestCsvLambdaClusterScoreProvider:
    def test_loads_and_queries_scores_by_cluster(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "lambda_preds.csv"
        df = pd.DataFrame(
            {
                "as_of_date": ["2024-01-02", "2024-01-02", "2024-01-03"],
                "market_id": ["US_EQ", "US_EQ", "US_EQ"],
                "sector": ["TECH", "FIN", "TECH"],
                "soft_target_class": ["STABLE", "FRAGILE", "STABLE"],
                "lambda_hat": [1.0, 2.0, 3.0],
                "experiment_id": ["EXP1", "EXP1", "EXP1"],
            }
        )
        df.to_csv(csv_path, index=False)

        provider = CsvLambdaClusterScoreProvider(csv_path=csv_path, experiment_id="EXP1")

        score = provider.get_cluster_score(
            as_of_date=date(2024, 1, 2),
            market_id="US_EQ",
            sector="TECH",
            soft_target_class="STABLE",
        )
        assert score == pytest.approx(1.0)

        missing = provider.get_cluster_score(
            as_of_date=date(2024, 1, 4),
            market_id="US_EQ",
            sector="TECH",
            soft_target_class="STABLE",
        )
        assert missing is None

    def test_raises_on_missing_columns(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "bad_lambda_preds.csv"
        df = pd.DataFrame({"foo": [1], "bar": [2]})
        df.to_csv(csv_path, index=False)

        with pytest.raises(ValueError):
            CsvLambdaClusterScoreProvider(csv_path=csv_path)

    def test_filters_by_experiment_id_if_provided(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "lambda_preds_exp.csv"
        df = pd.DataFrame(
            {
                "as_of_date": ["2024-01-02", "2024-01-02"],
                "market_id": ["US_EQ", "US_EQ"],
                "sector": ["TECH", "TECH"],
                "soft_target_class": ["STABLE", "STABLE"],
                "lambda_hat": [5.0, 10.0],
                "experiment_id": ["EXP1", "EXP2"],
            }
        )
        df.to_csv(csv_path, index=False)

        provider = CsvLambdaClusterScoreProvider(csv_path=csv_path, experiment_id="EXP2")

        score = provider.get_cluster_score(
            as_of_date=date(2024, 1, 2),
            market_id="US_EQ",
            sector="TECH",
            soft_target_class="STABLE",
        )
        assert score == pytest.approx(10.0)
