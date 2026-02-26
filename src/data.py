import re
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List
from sqlalchemy import create_engine

sys.path.append(str(Path(__file__).parent))
from operation_gas_costs import get_fusaka_dict
from operation_types import PRECOMPILES, CALL, STATEFUL


opcodes_file_name = Path(__file__).parent.joinpath("opcodes_in_test_name.txt")
with open(opcodes_file_name, "r") as f:
    OPCODES_IN_TEST_NAME_LIST = [line.strip() for line in f.readlines()]


def extract_param_values(params_str: str, param_name: str):
    regex_str = param_name + r"_(\d+)"
    values = re.findall(regex_str, params_str)
    if len(values) > 0:
        return values[0]
    else:
        return np.nan


def get_current_gas_cost(opcode: str, param: str) -> int | None:
    """Map opcode and parameter to current gas cost from fusaka_dict"""
    fusaka_dict = get_fusaka_dict()
    # Handle parameter-based costs
    # 8038 repricings
    if param == "new":
        return fusaka_dict.get(f"{opcode}_NEW", None)
    elif param == "cold":
        return fusaka_dict.get(f"{opcode}_COLD", None)
    elif param == "update":
        return fusaka_dict.get(f"{opcode}_UPDATE", None)
    elif param == "code_size":
        return fusaka_dict.get(f"{opcode}_SIZE", None)
    # 7904 repricings
    elif param == "num_rounds":
        return fusaka_dict.get(f"{opcode}_ROUNDS", None)
    elif param == "num_pairs":
        return fusaka_dict.get(f"{opcode}_PAIRS", None)
    elif param == "msg_size":
        return fusaka_dict.get(f"{opcode}_WORD", None)
    # For constant/main parameter, return the base cost
    elif param == "constant":
        return fusaka_dict.get(opcode, None)
    else:
        return None


def process_gas_bench_data(
    user: str,
    password: str,
    start_date: str,
    db_name: str,
    opcodes_sample: List[str] = None,
) -> pd.DataFrame:
    gas_bench_db_url = (
        f"postgresql://{user}:{password}@perfnet.core.nethermind.dev:5432/monitoring"
    )
    query_str = f"""
    SELECT 
        test_title,
        client_name,
        raw_run_duration_ms AS run_duration_ms,
        ingestion_timestamp
    FROM {db_name}
    WHERE ingestion_timestamp >= '{start_date}'::timestamp
    AND raw_run_duration_ms > 0
    """
    engine = create_engine(gas_bench_db_url)
    df = pd.read_sql(query_str, con=engine)
    # Fix client names
    df["client_name"] = df["client_name"].str.replace(
        "_repricings_stateful_mainnet", ""
    )
    df["client_name"] = df["client_name"].str.replace("_repricings_compute_mainnet", "")
    # Process title column
    df = process_test_title_col(df)
    # filter opcodes in sample
    if opcodes_sample is not None:
        df = df[df["test_opcode"].isin(opcodes_sample)]
    # Query trace data
    trace_df = process_test_trace_data(user, password, db_name, opcodes_sample)
    df = df.merge(trace_df[["test_title", "opcount"]], on="test_title", how="left")
    return df, trace_df


