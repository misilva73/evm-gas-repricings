import re
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List
from sqlalchemy import create_engine

sys.path.append(str(Path(__file__).parent))
from operation_gas_costs import get_fusaka_dict


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
    user: str, password: str, start_date: str, opcodes_sample: List[str] = None
) -> pd.DataFrame:
    gas_bench_db_url = (
        f"postgresql://{user}:{password}@perfnet.core.nethermind.dev:5432/monitoring"
    )
    query_str = f"""
    SELECT 
        test_title,
        client_name,
        raw_run_duration_ms AS run_duration_ms,
        opcount,
        ingestion_timestamp
    FROM repricings_new
    WHERE ingestion_timestamp >= '{start_date}'::timestamp
    AND raw_run_duration_ms > 0
    AND opcount > 0
    """
    engine = create_engine(gas_bench_db_url)
    df = pd.read_sql(query_str, con=engine)
    df = process_test_title_col(df)
    # df = df.drop(columns="test_title")
    # Filter bn128_add_infinities test config -> it is not the worse case for this opcode!
    # df = df[df["test_params"] != "bn128_add_infinities"]
    if opcodes_sample is not None:
        df = df[df["test_opcode"].isin(opcodes_sample)]
    return df


def process_test_title_col(prev_df: pd.DataFrame) -> pd.DataFrame:
    df = prev_df.copy()
    df["test_file"] = (
        df["test_title"].str.replace("tests_benchmark_", "").str.split(".py").str[0]
    )
    df["test_name"] = df["test_title"].str.split(".py__").str[1].str.split("[").str[0]
    df["test_opcode"] = np.where(
        df["test_name"].isin(OPCODES_IN_TEST_NAME_LIST),
        df["test_name"].str.split("_").str[1].str.upper(),
        df["test_title"].str.split("opcode_").str[1].str.split("-").str[0],
    )
    df["test_opcode"] = df["test_opcode"].str.split("]").str[0]
    df["test_params"] = (
        df["test_title"]
        .str.split("[")
        .str[1]
        .str.split("]")
        .str[0]
        .str.split("benchmark_test-")
        .str[1]
    )
    df["test_params"] = (
        df["test_params"]
        .str.split("-")
        .apply(
            lambda x: (
                [item for item in x if item[:6] not in ["opcode", "opcoun", ""]]
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
    # Format SSTORE and SLOAD
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
    df["test_opcode"] = np.where(
        df["test_opcode"] == "PREVRANDAO", "DIFFICULTY", df["test_opcode"]
    )
    # Cold/warm param addition
    df["extra_test_params"] = np.where(
        df["test_opcode"].isin(["SLOAD", "SSTORE"]),
        df["test_name"].apply(lambda x: "-cold_1" if "cold" in x else "-cold_0"),
        "",
    )
    df["test_params"] = df["test_params"] + df["extra_test_params"]
    # new slot param addition
    df["extra_test_params"] = np.where(
        df["test_opcode"] == "SSTORE",
        df["test_params"].apply(lambda x: "-new_1" if "new" in x else "-new_0"),
        "",
    )
    df["test_params"] = df["test_params"] + df["extra_test_params"]
    df = df.drop(columns=["extra_test_params"])
    # Remove sload and sstore from test params
    df["test_params"] = (
        df["test_params"]
        .str.split("-")
        .apply(
            lambda x: (
                [item for item in x if item[:5] not in ["SSTOR", "SLOAD"]]
                if isinstance(x, list)
                else []
            )
        )
        .apply(lambda x: "-".join(x) if isinstance(x, list) else np.nan)
    )
    return df


def process_test_trace_data(
    user: str, password: str, start_date: str, opcodes_sample: List[str]
) -> pd.DataFrame:
    gas_bench_db_url = (
        f"postgresql://{user}:{password}@perfnet.core.nethermind.dev:5432/monitoring"
    )
    # Query traces
    trace_query_str = f"""
    SELECT test_name as test_title, opcodes as traces
    FROM gas_limit_benchmarks_test_metadata
    """
    engine = create_engine(gas_bench_db_url)
    trace_df = pd.read_sql(trace_query_str, con=engine)
    trace_df = process_test_title_col(trace_df)
    traces_expanded = pd.json_normalize(trace_df["traces"])
    trace_df = pd.concat([trace_df.drop(columns=["traces"]), traces_expanded], axis=1)
    # Query test info
    test_query_str = f"""
    SELECT DISTINCT
        test_title,
        opcount
    FROM repricings_new
    WHERE ingestion_timestamp >= '{start_date}'::timestamp
    AND raw_run_duration_ms > 0
    AND opcount > 0
    """
    engine = create_engine(gas_bench_db_url)
    test_df = pd.read_sql(test_query_str, con=engine)
    # Join data
    df = test_df.merge(trace_df, on="test_title", how="left")
    df = df[df["test_opcode"].isin(opcodes_sample)]
    return df
