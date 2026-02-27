import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from data import (
    extract_param_values,
    get_current_gas_cost,
    process_test_title_col,
    process_account_params,
    add_opcount_col,
    _build_params,
    _remove_constant_params,
)


# ---------------------------------------------------------------------------
# Tests for extract_param_values
# ---------------------------------------------------------------------------


class TestExtractParamValues:
    def test_extracts_single_value(self):
        assert extract_param_values("opcount_500", "opcount") == "500"

    def test_extracts_different_param(self):
        assert extract_param_values("opcount_500-msg_size_32", "msg_size") == "32"

    def test_returns_nan_when_missing(self):
        result = extract_param_values("opcount_500", "msg_size")
        assert np.isnan(result)

    def test_returns_first_match(self):
        assert extract_param_values("x_10-x_20", "x") == "10"

    def test_empty_string(self):
        result = extract_param_values("", "opcount")
        assert np.isnan(result)


# ---------------------------------------------------------------------------
# Tests for _build_params
# ---------------------------------------------------------------------------


class TestBuildParams:
    def test_all_fields_present(self):
        row = pd.Series(
            {
                "_cold": 1,
                "_new": 0,
                "_update": 1,
                "_storage_size": np.nan,
                "_pre_read": np.nan,
            }
        )
        result = _build_params(row)
        assert result == "cold_1-new_0-update_1"

    def test_float_to_int_conversion(self):
        row = pd.Series(
            {
                "_cold": 1.0,
                "_new": 0.0,
                "_update": np.nan,
                "_storage_size": np.nan,
                "_pre_read": np.nan,
            }
        )
        result = _build_params(row)
        assert result == "cold_1-new_0"

    def test_float_storage_size_preserved(self):
        row = pd.Series(
            {
                "_cold": np.nan,
                "_new": np.nan,
                "_update": np.nan,
                "_storage_size": 9.0,
                "_pre_read": np.nan,
            }
        )
        result = _build_params(row)
        assert result == "storage_size_9"

    def test_all_nan_returns_nan(self):
        row = pd.Series(
            {
                "_cold": np.nan,
                "_new": np.nan,
                "_update": np.nan,
                "_storage_size": np.nan,
                "_pre_read": np.nan,
            }
        )
        result = _build_params(row)
        assert isinstance(result, float) and np.isnan(result)

    def test_pre_read_included(self):
        row = pd.Series(
            {
                "_cold": 0,
                "_new": 1,
                "_update": 1,
                "_storage_size": np.nan,
                "_pre_read": 1,
            }
        )
        result = _build_params(row)
        assert "pre_read_1" in result


# ---------------------------------------------------------------------------
# Tests for _remove_constant_params
# ---------------------------------------------------------------------------


class TestRemoveConstantParams:
    def test_removes_constant_params(self):
        result = _remove_constant_params("cold_1-new_0-update_1", {"new"})
        assert result == "cold_1-update_1"

    def test_removes_multiple_constants(self):
        result = _remove_constant_params("cold_1-new_0-update_1", {"new", "update"})
        assert result == "cold_1"

    def test_all_removed_returns_nan(self):
        result = _remove_constant_params("cold_1", {"cold"})
        assert isinstance(result, float) and np.isnan(result)

    def test_no_constants_returns_original(self):
        result = _remove_constant_params("cold_1-new_0", set())
        assert result == "cold_1-new_0"


# ---------------------------------------------------------------------------
# Tests for get_current_gas_cost
# ---------------------------------------------------------------------------


