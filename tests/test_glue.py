import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from glue import get_glue_opcodes_by_test, compute_glue_adjustment, generate_glue_opcode_report, get_all_glue_opcodes_for_target_opcodes


def _make_trace_df(rows, opcode_cols):
    """Build a DataFrame matching the shape returned by process_test_trace_data.

    Parameters
    ----------
    rows : list[dict]
        Each dict must contain the grouping columns (test_file, test_name,
        test_opcode, test_params), plus test_title, block_limit_million,
        opcount, and one key per entry in *opcode_cols*.
    opcode_cols : list[str]
        Names of the opcode-count columns (e.g. ["ADD", "MUL"]).
    """
    base_cols = [
        "test_file",
        "test_name",
        "test_opcode",
        "test_params",
        "test_title",
        "block_limit_million",
        "opcount",
    ]
    return pd.DataFrame(rows, columns=base_cols + opcode_cols)


def _linear_group(
    test_file,
    test_name,
    test_opcode,
    test_params,
    n_rows,
    opcode_ratios,
):
    """Generate *n_rows* rows for one test group.

    ``opcode_ratios`` maps opcode_name -> (ratio, constant).
    For each row i (1-based), opcode value = ratio * opcount + constant.
    opcount grows linearly: 100, 200, …, n_rows*100.
    """
    rows = []
    for i in range(1, n_rows + 1):
        opcount = 100 * i
        row = {
            "test_file": test_file,
            "test_name": test_name,
            "test_opcode": test_opcode,
            "test_params": test_params,
            "test_title": f"{test_name}_title",
            "block_limit_million": 30,
            "opcount": opcount,
        }
        for opcode, (ratio, constant) in opcode_ratios.items():
            row[opcode] = ratio * opcount + constant
        rows.append(row)
    return rows


def _filter_group(result_df, test_name, test_opcode):
    """Return rows from result_df matching the given grouping key."""
    mask = (
        (result_df["test_name"] == test_name)
        & (result_df["test_opcode"] == test_opcode)
    )
    return result_df[mask]


def _get_glue_opcodes(result_df, test_name, test_opcode):
    """Return the set of glue_opcode values for a given group."""
    group = _filter_group(result_df, test_name, test_opcode)
    return set(group["glue_opcode"].values)


def _get_ratio(result_df, test_name, test_opcode, glue_opcode):
    """Return the ratio value for a specific group + glue_opcode."""
    group = _filter_group(result_df, test_name, test_opcode)
    row = group[group["glue_opcode"] == glue_opcode]
    assert len(row) == 1, f"Expected 1 row for {glue_opcode}, got {len(row)}"
    return row["ratio"].iloc[0]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def proportional_df():
    """One group, 8 rows. ADD scales proportionally with opcount (ratio 0.5),
    MUL is constant (10). Only ADD should be detected as glue."""
    opcode_ratios = {"ADD": (0.5, 0), "MUL": (0, 10)}
    rows = _linear_group("f.py", "test_a", "PUSH1", "p1", 8, opcode_ratios)
    return _make_trace_df(rows, ["ADD", "MUL"])


@pytest.fixture
def self_opcode_df():
    """Group where test_opcode equals one of the glue candidates (ADD).
    ADD should be excluded from the result even though it tracks opcount."""
    opcode_ratios = {"ADD": (0.5, 0), "SUB": (0.3, 0)}
    rows = _linear_group("f.py", "test_b", "ADD", "p1", 8, opcode_ratios)
    return _make_trace_df(rows, ["ADD", "SUB"])


@pytest.fixture
def below_threshold_df():
    """Only 5 rows → non-enough data for reliable correlations."""
    opcode_ratios = {"ADD": (0.5, 0)}
    rows = _linear_group("f.py", "test_c", "PUSH1", "p1", 5, opcode_ratios)
    return _make_trace_df(rows, ["ADD"])


@pytest.fixture
def no_match_df():
    """All opcodes are constant → pct_changes are 0, opcount grows → no match."""
    opcode_ratios = {"ADD": (0, 10), "MUL": (0, 20)}
    rows = _linear_group("f.py", "test_d", "PUSH1", "p1", 8, opcode_ratios)
    return _make_trace_df(rows, ["ADD", "MUL"])


