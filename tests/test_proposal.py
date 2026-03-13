import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from proposal import (
    select_worst_case_estimates,
    compute_worst_gas_proposal,
    find_missing_client_estimations,
    compute_state_access_gas_params,
    compute_derived_state_access_params,
    find_poor_fit_glue_opcodes,
    _apply_filter,
    _STATE_ACCESS_CURRENT_GAS,
)


def _make_results_df(rows):
    """Build a DataFrame matching the shape of results.csv.

    Each row dict should contain at minimum: opcode, client_name, test_name,
    slope, slope_pvalue, slope_conf_int_low, slope_conf_int_high, rsquared.
    """
    return pd.DataFrame(rows)


def _base_row(
    opcode="ADD",
    client="geth",
    test_name="test_add",
    slope=0.01,
    slope_pvalue=0.01,
    slope_conf_low=0.008,
    slope_conf_high=0.012,
    rsquared=0.95,
):
    return {
        "opcode": opcode,
        "client_name": client,
        "test_name": test_name,
        "slope": slope,
        "slope_pvalue": slope_pvalue,
        "slope_conf_int_low": slope_conf_low,
        "slope_conf_int_high": slope_conf_high,
        "rsquared": rsquared,
    }


# ---------------------------------------------------------------------------
# Tests for select_worst_case_estimates
# ---------------------------------------------------------------------------


class TestSelectWorstCaseEstimates:
    def test_basic_single_opcode_single_client(self):
        """Single opcode, single client, good fit -> should produce one row."""
        df = _make_results_df(
            [_base_row(slope=0.05, slope_pvalue=0.01, slope_conf_low=0.04, slope_conf_high=0.06)]
        )
        anchor_rate = 1_000_000.0  # 1M gas/s
        new_gas_df, poor_fit_dict = select_worst_case_estimates(
            df,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=anchor_rate,
            params_multipliers={},
        )
        assert len(new_gas_df) == 1
        assert new_gas_df.iloc[0]["param"] == "constant"
        assert new_gas_df.iloc[0]["runtime_ms"] == 0.05
        expected_gas = np.ceil(anchor_rate * 0.05 / 1e3)
        assert new_gas_df.iloc[0]["new_gas_rounded"] == expected_gas
        assert len(poor_fit_dict) == 0

    def test_selects_worst_case_from_good_fits(self):
        """Multiple test configs with good fits -> selects max runtime."""
        df = _make_results_df(
            [
                _base_row(test_name="test_a", slope=0.02, slope_pvalue=0.01),
                _base_row(test_name="test_b", slope=0.05, slope_pvalue=0.03),
            ]
        )
        new_gas_df, _ = select_worst_case_estimates(
            df,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
        )
        assert len(new_gas_df) == 1
        assert new_gas_df.iloc[0]["runtime_ms"] == 0.05
        assert new_gas_df.iloc[0]["test_name"] == "test_b"

    def test_prefers_good_fits_over_poor_fits(self):
        """Good fit with lower runtime should be preferred over poor fit with higher runtime."""
        df = _make_results_df(
            [
                _base_row(test_name="test_good", slope=0.03, slope_pvalue=0.01),
                _base_row(test_name="test_bad", slope=0.10, slope_pvalue=0.10),
            ]
        )
        new_gas_df, _ = select_worst_case_estimates(
            df,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
        )
        assert len(new_gas_df) == 1
        assert new_gas_df.iloc[0]["runtime_ms"] == 0.03

    def test_poor_fits_tracked_in_dict(self):
        """When all fits are poor (p >= 0.05), they are tracked in poor_fit_dict."""
        df = _make_results_df(
            [
                _base_row(client="geth", slope=0.05, slope_pvalue=0.10),
                _base_row(client="reth", slope=0.04, slope_pvalue=0.20),
            ]
        )
        _, poor_fit_dict = select_worst_case_estimates(
            df,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
        )
        assert ("ADD", "slope") in poor_fit_dict
        assert poor_fit_dict[("ADD", "slope")] == {"geth", "reth"}

    def test_poor_rsquared_tracked(self):
        """Models with R² <= 0.5 are tracked as poor fit models."""
        df = _make_results_df(
            [_base_row(rsquared=0.3)]
        )
        _, poor_fit_dict = select_worst_case_estimates(
            df,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
        )
        assert ("ADD", "Model") in poor_fit_dict
        assert "geth" in poor_fit_dict[("ADD", "Model")]

    def test_multiple_clients(self):
        """Each client gets its own row in the output."""
        df = _make_results_df(
            [
                _base_row(client="geth", slope=0.02),
                _base_row(client="reth", slope=0.03),
            ]
        )
        new_gas_df, _ = select_worst_case_estimates(
            df,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
        )
        assert len(new_gas_df) == 2
        clients = set(new_gas_df["client_name"])
        assert clients == {"geth", "reth"}

    def test_extra_param_column(self):
        """Variable operations with extra params produce rows for each param."""
        df = _make_results_df(
            [
                {
                    **_base_row(),
                    "num_rounds": 0.001,
                    "num_rounds_pvalue": 0.02,
                    "num_rounds_conf_int_low": 0.0008,
                    "num_rounds_conf_int_high": 0.0012,
                }
            ]
        )
        new_gas_df, _ = select_worst_case_estimates(
            df,
            params=["num_rounds"],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
        )
        # Should have one row for "constant" (slope) and one for "num_rounds"
        assert len(new_gas_df) == 2
        params_found = set(new_gas_df["param"])
        assert params_found == {"constant", "num_rounds"}

    def test_params_multiplier_applied(self):
        """params_multipliers should scale the new_gas calculation."""
        df = _make_results_df(
            [
                {
                    **_base_row(slope=0.01),
                    "msg_size": 0.02,
                    "msg_size_pvalue": 0.01,
                    "msg_size_conf_int_low": 0.015,
                    "msg_size_conf_int_high": 0.025,
                }
            ]
        )
        anchor_rate = 1_000_000.0
        new_gas_df, _ = select_worst_case_estimates(
            df,
            params=["msg_size"],
            group_by=["client_name", "test_name"],
            anchor_rate=anchor_rate,
            params_multipliers={"msg_size": 2.0},
        )
        msg_row = new_gas_df[new_gas_df["param"] == "msg_size"].iloc[0]
        # new_gas = anchor_rate * runtime_ms * multiplier / 1e3
        expected = anchor_rate * 0.02 * 2.0 / 1e3
        assert msg_row["new_gas"] == expected

    def test_missing_param_column_skipped(self):
        """Params not present in results_df columns are silently skipped."""
        df = _make_results_df([_base_row()])
        new_gas_df, _ = select_worst_case_estimates(
            df,
            params=["nonexistent_param"],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
        )
        # Only the slope/constant row should exist
        assert len(new_gas_df) == 1
        assert new_gas_df.iloc[0]["param"] == "constant"

    def test_nan_slope_rows_filtered(self):
        """Rows where slope is NaN should be ignored."""
        df = _make_results_df(
            [
                _base_row(slope=np.nan, slope_pvalue=np.nan),
                _base_row(client="reth", slope=0.05),
            ]
        )
        new_gas_df, _ = select_worst_case_estimates(
            df,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
        )
        assert len(new_gas_df) == 1
        assert new_gas_df.iloc[0]["client_name"] == "reth"