class TestGetCurrentGasCost:
    def test_new_param(self):
        assert get_current_gas_cost("SSTORE", "new") == 20_000 - 100

    def test_cold_param(self):
        assert get_current_gas_cost("SLOAD", "cold") == 2_100 - 100

    def test_update_param(self):
        assert get_current_gas_cost("SSTORE", "update") == 5_000 - 2_100 - 100

    def test_code_size_param(self):
        assert get_current_gas_cost("EXTCODECOPY", "code_size") == 3

    def test_num_rounds_param(self):
        assert get_current_gas_cost("BLAKE2F", "num_rounds") == 1

    def test_num_pairs_param(self):
        assert get_current_gas_cost("ECPAIRING", "num_pairs") == 34_000

    def test_msg_size_param(self):
        assert get_current_gas_cost("KECCAK256", "msg_size") == 6

    def test_constant_param(self):
        assert get_current_gas_cost("ECRECOVER", "constant") == 3_000

    def test_unknown_param_returns_none(self):
        assert get_current_gas_cost("ADD", "unknown_param") is None

    def test_unknown_opcode_returns_none(self):
        assert get_current_gas_cost("NONEXISTENT", "constant") is None


# ---------------------------------------------------------------------------
# Tests for process_test_title_col
# ---------------------------------------------------------------------------


def _make_title_df(titles):
    """Helper: build a minimal DataFrame with a test_title column."""
    return pd.DataFrame({"test_title": titles})


