import re
import sys
import math
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import create_engine
from tqdm import tqdm

sys.path.append(str(Path(__file__).parent))
from operation_gas_costs import get_fusaka_dict
from operation_types import PRECOMPILES, CALL, STATEFUL


BENCHMARKOOR_BASE_URL = (
    "https://benchmarkoor-api.core.ethpandaops.io/api/v1/index/query"
)

opcodes_file_name = Path(__file__).parent.joinpath("opcodes_in_test_name.txt")
with open(opcodes_file_name, "r") as f:
    OPCODES_IN_TEST_NAME_LIST = [line.strip() for line in f.readlines()]


def extract_param_values(params_str: str, param_name: str):
    if not isinstance(params_str, str):
        return np.nan
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
    # 7904 repricings
    if param == "num_rounds":
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


def _query_gas_bench(
    user: str,
    password: str,
    db_name: str,
    start_date: str,
) -> pd.DataFrame:
    print("Querying gas benchmark database....")
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
    df["ingestion_timestamp"] = pd.to_datetime(df["ingestion_timestamp"])
    return df


def _get_benchmarkoor_session(bearer_token: str, count_exact: bool = False):
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=2, status_forcelist=[502, 503, 524])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update(
        {
            "Authorization": f"Bearer {bearer_token}",
        }
    )
    if count_exact:
        session.headers.update(
            {
                "Prefer": "count=exact",
            }
        )
    return session


def _get_latest_benchmarkoor_suite_hash(
    bearer_token: str,
    network: str,
    test_type: str,
    page_size: int,
) -> str:
    session = _get_benchmarkoor_session(bearer_token)
    # Resolve network + test_type to a suite_hash
    response = session.get(
        f"{BENCHMARKOOR_BASE_URL}/suites",
        params={"discovery_path": "eq.repricings/results", "limit": page_size},
    )
    response.raise_for_status()
    suites_df = pd.DataFrame(response.json()["data"])
    if suites_df.empty:
        raise ValueError(f"No suite found for network={network}, test_type={test_type}")
    # Filter weird compute run...
    suites_df = suites_df[suites_df["suite_hash"] != "d74b491048b10299"]
    # TODO: should remove this filter eventually...
    parsed = suites_df["name"].str.extract(r"^(.+)-(\d+)-([^-]+)$")
    suites_df["network"] = parsed[0].str.replace("-", "_")
    suites_df["test_type"] = parsed[2]
    suites_df["indexed_at"] = pd.to_datetime(suites_df["indexed_at"])
    suites_df = suites_df.loc[
        suites_df.groupby(["network", "test_type"])["indexed_at"].idxmax()
    ]
    suite_row = suites_df[
        (suites_df["network"] == network) & (suites_df["test_type"] == test_type)
    ]
    if suite_row.empty:
        raise ValueError(f"No suite found for network={network}, test_type={test_type}")
    suite_hash = suite_row.iloc[0]["suite_hash"]
    return suite_hash


def _get_benchmarkoor_total_pages(
    bearer_token: str, page_size: int, params: Dict[str, str]
):
    session = _get_benchmarkoor_session(bearer_token, count_exact=True)
    response = session.get(
        f"{BENCHMARKOOR_BASE_URL}/test_stats", params={**params, "limit": 0}
    )
    response.raise_for_status()
    total = response.json()["total"]
    total_pages = math.ceil(total / page_size)
    return total_pages


def _query_benchmarkoor(
    bearer_token: str,
    network: str,
    test_type: str,
    start_date: str,
    page_size: int = 10_000,
    max_workers: int = 5,
) -> pd.DataFrame:
    print("Querying benchmarkoor database....")
    suite_hash = _get_latest_benchmarkoor_suite_hash(
        bearer_token, network, test_type, page_size
    )
    # Query test stats
    params = {
        "select": "test_name,client,test_time_ns,run_start",
        "test_time_ns": "gt.0",
        "suite_hash": f"eq.{suite_hash}",
    }
    if start_date is not None:
        start_ts = int(pd.Timestamp(start_date).timestamp())
        params["run_start"] = f"gt.{start_ts}"
    total_pages = _get_benchmarkoor_total_pages(bearer_token, page_size, params)
    session = _get_benchmarkoor_session(bearer_token)

    def fetch_page(page):
        paginated_params = {**params, "limit": page_size, "offset": page * page_size}
        resp = session.get(
            f"{BENCHMARKOOR_BASE_URL}/test_stats", params=paginated_params
        )
        resp.raise_for_status()
        return page, resp.json()["data"]

    all_data = [None] * total_pages
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_page, page): page for page in range(total_pages)
        }
        for future in tqdm(
            as_completed(futures), total=total_pages, desc="Fetching test_stats"
        ):
            page, data = future.result()
            all_data[page] = data

    df = pd.DataFrame([row for page_data in all_data for row in page_data])
    df["run_duration_ms"] = df["test_time_ns"] / 1_000_000
    df = df.drop(columns=["test_time_ns"])
    df = df.rename(
        columns={
            "client": "client_name",
            "test_name": "test_title",
            "run_start": "ingestion_timestamp",
        }
    )
    df["ingestion_timestamp"] = pd.to_datetime(df["ingestion_timestamp"], unit="s")
    df["test_title"] = df["test_title"].str.replace(".txt", "")
    return df