# ---------------------------------------------------------------------------
# Tests for compute_worst_gas_proposal
# ---------------------------------------------------------------------------


class TestComputeWorstGasProposal:
    def test_takes_max_across_clients(self):
        """Should take the maximum new_gas_rounded per (opcode, param)."""
        new_gas_df = pd.DataFrame(
            [
                {"opcode": "SLOAD", "param": "constant", "new_gas_rounded": 100, "client_name": "geth"},
                {"opcode": "SLOAD", "param": "constant", "new_gas_rounded": 150, "client_name": "reth"},
            ]
        )
        result = compute_worst_gas_proposal(new_gas_df)
        assert len(result) == 1
        assert result.iloc[0]["new_gas_rounded"] == 150

    def test_includes_current_gas_and_change(self):
        """Result should include current_gas lookup and change calculation."""
        new_gas_df = pd.DataFrame(
            [
                {"opcode": "SLOAD", "param": "constant", "new_gas_rounded": 4000.0, "client_name": "geth"},
            ]
        )
        result = compute_worst_gas_proposal(new_gas_df)
        assert "current_gas" in result.columns
        assert "change" in result.columns
        # SLOAD constant -> current gas is known (should not be None)
        assert result.iloc[0]["current_gas"] is not None

    def test_change_calculation(self):
        """Change should be (new / current) - 1, rounded to 2 decimals."""
        new_gas_df = pd.DataFrame(
            [
                {"opcode": "SLOAD", "param": "constant", "new_gas_rounded": 400.0, "client_name": "geth"},
            ]
        )
        result = compute_worst_gas_proposal(new_gas_df)
        current = result.iloc[0]["current_gas"]
        if current is not None and current > 0:
            expected_change = round(400.0 / current - 1, 2)
            assert result.iloc[0]["change"] == expected_change

    def test_multiple_opcodes_and_params(self):
        """Each (opcode, param) combination gets its own row."""
        new_gas_df = pd.DataFrame(
            [
                {"opcode": "SLOAD", "param": "constant", "new_gas_rounded": 100.0, "client_name": "geth"},
                {"opcode": "SSTORE", "param": "constant", "new_gas_rounded": 200.0, "client_name": "geth"},
                {"opcode": "SSTORE", "param": "new", "new_gas_rounded": 300.0, "client_name": "geth"},
            ]
        )
        result = compute_worst_gas_proposal(new_gas_df)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Tests for find_missing_client_estimations
# ---------------------------------------------------------------------------


class TestFindMissingClientEstimations:
    def test_all_clients_present(self):
        """Returns empty dict when all 5 clients are present for every opcode."""
        all_clients = ["geth", "reth", "nethermind", "besu", "erigon"]
        rows = [{"opcode": "ADD", "client_name": c} for c in all_clients]
        df = pd.DataFrame(rows)
        result = find_missing_client_estimations(df)
        assert result == {}

    def test_missing_one_client(self):
        """Detects a single missing client."""
        present = ["geth", "reth", "nethermind", "besu"]
        rows = [{"opcode": "ADD", "client_name": c} for c in present]
        df = pd.DataFrame(rows)
        result = find_missing_client_estimations(df)
        assert "ADD" in result
        assert result["ADD"] == ["erigon"]

    def test_missing_multiple_clients(self):
        """Detects multiple missing clients, returned sorted."""
        present = ["geth", "reth"]
        rows = [{"opcode": "MUL", "client_name": c} for c in present]
        df = pd.DataFrame(rows)
        result = find_missing_client_estimations(df)
        assert "MUL" in result
        assert result["MUL"] == sorted(["besu", "erigon", "nethermind"])

    def test_multiple_opcodes_mixed(self):
        """Some opcodes complete, some missing -> only missing ones returned."""
        all_clients = ["geth", "reth", "nethermind", "besu", "erigon"]
        rows = [{"opcode": "ADD", "client_name": c} for c in all_clients]
        rows += [{"opcode": "SUB", "client_name": c} for c in ["geth", "reth"]]
        df = pd.DataFrame(rows)
        result = find_missing_client_estimations(df)
        assert "ADD" not in result
        assert "SUB" in result
        assert set(result["SUB"]) == {"besu", "erigon", "nethermind"}

    def test_empty_dataframe(self):
        """Empty dataframe -> empty result."""
        df = pd.DataFrame(columns=["opcode", "client_name"])
        result = find_missing_client_estimations(df)
        assert result == {}

    def test_required_opcode_entirely_absent(self):
        """An opcode in required_opcodes with no rows in results_df lists all 5 clients."""
        all_clients = ["geth", "reth", "nethermind", "besu", "erigon"]
        rows = [{"opcode": "ADD", "client_name": c} for c in all_clients]
        df = pd.DataFrame(rows)
        result = find_missing_client_estimations(df, required_opcodes=["MUL"])
        assert "ADD" not in result
        assert result["MUL"] == sorted(all_clients)

    def test_required_opcode_already_present(self):
        """Opcodes in required_opcodes that already appear in results_df are not duplicated."""
        all_clients = ["geth", "reth", "nethermind", "besu", "erigon"]
        rows = [{"opcode": "ADD", "client_name": c} for c in all_clients]
        df = pd.DataFrame(rows)
        result = find_missing_client_estimations(df, required_opcodes=["ADD"])
        assert result == {}

    def test_required_opcode_partially_present(self):
        """An opcode in required_opcodes that has some clients still reports missing ones."""
        present = ["geth", "reth"]
        rows = [{"opcode": "ADD", "client_name": c} for c in present]
        df = pd.DataFrame(rows)
        result = find_missing_client_estimations(df, required_opcodes=["ADD", "MUL"])
        assert result["ADD"] == sorted(["besu", "erigon", "nethermind"])
        assert result["MUL"] == sorted(["besu", "erigon", "geth", "nethermind", "reth"])


