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

PARAMS = [
    "new",
    "cold",
    # "update"
]

PARAM_MULTIPLIERS = {}


if __name__ == "__main__":
    run_time = datetime.datetime.now()
    # Start date for querying
    start_date = "2026-01-26"
    # Anchor rate for repricings
    anchor_rate = 60 * 1e6
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
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "figs"), exist_ok=True)
    # Secrets for acessing gas bench DB
    with open(os.path.join(repo_dir, "secrets.json"), "r") as file:
        secrets_dict = json.load(file)
    user = secrets_dict["gas_bench_username"]
    password = secrets_dict["gas_bench_password"]
    # Query raw data and save
    gas_bench_df = process_gas_bench_data(
        user, password, start_date, operation_types.STATEFUL
    )
    outfile = os.path.join(out_dir, "gas_bench_data.csv")
    gas_bench_df.to_csv(outfile, index=False)
    # Run estimations and generate reports
    generate_runtime_report(
        start_date=start_date,
        end_date=run_time.strftime("%Y-%m-%d"),
        eip_number=8038,
        gas_bench_df=gas_bench_df,
        out_dir=out_dir,
        params=PARAMS,
        variable_operations=["SSTORE", "SLOAD"],
    )
    generate_repricings_report(
        start_date=start_date,
        end_date=run_time.strftime("%Y-%m-%d"),
        out_dir=out_dir,
        anchor_rate=anchor_rate,
        eip_number=8038,
        params=PARAMS,
        params_multipliers=PARAM_MULTIPLIERS,
    )
