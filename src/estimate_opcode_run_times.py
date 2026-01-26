import os
import re
import sys
import json
import datetime
import warnings
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
import matplotlib.pyplot as plt
from scipy.stats import probplot, zscore
from tqdm import tqdm
from pathlib import Path
from typing import List, Any
from mdutils.mdutils import MdUtils
from sqlalchemy import create_engine

# Suppress warnings
warnings.filterwarnings("ignore", module="statsmodels")
warnings.filterwarnings("ignore", message="Tight layout not applied")
pd.options.mode.chained_assignment = None


sys.path.append(str(Path(__file__).parent))
import operation_types

opcodes_file_name = Path(__file__).parent.joinpath("opcodes_in_test_name.txt")
with open(opcodes_file_name, "r") as f:
    OPCODES_IN_TEST_NAME_LIST = [line.strip() for line in f.readlines()]

MEMORY_PARAMS = [
    "calldata_size",
    "mem_size",
    "code_size",
    "msg_size",
    "copy_size",
    "return_size",
]

LOG_PARAMS = [
    "log_size",
    "mem_size",
]

PRECOMPILE_PARAMS = [
    "size",
    "num_rounds",
    "k",
    "num_pairs",
]

### Data processing ########################################################################


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
    df = df.drop(columns="test_title")
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
    # Filter bn128_add_infinities test config -> it is not the worse case for this opcode!
    df = df[df["test_params"] != "bn128_add_infinities"]
    return df


### General ploting ##################################################################


def create_and_save_1dim_regression_plot(
    op_df: pd.DataFrame,
    result: sm.regression.linear_model.RegressionResultsWrapper,
    opcode: str,
    client: str,
    out_dir: str,
) -> None:
    intercept = result.params["const"]
    slope = result.params["opcount"]
    # Plot scatterplot with data
    fig = plt.figure(figsize=(10, 4))
    sns.scatterplot(data=op_df, x="opcount", y="run_duration_ms")
    # Plot OLS regression line
    X_range = np.linspace(op_df["opcount"].min(), op_df["opcount"].max(), 100)
    X_range_with_const = np.column_stack([np.ones(len(X_range)), X_range])
    y_pred = result.predict(X_range_with_const)
    plt.plot(X_range, y_pred, color="red", linewidth=2, label="OLS Regression line")
    plt.xlabel("Opcode Count")
    plt.ylabel("Run Duration (ms)")
    plt.title(
        f"OLS Linear Regression for {opcode} in {client}\nIntercept: {intercept:.2f}, Slope: {slope:.2e}"
    )
    # Save plot
    fig.savefig(
        os.path.join(out_dir, "figs", f"{opcode}_{client}_regression.png"),
        dpi=144,
        bbox_inches="tight",
    )
    plt.close("all")


def create_and_save_multidim_regression_plot(
    op_df: pd.DataFrame,
    result: sm.regression.linear_model.RegressionResultsWrapper,
    opcode: str,
    client: str,
    out_dir: str,
    all_features: List[str],
) -> None:
    features = list(set(all_features).difference(set(["opcount"])))
    # Process regression features
    feature_df = op_df.copy()
    feature_df[features] = feature_df[features].astype(float)
    # Get regression slope and intercept
    intercept = result.params["const"]
    slope = result.params["opcount"]
    # Create grid plot
    fig, axes = plt.subplots(1, len(features), figsize=(4 * len(features), 4))
    for i, feature in enumerate(features):
        ax = axes[i] if len(features) > 1 else axes
        sns.lineplot(
            data=feature_df,
            x="opcount",
            y="run_duration_ms",
            hue=feature,
            ax=ax,
            errorbar="sd",
            palette="Set2",
        )
        ax.set_title(f"{feature}: {result.params[feature]:.2e}")
    plt.suptitle(
        f"Run duration vs opcount by feature ({opcode} - {client})\nIntercept: {intercept:.2f}, Slope: {slope:.2e}"
    )
    plt.tight_layout()
    # Save plot
    fig.savefig(
        os.path.join(out_dir, "figs", f"{opcode}_{client}_regression.png"),
        dpi=144,
        bbox_inches="tight",
    )
    plt.close("all")