# ---------------------------------------------------------------------------
# Tests for select_worst_case_estimates with glue adjustment
# ---------------------------------------------------------------------------


def _make_glue_results_df(rows):
    """Build a DataFrame matching glue_results.csv shape."""
    return pd.DataFrame(rows)


def _make_glue_opcodes_by_test(rows):
    """Build a DataFrame matching glue_opcodes_by_test.csv shape."""
    return pd.DataFrame(rows)


class TestSelectWorstCaseWithGlue:
    def test_slope_adjusted_by_glue(self):
        """Slope should be reduced by glue opcode runtime."""
        results = _make_results_df(
            [_base_row(opcode="ADD", client="geth", test_name="test_add", slope=0.05)]
        )
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.005, "p_value": 0.0, "rsquared": 0.9}]
        )
        glue_by_test = _make_glue_opcodes_by_test(
            [
                {
                    "test_file": "test_add",
                    "test_name": "test_add",
                    "test_opcode": "ADD",
                    "test_params": "default",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 2.0,
                }
            ]
        )
        new_gas_df, _ = select_worst_case_estimates(
            results,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
            glue_results_df=glue_results,
            glue_opcodes_by_test=glue_by_test,
        )
        # Adjusted slope = 0.05 - 2.0 * 0.005 = 0.04
        assert len(new_gas_df) == 1
        assert np.isclose(new_gas_df.iloc[0]["runtime_ms"], 0.04)

    def test_slope_clipped_at_zero(self):
        """If glue adjustment exceeds slope, slope is clipped to 0."""
        results = _make_results_df(
            [_base_row(opcode="ADD", client="geth", test_name="test_add", slope=0.01)]
        )
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.01, "p_value": 0.0, "rsquared": 0.9}]
        )
        glue_by_test = _make_glue_opcodes_by_test(
            [
                {
                    "test_file": "test_add",
                    "test_name": "test_add",
                    "test_opcode": "ADD",
                    "test_params": "default",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 5.0,
                }
            ]
        )
        new_gas_df, _ = select_worst_case_estimates(
            results,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
            glue_results_df=glue_results,
            glue_opcodes_by_test=glue_by_test,
        )
        # Adjustment = 5.0 * 0.01 = 0.05 > slope 0.01 -> clipped to 0
        assert new_gas_df.iloc[0]["runtime_ms"] == 0.0

    def test_no_glue_for_test_leaves_slope_unchanged(self):
        """Tests with no matching glue opcodes keep their original slope."""
        results = _make_results_df(
            [_base_row(opcode="MUL", client="geth", test_name="test_mul", slope=0.05)]
        )
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.005, "p_value": 0.0, "rsquared": 0.9}]
        )
        # Glue opcodes only for ADD, not MUL
        glue_by_test = _make_glue_opcodes_by_test(
            [
                {
                    "test_file": "test_add",
                    "test_name": "test_add",
                    "test_opcode": "ADD",
                    "test_params": "default",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 2.0,
                }
            ]
        )
        new_gas_df, _ = select_worst_case_estimates(
            results,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
            glue_results_df=glue_results,
            glue_opcodes_by_test=glue_by_test,
        )
        # No glue match for MUL -> slope unchanged
        assert np.isclose(new_gas_df.iloc[0]["runtime_ms"], 0.05)

    def test_confidence_intervals_also_adjusted(self):
        """Confidence interval bounds should also be adjusted by glue runtime."""
        results = _make_results_df(
            [
                _base_row(
                    opcode="ADD",
                    client="geth",
                    test_name="test_add",
                    slope=0.05,
                    slope_conf_low=0.04,
                    slope_conf_high=0.06,
                )
            ]
        )
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.005, "p_value": 0.0, "rsquared": 0.9}]
        )
        glue_by_test = _make_glue_opcodes_by_test(
            [
                {
                    "test_file": "test_add",
                    "test_name": "test_add",
                    "test_opcode": "ADD",
                    "test_params": "default",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 2.0,
                }
            ]
        )
        new_gas_df, _ = select_worst_case_estimates(
            results,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
            glue_results_df=glue_results,
            glue_opcodes_by_test=glue_by_test,
        )
        # Adjustment = 2.0 * 0.005 = 0.01
        row = new_gas_df.iloc[0]
        assert np.isclose(row["conf_int_low"], 0.04 - 0.01)
        assert np.isclose(row["conf_int_high"], 0.06 - 0.01)

    def test_worst_case_selection_uses_adjusted_slope(self):
        """Worst case selection should use glue-adjusted slopes."""
        # test_a has higher raw slope but also higher glue adjustment
        # test_b has lower raw slope but no glue -> should be selected as worst
        results = _make_results_df(
            [
                _base_row(opcode="ADD", client="geth", test_name="test_a", slope=0.10),
                _base_row(opcode="ADD", client="geth", test_name="test_b", slope=0.06),
            ]
        )
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.01, "p_value": 0.0, "rsquared": 0.9}]
        )
        # Only test_a has glue opcodes (ratio=5 -> adjustment=0.05, adjusted slope=0.05)
        # test_b has no glue opcodes (adjusted slope=0.06)
        glue_by_test = _make_glue_opcodes_by_test(
            [
                {
                    "test_file": "test_a",
                    "test_name": "test_a",
                    "test_opcode": "ADD",
                    "test_params": "default",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 5.0,
                }
            ]
        )
        new_gas_df, _ = select_worst_case_estimates(
            results,
            params=[],
            group_by=["client_name", "test_name"],
            anchor_rate=1_000_000.0,
            params_multipliers={},
            glue_results_df=glue_results,
            glue_opcodes_by_test=glue_by_test,
        )
        assert len(new_gas_df) == 1
        # test_b (adjusted 0.06) > test_a (adjusted 0.05) -> test_b selected
        assert new_gas_df.iloc[0]["test_name"] == "test_b"
        assert np.isclose(new_gas_df.iloc[0]["runtime_ms"], 0.06)