def process_gas_bench_data(
    network: str,
    test_type: str,
    start_date: str,
    source: str = "gas_bench",
    opcodes_sample: List[str] = None,
    user: str = None,
    password: str = None,
    bearer_token: str = None,
) -> pd.DataFrame:
    db_name = f"{test_type}_{network}"
    if source == "gas_bench":
        df = _query_gas_bench(user, password, db_name, start_date)
    elif source == "benchmarkoor":
        df = _query_benchmarkoor(bearer_token, network, test_type, start_date)
    else:
        raise ValueError(
            f"Unknown source: {source!r}. Must be 'gas_bench' or 'benchmarkoor'."
        )
    # Fix client names
    df["client_name"] = df["client_name"].str.replace(
        "_repricings_stateful_mainnet", ""
    )
    df["client_name"] = df["client_name"].str.replace("_repricings_compute_mainnet", "")
    # Process title column
    df = process_test_title_col(df)
    # Filter opcodes in sample
    if opcodes_sample is not None:
        df = df[df["test_opcode"].isin(opcodes_sample)]
    # Query trace data from gas_bench (always)
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
    # Process general params
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
    df = process_compute_params(df)
    df = process_stateful_params(df)
    return df


def process_compute_params(prev_df: pd.DataFrame) -> pd.DataFrame:
    df = prev_df.copy()
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
    return df


def process_stateful_params(prev_df: pd.DataFrame) -> pd.DataFrame:
    df = prev_df.copy()
    # Set test_opcode for bloatnet storage tests not handled by process_test_title_col
    df["test_opcode"] = np.where(
        df["test_name"] == "test_sload_erc20_balanceof", "SLOAD", df["test_opcode"]
    )
    df["test_opcode"] = np.where(
        df["test_name"] == "test_sstore_erc20_mint", "SSTORE", df["test_opcode"]
    )
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
    # Set update param
    sstore_mint_mask = df["test_name"] == "test_sstore_erc20_mint"
    df.loc[sstore_mint_mask, "test_params"] = df.loc[
        sstore_mint_mask, "test_params"
    ].str.replace("no_change_False", "update_1")
    df.loc[sstore_mint_mask, "test_params"] = df.loc[
        sstore_mint_mask, "test_params"
    ].str.replace("no_change_True", "update_0")
    sstore_app_mask = df["test_name"] == "test_sstore_erc20_approve"
    df.loc[sstore_app_mask, "test_params"] = df.loc[
        sstore_app_mask, "test_params"
    ].str.replace("write_new_value_True", "update_1")
    df.loc[sstore_app_mask, "test_params"] = df.loc[
        sstore_app_mask, "test_params"
    ].str.replace("write_new_value_False", "update_0")
    account_mask = df["test_name"] == "test_account_access"
    df.loc[account_mask, "test_params"] = df.loc[
        account_mask, "test_params"
    ].str.replace("value_sent_1", "update_1")
    df.loc[account_mask, "test_params"] = df.loc[
        account_mask, "test_params"
    ].str.replace("value_sent_0", "update_0")
    # Fix existing_slots param in test_sstore_erc20_approve
    df.loc[sstore_app_mask, "test_params"] = df.loc[
        sstore_app_mask, "test_params"
    ].str.replace("existing_slot", "existing_slots")
    # Add new columns and remove from params 
    for new_col in ["cache_strategy", "account_mode", "token_name", "existing_slots"]:
        df[new_col] = df["test_params"].str.extract(rf"{new_col}.([^-]+)")
        df["test_params"] = df["test_params"].str.replace(
            rf"{new_col}_[^-]+-|-{new_col}_[^-]+|{new_col}_[^-]+",
            "",
            regex=True,
        )
    # Fix cache strategy and accoount_mode
    df["cache_strategy"] = df["cache_strategy"].str.replace("CacheStrategy.", "")
    df["account_mode"] = df["account_mode"].str.replace("AccountMode.", "")
    # existing_slots for test_storage_sload_same_key_benchmark
    df["existing_slots"] = np.where(
        df["test_name"] == "test_storage_sload_same_key_benchmark",
        np.where(
            df["test_params"].str.contains("storage_keys_pre_set_True"), True, False
        ),
        df["existing_slots"],  # preserve extracted value for other test names
    )
    df["test_params"] = np.where(
        df["test_name"] == "test_storage_sload_same_key_benchmark",
        df["test_params"].str.replace("storage_keys_pre_set_True", ""),
        df["test_params"],
    )
    df["test_params"] = np.where(
        df["test_name"] == "test_storage_sload_same_key_benchmark",
        df["test_params"].str.replace("storage_keys_pre_set_False", ""),
        df["test_params"],
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