def create_and_save_diagnostic_plots(
    result: sm.regression.linear_model.RegressionResultsWrapper,
    opcode: str,
    client: str,
    out_dir: str,
) -> None:
    # Calculate diagnostic values
    fitted_values = result.fittedvalues
    residuals = result.resid
    influence = result.get_influence()
    standardized_residuals = influence.resid_studentized_internal
    leverage = influence.hat_matrix_diag
    cooks_d = influence.cooks_distance[0]
    # Create 2x2 diagnostic plot panel
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    # Plot 1 (top-left): Residuals vs Fitted Values
    ax1 = axes[0, 0]
    sns.scatterplot(x=fitted_values, y=residuals, alpha=0.6, ax=ax1)
    ax1.axhline(y=0, color="red", linestyle="--", linewidth=1)
    sns.regplot(
        x=fitted_values,
        y=residuals,
        lowess=True,
        scatter=False,
        color="blue",
        ax=ax1,
        line_kws={"linewidth": 2},
    )
    ax1.set_xlabel("Fitted values")
    ax1.set_ylabel("Residuals")
    ax1.set_title("Residuals vs Fitted")
    ax1.grid(True, alpha=0.3)
    # Plot 2 (top-right): Q-Q Plot
    ax2 = axes[0, 1]
    probplot(residuals, dist="norm", plot=ax2)
    ax2.set_title("Normal Q-Q")
    ax2.set_xlabel("Theoretical Quantiles")
    ax2.set_ylabel("Sample Quantiles")
    ax2.grid(True, alpha=0.3)
    # Plot 3 (bottom-left): Scale-Location Plot
    ax3 = axes[1, 0]
    sqrt_abs_std_resid = np.sqrt(np.abs(standardized_residuals))
    sns.scatterplot(x=fitted_values, y=sqrt_abs_std_resid, alpha=0.6, ax=ax3)
    sns.regplot(
        x=fitted_values,
        y=sqrt_abs_std_resid,
        lowess=True,
        scatter=False,
        color="red",
        ax=ax3,
        line_kws={"linewidth": 2},
    )
    ax3.set_xlabel("Fitted values")
    ax3.set_ylabel("√|Standardized residuals|")
    ax3.set_title("Scale-Location")
    ax3.grid(True, alpha=0.3)
    # Plot 4 (bottom-right): Residuals vs Leverage
    ax4 = axes[1, 1]
    sns.scatterplot(x=leverage, y=standardized_residuals, alpha=0.6, ax=ax4)
    ax4.axhline(y=0, color="grey", linestyle="--", linewidth=0.8)
    # Add Cook's distance contours (optional - for points with high influence)
    # Highlight points with high Cook's distance (> 0.5)
    high_cooks_mask = cooks_d > 0.5
    if high_cooks_mask.any():
        high_leverage_idx = np.where(high_cooks_mask)[0]
        for idx in high_leverage_idx:
            ax4.annotate(
                f"{idx}",
                xy=(leverage[idx], standardized_residuals[idx]),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
            )
    ax4.set_xlabel("Leverage")
    ax4.set_ylabel("Standardized Residuals")
    ax4.set_title("Residuals vs Leverage")
    ax4.grid(True, alpha=0.3)
    # Add overall title
    plt.suptitle(f"Diagnostic Plots for {opcode} ({client})", fontsize=16, y=1.00)
    plt.tight_layout()
    # Save plot
    fig.savefig(
        os.path.join(out_dir, "figs", f"{opcode}_{client}_diagnostics.png"),
        dpi=144,
        bbox_inches="tight",
    )
    plt.close("all")


### OLS auxiliary functions ##############################################################


def fit_OLS(
    feature_df: pd.DataFrame, features: List[str]
) -> sm.regression.linear_model.RegressionResults:
    # Process variables
    X_df = feature_df[features].astype(float)
    X_with_intercept_df = sm.add_constant(X_df)  # adds intercept
    y = feature_df["run_duration_ms"].astype(float)
    # Fit OLS
    model = sm.OLS(y, X_with_intercept_df)
    result = model.fit()
    return result


def fit_OLS_without_low_diff_runs(
    op_df: pd.DataFrame, features: List[str]
) -> sm.regression.linear_model.RegressionResults:
    feature_df = op_df[features + ["run_duration_ms"]].dropna()
    result = fit_OLS(feature_df, features)
    # if we have a poor fit, try to remove runs with non-increasing runtimes
    if result.rsquared <= 0.5:
        filtered_op_df = find_low_diff_runs(op_df)
        filtered_feature_df = filtered_op_df[features + ["run_duration_ms"]].dropna()
        result_v2 = fit_OLS(filtered_feature_df, features)
        if result_v2.rsquared > 0.5:
            return result_v2
    # if we have a good fit or removing low diff runs does not help, return original model
    return result


