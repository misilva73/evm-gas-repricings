import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from runtime_estimation import (
    build_result_dict,
    add_param_results_to_dict,
    prepare_non_simple_model_data,
)
from nnls_results import NNLSResults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_nnls_result(
    features=("const", "opcount"),
    coefficients=(1.0, 3.0),
    n=50,
    seed=42,
):
    """Build a real NNLSResults object from specified coefficients."""
    rng = np.random.RandomState(seed)
    coefs = np.array(coefficients)
    n_features = len(features)
    # Build X matrix: first column is ones (const), rest are random features
    X = np.column_stack(
        [np.ones(n)]
        + [rng.uniform(1, 100, size=n) for _ in range(n_features - 1)]
    )
    y = X @ coefs + rng.normal(0, 0.3, size=n)
    y = np.maximum(y, 0)
    # Bootstrap coefs: small perturbations around true coefficients
    bootstrap_coefs = np.tile(coefs, (100, 1)) + rng.normal(0, 0.1, size=(100, n_features))
    bootstrap_coefs = np.maximum(bootstrap_coefs, 0)
    return NNLSResults(
        X=X,
        y=y,
        y_name="run_duration_ms",
        coefficients=coefs,
        bootstrap_coefs=bootstrap_coefs,
        feature_names=list(features),
        residual_norm=0.0,
    )