@pytest.fixture
def offset_df():
    """One group, 8 rows. ADD = 0.5*opcount + 50 (linear with offset),
    MUL is constant (10). ADD should still be detected as glue."""
    opcode_ratios = {"ADD": (0.5, 50), "MUL": (0, 10)}
    rows = _linear_group("f.py", "test_offset", "PUSH1", "p1", 8, opcode_ratios)
    return _make_trace_df(rows, ["ADD", "MUL"])


@pytest.fixture
def multi_glue_df():
    """One group where both ADD and MUL scale linearly with opcount."""
    opcode_ratios = {"ADD": (0.5, 0), "MUL": (0.3, 0), "SUB": (0, 10)}
    rows = _linear_group("f.py", "test_mg", "PUSH1", "p1", 8, opcode_ratios)
    return _make_trace_df(rows, ["ADD", "MUL", "SUB"])


@pytest.fixture
def unsorted_opcount_df():
    """One group, 8 rows with ADD = 0.5*opcount + small noise.

    diff().mean() reduces to (last − first) / (n − 1), so the estimated
    ratio depends entirely on which rows happen to be first and last.

    Here opcount=500 is first and opcount=400 is last (Δopcount = −100).
    Noise of ±10 is added at those two endpoints:
      ADD[opcount=500] = 260 (true 250, +10 noise)
      ADD[opcount=400] = 190 (true 200, −10 noise)

    Without sorting:
      ratio = (190 − 260) / (400 − 500) = −70 / −100 = 0.7  (wrong)
    After sorting by opcount (new code):
      diff(ADD).mean() = 50.0, diff(opcount).mean() = 100  → ratio = 0.5  (correct)

    The noise is small enough that Pearson correlation ≈ 0.9995 ≥ 0.95,
    so the row passes all other filters.
    """
    add_values = {oc: 0.5 * oc for oc in range(100, 900, 100)}
    add_values[400] -= 10  # noise: −10
    add_values[500] += 10  # noise: +10
    # Present rows with opcount=500 first and opcount=400 last
    shuffled_opcounts = [500, 100, 200, 300, 600, 700, 800, 400]
    rows = [
        {
            "test_file": "f.py",
            "test_name": "test_unsorted",
            "test_opcode": "PUSH1",
            "test_params": "p1",
            "test_title": "test_unsorted_title",
            "block_limit_million": 30,
            "opcount": oc,
            "ADD": add_values[oc],
            "MUL": 10,
        }
        for oc in shuffled_opcounts
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def low_ratio_df():
    """ADD scales with opcount but with a very small ratio (0.0004 < 0.0005 threshold).
    Should be filtered out despite high correlation."""
    opcode_ratios = {"ADD": (0.0004, 0)}
    rows = _linear_group("f.py", "test_low_ratio", "PUSH1", "p1", 8, opcode_ratios)
    return _make_trace_df(rows, ["ADD"])


@pytest.fixture
def negative_corr_df():
    """ADD has negative correlation with opcount (decreases as opcount grows)."""
    opcode_ratios = {"ADD": (-0.5, 1000)}
    rows = _linear_group("f.py", "test_neg", "PUSH1", "p1", 8, opcode_ratios)
    return _make_trace_df(rows, ["ADD"])


@pytest.fixture
def multi_group_df():
    """Two groups: group1 has ADD as glue, group2 has SUB as glue."""
    rows = _linear_group(
        "f.py", "test_e", "PUSH1", "p1", 8, {"ADD": (0.5, 0), "SUB": (0, 5)}
    )
    rows += _linear_group(
        "f.py", "test_f", "PUSH1", "p2", 8, {"ADD": (0, 7), "SUB": (0.3, 0)}
    )
    return _make_trace_df(rows, ["ADD", "SUB"])


# ---------------------------------------------------------------------------
# Tests for get_glue_opcodes_by_test
# ---------------------------------------------------------------------------


class TestGetGlueOpcodesByTest:
    def test_detects_proportional_glue_opcode(self, proportional_df):
        """ADD scales linearly with opcount → detected as glue."""
        result = get_glue_opcodes_by_test(proportional_df)
        glue_opcodes = _get_glue_opcodes(result, "test_a", "PUSH1")
        assert "ADD" in glue_opcodes
        ratio = _get_ratio(result, "test_a", "PUSH1", "ADD")
        assert ratio == pytest.approx(0.5)

    def test_constant_opcode_not_detected(self, proportional_df):
        """MUL is constant → NOT detected as glue."""
        result = get_glue_opcodes_by_test(proportional_df)
        glue_opcodes = _get_glue_opcodes(result, "test_a", "PUSH1")
        assert "MUL" not in glue_opcodes

    def test_self_opcode_excluded(self, self_opcode_df):
        """test_opcode == ADD → ADD must not appear in result for that test."""
        result = get_glue_opcodes_by_test(self_opcode_df)
        glue_opcodes = _get_glue_opcodes(result, "test_b", "ADD")
        assert "ADD" not in glue_opcodes

    def test_self_opcode_excluded_but_others_kept(self, self_opcode_df):
        """SUB also scales with opcount → should still be in result."""
        result = get_glue_opcodes_by_test(self_opcode_df)
        glue_opcodes = _get_glue_opcodes(result, "test_b", "ADD")
        assert "SUB" in glue_opcodes
        ratio = _get_ratio(result, "test_b", "ADD", "SUB")
        assert ratio == pytest.approx(0.3)

    def test_below_threshold_returns_empty(self, below_threshold_df):
        """Only 5 rows → at most 4 matching pct_change rows, ≤ 5 → filtered out."""
        result = get_glue_opcodes_by_test(below_threshold_df)
        assert result.empty

    def test_no_matching_opcodes(self, no_match_df):
        """Constant opcodes with growing opcount → no matches."""
        result = get_glue_opcodes_by_test(no_match_df)
        assert result.empty

    def test_multiple_groups(self, multi_group_df):
        """Two groups: group1 → ADD as glue, group2 → SUB as glue."""
        result = get_glue_opcodes_by_test(multi_group_df)
        glue1 = _get_glue_opcodes(result, "test_e", "PUSH1")
        glue2 = _get_glue_opcodes(result, "test_f", "PUSH1")
        assert "ADD" in glue1
        assert "SUB" in glue2

    def test_detects_offset_glue_opcode(self, offset_df):
        """ADD = 0.5*opcount + 50 → still detected as glue with ratio 0.5."""
        result = get_glue_opcodes_by_test(offset_df)
        glue_opcodes = _get_glue_opcodes(result, "test_offset", "PUSH1")
        assert "ADD" in glue_opcodes
        ratio = _get_ratio(result, "test_offset", "PUSH1", "ADD")
        assert ratio == pytest.approx(0.5)

    def test_offset_constant_opcode_not_detected(self, offset_df):
        """MUL is constant → NOT detected as glue even with offset fixture."""
        result = get_glue_opcodes_by_test(offset_df)
        glue_opcodes = _get_glue_opcodes(result, "test_offset", "PUSH1")
        assert "MUL" not in glue_opcodes

    def test_multiple_glue_opcodes_in_same_group(self, multi_glue_df):
        """Both ADD and MUL scale with opcount → both detected as glue."""
        result = get_glue_opcodes_by_test(multi_glue_df)
        glue_opcodes = _get_glue_opcodes(result, "test_mg", "PUSH1")
        assert "ADD" in glue_opcodes
        assert "MUL" in glue_opcodes
        assert "SUB" not in glue_opcodes
        assert _get_ratio(result, "test_mg", "PUSH1", "ADD") == pytest.approx(0.5)
        assert _get_ratio(result, "test_mg", "PUSH1", "MUL") == pytest.approx(0.3)

    def test_low_ratio_filtered_out(self, low_ratio_df):
        """ADD has ratio 0.0004 (< 0.0005 threshold) → filtered out."""
        result = get_glue_opcodes_by_test(low_ratio_df)
        assert result.empty

    def test_negative_correlation_not_detected(self, negative_corr_df):
        """ADD decreases as opcount grows → negative correlation → not detected."""
        result = get_glue_opcodes_by_test(negative_corr_df)
        assert result.empty

    def test_empty_input(self):
        """Empty DataFrame input should return an empty result without errors."""
        empty_df = _make_trace_df([], ["ADD", "MUL"])
        result = get_glue_opcodes_by_test(empty_df)
        assert result.empty

    def test_multiple_groups_ratios(self, multi_group_df):
        """Verify ratio values across both groups in multi_group_df."""
        result = get_glue_opcodes_by_test(multi_group_df)
        ratio1 = _get_ratio(result, "test_e", "PUSH1", "ADD")
        ratio2 = _get_ratio(result, "test_f", "PUSH1", "SUB")
        assert ratio1 == pytest.approx(0.5)
        assert ratio2 == pytest.approx(0.3)

    def test_custom_eps_tight(self, proportional_df):
        """With very small eps only near-perfect correlations pass."""
        result = get_glue_opcodes_by_test(proportional_df, eps=1e-10)
        glue_opcodes = _get_glue_opcodes(result, "test_a", "PUSH1")
        assert "ADD" in glue_opcodes

    def test_return_type(self, proportional_df):
        result = get_glue_opcodes_by_test(proportional_df)
        assert isinstance(result, pd.DataFrame)
        assert "glue_opcode" in result.columns
        assert "corr" in result.columns
        assert "ratio" in result.columns

    def test_glue_group_by_extra_column(self):
        """glue_group_by includes extra column in grouping; results split per group value."""
        opcode_ratios = {"ADD": (0.5, 0), "MUL": (0, 10)}
        df_a = _make_trace_df(
            _linear_group("f.py", "test_a", "PUSH1", "p1", 8, opcode_ratios),
            ["ADD", "MUL"],
        )
        df_a["client"] = "geth"
        df_b = _make_trace_df(
            _linear_group("f.py", "test_a", "PUSH1", "p1", 8, opcode_ratios),
            ["ADD", "MUL"],
        )
        df_b["client"] = "reth"
        df = pd.concat([df_a, df_b], ignore_index=True)
        result = get_glue_opcodes_by_test(df, glue_group_by=["client"])
        assert "client" in result.columns
        assert "glue_opcode" in result.columns
        assert "ADD" in result[result["client"] == "geth"]["glue_opcode"].values
        assert "ADD" in result[result["client"] == "reth"]["glue_opcode"].values

    def test_ratio_correct_when_rows_not_sorted_by_opcount(self, unsorted_opcount_df):
        """Ratio should be ~0.5 even when rows are presented in non-ascending opcount order.

        Without sorting by opcount before calling diff(), the estimator
        reduces to (ADD[last] − ADD[first]) / (opcount[last] − opcount[first]).
        The fixture deliberately places opcount=500 first and opcount=400 last
        (Δopcount = −100) with +/−100 noise injected at those two endpoints,
        which would yield ratio ≈ 1.5 for unsorted data.  Sorting first uses
        the full range Δopcount = 700 and gives ratio ≈ 0.5.
        """
        result = get_glue_opcodes_by_test(unsorted_opcount_df)
        assert "ADD" in _get_glue_opcodes(result, "test_unsorted", "PUSH1")
        ratio = _get_ratio(result, "test_unsorted", "PUSH1", "ADD")
        assert ratio == pytest.approx(0.5, abs=0.1)

    def test_glue_group_by_default_matches_no_extra_columns(self, proportional_df):
        """Default glue_group_by=[] produces same result as explicit empty list."""
        result_default = get_glue_opcodes_by_test(proportional_df)
        result_explicit = get_glue_opcodes_by_test(proportional_df, glue_group_by=[])
        assert set(result_default["glue_opcode"]) == set(result_explicit["glue_opcode"])


# ---------------------------------------------------------------------------
# Tests for compute_glue_adjustment
# ---------------------------------------------------------------------------


def _make_glue_results_df(rows):
    """Build a DataFrame matching glue_results.csv shape."""
    return pd.DataFrame(rows)


def _make_glue_opcodes_by_test(rows):
    """Build a DataFrame matching glue_opcodes_by_test.csv shape."""
    return pd.DataFrame(rows)


class TestComputeGlueAdjustment:
    def test_basic_single_glue_opcode(self):
        """Single glue opcode -> adjustment = ratio * runtime."""
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.0, "rsquared": 0.9}]
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
                    "ratio": 3.0,
                }
            ]
        )
        result = compute_glue_adjustment(glue_results, glue_by_test)
        assert len(result) == 1
        assert result.iloc[0]["opcode"] == "ADD"
        assert result.iloc[0]["client_name"] == "geth"
        assert np.isclose(result.iloc[0]["glue_adjustment"], 3.0 * 0.001)

    def test_multiple_glue_opcodes_summed(self):
        """Multiple glue opcodes -> adjustment is sum of ratio * runtime."""
        glue_results = _make_glue_results_df(
            [
                {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.0, "rsquared": 0.9},
                {"client": "geth", "glue_opcode": "CALL", "runtime": 0.005, "p_value": 0.0, "rsquared": 0.9},
            ]
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
                },
                {
                    "test_file": "test_add",
                    "test_name": "test_add",
                    "test_opcode": "ADD",
                    "test_params": "default",
                    "glue_opcode": "CALL",
                    "corr": 0.99,
                    "ratio": 1.0,
                },
            ]
        )
        result = compute_glue_adjustment(glue_results, glue_by_test)
        assert len(result) == 1
        expected = 2.0 * 0.001 + 1.0 * 0.005
        assert np.isclose(result.iloc[0]["glue_adjustment"], expected)

    def test_averages_ratio_across_test_params(self):
        """When multiple test_params exist, ratio is averaged."""
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.0, "rsquared": 0.9}]
        )
        glue_by_test = _make_glue_opcodes_by_test(
            [
                {
                    "test_file": "test_balance",
                    "test_name": "test_balance",
                    "test_opcode": "BALANCE",
                    "test_params": "cold_0",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 5.0,
                },
                {
                    "test_file": "test_balance",
                    "test_name": "test_balance",
                    "test_opcode": "BALANCE",
                    "test_params": "cold_1",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 3.0,
                },
            ]
        )
        result = compute_glue_adjustment(glue_results, glue_by_test)
        assert len(result) == 1
        # Average ratio = (5.0 + 3.0) / 2 = 4.0
        expected = 4.0 * 0.001
        assert np.isclose(result.iloc[0]["glue_adjustment"], expected)

    def test_per_client_adjustment(self):
        """Different clients get different adjustments based on their glue runtimes."""
        glue_results = _make_glue_results_df(
            [
                {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.0, "rsquared": 0.9},
                {"client": "reth", "glue_opcode": "PUSH1", "runtime": 0.002, "p_value": 0.0, "rsquared": 0.9},
            ]
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
                    "ratio": 3.0,
                }
            ]
        )
        result = compute_glue_adjustment(glue_results, glue_by_test)
        assert len(result) == 2
        geth_row = result[result["client_name"] == "geth"].iloc[0]
        reth_row = result[result["client_name"] == "reth"].iloc[0]
        assert np.isclose(geth_row["glue_adjustment"], 3.0 * 0.001)
        assert np.isclose(reth_row["glue_adjustment"], 3.0 * 0.002)

    def test_excludes_poor_pvalue_glue_opcodes(self):
        """Glue opcodes with p_value >= 0.05 are excluded from adjustment."""
        glue_results = _make_glue_results_df(
            [
                {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.0, "rsquared": 0.9},
                {"client": "geth", "glue_opcode": "CALL", "runtime": 0.005, "p_value": 0.10, "rsquared": 0.3},
            ]
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
                },
                {
                    "test_file": "test_add",
                    "test_name": "test_add",
                    "test_opcode": "ADD",
                    "test_params": "default",
                    "glue_opcode": "CALL",
                    "corr": 0.99,
                    "ratio": 1.0,
                },
            ]
        )
        result = compute_glue_adjustment(glue_results, glue_by_test)
        assert len(result) == 1
        # Only PUSH1 (p=0.0) contributes; CALL (p=0.10) is excluded
        expected = 2.0 * 0.001
        assert np.isclose(result.iloc[0]["glue_adjustment"], expected)

    def test_no_matching_glue_opcode(self):
        """When glue opcode has no runtime estimate, it's excluded (inner join)."""
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.0, "rsquared": 0.9}]
        )
        glue_by_test = _make_glue_opcodes_by_test(
            [
                {
                    "test_file": "test_add",
                    "test_name": "test_add",
                    "test_opcode": "ADD",
                    "test_params": "default",
                    "glue_opcode": "UNKNOWN_OP",
                    "corr": 0.99,
                    "ratio": 3.0,
                }
            ]
        )
        result = compute_glue_adjustment(glue_results, glue_by_test)
        assert len(result) == 0

    def test_custom_group_by_with_extra_column(self):
        """Custom group_by with an extra column produces separate adjustments per group."""
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.0, "rsquared": 0.9}]
        )
        glue_by_test = _make_glue_opcodes_by_test(
            [
                {
                    "test_file": "test_sload",
                    "test_name": "test_sload",
                    "test_opcode": "SLOAD",
                    "test_params": "default",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 2.0,
                    "cache_strategy": "NO_CACHE",
                },
                {
                    "test_file": "test_sload",
                    "test_name": "test_sload",
                    "test_opcode": "SLOAD",
                    "test_params": "default",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 4.0,
                    "cache_strategy": "CACHE_TX",
                },
            ]
        )
        result = compute_glue_adjustment(
            glue_results,
            glue_by_test,
            group_by=["test_name", "opcode", "client_name", "cache_strategy"],
        )
        assert len(result) == 2
        assert set(result.columns) == {"test_name", "opcode", "client_name", "cache_strategy", "glue_adjustment"}
        no_cache = result[result["cache_strategy"] == "NO_CACHE"].iloc[0]
        cache_tx = result[result["cache_strategy"] == "CACHE_TX"].iloc[0]
        assert np.isclose(no_cache["glue_adjustment"], 2.0 * 0.001)
        assert np.isclose(cache_tx["glue_adjustment"], 4.0 * 0.001)

    def test_custom_group_by_without_client(self):
        """group_by without client_name aggregates across clients."""
        glue_results = _make_glue_results_df(
            [
                {"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.0, "rsquared": 0.9},
                {"client": "reth", "glue_opcode": "PUSH1", "runtime": 0.003, "p_value": 0.0, "rsquared": 0.9},
            ]
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
        # Without client_name, both clients' contributions are summed
        result = compute_glue_adjustment(
            glue_results,
            glue_by_test,
            group_by=["test_name", "opcode"],
        )
        assert len(result) == 1
        assert "client_name" not in result.columns
        expected = 2.0 * 0.001 + 2.0 * 0.003
        assert np.isclose(result.iloc[0]["glue_adjustment"], expected)

    def test_custom_group_by_averages_ratios_per_group(self):
        """Extra group_by columns split ratio averaging into separate groups."""
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.001, "p_value": 0.0, "rsquared": 0.9}]
        )
        glue_by_test = _make_glue_opcodes_by_test(
            [
                {
                    "test_file": "test_sload",
                    "test_name": "test_sload",
                    "test_opcode": "SLOAD",
                    "test_params": "p1",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 6.0,
                    "cache_strategy": "NO_CACHE",
                },
                {
                    "test_file": "test_sload",
                    "test_name": "test_sload",
                    "test_opcode": "SLOAD",
                    "test_params": "p2",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 2.0,
                    "cache_strategy": "NO_CACHE",
                },
                {
                    "test_file": "test_sload",
                    "test_name": "test_sload",
                    "test_opcode": "SLOAD",
                    "test_params": "p1",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 10.0,
                    "cache_strategy": "CACHE_TX",
                },
            ]
        )
        # With cache_strategy in group_by, ratios are averaged separately per cache_strategy
        result = compute_glue_adjustment(
            glue_results,
            glue_by_test,
            group_by=["test_name", "opcode", "client_name", "cache_strategy"],
        )
        no_cache = result[result["cache_strategy"] == "NO_CACHE"].iloc[0]
        cache_tx = result[result["cache_strategy"] == "CACHE_TX"].iloc[0]
        # NO_CACHE: avg ratio = (6+2)/2 = 4.0
        assert np.isclose(no_cache["glue_adjustment"], 4.0 * 0.001)
        # CACHE_TX: avg ratio = 10.0/1 = 10.0
        assert np.isclose(cache_tx["glue_adjustment"], 10.0 * 0.001)

    def test_nan_in_group_by_columns_not_dropped(self):
        """Rows with NaN in group_by columns should still produce adjustments."""
        glue_results = _make_glue_results_df(
            [{"client": "geth", "glue_opcode": "PUSH1", "runtime": 0.002, "p_value": 0.01, "rsquared": 0.9}]
        )
        glue_by_test = _make_glue_opcodes_by_test(
            [
                {
                    "test_name": "test_sload",
                    "test_opcode": "SLOAD",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 5.0,
                    "cache_strategy": "NO_CACHE",
                    "account_mode": None,
                },
                {
                    "test_name": "test_sload",
                    "test_opcode": "SLOAD",
                    "glue_opcode": "PUSH1",
                    "corr": 0.99,
                    "ratio": 3.0,
                    "cache_strategy": "NO_CACHE",
                    "account_mode": "EXISTING_EOA",
                },
            ]
        )
        result = compute_glue_adjustment(
            glue_results,
            glue_by_test,
            group_by=["test_name", "opcode", "client_name", "cache_strategy", "account_mode"],
        )
        # Both rows should produce results (NaN account_mode not dropped)
        assert len(result) == 2
        nan_row = result[result["account_mode"].isna()].iloc[0]
        assert np.isclose(nan_row["glue_adjustment"], 5.0 * 0.002)
        eoa_row = result[result["account_mode"] == "EXISTING_EOA"].iloc[0]
        assert np.isclose(eoa_row["glue_adjustment"], 3.0 * 0.002)