# ---------------------------------------------------------------------------
# Helpers for state access tests
# ---------------------------------------------------------------------------


def _sa_row(
    opcode="SLOAD",
    client="geth",
    test_name="test_sload_erc20_balanceof",
    cache_strategy="NO_CACHE",
    account_mode=np.nan,
    existing_slots=np.nan,
    slope=0.01,
    slope_pvalue=0.01,
    slope_conf_low=0.008,
    slope_conf_high=0.012,
    update=np.nan,
    update_pvalue=np.nan,
    update_conf_low=np.nan,
    update_conf_high=np.nan,
    rsquared=0.95,
):
    return {
        "opcode": opcode,
        "client_name": client,
        "test_name": test_name,
        "cache_strategy": cache_strategy,
        "account_mode": account_mode,
        "existing_slots": existing_slots,
        "slope": slope,
        "slope_pvalue": slope_pvalue,
        "slope_conf_int_low": slope_conf_low,
        "slope_conf_int_high": slope_conf_high,
        "update": update,
        "update_pvalue": update_pvalue,
        "update_conf_int_low": update_conf_low,
        "update_conf_int_high": update_conf_high,
        "rsquared": rsquared,
    }


# ---------------------------------------------------------------------------
# Tests for _apply_filter
# ---------------------------------------------------------------------------


class TestApplyFilter:
    def test_equality_filter(self):
        df = pd.DataFrame([
            {"test_name": "a", "cache_strategy": "NO_CACHE"},
            {"test_name": "b", "cache_strategy": "CACHE_TX"},
        ])
        result = _apply_filter(df, {"cache_strategy": "NO_CACHE"})
        assert len(result) == 1
        assert result.iloc[0]["test_name"] == "a"

    def test_inequality_filter(self):
        df = pd.DataFrame([
            {"account_mode": "EXISTING_EOA"},
            {"account_mode": "EXISTING_CONTRACT"},
            {"account_mode": "NON_EXISTING_ACCOUNT"},
        ])
        result = _apply_filter(df, {"account_mode__ne": "EXISTING_CONTRACT"})
        assert len(result) == 2
        assert "EXISTING_CONTRACT" not in result["account_mode"].values

    def test_multiple_conditions(self):
        df = pd.DataFrame([
            {"test_name": "test_account_access", "cache_strategy": "NO_CACHE", "account_mode": "EXISTING_EOA"},
            {"test_name": "test_account_access", "cache_strategy": "CACHE_TX", "account_mode": "EXISTING_EOA"},
            {"test_name": "test_other", "cache_strategy": "NO_CACHE", "account_mode": "EXISTING_EOA"},
        ])
        result = _apply_filter(df, {"test_name": "test_account_access", "cache_strategy": "NO_CACHE"})
        assert len(result) == 1
        assert result.iloc[0]["account_mode"] == "EXISTING_EOA"

    def test_missing_column_ignored(self):
        df = pd.DataFrame([{"test_name": "a"}])
        result = _apply_filter(df, {"nonexistent": "value"})
        assert len(result) == 1

    def test_empty_filter_returns_all(self):
        df = pd.DataFrame([{"test_name": "a"}, {"test_name": "b"}])
        result = _apply_filter(df, {})
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Tests for compute_state_access_gas_params
# ---------------------------------------------------------------------------


