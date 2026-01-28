import re
import numpy as np
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine


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


def process_gas_bench_data(user: str, password: str, start_date: str) -> pd.DataFrame:
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
    AND opcount >= 0
    """
    engine = create_engine(gas_bench_db_url)
    df = pd.read_sql(query_str, con=engine)
    df = process_test_title_col(df)
    df = df.drop(columns="test_title")
    # Filter bn128_add_infinities test config -> it is not the worse case for this opcode!
    df = df[df["test_params"] != "bn128_add_infinities"]
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
        df["test_name"] == "test_storage_access_warm_benchmark",
        df["test_params"].str.split(" ").str[0].str.upper(),
        df["test_opcode"],
    )
    df["test_opcode"] = np.where(
        df["test_name"] == "test_storage_access_cold_benchmark",
        df["test_params"].str.split("_").str[0].str.upper(),
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
    return df


def process_test_trace_data(user: str, password: str) -> pd.DataFrame:
    gas_bench_db_url = (
        f"postgresql://{user}:{password}@perfnet.core.nethermind.dev:5432/monitoring"
    )
    query_str = f"""
    SELECT test_name as test_title, opcodes as traces
    FROM gas_limit_benchmarks_test_metadata
    """
    engine = create_engine(gas_bench_db_url)
    trace_df = pd.read_sql(query_str, con=engine)
    trace_df = process_test_title_col(trace_df)
    traces_expanded = pd.json_normalize(trace_df["traces"])
    trace_df = pd.concat([trace_df.drop(columns=["traces"]), traces_expanded], axis=1)
    trace_df = trace_df.drop(columns="test_title")
    return trace_df