def process_test_title_col(prev_df: pd.DataFrame) -> pd.DataFrame:
    df = prev_df.copy()
    # Process test file and name
    df["test_file"] = df["test_title"].str.split(".py").str[0]
    df["test_name"] = df["test_title"].str.split(".py__").str[1].str.split("[").str[0]
    # Process opcode name
    df["test_opcode"] = np.where(
        df["test_name"].isin(OPCODES_IN_TEST_NAME_LIST),
        df["test_name"].str.split("_").str[1].str.upper(),
        None,
    )
    mask = (~df["test_name"].isin(OPCODES_IN_TEST_NAME_LIST)) & (
        df["test_title"].str.contains("opcode_")
    )
    df.loc[mask, "test_opcode"] = (
        df.loc[mask, "test_title"].str.split("opcode_").str[1].str.split("-").str[0]
    )
    df["test_opcode"] = df["test_opcode"].str.split("]").str[0]
    # Process params
    bench_mask = df["test_title"].str.contains("benchmark_test-")
    df.loc[bench_mask, "test_params"] = (
        df.loc[bench_mask, "test_title"]
        .str.split("[")
        .str[1]
        .str.split("]")
        .str[0]
        .str.split("benchmark_test-")
        .str[1]
    )
    engine_mask = df["test_title"].str.contains("blockchain_test-")
    df.loc[engine_mask, "test_params"] = (
        df.loc[engine_mask, "test_title"]
        .str.split("[")
        .str[1]
        .str.split("]")
        .str[0]
        .str.split("blockchain_test-")
        .str[1]
    )
    df.loc[bench_mask, "block_limit_million"] = (
        df.loc[bench_mask, "test_params"]
        .str.split("benchmark_")
        .str[1]
        .str.split("-")
        .str[0]
        .str.replace("M", "")
    )
    df["test_params"] = (
        df["test_params"]
        .str.split("-")
        .apply(
            lambda x: (
                [
                    item
                    for item in x
                    if item[:6] not in ["opcode", "opcoun", "", "benchm"]
                ]
                if isinstance(x, list)
                else []
            )
        )
        .apply(lambda x: "-".join(x) if isinstance(x, list) else np.nan)
    )
    # Format alt_bn precompiles
    df["test_opcode"] = np.where(
        (df["test_name"] == "test_alt_bn128") & (df["test_params"].str.contains("add")),
        "ECADD",
        df["test_opcode"],
    )
    df["test_opcode"] = np.where(
        (df["test_name"] == "test_alt_bn128") & (df["test_params"].str.contains("mul")),
        "ECMUL",
        df["test_opcode"],
    )
    df["test_opcode"] = np.where(
        (df["test_name"] == "test_alt_bn128_benchmark")
        & (df["test_params"].str.contains("num_pairs")),
        "ECPAIRING",
        df["test_opcode"],
    )
    # Format BLS12 precompiles
    df["test_opcode"] = np.where(
        df["test_name"] == "test_bls12_381",
        df["test_params"].str.split("-").str[0].str.upper(),
        df["test_opcode"],
    )
    df["test_opcode"] = np.where(
        df["test_name"] == "test_bls12_g1_msm",
        "BLS12_G1MSM",
        df["test_opcode"],
    )
    df["test_opcode"] = np.where(
        df["test_name"] == "test_bls12_g2_msm",
        "BLS12_G2MSM",
        df["test_opcode"],
    )
    df["test_opcode"] = np.where(
        df["test_name"] == "test_bls12_pairing",
        "BLS12_PAIRING_CHECK",
        df["test_opcode"],
    )
    # Fixed misnamed operations
    df["test_opcode"] = np.where(
        df["test_opcode"] == "JUMPDESTS", "JUMPDEST", df["test_opcode"]
    )
    df["test_opcode"] = np.where(
        df["test_opcode"] == "KECCAK", "KECCAK256", df["test_opcode"]
    )
    df["test_opcode"] = np.where(
        df["test_opcode"] == "RIPEMD160", "RIPEMD-160", df["test_opcode"]
    )
    df["test_opcode"] = np.where(
        df["test_opcode"] == "SHA256", "SHA2-256", df["test_opcode"]
    )
    df["test_opcode"] = np.where(
        df["test_opcode"] == "POINT", "POINT_EVALUATION", df["test_opcode"]
    )
    df["test_opcode"] = np.where(
        df["test_opcode"] == "BLS12_FP_TO_G1", "BLS12_MAP_FP_TO_G1", df["test_opcode"]
    )
    df["test_opcode"] = np.where(
        df["test_opcode"] == "BLS12_FP_TO_G2", "BLS12_MAP_FP2_TO_G2", df["test_opcode"]
    )
    df = process_storage_params(df)
    df = process_account_params(df)
    return df


