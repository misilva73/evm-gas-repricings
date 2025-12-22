import os
import json
import datetime
import warnings
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
import matplotlib.pyplot as plt
from tqdm import tqdm
from typing import List, Any
from mdutils.mdutils import MdUtils
from sqlalchemy import create_engine

# Suppress statsmodels warnings
warnings.filterwarnings("ignore", module="statsmodels")


def process_gas_bench_data(
    user: str, password: str, start_date: str, end_date: str
) -> pd.DataFrame:
    file_dir = os.path.dirname(os.path.abspath(__file__))
    file_name = os.path.abspath(os.path.join(file_dir, "opcodes_in_test_name.txt"))
    with open(file_name, "r") as f:
        opcodes_in_test_name_list = [line.strip() for line in f.readlines()]
    gas_bench_db_url = (
        f"postgresql://{user}:{password}@perfnet.core.nethermind.dev:5432/monitoring"
    )
    query_str = f"""
    SELECT 
        test_title,
        client_name,
        raw_run_duration_ms AS run_duration_ms,
        opcount
    FROM repricings2
    WHERE ingestion_timestamp BETWEEN '{start_date}'::timestamp AND '{end_date}'::timestamp
    AND raw_run_duration_ms > 0
    """
    engine = create_engine(gas_bench_db_url)
    df = pd.read_sql(query_str, con=engine)
    df["test_file"] = (
        df["test_title"].str.replace("tests_benchmark_", "").str.split(".py").str[0]
    )
    df["test_name"] = df["test_title"].str.split(".py__").str[1].str.split("[").str[0]
    df["test_opcode"] = np.where(
        df["test_name"].isin(opcodes_in_test_name_list),
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
        .str.split("-")
        .apply(
            lambda x: (
                [item for item in x if item[:6] not in ["opcode", ""]]
                if isinstance(x, list)
                else []
            )
        )
    )
    df["test_params"] = np.where(
        df["test_params"].str.len() == 0, np.nan, df["test_params"]
    )
    df = df.drop(columns="test_title")
    return df


def estimate_opcode_run_times(
    gas_bench_df: pd.DataFrame, md_file: MdUtils, out_dir: str
) -> None:
    out_list = []
    # Simple opcodes (i.e. no inputs or params)
    file_dir = os.path.dirname(os.path.abspath(__file__))
    file_name = os.path.abspath(os.path.join(file_dir, "simple_opcodes.txt"))
    with open(file_name, "r") as f:
        simple_opcodes = [line.strip() for line in f.readlines()]
    for opcode in tqdm(simple_opcodes, desc="Estimating simple opcodes"):
        opcode_list = estimate_run_time_for_simple_opcode(
            gas_bench_df, opcode, md_file, out_dir
        )
        out_list.extend(opcode_list)
    # Create and save output dataframe
    out_df = pd.DataFrame(out_list)
    out_df.to_csv(os.path.join(out_dir, "results.csv"), index=False)


def estimate_run_time_for_simple_opcode(
    gas_bench_df: pd.DataFrame, opcode: str, md_file: MdUtils, out_dir: str
) -> List[dict[str, Any]]:
    md_file.new_header(level=1, title=opcode)
    clients = gas_bench_df["client_name"].unique().tolist()
    out_list = []
    for client in clients:
        md_file.new_header(level=2, title=f"{client}")
        # filter data and extract variables
        op_df = gas_bench_df[
            (gas_bench_df["client_name"] == client)
            & (gas_bench_df["test_opcode"] == opcode)
        ]
        X_df = op_df[["opcount"]]
        X_with_intercept_df = sm.add_constant(X_df)  # adds intercept
        y = op_df["run_duration_ms"]
        try:
            # Fit linear regression model using OLS
            model = sm.OLS(y, X_with_intercept_df)
            result = model.fit()
            intercept = result.params["const"]
            slope = result.params["opcount"]
            out_dict = {
                "opcode": opcode,
                "client": client,
                "intercept": intercept,
                "slope": slope,
                "type": "simple_opcode",
            }
            out_list.append(out_dict)
            # Add outputs in mardown report
            md_file.new_paragraph("```python")
            md_file.new_line(str(result.summary()))
            md_file.new_line("```")
            # Plot scatterplot with data
            fig = plt.figure(figsize=(10, 4))
            sns.scatterplot(data=op_df, x="opcount", y="run_duration_ms")
            # Plot OLS regression line
            X_range = np.linspace(op_df["opcount"].min(), op_df["opcount"].max(), 100)
            X_range_with_const = np.column_stack([np.ones(len(X_range)), X_range])
            y_pred = result.predict(X_range_with_const)
            plt.plot(
                X_range, y_pred, color="red", linewidth=2, label="OLS Regression line"
            )
            # Save plot
            fig.savefig(
                os.path.join(out_dir, "figs", f"{opcode}_{client}_regression.png"),
                dpi=144 * 3,
                bbox_inches="tight",
            )
            plt.close()
            # Add plot to markdown
            plt.title(
                f"Linear Regression for {opcode} opcode in {client} client\nIntercept: {intercept:.2f}, Slope: {slope:.2f}"
            )
            md_file.new_paragraph(
                f'<img src="./figs/{opcode}_{client}_regression.png" alt="{opcode}_{client}_regression" width="600"/>'
            )
            md_file.new_paragraph("")
        except Exception as e:
            md_file.new_line(f"OLS model did not run... Error: {str(e)}")
            md_file.new_line(f"")
    return out_list


if __name__ == "__main__":
    run_time = datetime.datetime.now()
    # Directories
    file_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.abspath(os.path.join(file_dir, ".."))
    out_dir = os.path.join(
        repo_dir,
        "reports",
        "opcode_run_times_estimation",
        "test",
        # run_time.strftime("%d-%m-%Y_%H:%M:%S"),
    )
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "figs"), exist_ok=True)
    # Secrets for acessing gas bench DB
    with open(os.path.join(repo_dir, "secrets.json"), "r") as file:
        secrets_dict = json.load(file)
    user = secrets_dict["gas_bench_username"]
    password = secrets_dict["gas_bench_password"]
    # Start and end data for querying
    start_date = "2025-12-19"
    end_date = "2025-12-20"
    # Query raw data and save
    gas_bench_df = process_gas_bench_data(user, password, start_date, end_date)
    outfile = os.path.join(out_dir, "gas_bench_data.csv")
    gas_bench_df.to_csv(outfile, index=False)
    # Start markdown report
    md_file = MdUtils(
        file_name=os.path.join(out_dir, "autogenerated_report"),
        title=f"Opcode run times estimation results",
    )
    md_file.new_header(level=1, title="Introduction", add_table_of_contents="n")
    md_file.new_paragraph(
        f"""
Description WIP
"""
    )
    estimate_opcode_run_times(gas_bench_df, md_file, out_dir)
    # Finish and save markdown file
    md_file.new_table_of_contents(depth=1)
    md_file.create_md_file()
