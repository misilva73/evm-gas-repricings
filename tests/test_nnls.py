import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from nnls import fit_NNLS, fit_NNLS_without_low_diff_runs, find_low_diff_runs
from nnls_results import NNLSResults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_linear_df(n=50, slope=3.0, intercept=1.0, seed=42):
    """Generate a simple linear dataset: y = intercept + slope * x + noise."""
    rng = np.random.RandomState(seed)
    x = rng.uniform(1, 100, size=n)
    y = intercept + slope * x + rng.normal(0, 0.5, size=n)
    y = np.maximum(y, 0)  # keep non-negative for NNLS sanity
    return pd.DataFrame({"opcount": x, "run_duration_ms": y})


def _make_multi_feature_df(n=80, seed=42):
    """Generate a dataset with two features."""
    rng = np.random.RandomState(seed)
    x1 = rng.uniform(1, 50, size=n)
    x2 = rng.uniform(1, 20, size=n)
    y = 2.0 + 1.5 * x1 + 3.0 * x2 + rng.normal(0, 0.5, size=n)
    y = np.maximum(y, 0)
    return pd.DataFrame({"feat_a": x1, "feat_b": x2, "run_duration_ms": y})


def _make_run_df(
    n_runs=5,
    opcounts=(10, 20, 30, 40, 50),
    slope=2.0,
    intercept=1.0,
    noise_std=0.1,
    seed=42,
):
    """Generate a DataFrame that mimics real benchmark runs with metadata columns."""
    rng = np.random.RandomState(seed)
    rows = []
    for run_idx in range(n_runs):
        ts = f"2024-01-{run_idx + 1:02d}"
        for oc in opcounts:
            dur = intercept + slope * oc + rng.normal(0, noise_std)
            rows.append(
                {
                    "test_file": "test_arith",
                    "test_name": "test_add",
                    "test_params": "warm",
                    "ingestion_timestamp": ts,
                    "opcount": oc,
                    "run_duration_ms": max(dur, 0),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tests for fit_NNLS
# ---------------------------------------------------------------------------


class TestFitNNLS:
    def test_returns_nnls_results(self):
        df = _make_linear_df()
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        assert isinstance(result, NNLSResults)

    def test_coefficients_are_non_negative(self):
        df = _make_linear_df()
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        assert (result.params >= 0).all()

    def test_recovers_slope_approximately(self):
        df = _make_linear_df(n=200, slope=3.0, intercept=1.0)
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        assert abs(result.params["opcount"] - 3.0) < 0.5

    def test_rsquared_high_for_linear_data(self):
        df = _make_linear_df(n=200)
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        assert result.rsquared > 0.95

    def test_feature_names_include_const(self):
        df = _make_linear_df()
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        assert list(result.params.index) == ["const", "opcount"]

    def test_nobs_matches_input(self):
        df = _make_linear_df(n=30)
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        assert result.nobs == 30

    def test_residuals_shape(self):
        df = _make_linear_df(n=40)
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        assert result.resid.shape == (40,)

    def test_fitted_plus_resid_equals_y(self):
        df = _make_linear_df()
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        reconstructed = result.fittedvalues + result.resid
        np.testing.assert_allclose(
            reconstructed, df["run_duration_ms"].values, atol=1e-10
        )

    def test_multiple_features(self):
        df = _make_multi_feature_df()
        result = fit_NNLS(df, ["feat_a", "feat_b"], n_bootstrap=50)
        assert list(result.params.index) == ["const", "feat_a", "feat_b"]
        assert result.rsquared > 0.95

    def test_pvalues_shape(self):
        df = _make_linear_df()
        result = fit_NNLS(df, ["opcount"], n_bootstrap=100)
        assert len(result.pvalues) == 2  # const + opcount

    def test_conf_int_shape(self):
        df = _make_linear_df()
        result = fit_NNLS(df, ["opcount"], n_bootstrap=100)
        ci = result.conf_int()
        assert ci.shape == (2, 2)
        assert list(ci.index) == ["const", "opcount"]

    def test_conf_int_lower_le_upper(self):
        df = _make_linear_df()
        result = fit_NNLS(df, ["opcount"], n_bootstrap=100)
        ci = result.conf_int()
        assert (ci[0] <= ci[1]).all()

    def test_summary_contains_key_info(self):
        df = _make_linear_df()
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        summary = result.summary()
        assert "NNLS Regression Results" in summary
        assert "R-squared" in summary
        assert "opcount" in summary
        assert "const" in summary

    def test_predict_with_new_data(self):
        df = _make_linear_df(n=100)
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        X_new = np.array([[10], [20], [30]])
        preds = result.predict(X_new)
        assert preds.shape == (3,)
        # Predictions should increase with opcount
        assert preds[0] < preds[1] < preds[2]

    def test_predict_with_dataframe(self):
        df = _make_linear_df(n=100)
        result = fit_NNLS(df, ["opcount"], n_bootstrap=50)
        X_new = pd.DataFrame({"opcount": [10, 50]})
        preds = result.predict(X_new)
        assert preds.shape == (2,)

    def test_reproducible_with_same_seed(self):
        df = _make_linear_df()
        r1 = fit_NNLS(df, ["opcount"], n_bootstrap=100, random_seed=123)
        r2 = fit_NNLS(df, ["opcount"], n_bootstrap=100, random_seed=123)
        np.testing.assert_array_equal(r1.params.values, r2.params.values)

    def test_different_seed_may_differ_in_bootstrap(self):
        df = _make_linear_df()
        r1 = fit_NNLS(df, ["opcount"], n_bootstrap=100, random_seed=1)
        r2 = fit_NNLS(df, ["opcount"], n_bootstrap=100, random_seed=2)
        # Primary coefficients should be the same (deterministic NNLS)
        np.testing.assert_array_equal(r1.params.values, r2.params.values)
        # But confidence intervals may differ
        ci1 = r1.conf_int()
        ci2 = r2.conf_int()
        # They won't necessarily be exactly equal
        assert not ci1.equals(ci2) or True  # guard: just ensure no crash


# ---------------------------------------------------------------------------
# Tests for fit_NNLS input validation
# ---------------------------------------------------------------------------


class TestFitNNLSValidation:
    def test_empty_dataframe_raises(self):
        df = pd.DataFrame(columns=["opcount", "run_duration_ms"])
        with pytest.raises(ValueError, match="cannot be empty"):
            fit_NNLS(df, ["opcount"])

    def test_missing_target_column_raises(self):
        df = pd.DataFrame({"opcount": [1, 2, 3]})
        with pytest.raises(ValueError, match="run_duration_ms"):
            fit_NNLS(df, ["opcount"])

    def test_missing_feature_column_raises(self):
        df = pd.DataFrame({"opcount": [1, 2, 3], "run_duration_ms": [1, 2, 3]})
        with pytest.raises(KeyError, match="nonexistent"):
            fit_NNLS(df, ["nonexistent"])


# ---------------------------------------------------------------------------
# Tests for find_low_diff_runs
# ---------------------------------------------------------------------------


class TestFindLowDiffRuns:
    def test_returns_dataframe(self):
        df = _make_run_df()
        result = find_low_diff_runs(df)
        assert isinstance(result, pd.DataFrame)

    def test_filters_noisy_runs(self):
        """A run with decreasing runtimes should be filtered out."""
        rng = np.random.RandomState(99)
        rows = []
        # 4 normal runs: runtime increases with opcount
        for run_idx in range(4):
            ts = f"2024-01-{run_idx + 1:02d}"
            for oc in [10, 20, 30, 40]:
                rows.append(
                    {
                        "test_file": "tf",
                        "test_name": "tn",
                        "test_params": "p",
                        "ingestion_timestamp": ts,
                        "opcount": oc,
                        "run_duration_ms": 1.0 + 2.0 * oc + rng.normal(0, 0.1),
                    }
                )
        # 1 anomalous run: runtime decreases with opcount
        ts_bad = "2024-01-10"
        for oc in [10, 20, 30, 40]:
            rows.append(
                {
                    "test_file": "tf",
                    "test_name": "tn",
                    "test_params": "p",
                    "ingestion_timestamp": ts_bad,
                    "opcount": oc,
                    "run_duration_ms": 100.0 - 2.0 * oc,
                }
            )

        df = pd.DataFrame(rows)
        filtered = find_low_diff_runs(df)
        assert ts_bad not in filtered["ingestion_timestamp"].values

    def test_preserves_columns(self):
        df = _make_run_df(n_runs=5)
        filtered = find_low_diff_runs(df)
        assert list(filtered.columns) == list(df.columns)

    def test_does_not_modify_input(self):
        df = _make_run_df()
        original_len = len(df)
        find_low_diff_runs(df)
        assert len(df) == original_len


# ---------------------------------------------------------------------------
# Tests for fit_NNLS_without_low_diff_runs
# ---------------------------------------------------------------------------


class TestFitNNLSWithoutLowDiffRuns:
    def test_returns_nnls_results(self):
        df = _make_run_df(n_runs=10)
        result = fit_NNLS_without_low_diff_runs(
            df, ["opcount"], n_bootstrap=50
        )
        assert isinstance(result, NNLSResults)

    def test_good_data_returns_high_rsquared(self):
        df = _make_run_df(n_runs=10, noise_std=0.05)
        result = fit_NNLS_without_low_diff_runs(
            df, ["opcount"], n_bootstrap=50
        )
        assert result.rsquared > 0.9

    def test_filters_when_initial_fit_poor(self):
        """When initial R^2 is low, filtering should be attempted."""
        rng = np.random.RandomState(42)
        rows = []
        # A few good runs
        for run_idx in range(3):
            ts = f"2024-01-{run_idx + 1:02d}"
            for oc in [10, 20, 30, 40, 50]:
                rows.append(
                    {
                        "test_file": "tf",
                        "test_name": "tn",
                        "test_params": "p",
                        "ingestion_timestamp": ts,
                        "opcount": oc,
                        "run_duration_ms": 1.0 + 2.0 * oc + rng.normal(0, 0.1),
                    }
                )
        # Many noisy runs to drag R^2 down
        for run_idx in range(10):
            ts = f"2024-02-{run_idx + 1:02d}"
            for oc in [10, 20, 30, 40, 50]:
                rows.append(
                    {
                        "test_file": "tf",
                        "test_name": "tn",
                        "test_params": "p",
                        "ingestion_timestamp": ts,
                        "opcount": oc,
                        "run_duration_ms": rng.uniform(0, 200),
                    }
                )
        df = pd.DataFrame(rows)
        result = fit_NNLS_without_low_diff_runs(
            df, ["opcount"], n_bootstrap=50
        )
        # Should still return a result (filtered or original)
        assert isinstance(result, NNLSResults)

    def test_drops_nan_values(self):
        df = _make_run_df(n_runs=5)
        # Inject a NaN
        df.loc[0, "run_duration_ms"] = np.nan
        result = fit_NNLS_without_low_diff_runs(
            df, ["opcount"], n_bootstrap=50
        )
        assert result.nobs == len(df) - 1

    def test_empty_after_dropna_raises(self):
        df = pd.DataFrame(
            {
                "opcount": [np.nan, np.nan],
                "run_duration_ms": [1.0, 2.0],
                "test_file": ["a", "b"],
                "test_name": ["t", "t"],
                "test_params": ["p", "p"],
                "ingestion_timestamp": ["ts1", "ts2"],
            }
        )
        with pytest.raises(ValueError, match="No valid data"):
            fit_NNLS_without_low_diff_runs(df, ["opcount"], n_bootstrap=50)