def _make_op_df(opcounts=(10, 20, 30, 40, 50), n_runs=3, seed=42):
    """Build a DataFrame mimicking benchmark data with test_params."""
    rng = np.random.RandomState(seed)
    rows = []
    for run_idx in range(n_runs):
        for oc in opcounts:
            msg_size = rng.choice([32, 64, 128])
            rows.append(
                {
                    "opcount": oc,
                    "test_params": f"opcount_{oc}-msg_size_{msg_size}",
                    "run_duration_ms": 1.0 + 2.0 * oc + 0.5 * msg_size + rng.normal(0, 0.1),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tests for build_result_dict
# ---------------------------------------------------------------------------


class TestBuildResultDict:
    def test_returns_dict(self):
        result = _make_nnls_result()
        out = build_result_dict(result, "ADD", ["client_name"], ("geth",))
        assert isinstance(out, dict)

    def test_contains_opcode(self):
        result = _make_nnls_result()
        out = build_result_dict(result, "MUL", ["client_name"], ("reth",))
        assert out["opcode"] == "MUL"

    def test_contains_group_by_columns(self):
        result = _make_nnls_result()
        out = build_result_dict(
            result, "ADD", ["client_name", "test_name"], ("geth", "test_arith")
        )
        assert out["client_name"] == "geth"
        assert out["test_name"] == "test_arith"

    def test_contains_nobs(self):
        result = _make_nnls_result(n=30)
        out = build_result_dict(result, "ADD", ["client_name"], ("geth",))
        assert out["nobs"] == 30

    def test_intercept_matches_result(self):
        result = _make_nnls_result(coefficients=(5.0, 2.0))
        out = build_result_dict(result, "ADD", ["client_name"], ("geth",))
        assert out["intercept"] == result.params["const"]

    def test_slope_matches_result(self):
        result = _make_nnls_result(coefficients=(1.0, 7.0))
        out = build_result_dict(result, "ADD", ["client_name"], ("geth",))
        assert out["slope"] == result.params["opcount"]

    def test_contains_pvalues(self):
        result = _make_nnls_result()
        out = build_result_dict(result, "ADD", ["client_name"], ("geth",))
        assert "intercept_pvalue" in out
        assert "slope_pvalue" in out
        assert out["intercept_pvalue"] == result.pvalues["const"]
        assert out["slope_pvalue"] == result.pvalues["opcount"]

    def test_contains_rsquared(self):
        result = _make_nnls_result()
        out = build_result_dict(result, "ADD", ["client_name"], ("geth",))
        assert out["rsquared"] == result.rsquared
        assert out["rsquared_adj"] == result.rsquared_adj

    def test_contains_confidence_intervals(self):
        result = _make_nnls_result()
        out = build_result_dict(result, "ADD", ["client_name"], ("geth",))
        ci = result.conf_int()
        assert out["slope_conf_int_low"] == ci.loc["opcount", 0]
        assert out["slope_conf_int_high"] == ci.loc["opcount", 1]

    def test_conf_int_low_le_high(self):
        result = _make_nnls_result()
        out = build_result_dict(result, "ADD", ["client_name"], ("geth",))
        assert out["slope_conf_int_low"] <= out["slope_conf_int_high"]

    def test_all_expected_keys_present(self):
        result = _make_nnls_result()
        out = build_result_dict(
            result, "ADD", ["client_name", "test_name"], ("geth", "test_arith")
        )
        expected_keys = {
            "opcode",
            "client_name",
            "test_name",
            "nobs",
            "intercept",
            "intercept_pvalue",
            "rsquared",
            "rsquared_adj",
            "slope",
            "slope_pvalue",
            "slope_conf_int_low",
            "slope_conf_int_high",
        }
        assert set(out.keys()) == expected_keys

    def test_single_group_by(self):
        result = _make_nnls_result()
        out = build_result_dict(result, "ADD", ["client_name"], ("geth",))
        assert "client_name" in out
        assert "test_name" not in out


# ---------------------------------------------------------------------------
# Tests for add_param_results_to_dict
# ---------------------------------------------------------------------------


class TestAddParamResultsToDict:
    def test_adds_existing_param(self):
        result = _make_nnls_result(
            features=("const", "opcount", "msg_size"),
            coefficients=(1.0, 3.0, 0.5),
        )
        out_dict = {}
        add_param_results_to_dict(out_dict, result, ["msg_size"])
        assert "msg_size" in out_dict
        assert out_dict["msg_size"] == result.params["msg_size"]

    def test_adds_pvalue_for_param(self):
        result = _make_nnls_result(
            features=("const", "opcount", "msg_size"),
            coefficients=(1.0, 3.0, 0.5),
        )
        out_dict = {}
        add_param_results_to_dict(out_dict, result, ["msg_size"])
        assert "msg_size_pvalue" in out_dict
        assert out_dict["msg_size_pvalue"] == result.pvalues["msg_size"]

    def test_adds_confidence_intervals_for_param(self):
        result = _make_nnls_result(
            features=("const", "opcount", "msg_size"),
            coefficients=(1.0, 3.0, 0.5),
        )
        out_dict = {}
        add_param_results_to_dict(out_dict, result, ["msg_size"])
        ci = result.conf_int()
        assert out_dict["msg_size_conf_int_low"] == ci.loc["msg_size", 0]
        assert out_dict["msg_size_conf_int_high"] == ci.loc["msg_size", 1]

    def test_skips_missing_param(self):
        result = _make_nnls_result(
            features=("const", "opcount"),
            coefficients=(1.0, 3.0),
        )
        out_dict = {}
        add_param_results_to_dict(out_dict, result, ["msg_size"])
        assert "msg_size" not in out_dict

    def test_handles_multiple_params(self):
        result = _make_nnls_result(
            features=("const", "opcount", "msg_size", "copy_size"),
            coefficients=(1.0, 3.0, 0.5, 0.2),
        )
        out_dict = {}
        add_param_results_to_dict(out_dict, result, ["msg_size", "copy_size"])
        assert "msg_size" in out_dict
        assert "copy_size" in out_dict
        assert out_dict["msg_size"] == 0.5
        assert out_dict["copy_size"] == 0.2

    def test_mixed_present_and_missing_params(self):
        result = _make_nnls_result(
            features=("const", "opcount", "msg_size"),
            coefficients=(1.0, 3.0, 0.5),
        )
        out_dict = {}
        add_param_results_to_dict(out_dict, result, ["msg_size", "nonexistent"])
        assert "msg_size" in out_dict
        assert "nonexistent" not in out_dict

    def test_mutates_dict_in_place(self):
        result = _make_nnls_result(
            features=("const", "opcount", "msg_size"),
            coefficients=(1.0, 3.0, 0.5),
        )
        out_dict = {"opcode": "KECCAK256"}
        add_param_results_to_dict(out_dict, result, ["msg_size"])
        # Existing key preserved
        assert out_dict["opcode"] == "KECCAK256"
        # New key added
        assert "msg_size" in out_dict

    def test_returns_none(self):
        result = _make_nnls_result(
            features=("const", "opcount", "msg_size"),
            coefficients=(1.0, 3.0, 0.5),
        )
        ret = add_param_results_to_dict({}, result, ["msg_size"])
        assert ret is None

    def test_empty_params_list(self):
        result = _make_nnls_result()
        out_dict = {"opcode": "ADD"}
        add_param_results_to_dict(out_dict, result, [])
        assert out_dict == {"opcode": "ADD"}


# ---------------------------------------------------------------------------
# Tests for prepare_non_simple_model_data
# ---------------------------------------------------------------------------


class TestPrepareNonSimpleModelData:
    def test_returns_tuple(self):
        df = _make_op_df()
        model_df, features = prepare_non_simple_model_data(df, ["msg_size"])
        assert isinstance(model_df, pd.DataFrame)
        assert isinstance(features, list)

    def test_features_start_with_opcount(self):
        df = _make_op_df()
        _, features = prepare_non_simple_model_data(df, ["msg_size"])
        assert features[0] == "opcount"

    def test_detected_feature_in_features(self):
        df = _make_op_df()
        _, features = prepare_non_simple_model_data(df, ["msg_size"])
        assert "msg_size" in features

    def test_missing_param_excluded_from_features(self):
        """A param that is NaN for all rows should not appear in features."""
        df = _make_op_df()
        # "nonexistent_param" won't match any test_params string
        _, features = prepare_non_simple_model_data(
            df, ["msg_size", "nonexistent_param"]
        )
        assert "msg_size" in features
        assert "nonexistent_param" not in features

    def test_extra_features_multiplied_by_opcount(self):
        df = _make_op_df()
        model_df, features = prepare_non_simple_model_data(df, ["msg_size"])
        # For each row, model_df["msg_size"] should equal original_msg_size * opcount
        original_msg_sizes = df["test_params"].str.extract(r"msg_size_(\d+)")[0].astype(float)
        expected = original_msg_sizes * df["opcount"]
        pd.testing.assert_series_equal(
            model_df["msg_size"].reset_index(drop=True),
            expected.reset_index(drop=True),
            check_names=False,
        )

    def test_opcount_unchanged_in_model_df(self):
        df = _make_op_df()
        model_df, _ = prepare_non_simple_model_data(df, ["msg_size"])
        pd.testing.assert_series_equal(
            model_df["opcount"].reset_index(drop=True),
            df["opcount"].reset_index(drop=True),
            check_names=False,
        )

    def test_does_not_modify_input_opcount(self):
        df = _make_op_df()
        original_opcounts = df["opcount"].copy()
        prepare_non_simple_model_data(df, ["msg_size"])
        pd.testing.assert_series_equal(df["opcount"], original_opcounts)

    def test_model_df_is_a_copy(self):
        df = _make_op_df()
        model_df, _ = prepare_non_simple_model_data(df, ["msg_size"])
        # Modifying model_df should not affect original
        model_df["opcount"] = 0
        assert (df["opcount"] != 0).all()

    def test_multiple_params(self):
        """Test with data containing multiple extractable params."""
        rows = [
            {"opcount": 10, "test_params": "opcount_10-msg_size_32-copy_size_64", "run_duration_ms": 5.0},
            {"opcount": 20, "test_params": "opcount_20-msg_size_64-copy_size_128", "run_duration_ms": 10.0},
            {"opcount": 30, "test_params": "opcount_30-msg_size_128-copy_size_256", "run_duration_ms": 15.0},
        ]
        df = pd.DataFrame(rows)
        model_df, features = prepare_non_simple_model_data(df, ["msg_size", "copy_size"])
        assert "msg_size" in features
        assert "copy_size" in features
        # Check multiplication: first row msg_size=32, opcount=10 → model value=320
        assert model_df.iloc[0]["msg_size"] == 32.0 * 10
        assert model_df.iloc[0]["copy_size"] == 64.0 * 10

    def test_all_params_missing_returns_opcount_only(self):
        """If no params match any rows, features should just be ['opcount']."""
        rows = [
            {"opcount": 10, "test_params": "opcount_10", "run_duration_ms": 5.0},
            {"opcount": 20, "test_params": "opcount_20", "run_duration_ms": 10.0},
        ]
        df = pd.DataFrame(rows)
        _, features = prepare_non_simple_model_data(df, ["msg_size", "copy_size"])
        assert features == ["opcount"]

    def test_constant_param_excluded_from_features(self):
        """A param that exists but has the same value for all rows should not appear in features."""
        rows = [
            {"opcount": 10, "test_params": "opcount_10-update_0", "run_duration_ms": 5.0},
            {"opcount": 20, "test_params": "opcount_20-update_0", "run_duration_ms": 10.0},
            {"opcount": 30, "test_params": "opcount_30-update_0", "run_duration_ms": 15.0},
        ]
        df = pd.DataFrame(rows)
        _, features = prepare_non_simple_model_data(df, ["update"])
        assert "update" not in features
        assert features == ["opcount"]

    def test_constant_param_excluded_but_varying_param_kept(self):
        """Only constant-value params are excluded; varying ones are kept."""
        rows = [
            {"opcount": 10, "test_params": "opcount_10-msg_size_32-update_0", "run_duration_ms": 5.0},
            {"opcount": 20, "test_params": "opcount_20-msg_size_64-update_0", "run_duration_ms": 10.0},
            {"opcount": 30, "test_params": "opcount_30-msg_size_128-update_0", "run_duration_ms": 15.0},
        ]
        df = pd.DataFrame(rows)
        _, features = prepare_non_simple_model_data(df, ["msg_size", "update"])
        assert "msg_size" in features
        assert "update" not in features

    def test_feature_column_dtype_is_float(self):
        df = _make_op_df()
        model_df, features = prepare_non_simple_model_data(df, ["msg_size"])
        for feat in features:
            if feat != "opcount":
                assert model_df[feat].dtype == np.float64
