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


def build_result_dict(
    result,
    opcode: str,
    group_by: List[str],
    group_values: tuple,
) -> dict[str, Any]:
    """Build the output dictionary from an NNLSResults object."""
    return {
        "opcode": opcode,
        **{col: val for col, val in zip(group_by, group_values)},
        "nobs": result.nobs,
        "intercept": result.params["const"],
        "intercept_pvalue": result.pvalues["const"],
        "rsquared": result.rsquared,
        "rsquared_adj": result.rsquared_adj,
        "slope": result.params["opcount"],
        "slope_pvalue": result.pvalues["opcount"],
        "slope_conf_int_low": result.conf_int().loc["opcount", 0],
        "slope_conf_int_high": result.conf_int().loc["opcount", 1],
    }


def add_param_results_to_dict(
    out_dict: dict[str, Any],
    result,
    params: List[str],
) -> None:
    """Add parameter-specific coefficients, p-values, and confidence intervals to a result dict."""
    for param in params:
        if param in result.params:
            out_dict[param] = result.params[param]
            out_dict[param + "_pvalue"] = result.pvalues[param]
            out_dict[param + "_conf_int_low"] = result.conf_int().loc[param, 0]
            out_dict[param + "_conf_int_high"] = result.conf_int().loc[param, 1]


def write_group_headers(
    group_values: tuple,
    last_values: List,
    md_file: MdUtils,
    group_by: List[str],
    opcode: str,
) -> str:
    """Write markdown headers when a group level changes and return the plot label.

    Mutates last_values in place to track which headers have been written.
    """
    for i, val in enumerate(group_values):
        if val != last_values[i]:
            md_file.new_header(level=i + 2, title=f"{val}")
            last_values[i] = val
            for j in range(i + 1, len(group_by)):
                last_values[j] = None
    return f"{opcode}_{'_'.join(str(v) for v in group_values)}"


def prepare_non_simple_model_data(
    op_df: pd.DataFrame,
    params: List[str],
) -> tuple[pd.DataFrame, List[str]]:
    """Prepare data for non-simple operation modeling.

    Extracts parameter values, determines which features have data,
    and multiplies extra features by opcount.

    Returns (model_df, features) where features = ["opcount"] + active params.
    """
    for param in params:
        op_df[param] = op_df["test_params"].apply(
            lambda x: extract_param_values(x, param)
        )
    na_counts = op_df[params].isna().sum()
    extra_features = na_counts[na_counts != len(op_df)].index.to_list()
    features = ["opcount"] + extra_features
    model_op_df = op_df.copy()
    model_op_df[extra_features] = model_op_df[extra_features].astype(float)
    model_op_df[extra_features] = model_op_df[extra_features].mul(
        model_op_df["opcount"], axis=0
    )
    return model_op_df, features


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
        plot_label = write_group_headers(group_values, last_values, md_file, group_by, opcode)
        try:
            result = fit_NNLS_without_low_diff_runs(op_df, ["opcount"])
        except Exception as e:
            md_file.new_line(f"NNLS model did not run... Error: {str(e)}")
            md_file.new_line(f"")
            continue
        out_dict = build_result_dict(result, opcode, group_by, group_values)
        out_list.append(out_dict)
        # Add outputs in markdown report
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
    out_list = []
    last_values = [None] * len(group_by)
    for group_values, op_df in opcode_df.groupby(group_by):
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        plot_label = write_group_headers(group_values, last_values, md_file, group_by, opcode)
        try:
            model_op_df, features = prepare_non_simple_model_data(op_df, params)
            result = fit_NNLS_without_low_diff_runs(model_op_df, features)
        except Exception as e:
            md_file.new_line(f"NNLS model did not run... Error: {str(e)}")
            md_file.new_line(f"")
            continue
        out_dict = build_result_dict(result, opcode, group_by, group_values)
        add_param_results_to_dict(out_dict, result, params)
        out_list.append(out_dict)
        # Add outputs in markdown report
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
