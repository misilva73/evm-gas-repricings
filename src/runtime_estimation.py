import sys
import pandas as pd
from pathlib import Path
from typing import List, Any
from mdutils.mdutils import MdUtils


sys.path.append(str(Path(__file__).parent))
from plotting import (
    create_and_save_1dim_nnls_regression_plot,
    create_and_save_nnls_diagnostic_plots,
    create_and_save_multidim_nnls_regression_plot,
    create_and_save_nnls_bootstrap_diagnostic,
)
from data import extract_param_values
from nnls import fit_NNLS_without_low_diff_runs


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
            # Fit linear regression model using NNLS
            result = fit_NNLS_without_low_diff_runs(op_df, ["opcount"])
        except Exception as e:
            md_file.new_line(f"NNLS model did not run... Error: {str(e)}")
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
        # Create and save plots
        create_and_save_1dim_nnls_regression_plot(
            op_df, result, opcode, client, out_dir
        )
        create_and_save_nnls_diagnostic_plots(result, opcode, client, out_dir)
        create_and_save_nnls_bootstrap_diagnostic(result, opcode, client, out_dir)
        # Add plots to markdown
        md_file.new_paragraph(
            f'<img src="./figs/{opcode}_{client}_regression.png" alt="{opcode}_{client}_regression" width="600"/>'
        )
        md_file.new_paragraph(
            f'<img src="./figs/{opcode}_{client}_diagnostics.png" alt="{opcode}_{client}_diagnostics" width="600"/>'
        )
        md_file.new_paragraph(
            f'<img src="./figs/{opcode}_{client}_bootstrap.png" alt="{opcode}_{client}_bootstrap" width="600"/>'
        )
        md_file.new_paragraph("")
    return out_list


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
        extra_features = na_counts[na_counts != len(op_df)].index.to_list()
        features = ["opcount"] + extra_features
        try:
            # Prepare data for modeling - extra params must be multiplied by opcount
            model_op_df = op_df.copy()
            model_op_df[extra_features] = model_op_df[extra_features].astype(float)
            model_op_df[extra_features] = model_op_df[extra_features].mul(
                model_op_df["opcount"], axis=0
            )
            # Fit linear regression model using NNLS
            result = fit_NNLS_without_low_diff_runs(model_op_df, features)
        except Exception as e:
            md_file.new_line(f"NNLS model did not run... Error: {str(e)}")
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
        # Create and save plots
        create_and_save_multidim_nnls_regression_plot(
            op_df, result, opcode, client, out_dir, features
        )
        create_and_save_nnls_diagnostic_plots(result, opcode, client, out_dir)
        create_and_save_nnls_bootstrap_diagnostic(result, opcode, client, out_dir)
        # Add plots to markdown
        md_file.new_paragraph(
            f'<img src="./figs/{opcode}_{client}_regression.png" alt="{opcode}_{client}_regression" width="600"/>'
        )
        md_file.new_paragraph(
            f'<img src="./figs/{opcode}_{client}_diagnostics.png" alt="{opcode}_{client}_diagnostics" width="600"/>'
        )
        md_file.new_paragraph(
            f'<img src="./figs/{opcode}_{client}_bootstrap.png" alt="{opcode}_{client}_bootstrap" width="600"/>'
        )
        md_file.new_paragraph("")
    return out_list
