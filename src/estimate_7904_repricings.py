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
from reports import generate_repricings_report, generate_runtime_report
from glue import generate_glue_opcode_report


PARAMS = [
    "num_rounds",
    "num_pairs",
    "msg_size",
]

PARAM_MULTIPLIERS = {
    "msg_size": 1 / 32.0,  # per word (32 bytes)
}


if __name__ == "__main__":
    run_time = datetime.datetime.now()
    # Start date for querying
    start_date = "2026-03-24"
    # fork - osaka, amsterdam or None
    fork = "osaka"
    # run_type - None, full, nobatchio, or sequential
    run_type = None
    # Anchor rate for repricings
    anchor_rate = 150 * 1e6
    # Directories
    file_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.abspath(os.path.join(file_dir, ".."))
    out_dir = os.path.join(
        repo_dir,
        "reports",
        "eip-7904",
        "runtime_estimation",
        f"{start_date}_{run_time.strftime('%Y-%m-%d')}",
    )
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "figs"), exist_ok=True)
    # Secrets for acessing gas bench DB
    with open(os.path.join(repo_dir, "secrets.json"), "r") as file:
        secrets_dict = json.load(file)
    user = secrets_dict["gas_bench_username"]
    password = secrets_dict["gas_bench_password"]
    bearer_token=secrets_dict["benchmarkoor_bearer_token"]
    # Query raw data and save
    compute_gas_bench_df, compute_trace_df = process_bench_data(
        network="mainnet",
        test_type="compute",
        start_date=start_date,
        fork=fork,
        bearer_token=bearer_token,
        run_type=run_type,
    )
    state_gas_bench_df, state_trace_df = process_bench_data(
        network="mainnet",
        test_type="stateful",
        start_date=start_date,
        fork=fork,
        bearer_token=bearer_token,
        run_type=run_type,
    )
    gas_bench_df = pd.concat(
        [compute_gas_bench_df, state_gas_bench_df], ignore_index=True
    )
    # Filter MOD, SMOD, ADDMOD and MULMOD fast tests
    gas_bench_df = gas_bench_df[
        ~(
            (gas_bench_df["test_opcode"].isin(["ADDMOD", "MULMOD", "MOD", "SMOD"]))
            & (gas_bench_df["test_name"] == "test_arithmetic")
        )
    ]
    # Filter bn128_add_infinities test config -> it is not the worse case for this opcode!
    gas_bench_df = gas_bench_df[gas_bench_df["test_params"] != "bn128_add_infinities"]
    # Save data
    outfile = os.path.join(out_dir, "gas_bench_data.csv")
    gas_bench_df.to_csv(outfile, index=False)
    trace_df = pd.concat([compute_trace_df, state_trace_df], ignore_index=True)
    outfile = os.path.join(out_dir, f"trace_data.csv")
    trace_df.to_csv(outfile, index=False)
    # Run estimations and generate reports
    generate_runtime_report(
        start_date=start_date,
        end_date=run_time.strftime("%Y-%m-%d"),
        eip_number=7904,
        gas_bench_df=gas_bench_df,
        out_dir=out_dir,
        params=PARAMS,
        operations=operation_types.SIMPLE_EIP_7904+operation_types.VARIABLE_EIP_7904,
    )
    generate_glue_opcode_report(
        start_date=start_date,
        end_date=run_time.strftime("%Y-%m-%d"),
        eip_number=7904,
        gas_bench_df=gas_bench_df,
        trace_df=trace_df,
        out_dir=out_dir,
        target_opcodes=operation_types.SIMPLE_EIP_7904
        + operation_types.VARIABLE_EIP_7904,
    )
    generate_repricings_report(
        start_date=start_date,
        end_date=run_time.strftime("%Y-%m-%d"),
        out_dir=out_dir,
        anchor_rate=anchor_rate,
        eip_number=7904,
        params=PARAMS,
        params_multipliers=PARAM_MULTIPLIERS,
        target_operations=operation_types.SIMPLE_EIP_7904
        + operation_types.VARIABLE_EIP_7904,
    )