def find_low_diff_runs(op_df: pd.DataFrame) -> pd.DataFrame:
    cols_zscore = ["test_file", "test_name", "test_params"]
    all_cols = cols_zscore + ["ingestion_timestamp"]
    # Compute average diff in runtime per run
    avg_diff_df = (
        op_df.sort_values("opcount")
        .groupby(all_cols)["run_duration_ms"]
        .apply(lambda x: x.diff().mean())
        .reset_index()
        .rename(columns={"run_duration_ms": "avg_diff"})
    )
    # Calculate z-scores on average diff
    avg_diff_df["z_score"] = avg_diff_df.groupby(cols_zscore)["avg_diff"].transform(
        lambda x: zscore(x, nan_policy="omit") if len(x) > 1 else 0
    )
    # Filter runs with low average diff (based on z-score)
    low_diff_runs = avg_diff_df[avg_diff_df["z_score"] < -1][
        "ingestion_timestamp"
    ].unique()
    filtered_op_df = op_df[~op_df["ingestion_timestamp"].isin(low_diff_runs)]
    return filtered_op_df


### Simple opcode analysis ################################################################


def generate_simple_opcode_report(gas_bench_df: pd.DataFrame, out_dir: str) -> None:
    # Start markdown report
    md_file = MdUtils(
        file_name=os.path.join(out_dir, "simple_opcode_autogenerated_report"),
        title=f"Opcode run times estimation results - Simple opcodes",
    )
    md_file.new_header(level=1, title="Introduction", add_table_of_contents="n")
    md_file.new_paragraph(
        f"""
This is an automated report generated from the opcode run times 
estimation script `./src/estimate_opcode_run_times.py`. The script 
uses data generated by running the 
[EEST benchmark suite](https://github.com/ethereum/execution-spec-tests/tree/main/tests/benchmark) 
with the [Nethermind benchmarking tooling](https://github.com/NethermindEth/gas-benchmarks).

The data includes all the simple opcode tests run between {start_date} and {run_time.strftime('%Y-%m-%d')}.

For each opcode and client, an OLS linear regression model is fitted to estimate the 
opcode run time as a function of the opcode count. The results are presented below.
"""
    )
    # Estimate run times for simple opcodes (i.e. no inputs or params)
    out_list = []
    simple_opcodes = operation_types.SIMPLE_COMPUTE
    for opcode in tqdm(simple_opcodes, desc="Estimating simple opcodes"):
        # Run estimation and add to report
        opcode_list = estimate_run_time_for_simple_operation(
            gas_bench_df, opcode, md_file, out_dir
        )
        out_list.extend(opcode_list)
    # Create and save output dataframe
    out_df = pd.DataFrame(out_list)
    out_df.to_csv(os.path.join(out_dir, "simple_opcodes_results.csv"), index=False)
    # Finish and save markdown file
    md_file.new_table_of_contents(depth=1)
    md_file.create_md_file()


