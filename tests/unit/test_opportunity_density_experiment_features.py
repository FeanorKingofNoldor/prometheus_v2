from __future__ import annotations

import numpy as np
import pandas as pd

from prometheus.scripts.run_opportunity_density_experiment import _build_feature_matrix


class TestOpportunityDensityExperimentFeatures:
    def test_build_feature_matrix_handles_missing_columns_and_nans(self) -> None:
        df = pd.DataFrame(
            {
                "lambda_value": [1.0, 2.0],
                # Include a column with NaNs to ensure they are converted
                # to zeros inside the feature matrix.
                "regime_risk_score": [0.5, np.nan],
            }
        )

        # Request both present and missing feature columns.
        X = _build_feature_matrix(df, ["lambda_value", "regime_risk_score", "avg_vol_window"])

        # Shape: 2 rows, 3 features.
        assert X.shape == (2, 3)

        # First row: lambda_value=1.0, regime_risk_score=0.5, avg_vol_window missing→0.0
        assert np.allclose(X[0], np.array([1.0, 0.5, 0.0]))

        # Second row: lambda_value=2.0, regime_risk_score NaN→0.0, avg_vol_window missing→0.0
        assert np.allclose(X[1], np.array([2.0, 0.0, 0.0]))
