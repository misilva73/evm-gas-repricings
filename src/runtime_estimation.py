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
    gas_bench_df: pd.DataFrame,
    opcode: str,
    md_file: MdUtils,
    out_dir: str,
    group_by: List[str] = ["client_name", "test_name"],
) -> List[dict[str, Any]]:
    md_file.new_header(level=1, title=opcode)
    opcode_df = gas_bench_df[gas_bench_df["test_opcode"] == opcode]
    out_list = []
    last_values = [None] * len(group_by)
    for group_values, op_df in opcode_df.groupby(group_by):
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        # Write markdown headers only when a group level changes
        for i, val in enumerate(group_values):
            if val != last_values[i]:
                md_file.new_header(level=i + 2, title=f"{val}")
                last_values[i] = val
                for j in range(i + 1, len(group_by)):
                    last_values[j] = None
        plot_label = f"{opcode}_{'_'.join(str(v) for v in group_values)}"
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
            **{col: val for col, val in zip(group_by, group_values)},
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
            op_df, result, opcode, group_values[0], out_dir, label=plot_label
        )
        create_and_save_nnls_diagnostic_plots(
            result, opcode, group_values[0], out_dir, label=plot_label
        )
        create_and_save_nnls_bootstrap_diagnostic(
            result, opcode, group_values[0], out_dir, label=plot_label
        )
        # Add plots to markdown
        md_file.new_paragraph(
            f'<img src="./figs/{plot_label}_regression.png" alt="{plot_label}_regression" width="600"/>'
        )
        md_file.new_paragraph(
            f'<img src="./figs/{plot_label}_diagnostics.png" alt="{plot_label}_diagnostics" width="600"/>'
        )
        md_file.new_paragraph(
            f'<img src="./figs/{plot_label}_bootstrap.png" alt="{plot_label}_bootstrap" width="600"/>'
        )
        md_file.new_paragraph("")
    return out_list


def estimate_run_time_for_non_simple_operation(
    gas_bench_df: pd.DataFrame,
    opcode: str,
    md_file: MdUtils,
    out_dir: str,
    params: List[str],
    group_by: List[str] = ["client_name", "test_name"],
) -> List[dict[str, Any]]:
    md_file.new_header(level=1, title=opcode)
    opcode_df = gas_bench_df[gas_bench_df["test_opcode"] == opcode]
    # Process opcode parameters
    for param in params:
        opcode_df[param] = opcode_df["test_params"].apply(
            lambda x: extract_param_values(x, param)
        )
    out_list = []
    last_values = [None] * len(group_by)
    for group_values, op_df in opcode_df.groupby(group_by):
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        # Write markdown headers only when a group level changes
        for i, val in enumerate(group_values):
            if val != last_values[i]:
                md_file.new_header(level=i + 2, title=f"{val}")
                last_values[i] = val
                for j in range(i + 1, len(group_by)):
                    last_values[j] = None
        plot_label = f"{opcode}_{'_'.join(str(v) for v in group_values)}"
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
            **{col: val for col, val in zip(group_by, group_values)},
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
            op_df, result, opcode, group_values[0], out_dir, features, label=plot_label
        )
        create_and_save_nnls_diagnostic_plots(
            result, opcode, group_values[0], out_dir, label=plot_label
        )
        create_and_save_nnls_bootstrap_diagnostic(
            result, opcode, group_values[0], out_dir, label=plot_label
        )
        # Add plots to markdown
        md_file.new_paragraph(
            f'<img src="./figs/{plot_label}_regression.png" alt="{plot_label}_regression" width="600"/>'
        )
        md_file.new_paragraph(
            f'<img src="./figs/{plot_label}_diagnostics.png" alt="{plot_label}_diagnostics" width="600"/>'
        )
        md_file.new_paragraph(
            f'<img src="./figs/{plot_label}_bootstrap.png" alt="{plot_label}_bootstrap" width="600"/>'
        )
        md_file.new_paragraph("")
    return out_list
