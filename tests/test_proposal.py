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