# ---------------------------------------------------------------------------
# Tests for get_all_glue_opcodes_for_target_opcodes
# ---------------------------------------------------------------------------


def _make_glue_by_test(*pairs):
    """Build a minimal glue_opcodes_by_test DataFrame.

    Each pair is (test_opcode, glue_opcode).
    """
    return pd.DataFrame(
        [{"test_opcode": t, "glue_opcode": g} for t, g in pairs]
    )


class TestGetAllGlueOpcodesForTargetOpcodes:
    def test_basic_returns_direct_glue_opcodes(self):
        """Direct glue opcodes of a target are returned."""
        df = _make_glue_by_test(("ADD", "PUSH1"), ("ADD", "CALL"))
        result = get_all_glue_opcodes_for_target_opcodes(["ADD"], df)
        assert set(result) == {"PUSH1", "CALL"}

    def test_target_opcode_excluded_from_result(self):
        """Target opcode is excluded from the returned list even if it appears as a glue opcode."""
        # ADD is a target; PUSH1's glue includes ADD — ADD must be stripped from result
        df = _make_glue_by_test(("ADD", "PUSH1"), ("PUSH1", "ADD"))
        result = get_all_glue_opcodes_for_target_opcodes(["ADD"], df)
        assert "PUSH1" in result
        assert "ADD" not in result

    def test_no_glue_opcodes_returns_empty(self):
        """When no glue opcodes exist for the target, return empty list."""
        df = _make_glue_by_test(("MUL", "PUSH1"))
        result = get_all_glue_opcodes_for_target_opcodes(["ADD"], df)
        assert result == []

    def test_multiple_targets(self):
        """Glue opcodes across multiple target opcodes are all included."""
        df = _make_glue_by_test(("ADD", "PUSH1"), ("MUL", "CALL"))
        result = get_all_glue_opcodes_for_target_opcodes(["ADD", "MUL"], df)
        assert "PUSH1" in result
        assert "CALL" in result