def process_storage_params(prev_df: pd.DataFrame) -> pd.DataFrame:
    df = prev_df.copy()
    # Set test_opcode for bloatnet storage tests not handled by process_test_title_col
    df["test_opcode"] = np.where(
        df["test_name"] == "test_storage_sload_benchmark", "SLOAD", df["test_opcode"]
    )
    df["test_opcode"] = np.where(
        df["test_name"] == "test_storage_sload_same_key_benchmark",
        "SLOAD",
        df["test_opcode"],
    )
    df["test_opcode"] = np.where(
        df["test_name"].str.contains("test_storage_access"),
        df["test_params"].str.split(" ").str[0].str.upper(),
        df["test_opcode"],
    )
    df["test_opcode"] = np.where(
        df["test_opcode"].str.contains("SSTORE_"),
        df["test_opcode"].str.split("_").str[0],
        df["test_opcode"],
    )
    # Initialize intermediate columns as NaN
    storage_mask = df["test_opcode"].isin(["SLOAD", "SSTORE"])
    for col in ["_cold", "_new", "_update", "_pre_read"]:
        df[col] = np.nan
    df["_storage_size"] = pd.Series(np.nan, index=df.index, dtype="object")
    # --- 1. test_storage_access_cold_benchmark / test_storage_access_warm_benchmark ---
    access_mask = df["test_name"].str.contains("test_storage_access", na=False)
    df.loc[access_mask, "_cold"] = np.where(
        df.loc[access_mask, "test_name"].str.contains("cold"), 1, 0
    )
    df.loc[access_mask, "_new"] = 1  # always new slots
    df.loc[access_mask, "_storage_size"] = 0.0  # always zero storage
    # "SSTORE_same" / "SSTORE same value" → update 0; "SSTORE_new" / "SSTORE new value" → update 1
    sstore_access = access_mask & (df["test_opcode"] == "SSTORE")
    df.loc[sstore_access, "_update"] = np.where(
        df.loc[sstore_access, "test_title"].str.contains("same", case=False), 0, 1
    )
    # --- 2. test_sload_empty_erc20_balanceof ---
    erc20_sload = df["test_name"] == "test_sload_empty_erc20_balanceof"
    df.loc[erc20_sload, "_cold"] = 1
    df.loc[erc20_sload, "_new"] = 1
    _token_to_int = {"IMT": 0.001, "USDC": 1.0, "XEN": 9.0, "30GB_ERC20": 30.0}
    df.loc[erc20_sload, "_storage_size"] = (
        df.loc[erc20_sload, "test_title"]
        .str.extract(r"token_name_(\w+)", expand=False)
        .map(_token_to_int)
    )
    # --- 3. test_sstore_erc20_approve ---
    erc20_sstore = df["test_name"] == "test_sstore_erc20_approve"
    df.loc[erc20_sstore, "_cold"] = 1
    df.loc[erc20_sstore, "_new"] = 1
    df.loc[erc20_sstore, "_update"] = 1
    df.loc[erc20_sstore, "_storage_size"] = (
        df.loc[erc20_sstore, "test_title"]
        .str.extract(r"token_name_(\w+)", expand=False)
        .map(_token_to_int)
    )
    # --- 4. test_sstore_variants --- (this one will be filtered...)
    variants = df["test_name"] == "test_sstore_variants"
    df.loc[variants, "_cold"] = np.where(
        df.loc[variants, "test_title"].str.contains("sloads_before_sstore_True"), 0, 1
    )
    # nonzero_to_* → existing slot (0); zero_to_* → new slot (1)
    df.loc[variants, "_new"] = np.where(
        df.loc[variants, "test_title"].str.contains("nonzero_to_"), 0, 1
    )
    # to_zero / to_same → no value change (0); to_nonzero / to_diff → value changes (1)
    df.loc[variants, "_update"] = np.where(
        df.loc[variants, "test_title"].str.contains("to_zero|to_same", regex=True), 0, 1
    )
    df.loc[variants, "_pre_read"] = np.where(
        df.loc[variants, "test_title"].str.contains("sloads_before_sstore_True"), 1, 0
    )
    # --- 5. test_storage_sload_benchmark --- (this one will be filtered...)
    sload_bench = df["test_name"] == "test_storage_sload_benchmark"
    df.loc[sload_bench, "_cold"] = np.where(
        df.loc[sload_bench, "test_title"].str.contains("access_warm_True"), 0, 1
    )
    df.loc[sload_bench, "_new"] = np.where(
        df.loc[sload_bench, "test_title"].str.contains("storage_keys_pre_set_True"),
        0,
        1,
    )
    # --- 6. test_storage_sload_same_key_benchmark ---
    same_key = df["test_name"] == "test_storage_sload_same_key_benchmark"
    df.loc[same_key, "_cold"] = 0  # always warm
    df.loc[same_key, "_new"] = np.where(
        df.loc[same_key, "test_title"].str.contains("storage_keys_pre_set_True"), 0, 1
    )
    df.loc[same_key, "_storage_size"] = 0.0  # always zero storage
    # --- Build test_params column ---
    df.loc[storage_mask, "test_params"] = df.loc[storage_mask].apply(
        _build_params, axis=1
    )
    # Drop intermediate columns
    df = df.drop(columns=["_cold", "_new", "_update", "_storage_size", "_pre_read"])
    return df


