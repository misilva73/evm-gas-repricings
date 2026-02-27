import pandas as pd
import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from glue import get_glue_opcodes_by_test, generate_glue_opcode_report


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


def _filter_group(
    result_df, test_file, test_name, test_opcode, test_params, block_limit_million=30
):
    """Return rows from result_df matching the given grouping key."""
    mask = (
        (result_df["test_file"] == test_file)
        & (result_df["test_name"] == test_name)
        & (result_df["test_opcode"] == test_opcode)
        & (result_df["test_params"] == test_params)
        & (result_df["block_limit_million"] == block_limit_million)
    )
    return result_df[mask]


def _get_glue_opcodes(
    result_df, test_file, test_name, test_opcode, test_params, block_limit_million=30
):
    """Return the set of glue_opcode values for a given group."""
    group = _filter_group(
        result_df, test_file, test_name, test_opcode, test_params, block_limit_million
    )
    return set(group["glue_opcode"].values)


def _get_ratio(
    result_df,
    test_file,
    test_name,
    test_opcode,
    test_params,
    glue_opcode,
    block_limit_million=30,
):
    """Return the ratio value for a specific group + glue_opcode."""
    group = _filter_group(
        result_df, test_file, test_name, test_opcode, test_params, block_limit_million
    )
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
        glue_opcodes = _get_glue_opcodes(result, "f.py", "test_a", "PUSH1", "p1")
        assert "ADD" in glue_opcodes
        ratio = _get_ratio(result, "f.py", "test_a", "PUSH1", "p1", "ADD")
        assert ratio == pytest.approx(0.5)

    def test_constant_opcode_not_detected(self, proportional_df):
        """MUL is constant → NOT detected as glue."""
        result = get_glue_opcodes_by_test(proportional_df)
        glue_opcodes = _get_glue_opcodes(result, "f.py", "test_a", "PUSH1", "p1")
        assert "MUL" not in glue_opcodes

    def test_self_opcode_excluded(self, self_opcode_df):
        """test_opcode == ADD → ADD must not appear in result for that test."""
        result = get_glue_opcodes_by_test(self_opcode_df)
        glue_opcodes = _get_glue_opcodes(result, "f.py", "test_b", "ADD", "p1")
        assert "ADD" not in glue_opcodes

    def test_self_opcode_excluded_but_others_kept(self, self_opcode_df):
        """SUB also scales with opcount → should still be in result."""
        result = get_glue_opcodes_by_test(self_opcode_df)
        glue_opcodes = _get_glue_opcodes(result, "f.py", "test_b", "ADD", "p1")
        assert "SUB" in glue_opcodes
        ratio = _get_ratio(result, "f.py", "test_b", "ADD", "p1", "SUB")
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
        glue1 = _get_glue_opcodes(result, "f.py", "test_e", "PUSH1", "p1")
        glue2 = _get_glue_opcodes(result, "f.py", "test_f", "PUSH1", "p2")
        assert "ADD" in glue1
        assert "SUB" in glue2

    def test_detects_offset_glue_opcode(self, offset_df):
        """ADD = 0.5*opcount + 50 → still detected as glue with ratio 0.5."""
        result = get_glue_opcodes_by_test(offset_df)
        glue_opcodes = _get_glue_opcodes(result, "f.py", "test_offset", "PUSH1", "p1")
        assert "ADD" in glue_opcodes
        ratio = _get_ratio(result, "f.py", "test_offset", "PUSH1", "p1", "ADD")
        assert ratio == pytest.approx(0.5)

    def test_offset_constant_opcode_not_detected(self, offset_df):
        """MUL is constant → NOT detected as glue even with offset fixture."""
        result = get_glue_opcodes_by_test(offset_df)
        glue_opcodes = _get_glue_opcodes(result, "f.py", "test_offset", "PUSH1", "p1")
        assert "MUL" not in glue_opcodes

    def test_multiple_glue_opcodes_in_same_group(self, multi_glue_df):
        """Both ADD and MUL scale with opcount → both detected as glue."""
        result = get_glue_opcodes_by_test(multi_glue_df)
        glue_opcodes = _get_glue_opcodes(result, "f.py", "test_mg", "PUSH1", "p1")
        assert "ADD" in glue_opcodes
        assert "MUL" in glue_opcodes
        assert "SUB" not in glue_opcodes
        assert _get_ratio(result, "f.py", "test_mg", "PUSH1", "p1", "ADD") == pytest.approx(0.5)
        assert _get_ratio(result, "f.py", "test_mg", "PUSH1", "p1", "MUL") == pytest.approx(0.3)

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
        ratio1 = _get_ratio(result, "f.py", "test_e", "PUSH1", "p1", "ADD")
        ratio2 = _get_ratio(result, "f.py", "test_f", "PUSH1", "p2", "SUB")
        assert ratio1 == pytest.approx(0.5)
        assert ratio2 == pytest.approx(0.3)

    def test_custom_eps_tight(self, proportional_df):
        """With very small eps only near-perfect correlations pass."""
        result = get_glue_opcodes_by_test(proportional_df, eps=1e-10)
        glue_opcodes = _get_glue_opcodes(result, "f.py", "test_a", "PUSH1", "p1")
        assert "ADD" in glue_opcodes

    def test_return_type(self, proportional_df):
        result = get_glue_opcodes_by_test(proportional_df)
        assert isinstance(result, pd.DataFrame)
        assert "glue_opcode" in result.columns
        assert "corr" in result.columns
        assert "ratio" in result.columns


# ---------------------------------------------------------------------------
# Tests for generate_glue_opcode_report (currently a no-op)
# ---------------------------------------------------------------------------


class TestGenerateGlueOpcodeReport:
    def test_returns_none(self):
        assert generate_glue_opcode_report() is None