class TestComputeStateAccessGasParams:
    ANCHOR = 60_000_000.0  # 60M gas/s
    EMPTY_GLUE_RESULTS = pd.DataFrame(
        columns=["client", "glue_opcode", "runtime", "p_value", "rsquared"]
    )
    EMPTY_GLUE_BY_TEST = pd.DataFrame(
        columns=["test_file", "test_name", "test_opcode", "test_params", "glue_opcode", "corr", "ratio"]
    )

    def test_cold_storage_access_from_sload_no_cache(self):
        """GAS_COLD_STORAGE_ACCESS is estimated from test_sload_erc20_balanceof NO_CACHE slope."""
        df = pd.DataFrame([_sa_row(
            test_name="test_sload_erc20_balanceof",
            cache_strategy="NO_CACHE",
            slope=0.03,
            slope_pvalue=0.01,
        )])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        row = params_df[params_df["gas_param"] == "GAS_COLD_STORAGE_ACCESS"]
        assert len(row) == 1
        assert np.isclose(row.iloc[0]["runtime_ms"], 0.03)

    def test_cold_storage_write_from_update_coef(self):
        """GAS_COLD_STORAGE_WRITE is estimated from test_sstore_erc20_mint NO_CACHE update coef."""
        df = pd.DataFrame([_sa_row(
            test_name="test_sstore_erc20_mint",
            cache_strategy="NO_CACHE",
            slope=0.02,
            slope_pvalue=0.01,
            update=0.05,
            update_pvalue=0.01,
            update_conf_low=0.04,
            update_conf_high=0.06,
        )])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        write_row = params_df[params_df["gas_param"] == "GAS_COLD_STORAGE_WRITE"]
        assert len(write_row) == 1
        assert np.isclose(write_row.iloc[0]["runtime_ms"], 0.05)

    def test_warm_access_from_account_access_cache_tx(self):
        """GAS_WARM_ACCESS is estimated from test_account_access CACHE_TX slope."""
        df = pd.DataFrame([_sa_row(
            opcode="BALANCE",
            test_name="test_account_access",
            cache_strategy="CACHE_TX",
            account_mode="EXISTING_EOA",
            slope=0.005,
            slope_pvalue=0.01,
        )])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        row = params_df[params_df["gas_param"] == "GAS_WARM_ACCESS"]
        assert len(row) == 1
        assert np.isclose(row.iloc[0]["runtime_ms"], 0.005)

    def test_cold_account_nocode_excludes_existing_contract(self):
        """GAS_COLD_ACCOUNT_NOCODE_ACCESS must exclude EXISTING_CONTRACT rows."""
        df = pd.DataFrame([
            _sa_row(
                opcode="BALANCE",
                test_name="test_account_access",
                cache_strategy="NO_CACHE",
                account_mode="EXISTING_EOA",
                slope=0.04,
                slope_pvalue=0.01,
            ),
            _sa_row(
                opcode="BALANCE",
                test_name="test_account_access",
                cache_strategy="NO_CACHE",
                account_mode="EXISTING_CONTRACT",
                slope=0.10,  # higher, but should be excluded
                slope_pvalue=0.01,
            ),
        ])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        nocode = params_df[params_df["gas_param"] == "GAS_COLD_ACCOUNT_NOCODE_ACCESS"]
        assert len(nocode) == 1
        assert np.isclose(nocode.iloc[0]["runtime_ms"], 0.04)

    def test_cold_account_code_excludes_existing_eoa(self):
        """GAS_COLD_ACCOUNT_CODE_ACCESS must exclude EXISTING_EOA rows."""
        df = pd.DataFrame([
            _sa_row(
                opcode="BALANCE",
                test_name="test_account_access",
                cache_strategy="NO_CACHE",
                account_mode="EXISTING_CONTRACT",
                slope=0.04,
                slope_pvalue=0.01,
            ),
            _sa_row(
                opcode="BALANCE",
                test_name="test_account_access",
                cache_strategy="NO_CACHE",
                account_mode="EXISTING_EOA",
                slope=0.10,  # higher, but should be excluded
                slope_pvalue=0.01,
            ),
        ])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        code = params_df[params_df["gas_param"] == "GAS_COLD_ACCOUNT_CODE_ACCESS"]
        assert len(code) == 1
        assert np.isclose(code.iloc[0]["runtime_ms"], 0.04)

    def test_worst_case_selected_across_test_configs(self):
        """For a given gas_param and client, the worst-case (max runtime) row is selected."""
        df = pd.DataFrame([
            _sa_row(test_name="test_sload_erc20_balanceof", cache_strategy="NO_CACHE", slope=0.02, slope_pvalue=0.01),
            _sa_row(test_name="test_sstore_erc20_mint", cache_strategy="NO_CACHE", slope=0.05, slope_pvalue=0.01),
        ])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        cold_access = params_df[params_df["gas_param"] == "GAS_COLD_STORAGE_ACCESS"]
        assert len(cold_access) == 1
        assert np.isclose(cold_access.iloc[0]["runtime_ms"], 0.05)

    def test_prefers_good_fit_over_poor_fit(self):
        """Rows with p < 0.05 are preferred over rows with p >= 0.05 even if runtime is lower."""
        df = pd.DataFrame([
            _sa_row(test_name="test_sload_erc20_balanceof", cache_strategy="NO_CACHE", slope=0.01, slope_pvalue=0.02),
            _sa_row(test_name="test_sstore_erc20_mint", cache_strategy="NO_CACHE", slope=0.09, slope_pvalue=0.20),
        ])
        params_df, _, poor_fit = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        cold_access = params_df[params_df["gas_param"] == "GAS_COLD_STORAGE_ACCESS"]
        assert np.isclose(cold_access.iloc[0]["runtime_ms"], 0.01)
        assert "GAS_COLD_STORAGE_ACCESS" not in poor_fit

    def test_poor_fit_tracked_when_no_good_fits(self):
        """gas_param is added to poor_fit_dict when all matching rows have p >= 0.05."""
        df = pd.DataFrame([
            _sa_row(test_name="test_sload_erc20_balanceof", cache_strategy="NO_CACHE", slope=0.05, slope_pvalue=0.10),
        ])
        _, _, poor_fit = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        assert "GAS_COLD_STORAGE_ACCESS" in poor_fit
        assert "geth" in poor_fit["GAS_COLD_STORAGE_ACCESS"]

    def test_new_gas_calculation(self):
        """new_gas_rounded = ceil(anchor_rate * runtime_ms / 1000)."""
        slope = 0.033333  # ms
        df = pd.DataFrame([_sa_row(
            test_name="test_sload_erc20_balanceof",
            cache_strategy="NO_CACHE",
            slope=slope,
            slope_pvalue=0.01,
        )])
        anchor = 60_000_000.0
        params_df, _, _ = compute_state_access_gas_params(df, anchor, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        row = params_df[params_df["gas_param"] == "GAS_COLD_STORAGE_ACCESS"].iloc[0]
        expected = np.ceil(anchor * slope / 1e3)
        assert row["new_gas_rounded"] == expected

    def test_missing_test_name_ignored(self):
        """Tests not in _STATE_ACCESS_PARAM_SOURCES simply produce no candidates."""
        df = pd.DataFrame([_sa_row(
            test_name="test_nonexistent_benchmark",
            cache_strategy="NO_CACHE",
            slope=0.99,
            slope_pvalue=0.01,
        )])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        assert params_df.empty

    def test_empty_dataframe_returns_empty(self):
        """Empty input produces empty outputs without error."""
        df = pd.DataFrame(columns=["opcode", "client_name", "test_name", "cache_strategy",
                                   "account_mode", "slope", "slope_pvalue",
                                   "slope_conf_int_low", "slope_conf_int_high"])
        params_df, _, poor_fit = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        assert params_df.empty
        assert poor_fit == {}

    def test_multiple_clients_each_get_own_row(self):
        """Each client produces its own worst-case row per gas parameter."""
        df = pd.DataFrame([
            _sa_row(client="geth", test_name="test_sload_erc20_balanceof",
                    cache_strategy="NO_CACHE", slope=0.02, slope_pvalue=0.01),
            _sa_row(client="reth", test_name="test_sload_erc20_balanceof",
                    cache_strategy="NO_CACHE", slope=0.03, slope_pvalue=0.01),
        ])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        cold_access = params_df[params_df["gas_param"] == "GAS_COLD_STORAGE_ACCESS"]
        assert set(cold_access["client_name"]) == {"geth", "reth"}

    def test_glue_adjustment_applied_to_slope(self):
        """Glue opcode runtime is subtracted from slope before computing gas."""
        df = pd.DataFrame([_sa_row(
            opcode="SLOAD",
            test_name="test_sload_erc20_balanceof",
            cache_strategy="NO_CACHE",
            slope=0.05,
            slope_pvalue=0.01,
            slope_conf_low=0.04,
            slope_conf_high=0.06,
        )])
        glue_results = pd.DataFrame([{
            "client": "geth", "glue_opcode": "PUSH1", "runtime": 0.005, "p_value": 0.0, "rsquared": 0.9,
        }])
        glue_by_test = pd.DataFrame([{
            "test_file": "test_sload", "test_name": "test_sload_erc20_balanceof",
            "test_opcode": "SLOAD", "test_params": "default",
            "glue_opcode": "PUSH1", "corr": 0.99, "ratio": 2.0,
        }])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, glue_results, glue_by_test)
        row = params_df[params_df["gas_param"] == "GAS_COLD_STORAGE_ACCESS"].iloc[0]
        # adjusted slope = 0.05 - 2.0 * 0.005 = 0.04
        assert np.isclose(row["runtime_ms"], 0.04)

    def test_cold_account_write_from_existing_eoa(self):
        """GAS_COLD_ACCOUNT_WRITE is estimated from test_account_access NO_CACHE update coef
        for EXISTING_EOA (excluded from EXISTING_CONTRACT filter)."""
        df = pd.DataFrame([_sa_row(
            opcode="BALANCE",
            test_name="test_account_access",
            cache_strategy="NO_CACHE",
            account_mode="EXISTING_EOA",
            slope=0.02,
            slope_pvalue=0.01,
            update=0.06,
            update_pvalue=0.01,
            update_conf_low=0.05,
            update_conf_high=0.07,
        )])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        write_row = params_df[params_df["gas_param"] == "GAS_COLD_ACCOUNT_WRITE"]
        assert len(write_row) == 1
        assert np.isclose(write_row.iloc[0]["runtime_ms"], 0.06)

    def test_cold_account_write_from_existing_contract(self):
        """GAS_COLD_ACCOUNT_WRITE is estimated from test_account_access NO_CACHE update coef
        for EXISTING_CONTRACT (excluded from EXISTING_EOA filter)."""
        df = pd.DataFrame([_sa_row(
            opcode="BALANCE",
            test_name="test_account_access",
            cache_strategy="NO_CACHE",
            account_mode="EXISTING_CONTRACT",
            slope=0.02,
            slope_pvalue=0.01,
            update=0.08,
            update_pvalue=0.01,
            update_conf_low=0.07,
            update_conf_high=0.09,
        )])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        write_row = params_df[params_df["gas_param"] == "GAS_COLD_ACCOUNT_WRITE"]
        assert len(write_row) == 1
        assert np.isclose(write_row.iloc[0]["runtime_ms"], 0.08)

    def test_cold_account_write_selects_worst_across_account_modes(self):
        """GAS_COLD_ACCOUNT_WRITE takes worst-case update runtime across EOA and CONTRACT."""
        df = pd.DataFrame([
            _sa_row(
                opcode="BALANCE",
                test_name="test_account_access",
                cache_strategy="NO_CACHE",
                account_mode="EXISTING_EOA",
                slope=0.02, slope_pvalue=0.01,
                update=0.04, update_pvalue=0.01,
                update_conf_low=0.03, update_conf_high=0.05,
            ),
            _sa_row(
                opcode="BALANCE",
                test_name="test_account_access",
                cache_strategy="NO_CACHE",
                account_mode="EXISTING_CONTRACT",
                slope=0.02, slope_pvalue=0.01,
                update=0.09, update_pvalue=0.01,
                update_conf_low=0.08, update_conf_high=0.10,
            ),
        ])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, self.EMPTY_GLUE_RESULTS, self.EMPTY_GLUE_BY_TEST)
        write_row = params_df[params_df["gas_param"] == "GAS_COLD_ACCOUNT_WRITE"]
        assert len(write_row) == 1
        assert np.isclose(write_row.iloc[0]["runtime_ms"], 0.09)

    def test_state_glue_balance_adjusts_sload_slope(self):
        """BALANCE slope from results_df is used as a glue runtime to adjust SLOAD slope."""
        df = pd.DataFrame([
            _sa_row(
                opcode="SLOAD",
                test_name="test_sload_erc20_balanceof",
                cache_strategy="NO_CACHE",
                slope=0.05,
                slope_pvalue=0.01,
                slope_conf_low=0.04,
                slope_conf_high=0.06,
            ),
            _sa_row(
                opcode="BALANCE",
                test_name="test_account_access",
                cache_strategy="NO_CACHE",
                account_mode="EXISTING_EOA",
                slope=0.01,
                slope_pvalue=0.0,
            ),
        ])
        # Start with empty glue_results — BALANCE will be added by add_state_glue_results
        glue_results = pd.DataFrame(
            columns=["client", "glue_opcode", "runtime", "p_value", "rsquared"]
        )
        glue_by_test = pd.DataFrame([{
            "test_file": "test_sload",
            "test_name": "test_sload_erc20_balanceof",
            "test_opcode": "SLOAD",
            "test_params": "default",
            "glue_opcode": "BALANCE",
            "corr": 0.99,
            "ratio": 2.0,
        }])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, glue_results, glue_by_test)
        row = params_df[params_df["gas_param"] == "GAS_COLD_STORAGE_ACCESS"].iloc[0]
        # BALANCE runtime = 0.01, ratio = 2.0 → adjustment = 0.02
        # adjusted SLOAD slope = 0.05 - 0.02 = 0.03
        assert np.isclose(row["runtime_ms"], 0.03)

    def test_state_glue_poor_fit_balance_not_used(self):
        """BALANCE with poor slope_pvalue is not used as glue adjustment."""
        df = pd.DataFrame([
            _sa_row(
                opcode="SLOAD",
                test_name="test_sload_erc20_balanceof",
                cache_strategy="NO_CACHE",
                slope=0.05,
                slope_pvalue=0.01,
            ),
            _sa_row(
                opcode="BALANCE",
                test_name="test_account_access",
                cache_strategy="NO_CACHE",
                account_mode="EXISTING_EOA",
                slope=0.01,
                slope_pvalue=0.20,  # poor fit → excluded from glue adjustment
            ),
        ])
        glue_results = pd.DataFrame(
            columns=["client", "glue_opcode", "runtime", "p_value", "rsquared"]
        )
        glue_by_test = pd.DataFrame([{
            "test_file": "test_sload",
            "test_name": "test_sload_erc20_balanceof",
            "test_opcode": "SLOAD",
            "test_params": "default",
            "glue_opcode": "BALANCE",
            "corr": 0.99,
            "ratio": 2.0,
        }])
        params_df, _, _ = compute_state_access_gas_params(df, self.ANCHOR, glue_results, glue_by_test)
        row = params_df[params_df["gas_param"] == "GAS_COLD_STORAGE_ACCESS"].iloc[0]
        # BALANCE p_value >= 0.05 → no glue adjustment → SLOAD slope unchanged at 0.05
        assert np.isclose(row["runtime_ms"], 0.05)