class TestProcessTestTitleCol:
    def test_extracts_test_file(self):
        df = _make_title_df(
            ["test_arithmetic.py__test_add[fork_Osaka-blockchain_test-opcode_ADD-opcount_100]"]
        )
        result = process_test_title_col(df)
        assert result["test_file"].iloc[0] == "test_arithmetic"

    def test_extracts_test_name(self):
        df = _make_title_df(
            ["test_arithmetic.py__test_add[fork_Osaka-blockchain_test-opcode_ADD-opcount_100]"]
        )
        result = process_test_title_col(df)
        assert result["test_name"].iloc[0] == "test_add"

    def test_extracts_opcode_from_title(self):
        df = _make_title_df(
            ["test_add.py__test_add[fork_Osaka-blockchain_test-opcode_ADD-opcount_100]"]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "ADD"

    def test_opcode_from_opcodes_in_test_name(self):
        """test_jumpi_fallthrough is in OPCODES_IN_TEST_NAME_LIST → opcode from test_name split."""
        df = _make_title_df(
            [
                "test_control_flow.py__test_jumpi_fallthrough[fork_Osaka-blockchain_test-opcount_100]"
            ]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "JUMPI"

    def test_renames_keccak(self):
        df = _make_title_df(
            [
                "test_keccak.py__test_keccak_max_permutations[fork_Osaka-blockchain_test-opcode_KECCAK-opcount_100]"
            ]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "KECCAK256"

    def test_renames_sha256(self):
        df = _make_title_df(
            [
                "test_sha256.py__test_sha256_fixed_size[fork_Osaka-blockchain_test-opcode_SHA256-opcount_100]"
            ]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "SHA2-256"

    def test_renames_ripemd160(self):
        df = _make_title_df(
            [
                "test_ripemd160.py__test_ripemd160_fixed_size[fork_Osaka-blockchain_test-opcode_RIPEMD160-opcount_100]"
            ]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "RIPEMD-160"

    def test_renames_jumpdests(self):
        df = _make_title_df(
            [
                "test_jumpdests.py__test_jumpdests[fork_Osaka-blockchain_test-opcode_JUMPDESTS-opcount_100]"
            ]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "JUMPDEST"

    def test_alt_bn128_add(self):
        df = _make_title_df(
            [
                "test_alt_bn128.py__test_alt_bn128[fork_Osaka-blockchain_test-add-opcount_100]"
            ]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "ECADD"

    def test_alt_bn128_mul(self):
        df = _make_title_df(
            [
                "test_alt_bn128.py__test_alt_bn128[fork_Osaka-blockchain_test-mul-opcount_100]"
            ]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "ECMUL"

    def test_bls12_g1_msm(self):
        df = _make_title_df(
            ["test_bls12.py__test_bls12_g1_msm[fork_Osaka-blockchain_test-opcount_100]"]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "BLS12_G1MSM"

    def test_bls12_g2_msm(self):
        df = _make_title_df(
            ["test_bls12.py__test_bls12_g2_msm[fork_Osaka-blockchain_test-opcount_100]"]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "BLS12_G2MSM"

    def test_bls12_pairing(self):
        df = _make_title_df(
            [
                "test_bls12.py__test_bls12_pairing[fork_Osaka-blockchain_test-opcount_100]"
            ]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "BLS12_PAIRING_CHECK"

    def test_benchmark_params_extracted(self):
        df = _make_title_df(
            [
                "test_foo.py__test_foo[fork_Osaka-benchmark_test-benchmark_30M-opcode_ADD-opcount_100]"
            ]
        )
        result = process_test_title_col(df)
        assert result["block_limit_million"].iloc[0] == "30"

    def test_point_evaluation_renamed(self):
        df = _make_title_df(
            [
                "test_point.py__test_point_evaluation[fork_Osaka-blockchain_test-opcode_POINT-opcount_100]"
            ]
        )
        result = process_test_title_col(df)
        assert result["test_opcode"].iloc[0] == "POINT_EVALUATION"


# ---------------------------------------------------------------------------
# Tests for process_storage_params (tested via the full process_test_title_col pipeline)
# ---------------------------------------------------------------------------


class TestProcessStorageParams:
    def test_sload_benchmark_cold(self):
        title = "test_storage_sload_benchmark.py__test_storage_sload_benchmark[fork_Osaka-blockchain_test-access_warm_False-storage_keys_pre_set_True-opcount_100]"
        result = process_test_title_col(pd.DataFrame({"test_title": [title]}))
        assert result["test_opcode"].iloc[0] == "SLOAD"
        params = result["test_params"].iloc[0]
        assert "cold_1" in params
        assert "new_0" in params

    def test_sload_benchmark_warm(self):
        title = "test_storage_sload_benchmark.py__test_storage_sload_benchmark[fork_Osaka-blockchain_test-access_warm_True-storage_keys_pre_set_True-opcount_100]"
        result = process_test_title_col(pd.DataFrame({"test_title": [title]}))
        params = result["test_params"].iloc[0]
        assert "cold_0" in params

    def test_storage_access_cold_sstore_new(self):
        title = "test_storage_access_cold_benchmark.py__test_storage_access_cold_benchmark[fork_Osaka-blockchain_test-SSTORE new value-opcount_100]"
        result = process_test_title_col(pd.DataFrame({"test_title": [title]}))
        assert result["test_opcode"].iloc[0] == "SSTORE"
        params = result["test_params"].iloc[0]
        assert "cold_1" in params
        assert "update_1" in params

    def test_storage_access_cold_sstore_same(self):
        title = "test_storage_access_cold_benchmark.py__test_storage_access_cold_benchmark[fork_Osaka-blockchain_test-SSTORE same value-opcount_100]"
        result = process_test_title_col(pd.DataFrame({"test_title": [title]}))
        params = result["test_params"].iloc[0]
        assert "update_0" in params

    def test_sload_same_key_warm(self):
        title = "test_storage_sload_same_key_benchmark.py__test_storage_sload_same_key_benchmark[fork_Osaka-blockchain_test-storage_keys_pre_set_True-opcount_100]"
        result = process_test_title_col(pd.DataFrame({"test_title": [title]}))
        params = result["test_params"].iloc[0]
        assert "cold_0" in params
        assert "new_0" in params

    def test_intermediate_columns_dropped(self):
        title = "test_storage_sload_benchmark.py__test_storage_sload_benchmark[fork_Osaka-blockchain_test-access_warm_False-storage_keys_pre_set_True-opcount_100]"
        result = process_test_title_col(pd.DataFrame({"test_title": [title]}))
        for col in ["_cold", "_new", "_update", "_storage_size", "_pre_read"]:
            assert col not in result.columns


# ---------------------------------------------------------------------------
# Tests for process_account_params
# ---------------------------------------------------------------------------


class TestProcessAccountParams:
    def test_warm_to_cold_0(self):
        """access_warm_True → cold_0 for account opcodes."""
        df = pd.DataFrame(
            {
                "test_title": ["t1", "t2"],
                "test_file": ["f", "f"],
                "test_name": ["test_balance", "test_balance"],
                "test_opcode": ["BALANCE", "BALANCE"],
                "test_params": [
                    "access_warm_True-value_0",
                    "access_warm_False-value_0",
                ],
                "block_limit_million": [30, 30],
            }
        )
        result = process_account_params(df)
        assert "cold_0" in result["test_params"].iloc[0]
        assert "access_warm_True" not in result["test_params"].iloc[0]

    def test_cold_to_cold_1(self):
        """access_warm_False → cold_1 for account opcodes."""
        df = pd.DataFrame(
            {
                "test_title": ["t1", "t2"],
                "test_file": ["f", "f"],
                "test_name": ["test_balance", "test_balance"],
                "test_opcode": ["BALANCE", "BALANCE"],
                "test_params": [
                    "access_warm_True-value_0",
                    "access_warm_False-value_0",
                ],
                "block_limit_million": [30, 30],
            }
        )
        result = process_account_params(df)
        assert "cold_1" in result["test_params"].iloc[1]

    def test_non_account_opcode_unchanged(self):
        """Non-account opcodes should not have access_warm replaced."""
        df = pd.DataFrame(
            {
                "test_title": ["t"],
                "test_file": ["f"],
                "test_name": ["test_add"],
                "test_opcode": ["ADD"],
                "test_params": ["access_warm_True-value_0"],
                "block_limit_million": [30],
            }
        )
        result = process_account_params(df)
        assert "access_warm_True" in result["test_params"].iloc[0]

    def test_removes_constant_params_across_opcode(self):
        """Params that don't vary for an opcode should be removed."""
        df = pd.DataFrame(
            {
                "test_title": ["t1", "t2"],
                "test_file": ["f", "f"],
                "test_name": ["test_balance", "test_balance"],
                "test_opcode": ["BALANCE", "BALANCE"],
                "test_params": [
                    "cold_0-value_0",
                    "cold_1-value_0",
                ],
                "block_limit_million": [30, 30],
            }
        )
        result = process_account_params(df)
        # "value" has the same value (0) for both rows → should be removed
        for val in result["test_params"]:
            assert "value_0" not in val


# ---------------------------------------------------------------------------
# Tests for add_opcount_col
# ---------------------------------------------------------------------------


class TestAddOpcountCol:
    def test_regular_opcode_uses_own_column(self):
        df = pd.DataFrame(
            {
                "test_opcode": ["ADD"],
                "ADD": [500],
                "STATICCALL": [10],
            }
        )
        result = add_opcount_col(df)
        assert result["opcount"].iloc[0] == 500

    def test_precompile_uses_staticcall(self):
        df = pd.DataFrame(
            {
                "test_opcode": ["ECRECOVER"],
                "ECRECOVER": [0],
                "STATICCALL": [42],
            }
        )
        result = add_opcount_col(df)
        assert result["opcount"].iloc[0] == 42

    def test_does_not_modify_input(self):
        df = pd.DataFrame(
            {
                "test_opcode": ["ADD"],
                "ADD": [100],
                "STATICCALL": [5],
            }
        )
        add_opcount_col(df)
        assert "opcount" not in df.columns

    def test_multiple_rows(self):
        df = pd.DataFrame(
            {
                "test_opcode": ["ADD", "ECRECOVER", "MUL"],
                "ADD": [100, 0, 0],
                "MUL": [0, 0, 200],
                "ECRECOVER": [0, 0, 0],
                "STATICCALL": [5, 42, 3],
            }
        )
        result = add_opcount_col(df)
        assert list(result["opcount"]) == [100, 42, 200]
