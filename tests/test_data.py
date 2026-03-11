import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from unittest.mock import patch, MagicMock

from data import (
    extract_param_values,
    get_current_gas_cost,
    process_test_title_col,
    process_compute_params,
    process_stateful_params,
    add_opcount_col,
    _query_benchmarkoor,
    process_gas_bench_data,
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
# Tests for process_compute_params
# ---------------------------------------------------------------------------


def _make_compute_df(test_name, test_params, test_opcode):
    return pd.DataFrame(
        {"test_name": [test_name], "test_params": [test_params], "test_opcode": [test_opcode]}
    )


class TestProcessComputeParams:
    def test_ecadd_from_alt_bn128_add(self):
        df = _make_compute_df("test_alt_bn128", "add-opcount_100", None)
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "ECADD"

    def test_ecmul_from_alt_bn128_mul(self):
        df = _make_compute_df("test_alt_bn128", "mul-opcount_100", None)
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "ECMUL"

    def test_ecpairing_from_alt_bn128_benchmark(self):
        df = _make_compute_df("test_alt_bn128_benchmark", "num_pairs_4", None)
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "ECPAIRING"

    def test_bls12_g1msm(self):
        df = _make_compute_df("test_bls12_g1_msm", "opcount_100", None)
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "BLS12_G1MSM"

    def test_bls12_g2msm(self):
        df = _make_compute_df("test_bls12_g2_msm", "opcount_100", None)
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "BLS12_G2MSM"

    def test_bls12_pairing_check(self):
        df = _make_compute_df("test_bls12_pairing", "opcount_100", None)
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "BLS12_PAIRING_CHECK"

    def test_bls12_381_opcode_from_params(self):
        df = _make_compute_df("test_bls12_381", "g1add-opcount_100", None)
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "G1ADD"

    def test_keccak_renamed(self):
        df = _make_compute_df("test_keccak", "opcount_100", "KECCAK")
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "KECCAK256"

    def test_ripemd160_renamed(self):
        df = _make_compute_df("test_ripemd", "opcount_100", "RIPEMD160")
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "RIPEMD-160"

    def test_sha256_renamed(self):
        df = _make_compute_df("test_sha256", "opcount_100", "SHA256")
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "SHA2-256"

    def test_jumpdests_renamed(self):
        df = _make_compute_df("test_jumpdests", "opcount_100", "JUMPDESTS")
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "JUMPDEST"

    def test_point_evaluation_renamed(self):
        df = _make_compute_df("test_point", "opcount_100", "POINT")
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "POINT_EVALUATION"

    def test_bls12_fp_to_g1_renamed(self):
        df = _make_compute_df("test_bls", "opcount_100", "BLS12_FP_TO_G1")
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "BLS12_MAP_FP_TO_G1"

    def test_bls12_fp_to_g2_renamed(self):
        df = _make_compute_df("test_bls", "opcount_100", "BLS12_FP_TO_G2")
        result = process_compute_params(df)
        assert result["test_opcode"].iloc[0] == "BLS12_MAP_FP2_TO_G2"

    def test_does_not_modify_input(self):
        df = _make_compute_df("test_keccak", "opcount_100", "KECCAK")
        process_compute_params(df)
        assert df["test_opcode"].iloc[0] == "KECCAK"



# ---------------------------------------------------------------------------
# Tests for get_current_gas_cost
# ---------------------------------------------------------------------------


class TestGetCurrentGasCost:
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
# Tests for process_stateful_params
# ---------------------------------------------------------------------------


def _make_stateful_df(test_name, test_params, test_opcode=None):
    return pd.DataFrame(
        {"test_name": [test_name], "test_params": [test_params], "test_opcode": [test_opcode]}
    )


class TestProcessStatefulParams:
    def test_sload_opcode_set_for_sload_benchmark(self):
        df = _make_stateful_df("test_storage_sload_benchmark", "cold_1")
        result = process_stateful_params(df)
        assert result["test_opcode"].iloc[0] == "SLOAD"

    def test_sload_opcode_set_for_sload_same_key(self):
        df = _make_stateful_df("test_storage_sload_same_key_benchmark", "some_param")
        result = process_stateful_params(df)
        assert result["test_opcode"].iloc[0] == "SLOAD"

    def test_sload_opcode_set_for_erc20_balanceof(self):
        df = _make_stateful_df("test_sload_erc20_balanceof", "some_param")
        result = process_stateful_params(df)
        assert result["test_opcode"].iloc[0] == "SLOAD"

    def test_sstore_opcode_set_for_erc20_mint(self):
        df = _make_stateful_df("test_sstore_erc20_mint", "no_change_False")
        result = process_stateful_params(df)
        assert result["test_opcode"].iloc[0] == "SSTORE"

    def test_sstore_opcode_from_storage_access_params(self):
        df = _make_stateful_df("test_storage_access_cold_benchmark", "SSTORE new value")
        result = process_stateful_params(df)
        assert result["test_opcode"].iloc[0] == "SSTORE"

    def test_sstore_prefix_stripped_from_opcode(self):
        df = _make_stateful_df("test_storage_access_cold_benchmark", "SSTORE_new value", "SSTORE_NEW")
        result = process_stateful_params(df)
        assert result["test_opcode"].iloc[0] == "SSTORE"

    def test_sstore_erc20_mint_no_change_false_maps_to_update_1(self):
        df = _make_stateful_df("test_sstore_erc20_mint", "no_change_False")
        result = process_stateful_params(df)
        assert "update_1" in result["test_params"].iloc[0]

    def test_sstore_erc20_mint_no_change_true_maps_to_update_0(self):
        df = _make_stateful_df("test_sstore_erc20_mint", "no_change_True")
        result = process_stateful_params(df)
        assert "update_0" in result["test_params"].iloc[0]

    def test_account_access_value_sent_1_maps_to_update_1(self):
        df = _make_stateful_df("test_account_access", "value_sent_1")
        result = process_stateful_params(df)
        assert "update_1" in result["test_params"].iloc[0]

    def test_account_access_value_sent_0_maps_to_update_0(self):
        df = _make_stateful_df("test_account_access", "value_sent_0")
        result = process_stateful_params(df)
        assert "update_0" in result["test_params"].iloc[0]

    def test_cache_strategy_extracted_to_column(self):
        df = _make_stateful_df("test_storage_sload_benchmark", "cache_strategy_CacheStrategy.HOT-cold_1")
        result = process_stateful_params(df)
        assert result["cache_strategy"].iloc[0] == "HOT"
        assert "cache_strategy" not in result["test_params"].iloc[0]

    def test_account_mode_extracted_to_column(self):
        df = _make_stateful_df("test_account_access", "account_mode_AccountMode.EXISTING-cold_1")
        result = process_stateful_params(df)
        assert result["account_mode"].iloc[0] == "EXISTING"
        assert "account_mode" not in result["test_params"].iloc[0]

    def test_token_name_extracted_to_column(self):
        df = _make_stateful_df("test_sload_erc20_balanceof", "token_name_USDT-cold_1")
        result = process_stateful_params(df)
        assert result["token_name"].iloc[0] == "USDT"
        assert "token_name" not in result["test_params"].iloc[0]

    def test_existing_slots_extracted_to_column(self):
        df = _make_stateful_df("test_storage_sload_benchmark", "existing_slots_100-cold_1")
        result = process_stateful_params(df)
        assert result["existing_slots"].iloc[0] == "100"
        assert "existing_slots" not in result["test_params"].iloc[0]

    def test_remaining_params_preserved(self):
        df = _make_stateful_df("test_storage_sload_benchmark", "cache_strategy_CacheStrategy.HOT-cold_1-new_0")
        result = process_stateful_params(df)
        assert "cold_1" in result["test_params"].iloc[0]
        assert "new_0" in result["test_params"].iloc[0]

    def test_does_not_modify_input(self):
        df = _make_stateful_df("test_sstore_erc20_mint", "no_change_False")
        process_stateful_params(df)
        assert df["test_params"].iloc[0] == "no_change_False"



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


# ---------------------------------------------------------------------------
# Tests for _query_benchmarkoor
# ---------------------------------------------------------------------------


def _make_suites_response(network, test_type, suite_hash):
    return {
        "data": [
            {
                "name": f"{network}-12345678-{test_type}",
                "suite_hash": suite_hash,
                "indexed_at": "2026-01-01T00:00:00Z",
            }
        ]
    }


def _make_stats_response(data=None, total=0):
    return {"data": data or [], "total": total}


class TestQueryBenchmarkoor:
    def _mock_session(self, network, test_type, suite_hash, rows):
        mock_session = MagicMock()
        suites_resp = MagicMock()
        suites_resp.json.return_value = _make_suites_response(network, test_type, suite_hash)

        count_resp = MagicMock()
        count_resp.json.return_value = _make_stats_response(total=len(rows))

        data_resp = MagicMock()
        data_resp.json.return_value = _make_stats_response(data=rows, total=len(rows))

        mock_session.get.side_effect = [suites_resp, count_resp, data_resp]
        return mock_session

    def test_returns_expected_columns(self):
        rows = [
            {"test_name": "test_add.py__test_add[fork_Osaka]", "client": "geth", "test_time_ns": 1_000_000, "run_start": 1700000000},
        ]
        with patch("requests.Session") as MockSession:
            MockSession.return_value = self._mock_session("mainnet", "compute", "abc123", rows)
            df = _query_benchmarkoor("token", "mainnet", "compute", "2026-01-01")
        assert set(["test_title", "client_name", "run_duration_ms", "ingestion_timestamp"]).issubset(df.columns)

    def test_converts_ns_to_ms(self):
        rows = [
            {"test_name": "t", "client": "geth", "test_time_ns": 2_000_000, "run_start": 1700000000},
        ]
        with patch("requests.Session") as MockSession:
            MockSession.return_value = self._mock_session("mainnet", "compute", "abc123", rows)
            df = _query_benchmarkoor("token", "mainnet", "compute", "2026-01-01")
        assert df["run_duration_ms"].iloc[0] == pytest.approx(2.0)

    def test_ingestion_timestamp_is_datetime(self):
        rows = [
            {"test_name": "t", "client": "geth", "test_time_ns": 1_000_000, "run_start": 1700000000},
        ]
        with patch("requests.Session") as MockSession:
            MockSession.return_value = self._mock_session("mainnet", "compute", "abc123", rows)
            df = _query_benchmarkoor("token", "mainnet", "compute", "2026-01-01")
        assert pd.api.types.is_datetime64_any_dtype(df["ingestion_timestamp"])

    def test_raises_on_missing_suite(self):
        with patch("requests.Session") as MockSession:
            mock_session = MagicMock()
            resp = MagicMock()
            resp.json.return_value = {"data": []}
            mock_session.get.return_value = resp
            MockSession.return_value = mock_session
            with pytest.raises(ValueError, match="No suite found"):
                _query_benchmarkoor("token", "unknown-net", "compute", "2026-01-01")


# ---------------------------------------------------------------------------
# Tests for process_gas_bench_data routing
# ---------------------------------------------------------------------------


class TestProcessGasBenchData:
    def _minimal_raw_df(self):
        return pd.DataFrame({
            "test_title": ["test_add.py__test_add[fork_Osaka-blockchain_test-opcode_ADD-opcount_100]"],
            "client_name": ["geth"],
            "run_duration_ms": [10.0],
            "ingestion_timestamp": ["2026-01-01"],
        })

    def test_unknown_source_raises(self):
        with pytest.raises(ValueError, match="Unknown source"):
            process_gas_bench_data(network="mainnet", test_type="compute", start_date="2026-01-01", source="invalid")

    def test_gas_bench_source_calls_query_gas_bench(self):
        raw_df = self._minimal_raw_df()
        trace_df = pd.DataFrame({"test_title": [], "opcount": []})
        with patch("data._query_gas_bench", return_value=raw_df) as mock_qgb, \
             patch("data.process_test_trace_data", return_value=trace_df):
            df, _ = process_gas_bench_data(
                network="mainnet", test_type="compute", start_date="2026-01-01",
                user="u", password="p",
            )
        mock_qgb.assert_called_once_with("u", "p", "compute_mainnet", "2026-01-01")

    def test_benchmarkoor_source_calls_query_benchmarkoor(self):
        raw_df = self._minimal_raw_df()
        trace_df = pd.DataFrame({"test_title": [], "opcount": []})
        with patch("data._query_benchmarkoor", return_value=raw_df) as mock_qbm, \
             patch("data.process_test_trace_data", return_value=trace_df):
            df, _ = process_gas_bench_data(
                network="mainnet", test_type="compute", start_date="2026-01-01",
                source="benchmarkoor", bearer_token="tok", user="u", password="p",
            )
        mock_qbm.assert_called_once_with("tok", "mainnet", "compute", "2026-01-01")

    def test_benchmarkoor_still_queries_trace_data(self):
        raw_df = self._minimal_raw_df()
        trace_df = pd.DataFrame({"test_title": [], "opcount": []})
        with patch("data._query_benchmarkoor", return_value=raw_df), \
             patch("data.process_test_trace_data", return_value=trace_df) as mock_trace:
            process_gas_bench_data(
                network="mainnet", test_type="compute", start_date="2026-01-01",
                source="benchmarkoor", bearer_token="tok", user="u", password="p",
            )
        mock_trace.assert_called_once_with("u", "p", "compute_mainnet", None)

    def test_db_name_constructed_correctly(self):
        raw_df = self._minimal_raw_df()
        trace_df = pd.DataFrame({"test_title": [], "opcount": []})
        with patch("data._query_gas_bench", return_value=raw_df) as mock_qgb, \
             patch("data.process_test_trace_data", return_value=trace_df):
            process_gas_bench_data(
                network="perf-devnet-2", test_type="stateful", start_date="2026-01-01",
                user="u", password="p",
            )
        mock_qgb.assert_called_once_with("u", "p", "stateful_perf-devnet-2", "2026-01-01")