# ---------------------------------------------------------------------------
# Tests for find_poor_fit_glue_opcodes
# ---------------------------------------------------------------------------


def _make_glue_res(*rows):
    return pd.DataFrame(rows)


def _make_glue_by_test_df(*rows):
    return pd.DataFrame(rows)


class TestFindPoorFitGlueOpcodes:
    def test_poor_fit_opcode_returned(self):
        """Glue opcode with p_value >= 0.05 for any client is included."""
        glue_results = _make_glue_res(
            {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.10},
        )
        glue_by_test = _make_glue_by_test_df(
            {"glue_opcode": "PUSH1", "test_opcode": "ADD"},
        )
        result = find_poor_fit_glue_opcodes(glue_results, glue_by_test)
        assert "PUSH1" in result
        assert result["PUSH1"]["clients"] == ["geth"]
        assert result["PUSH1"]["test_opcodes"] == ["ADD"]

    def test_good_fit_opcode_not_returned(self):
        """Glue opcode with p_value < 0.05 is excluded."""
        glue_results = _make_glue_res(
            {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.01},
        )
        glue_by_test = _make_glue_by_test_df(
            {"glue_opcode": "PUSH1", "test_opcode": "ADD"},
        )
        result = find_poor_fit_glue_opcodes(glue_results, glue_by_test)
        assert result == {}

    def test_glue_opcode_not_in_mapping_excluded(self):
        """Glue opcode with poor fit but absent from glue_opcodes_by_test is excluded."""
        glue_results = _make_glue_res(
            {"client": "geth", "glue_opcode": "UNKNOWN", "runtime": 0.001, "p_value": 0.20},
        )
        glue_by_test = _make_glue_by_test_df(
            {"glue_opcode": "PUSH1", "test_opcode": "ADD"},
        )
        result = find_poor_fit_glue_opcodes(glue_results, glue_by_test)
        assert result == {}

    def test_multiple_clients_all_listed(self):
        """All clients with poor fit for the same glue opcode are listed."""
        glue_results = _make_glue_res(
            {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.10},
            {"client": "reth", "glue_opcode": "PUSH1", "runtime": 0.002, "p_value": 0.15},
        )
        glue_by_test = _make_glue_by_test_df(
            {"glue_opcode": "PUSH1", "test_opcode": "ADD"},
        )
        result = find_poor_fit_glue_opcodes(glue_results, glue_by_test)
        assert result["PUSH1"]["clients"] == ["geth", "reth"]

    def test_mixed_clients_only_poor_ones_listed(self):
        """Only clients with p_value >= 0.05 are listed."""
        glue_results = _make_glue_res(
            {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.01},
            {"client": "reth", "glue_opcode": "PUSH1", "runtime": 0.002, "p_value": 0.15},
        )
        glue_by_test = _make_glue_by_test_df(
            {"glue_opcode": "PUSH1", "test_opcode": "ADD"},
        )
        result = find_poor_fit_glue_opcodes(glue_results, glue_by_test)
        assert "PUSH1" in result
        assert result["PUSH1"]["clients"] == ["reth"]

    def test_target_operations_filters_test_opcodes(self):
        """With target_operations, only matching test opcodes are returned."""
        glue_results = _make_glue_res(
            {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.10},
        )
        glue_by_test = _make_glue_by_test_df(
            {"glue_opcode": "PUSH1", "test_opcode": "ADD"},
            {"glue_opcode": "PUSH1", "test_opcode": "MUL"},
        )
        result = find_poor_fit_glue_opcodes(glue_results, glue_by_test, target_operations=["ADD"])
        assert result["PUSH1"]["test_opcodes"] == ["ADD"]
        assert "MUL" not in result["PUSH1"]["test_opcodes"]

    def test_target_operations_excludes_glue_opcode_with_no_match(self):
        """Glue opcode whose test_opcodes don't overlap target_operations is excluded."""
        glue_results = _make_glue_res(
            {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.10},
        )
        glue_by_test = _make_glue_by_test_df(
            {"glue_opcode": "PUSH1", "test_opcode": "MUL"},
        )
        result = find_poor_fit_glue_opcodes(glue_results, glue_by_test, target_operations=["ADD"])
        assert result == {}

    def test_result_sorted_by_glue_opcode(self):
        """Result dict keys are sorted alphabetically."""
        glue_results = _make_glue_res(
            {"client": "geth", "glue_opcode": "PUSH2", "runtime": 0.001, "p_value": 0.10},
            {"client": "geth", "glue_opcode": "CALL", "runtime": 0.005, "p_value": 0.20},
        )
        glue_by_test = _make_glue_by_test_df(
            {"glue_opcode": "PUSH2", "test_opcode": "ADD"},
            {"glue_opcode": "CALL", "test_opcode": "MUL"},
        )
        result = find_poor_fit_glue_opcodes(glue_results, glue_by_test)
        assert list(result.keys()) == sorted(result.keys())

    def test_empty_glue_results_returns_empty(self):
        """Empty glue_results_df returns empty dict."""
        glue_results = pd.DataFrame(columns=["client", "glue_opcode", "runtime", "p_value"])
        glue_by_test = _make_glue_by_test_df(
            {"glue_opcode": "PUSH1", "test_opcode": "ADD"},
        )
        result = find_poor_fit_glue_opcodes(glue_results, glue_by_test)
        assert result == {}

    def test_multiple_test_opcodes_per_glue_opcode(self):
        """All test opcodes affected by a poor-fit glue opcode are listed."""
        glue_results = _make_glue_res(
            {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.10},
        )
        glue_by_test = _make_glue_by_test_df(
            {"glue_opcode": "PUSH1", "test_opcode": "ADD"},
            {"glue_opcode": "PUSH1", "test_opcode": "MUL"},
            {"glue_opcode": "PUSH1", "test_opcode": "ADD"},  # duplicate, should deduplicate
        )
        result = find_poor_fit_glue_opcodes(glue_results, glue_by_test)
        assert result["PUSH1"]["test_opcodes"] == ["ADD", "MUL"]