def _build_params(row):
    parts = []
    for field in ["_cold", "_new", "_update", "_storage_size", "_pre_read"]:
        val = row[field]
        if pd.notna(val):
            name = field.lstrip("_")
            if isinstance(val, float) and val == int(val):
                val = int(val)
            parts.append(f"{name}_{val}")
    return "-".join(parts) if parts else np.nan


def _remove_constant_params(params_str: str, constant_params: set) -> str:
    parts = params_str.split("-")
    filtered = [p for p in parts if p.rsplit("_", 1)[0] not in constant_params]
    return "-".join(filtered) if filtered else np.nan


def process_account_params(prev_df: pd.DataFrame) -> pd.DataFrame:
    df = prev_df.copy()
    account_opcodes = set(CALL + STATEFUL).difference(set(["SSTORE", "SLOAD"]))
    # warm / cold
    df["test_params"] = np.where(
        df["test_opcode"].isin(account_opcodes),
        df["test_params"].str.replace("access_warm_True", "cold_0"),
        df["test_params"],
    )
    df["test_params"] = np.where(
        df["test_opcode"].isin(account_opcodes),
        df["test_params"].str.replace("access_warm_False", "cold_1"),
        df["test_params"],
    )
    # Remove parameters that don't vary per opcode
    account_mask = df["test_opcode"].isin(account_opcodes)
    for opcode in df.loc[account_mask, "test_opcode"].unique():
        op_mask = df["test_opcode"] == opcode
        unique_params = df.loc[op_mask, "test_params"].dropna().unique()
        # Collect all values for each param name
        all_parts = {}
        for params_str in unique_params:
            for part in params_str.split("-"):
                name_value = part.rsplit("_", 1)
                if len(name_value) == 2:
                    name, value = name_value
                    all_parts.setdefault(name, set()).add(value)
        # Find params where only one value exists across all configs
        constant_params = {
            name for name, values in all_parts.items() if len(values) == 1
        }
        if constant_params:
            df.loc[op_mask, "test_params"] = df.loc[op_mask, "test_params"].apply(
                lambda x, cp=constant_params: (
                    _remove_constant_params(x, cp) if pd.notna(x) else x
                )
            )
    return df


def process_test_trace_data(
    user: str, password: str, db_name: str, opcodes_sample: List[str] = None
) -> pd.DataFrame:
    gas_bench_db_url = (
        f"postgresql://{user}:{password}@perfnet.core.nethermind.dev:5432/monitoring"
    )
    db_name_full = "repricings_" + db_name + "_metadata"
    # Query traces
    trace_query_str = f"""
    SELECT test_name as test_title, opcodes as traces
    FROM {db_name_full}
    """
    engine = create_engine(gas_bench_db_url)
    trace_df = pd.read_sql(trace_query_str, con=engine)
    traces_expanded = pd.json_normalize(trace_df["traces"])
    trace_df = pd.concat([trace_df.drop(columns=["traces"]), traces_expanded], axis=1)
    trace_df = process_test_title_col(trace_df)
    trace_df = add_opcount_col(trace_df)
    if opcodes_sample is not None:
        trace_df = trace_df[trace_df["test_opcode"].isin(opcodes_sample)]
    return trace_df


def add_opcount_col(trace_df: pd.DataFrame) -> pd.DataFrame:
    new_trace_df = trace_df.copy()
    new_trace_df["opcount"] = new_trace_df.apply(
        lambda row: (
            row["STATICCALL"]
            if row["test_opcode"] in PRECOMPILES
            else row.get(row["test_opcode"])
        ),
        axis=1,
    )
    return new_trace_df
