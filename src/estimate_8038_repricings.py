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
pd.options.mode.chained_assignment = None


sys.path.append(str(Path(__file__).parent))
import operation_types
from data import process_gas_bench_data
from reports import generate_repricings_report, generate_runtime_report
from glue import generate_glue_opcode_report

PARAMS = [
    "new",
    "cold",
    "update",
    "storage_size",
    "mem_size",
    "code_size",
    "value_sent",
]

PARAM_MULTIPLIERS = {
    "code_size": 1 / 32.0,  # per word (32 bytes)
}


if __name__ == "__main__":
    run_time = datetime.datetime.now()
    # Start date for querying
    start_date = "2026-01-26"
    # Query source - benchmarkoor or gas_bench
    query_source = "benchmarkoor"
    # Anchor rate for repricings
    anchor_rate = 60 * 1e6
    # Directories
    file_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.abspath(os.path.join(file_dir, ".."))
    main_out_dir = os.path.join(
        repo_dir,
        "reports",
        "eip-8038",
        "runtime_estimation",
        f"{start_date}_{run_time.strftime('%Y-%m-%d')}_{query_source}",
    )
    # Secrets for acessing gas bench DB
    with open(os.path.join(repo_dir, "secrets.json"), "r") as file:
        secrets_dict = json.load(file)
    user = secrets_dict["gas_bench_username"]
    password = secrets_dict["gas_bench_password"]
    bearer_token=secrets_dict["benchmarkoor_bearer_token"]
    # Query raw data and save - bloatnet + mainnet
    for network in ["mainnet"]:
        out_dir = os.path.join(main_out_dir, network)
        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(os.path.join(out_dir, "figs"), exist_ok=True)
        # Query raw data and save
        compute_gas_bench_df, compute_trace_df = process_gas_bench_data(
            network=network,
            test_type="compute",
            start_date=start_date,
            source=query_source,
            user=user,
            password=password,
            bearer_token=bearer_token,
        )
        state_gas_bench_df, state_trace_df = process_gas_bench_data(
            network=network,
            test_type="stateful",
            start_date=start_date,
            source=query_source,
            user=user,
            password=password,
            bearer_token=bearer_token,
        )
        gas_bench_df = pd.concat(
            [compute_gas_bench_df, state_gas_bench_df], ignore_index=True
        )
        # Excluding some tests not relevant for repricings
        gas_bench_df = gas_bench_df[
            ~gas_bench_df["test_name"].isin(
                [
                    "test_mixed_sload_sstore",
                    "test_ext_account_query_warm",
                    "test_ext_account_query_cold",
                    "test_sstore_variants",
                    "test_storage_sload_benchmark",
                ]
            )
        ]
        gas_bench_df = gas_bench_df[
            ~(
                (gas_bench_df["test_opcode"] == "SLOAD")
                & (gas_bench_df["test_name"] == "test_storage_access_warm_benchmark")
            )
        ]
        outfile = os.path.join(out_dir, f"gas_bench_data.csv")
        gas_bench_df.to_csv(outfile, index=False)
        trace_df = pd.concat([compute_trace_df, state_trace_df], ignore_index=True)
        # Run estimations and generate reports
        generate_runtime_report(
            start_date=start_date,
            end_date=run_time.strftime("%Y-%m-%d"),
            eip_number=8038,
            gas_bench_df=gas_bench_df,
            out_dir=out_dir,
            params=PARAMS,
            variable_operations=operation_types.STATEFUL + operation_types.CALL,
        )
        generate_glue_opcode_report(
            start_date=start_date,
            end_date=run_time.strftime("%Y-%m-%d"),
            eip_number=8038,
            gas_bench_df=gas_bench_df,
            trace_df=trace_df,
            out_dir=out_dir,
            target_opcodes=operation_types.STATEFUL + operation_types.CALL,
        )
        generate_repricings_report(
            start_date=start_date,
            end_date=run_time.strftime("%Y-%m-%d"),
            out_dir=out_dir,
            anchor_rate=anchor_rate,
            eip_number=8038,
            params=PARAMS,
            params_multipliers=PARAM_MULTIPLIERS,
            target_operations=operation_types.STATEFUL + operation_types.CALL,
        )