def estimate_run_time_for_simple_operation(
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
        try:
            # Fit linear regression model using OLS
            result = fit_OLS_without_low_diff_runs(op_df, ["opcount"])
        except Exception as e:
            md_file.new_line(f"OLS model did not run... Error: {str(e)}")
            md_file.new_line(f"")
            continue
        intercept = result.params["const"]
        slope = result.params["opcount"]
        out_dict = {
            "opcode": opcode,
            "client": client,
            "nobs": result.nobs,
            "intercept": intercept,
            "intercept_pvalue": result.pvalues["const"],
            "rsquared": result.rsquared,
            "rsquared_adj": result.rsquared_adj,
            "slope": slope,
            "slope_pvalue": result.pvalues["opcount"],
            "slope_conf_int_low": result.conf_int().loc["opcount", 0],
            "slope_conf_int_high": result.conf_int().loc["opcount", 1],
        }
        out_list.append(out_dict)
        # Add outputs in mardown report
        md_file.new_paragraph("```python")
        md_file.new_line(str(result.summary()))
        md_file.new_line("```")
        # Create a save plots
        create_and_save_1dim_regression_plot(op_df, result, opcode, client, out_dir)
        create_and_save_diagnostic_plots(result, opcode, client, out_dir)
        # Add plots to markdown
        md_file.new_paragraph(
            f'<img src="./figs/{opcode}_{client}_regression.png" alt="{opcode}_{client}_regression" width="600"/>'
        )
        md_file.new_paragraph(
            f'<img src="./figs/{opcode}_{client}_diagnostics.png" alt="{opcode}_{client}_diagnostics" width="600"/>'
        )
        md_file.new_paragraph("")
    return out_list


### Non-simple opcode analysis ################################################################


def generate_non_simple_opcode_report(
    gas_bench_df: pd.DataFrame, out_dir: str, op_type: str
) -> None:
    # Start markdown report
    md_file = MdUtils(
        file_name=os.path.join(out_dir, f"{op_type}_opcode_autogenerated_report"),
        title=f"Opcode run times estimation results - {op_type} opcodes",
    )
    md_file.new_header(level=1, title="Introduction", add_table_of_contents="n")
    md_file.new_paragraph(
        f"""
This is an automated report generated from the opcode run times 
estimation script `./src/estimate_opcode_run_times.py`. The script 
uses data generated by running the 
[EEST benchmark suite](https://github.com/ethereum/execution-spec-tests/tree/main/tests/benchmark) 
with the [Nethermind benchmarking tooling](https://github.com/NethermindEth/gas-benchmarks).

The data includes all the {op_type} opcode tests run between {start_date} and {run_time.strftime('%Y-%m-%d')}.

For each opcode and client, an OLS linear regression model is fitted to estimate the 
opcode run time as a function of the opcode count and other opcode configurations. The results are presented below.
"""
    )
    # Process op_type
    if op_type == "memory":
        opcodes = operation_types.MEMORY_COMPUTE
        params = MEMORY_PARAMS
    elif op_type == "log":
        opcodes = operation_types.LOG
        params = LOG_PARAMS
    else:
        raise ValueError("op_type must be `memory` or `log`")

    # Estimate run times for variable opcodes (i.e. with inputs or params)
    out_list = []
    for opcode in tqdm(opcodes, desc=f"Estimating {op_type} opcodes"):
        # Run estimation and add to report
        opcode_list = estimate_run_time_for_non_simple_operation(
            gas_bench_df, opcode, md_file, out_dir, params
        )
        out_list.extend(opcode_list)
    # Create and save output dataframe
    out_df = pd.DataFrame(out_list)
    out_df.to_csv(os.path.join(out_dir, f"{op_type}_opcodes_results.csv"), index=False)
    # Finish and save markdown file
    md_file.new_table_of_contents(depth=1)
    md_file.create_md_file()


def estimate_run_time_for_non_simple_operation(
    gas_bench_df: pd.DataFrame,
    opcode: str,
    md_file: MdUtils,
    out_dir: str,
    params: List[str],
) -> List[dict[str, Any]]:
    md_file.new_header(level=1, title=opcode)
    clients = gas_bench_df["client_name"].unique().tolist()
    out_list = []
    for client in clients:
        md_file.new_header(level=2, title=f"{client}")
        # Filter data and extract variables
        op_df = gas_bench_df[
            (gas_bench_df["client_name"] == client)
            & (gas_bench_df["test_opcode"] == opcode)
        ]
        # Process opcode parameters
        for param in params:
            op_df[param] = op_df["test_params"].apply(
                lambda x: extract_param_values(x, param)
            )
        # Get feature matrix
        na_counts = op_df[params].isna().sum()
        features = ["opcount"] + na_counts[na_counts != len(op_df)].index.to_list()
        try:
            # Fit linear regression model using OLS
            result = fit_OLS_without_low_diff_runs(op_df, features)
        except Exception as e:
            md_file.new_line(f"OLS model did not run... Error: {str(e)}")
            md_file.new_line(f"")
            continue
        intercept = result.params["const"]
        slope = result.params["opcount"]
        out_dict = {
            "opcode": opcode,
            "client": client,
            "nobs": result.nobs,
            "intercept": intercept,
            "intercept_pvalue": result.pvalues["const"],
            "rsquared": result.rsquared,
            "rsquared_adj": result.rsquared_adj,
            "slope": slope,
            "slope_pvalue": result.pvalues["opcount"],
            "slope_conf_int_low": result.conf_int().loc["opcount", 0],
            "slope_conf_int_high": result.conf_int().loc["opcount", 1],
        }
        for param in params:
            if param in result.params:
                out_dict[param] = result.params[param]
                out_dict[param + "_pvalue"] = result.pvalues[param]
                out_dict[param + "_conf_int_low"] = result.conf_int().loc[param, 0]
                out_dict[param + "_conf_int_high"] = result.conf_int().loc[param, 1]
        out_list.append(out_dict)
        # Add outputs in mardown report
        md_file.new_paragraph("```python")
        md_file.new_line(str(result.summary()))
        md_file.new_line("```")
        # Create a save plots
        create_and_save_multidim_regression_plot(
            op_df, result, opcode, client, out_dir, features
        )
        create_and_save_diagnostic_plots(result, opcode, client, out_dir)
        # Add plots to markdown
        md_file.new_paragraph(
            f'<img src="./figs/{opcode}_{client}_regression.png" alt="{opcode}_{client}_regression" width="600"/>'
        )
        md_file.new_paragraph(
            f'<img src="./figs/{opcode}_{client}_diagnostics.png" alt="{opcode}_{client}_diagnostics" width="600"/>'
        )
        md_file.new_paragraph("")

    return out_list


### Precompiles analysis ##################################################################


def generate_precompiles_report(gas_bench_df: pd.DataFrame, out_dir: str) -> None:
    # Start markdown report
    md_file = MdUtils(
        file_name=os.path.join(out_dir, f"precompiles_autogenerated_report"),
        title="Opcode run times estimation results - Precompiles",
    )
    md_file.new_header(level=1, title="Introduction", add_table_of_contents="n")
    md_file.new_paragraph(
        f"""
This is an automated report generated from the opcode run times 
estimation script `./src/estimate_opcode_run_times.py`. The script 
uses data generated by running the 
[EEST benchmark suite](https://github.com/ethereum/execution-spec-tests/tree/main/tests/benchmark) 
with the [Nethermind benchmarking tooling](https://github.com/NethermindEth/gas-benchmarks).

The data includes all the precompile tests run between {start_date} and {run_time.strftime('%Y-%m-%d')}.

For each opcode and client, an OLS linear regression model is fitted to estimate the 
precompile run time as a function of the precompile count and other configurations. The results are presented below.

Everytime the report references "opcode", assume we it means "precompile". 
"""
    )
    # Estimate run times for simple precompiles
    out_list = []
    for precomp in tqdm(
        operation_types.SIMPLE_PRECOMPILES, desc=f"Estimating simple precompiles"
    ):
        # Run estimation and add to report
        opcode_list = estimate_run_time_for_simple_operation(
            gas_bench_df, precomp, md_file, out_dir
        )
        out_list.extend(opcode_list)
    # Estimate run times for complex precompiles
    for precomp in tqdm(
        operation_types.VARIABLE_PRECOMPILES, desc=f"Estimating variable precompiles"
    ):
        # Run estimation and add to report
        opcode_list = estimate_run_time_for_non_simple_operation(
            gas_bench_df, precomp, md_file, out_dir, PRECOMPILE_PARAMS
        )
        out_list.extend(opcode_list)
    # Create and save output dataframe
    out_df = pd.DataFrame(out_list)
    out_df.to_csv(os.path.join(out_dir, "precompiles_results.csv"), index=False)
    # Finish and save markdown file
    md_file.new_table_of_contents(depth=1)
    md_file.create_md_file()


### Main runner ###########################################################################


if __name__ == "__main__":
    run_time = datetime.datetime.now()
    # Start date for querying
    start_date = "2026-01-10"
    # Directories
    file_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.abspath(os.path.join(file_dir, ".."))
    out_dir = os.path.join(
        repo_dir,
        "reports",
        "opcode_run_times_estimation",
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
    gas_bench_df = process_gas_bench_data(user, password, start_date)
    outfile = os.path.join(out_dir, "gas_bench_data.csv")
    gas_bench_df.to_csv(outfile, index=False)
    # Run estimations and generate reports
    generate_simple_opcode_report(gas_bench_df, out_dir)
    generate_non_simple_opcode_report(gas_bench_df, out_dir, "memory")
    generate_non_simple_opcode_report(gas_bench_df, out_dir, "log")
    generate_precompiles_report(gas_bench_df, out_dir)