# ---------------------------------------------------------------------------
# Tests for compute_derived_state_access_params
# ---------------------------------------------------------------------------


def _make_params_df(**kwargs):
    """Build a minimal params_df with gas_param and new_gas_rounded columns."""
    rows = [{"gas_param": k, "new_gas_rounded": v, "client_name": "geth"} for k, v in kwargs.items()]
    return pd.DataFrame(rows)


class TestComputeDerivedStateAccessParams:
    def test_access_list_storage_key_equals_cold_storage_access(self):
        df = _make_params_df(GAS_COLD_STORAGE_ACCESS=3515)
        result = compute_derived_state_access_params(df)
        assert result["ACCESS_LIST_STORAGE_KEY_COST"] == 3515

    def test_access_list_address_equals_cold_account_code_access(self):
        df = _make_params_df(GAS_COLD_ACCOUNT_CODE_ACCESS=1156)
        result = compute_derived_state_access_params(df)
        assert result["ACCESS_LIST_ADDRESS_COST"] == 1156

    def test_storage_clear_refund_formula(self):
        df = _make_params_df(GAS_COLD_STORAGE_WRITE=2000, GAS_COLD_STORAGE_ACCESS=3000)
        result = compute_derived_state_access_params(df)
        expected = int(np.ceil((2000 + 3000) * (4800 / 5000)))
        assert result["GAS_STORAGE_CLEAR_REFUND"] == expected

    def test_missing_params_default_to_zero(self):
        df = _make_params_df(GAS_WARM_ACCESS=100)
        result = compute_derived_state_access_params(df)
        assert result["ACCESS_LIST_STORAGE_KEY_COST"] == 0
        assert result["ACCESS_LIST_ADDRESS_COST"] == 0
        assert result["GAS_STORAGE_CLEAR_REFUND"] == 0

    def test_worst_case_across_clients(self):
        """Takes the max across clients, not just the first row."""
        df = pd.DataFrame([
            {"gas_param": "GAS_COLD_STORAGE_ACCESS", "new_gas_rounded": 1000, "client_name": "geth"},
            {"gas_param": "GAS_COLD_STORAGE_ACCESS", "new_gas_rounded": 3515, "client_name": "besu"},
        ])
        result = compute_derived_state_access_params(df)
        assert result["ACCESS_LIST_STORAGE_KEY_COST"] == 3515
