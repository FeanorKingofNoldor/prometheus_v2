"""Tests for daily λ / scenario / STAB-scenario config loaders in pipeline tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from prometheus.pipeline import tasks


class TestDailyUniverseLambdaConfig:
    """Tests for _load_daily_universe_lambda_config."""

    def test_defaults_when_config_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """If the YAML file is missing, return a config with lambda disabled."""

        # Point PROJECT_ROOT at an empty temporary directory.
        monkeypatch.setattr(tasks, "PROJECT_ROOT", tmp_path)

        cfg = tasks._load_daily_universe_lambda_config("US")

        assert cfg.predictions_csv is None
        assert cfg.experiment_id is None
        assert cfg.score_column == "lambda_hat"
        assert cfg.score_weight == 0.0

    def test_loads_region_specific_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """YAML values for a region are mapped into DailyUniverseLambdaConfig."""

        root = tmp_path
        cfg_dir = root / "configs" / "universe"
        cfg_dir.mkdir(parents=True)

        yaml_text = """
core_long_eq:
  US:
    lambda_predictions_csv: data/lambda_predictions_US_EQ.csv
    lambda_experiment_id: US_EQ_GL_POLY2_V0
    lambda_score_column: lambda_custom
    lambda_score_weight: 7.5
  EU:
    lambda_predictions_csv: data/lambda_predictions_EU_EQ.csv
    lambda_experiment_id: EU_EQ_EXP
    lambda_score_weight: 5.0
"""
        (cfg_dir / "core_long_eq_daily.yaml").write_text(yaml_text)

        monkeypatch.setattr(tasks, "PROJECT_ROOT", root)

        cfg_us = tasks._load_daily_universe_lambda_config("US")
        assert cfg_us.predictions_csv == "data/lambda_predictions_US_EQ.csv"
        assert cfg_us.experiment_id == "US_EQ_GL_POLY2_V0"
        assert cfg_us.score_column == "lambda_custom"
        assert pytest.approx(cfg_us.score_weight, rel=1e-6) == 7.5

        cfg_eu = tasks._load_daily_universe_lambda_config("EU")
        assert cfg_eu.predictions_csv == "data/lambda_predictions_EU_EQ.csv"
        assert cfg_eu.experiment_id == "EU_EQ_EXP"
        # EU entry omits lambda_score_column so it should default.
        assert cfg_eu.score_column == "lambda_hat"
        assert pytest.approx(cfg_eu.score_weight, rel=1e-6) == 5.0


class TestDailyPortfolioRiskConfig:
    """Tests for _load_daily_portfolio_risk_config."""

    def test_defaults_when_config_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """If the YAML file is missing, return a config with features disabled."""

        monkeypatch.setattr(tasks, "PROJECT_ROOT", tmp_path)

        cfg = tasks._load_daily_portfolio_risk_config("US")

        assert cfg.scenario_risk_set_id is None
        assert cfg.stab_scenario_set_id is None
        assert cfg.stab_joint_model_id == "joint-stab-fragility-v1"

    def test_loads_scenario_and_stab_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """YAML values map into scenario and STAB-scenario settings."""

        root = tmp_path
        cfg_dir = root / "configs" / "portfolio"
        cfg_dir.mkdir(parents=True)

        yaml_text = """
core_long_eq:
  US:
    scenario_risk_set_id: US_EQ_HIST_20D_2020ON
    stab_scenario_set_id: US_EQ_HIST_20D_2020ON
    stab_joint_model_id: joint-stab-fragility-v1
  EU:
    scenario_risk_set_id: EU_EQ_HIST_20D
"""
        (cfg_dir / "core_long_eq_daily.yaml").write_text(yaml_text)

        monkeypatch.setattr(tasks, "PROJECT_ROOT", root)

        cfg_us = tasks._load_daily_portfolio_risk_config("US")
        assert cfg_us.scenario_risk_set_id == "US_EQ_HIST_20D_2020ON"
        assert cfg_us.stab_scenario_set_id == "US_EQ_HIST_20D_2020ON"
        assert cfg_us.stab_joint_model_id == "joint-stab-fragility-v1"

        cfg_eu = tasks._load_daily_portfolio_risk_config("EU")
        assert cfg_eu.scenario_risk_set_id == "EU_EQ_HIST_20D"
        # No STAB config for EU; defaults should apply.
        assert cfg_eu.stab_scenario_set_id is None
        assert cfg_eu.stab_joint_model_id == "joint-stab-fragility-v1"
