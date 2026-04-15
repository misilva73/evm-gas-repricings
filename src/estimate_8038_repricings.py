import os
import sys
import json
import datetime
import warnings
import pandas as pd
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore", module="statsmodels")
warnings.filterwarnings("ignore", message="Tight layout not applied")
warnings.filterwarnings("ignore", message="invalid value encountered in divide")
warnings.filterwarnings("ignore", message="The values in the array are unorderable")
pd.options.mode.chained_assignment = None


sys.path.append(str(Path(__file__).parent))
import operation_types
from data import process_bench_data
from reports import generate_state_access_repricings_report, generate_runtime_report
from glue import generate_glue_opcode_report

PARAMS = ["update"]

MODEL_BY = [
    "cache_strategy",
    "account_mode",
    "existing_slots",
]

if __name__ == "__main__":
    run_time = datetime.datetime.now()
    # Start date for querying
    start_date = "2026-03-01"
    # fork - osaka, amsterdam or None
    fork = "osaka"
    # Anchor rate for repricings
    anchor_rate = 60 * 1e6
    # target storage size
    target_token = "10GB"
    # Directories
    file_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.abspath(os.path.join(file_dir, ".."))
    out_dir = os.path.join(
        repo_dir,
        "reports",
        "eip-8038",
        "runtime_estimation",
        f"{start_date}_{run_time.strftime('%Y-%m-%d')}",
    )
    os.makedirs(os.path.join(out_dir, "figs"), exist_ok=True)
    # Secrets for acessing gas bench DB
    with open(os.path.join(repo_dir, "secrets.json"), "r") as file:
        secrets_dict = json.load(file)
    user = secrets_dict["gas_bench_username"]
    password = secrets_dict["gas_bench_password"]
    bearer_token = secrets_dict["benchmarkoor_bearer_token"]
    # Query raw data and save
    state_gas_bench_df, state_trace_df = process_bench_data(
        network="perf_devnet_3",
        test_type="stateful",
        start_date=start_date,
        fork=fork,
        bearer_token=bearer_token,
    )
    state_tests = [
        "test_storage_sload_same_key_benchmark",
        "test_sload_bloated",
        "test_sstore_bloated",
        "test_ext_account_query_warm",
        "test_account_access",
    ]
    filtered_state_gas_bench_df = state_gas_bench_df[
        state_gas_bench_df["test_name"].isin(state_tests)
    ]
    filtered_state_trace_df = state_trace_df[
        state_trace_df["test_name"].isin(state_tests)
    ]
    compute_gas_bench_df, compute_trace_df = process_bench_data(
        network="mainnet",
        test_type="compute",
        start_date=start_date,
        fork=fork,
        bearer_token=bearer_token,
    )
    filtered_compute_gas_bench_df = compute_gas_bench_df[
        ~compute_gas_bench_df["test_opcode"].isin(
            operation_types.STATEFUL + operation_types.CALL
        )
    ]
    filtered_compute_trace_df = compute_trace_df[
        ~compute_trace_df["test_opcode"].isin(
            operation_types.STATEFUL + operation_types.CALL
        )
    ]
    gas_bench_df = pd.concat(
        [filtered_compute_gas_bench_df, filtered_state_gas_bench_df], ignore_index=True
    )
    outfile = os.path.join(out_dir, f"gas_bench_data.csv")
    gas_bench_df.to_csv(outfile, index=False)
    trace_df = pd.concat(
        [filtered_compute_trace_df, filtered_state_trace_df], ignore_index=True
    )
    outfile = os.path.join(out_dir, f"trace_data.csv")
    trace_df.to_csv(outfile, index=False)
    # Run estimations and generate reports
    generate_runtime_report(
        start_date=start_date,
        end_date=run_time.strftime("%Y-%m-%d"),
        eip_number=8038,
        gas_bench_df=gas_bench_df[
            (gas_bench_df["token_name"] == target_token)
            | (gas_bench_df["token_name"].isna())
        ],
        out_dir=out_dir,
        params=PARAMS,
        operations=operation_types.STATEFUL + operation_types.CALL,
        group_by=["client_name", "test_name"] + MODEL_BY,
    )
    generate_glue_opcode_report(
        start_date=start_date,
        end_date=run_time.strftime("%Y-%m-%d"),
        eip_number=8038,
        gas_bench_df=gas_bench_df[
            (gas_bench_df["token_name"] == target_token)
            | (gas_bench_df["token_name"].isna())
        ],
        trace_df=trace_df[
            (trace_df["token_name"] == target_token) | (trace_df["token_name"].isna())
        ],
        out_dir=out_dir,
        target_opcodes=operation_types.STATEFUL + operation_types.CALL,
        glue_group_by=MODEL_BY,
    )
    generate_state_access_repricings_report(
        start_date=start_date,
        end_date=run_time.strftime("%Y-%m-%d"),
        out_dir=out_dir,
        anchor_rate=anchor_rate,
        eip_number=8038,
        group_by=["client_name", "test_name"] + MODEL_BY,
    )
