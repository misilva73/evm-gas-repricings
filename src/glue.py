import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List
from mdutils.mdutils import MdUtils

sys.path.append(str(Path(__file__).parent))
from runtime_estimation import estimate_run_time_for_glue_opcodes
import operation_types


def compute_glue_adjustment(
    glue_results_df: pd.DataFrame,
    glue_opcodes_by_test: pd.DataFrame,
    group_by: List[str] = ["test_name", "client_name"],
) -> pd.DataFrame:
    """Compute glue opcode runtime adjustment for each test.

    For each combination of ``group_by`` columns + opcode, computes the total glue
    opcode runtime to subtract from the slope. This accounts for the fact
    that glue opcodes (e.g., PUSH1, CALL) scale with the main opcode count
    and their runtime is captured in the slope coefficient.

    The adjustment is: sum(ratio_i * glue_runtime_i) for all glue opcodes i
    where ratio_i is the average number of glue opcode instances per main opcode
    instance (averaged across test_params), and glue_runtime_i is the estimated
    per-execution runtime of the glue opcode for the given client. Only glue
    opcodes with a statistically significant fit (p_value < 0.05) are included.

    Returns:
        DataFrame with columns: *group_by, opcode, glue_adjustment
    """
    group_by = np.unique(group_by + ["opcode"]).tolist()
    # Map output column names to source column names
    _OUTPUT_TO_SOURCE = {"opcode": "test_opcode", "client_name": "client"}
    source_group_by = [_OUTPUT_TO_SOURCE.get(c, c) for c in group_by]

    # Split into columns from glue_opcodes_by_test vs glue_results_df
    glue_results_cols = {"client"}
    ratio_group_cols = [c for c in source_group_by if c not in glue_results_cols]

    # Average ratios across test_params for each (ratio_group_cols, glue_opcode)
    avg_ratios = (
        glue_opcodes_by_test.groupby(ratio_group_cols + ["glue_opcode"], dropna=False)[
            "ratio"
        ]
        .mean()
        .reset_index()
    )
    # Only use glue opcodes with a statistically significant fit
    significant_glue = glue_results_df[glue_results_df["p_value"] < 0.05]
    # Merge with glue runtimes to get ratio * runtime per (group_by, glue_opcode)
    glue_with_runtime = avg_ratios.merge(
        significant_glue[["client", "glue_opcode", "runtime"]],
        on="glue_opcode",
        how="inner",
    )
    glue_with_runtime["glue_runtime_contribution"] = (
        glue_with_runtime["ratio"] * glue_with_runtime["runtime"]
    )
    # Sum contributions per group_by
    glue_adjustment = (
        glue_with_runtime.groupby(source_group_by, dropna=False)[
            "glue_runtime_contribution"
        ]
        .sum()
        .reset_index()
    )
    # Rename source columns to output column names
    rename_map = {v: k for k, v in _OUTPUT_TO_SOURCE.items() if v in glue_adjustment.columns}
    rename_map["glue_runtime_contribution"] = "glue_adjustment"
    glue_adjustment = glue_adjustment.rename(columns=rename_map)
    return glue_adjustment


def get_glue_opcodes_by_test(
    trace_df: pd.DataFrame,
    eps: float = 0.05,
    glue_group_by: List[str] = [],
) -> Dict[str, Dict[str, float]]:
    # Define columns lists
    grouping_cols = [
        "test_name",
        "test_opcode",
    ] + glue_group_by
    opcode_cols = list(
        set(trace_df.columns.tolist()).intersection(set(operation_types.ALL_OPCODES))
    )
    # filter tests with less than 5 different block limits (pearson correlation is not reliable)
    filtered_trace_df = trace_df.groupby(grouping_cols, dropna=False).filter(
        lambda g: len(g) > 5
    )
    # Compute correlation by group
    grouped = filtered_trace_df.groupby(grouping_cols, dropna=False)
    corrs = grouped.apply(
        lambda g: g[opcode_cols].corrwith(g["opcount"]),
        include_groups=False,
    )
    # Compute ratios by group
    ratios = grouped.apply(
        lambda g: g[opcode_cols].diff().mean() / g["opcount"].diff().mean(),
        include_groups=False,
    )
    # Add data to single dataframe + filter
    result_df = pd.DataFrame(
        {"corr": corrs.stack(), "ratio": ratios.stack()}
    ).reset_index()
    result_df = result_df.rename(columns={f"level_{len(grouping_cols)}": "glue_opcode"})
    # Filter low correlations, self-correlations and low ratios
    result_df = result_df[
        result_df["corr"].notna()
        & (result_df["corr"] >= 1 - eps)
        & (result_df["ratio"] >= 0.0005)
        & (result_df["test_opcode"] != result_df["glue_opcode"])
    ]
    return result_df


def get_all_glue_opcodes_for_target_opcodes(
    target_opcodes: List[str], glue_opcodes_by_test: pd.DataFrame, max_iter: int = 1e5
):
    df = glue_opcodes_by_test[glue_opcodes_by_test["test_opcode"].isin(target_opcodes)]
    prev_glue_opcodes = []
    glue_opcodes = df["glue_opcode"].unique().tolist()
    i = 0
    while len(prev_glue_opcodes) != len(glue_opcodes) and i < max_iter:
        new_glue_opcodes = df[df["test_opcode"].isin(glue_opcodes)][
            "glue_opcode"
        ].unique()
        prev_glue_opcodes = glue_opcodes
        glue_opcodes = list(set(glue_opcodes).union(set(new_glue_opcodes)))
        i += 1
    return glue_opcodes


def generate_glue_opcode_report(
    start_date: str,
    end_date: str,
    eip_number: int,
    gas_bench_df: pd.DataFrame,
    trace_df: pd.DataFrame,
    out_dir: str,
    target_opcodes: List[str],
    glue_group_by: List[str] = [],
) -> None:
    print("Estimating glue operations...")
    # Start markdown report
    md_file = MdUtils(
        file_name=os.path.join(out_dir, f"glue_opcodes_autogenerated_report"),
        title=f"Operation run times estimation results - Glue opcodes",
    )
    md_file.new_header(level=1, title="Introduction", add_table_of_contents="n")
    md_file.new_paragraph(
        f"""
This is an automated report generated from the opcode run times
estimation script `./src/glue.py`. The script
uses data generated by running the
[EEST benchmark suite](https://github.com/ethereum/execution-spec-tests/tree/main/tests/benchmark)
with the [Nethermind benchmarking tooling](https://github.com/NethermindEth/gas-benchmarks).

The data includes all the tests for glue operations repriced in EIP-{eip_number} run
between {start_date} and {end_date}.
"""
    )
    md_file.new_header(
        level=2, title="What is a glue opcode?", add_table_of_contents="n"
    )
    md_file.new_paragraph(
        f"""
A **glue opcode** is an opcode whose execution count scales proportionally with the count of
a target opcode under test. Concretely, an opcode is classified as a glue opcode for a given
test if its execution count has a Pearson correlation ≥ 0.95 with the target opcode count
across different test parameter values, and its average count per target opcode execution
is at least 0.0005. Self-correlations are excluded. This identification is done automatically
from opcode-level execution traces.

The glue opcode set is also expanded transitively: if opcode A is a glue opcode for a target,
and opcode B is a glue opcode for A, then B is also included. This captures indirect
dependencies in the benchmark scaffolding.

**Why do glue opcodes matter?**

Because glue opcodes scale with the target opcode count, their runtime is absorbed into the
slope coefficient when regressing total test execution time on target opcode count. Without
correction, the slope overestimates the target opcode's per-execution runtime. The glue opcode
runtimes estimated in this report are used to compute a **glue adjustment** — a correction
subtracted from each target opcode's slope to remove the contribution of glue opcodes.
"""
    )
    md_file.new_header(
        level=2,
        title="How glue opcode runtimes are estimated?",
        add_table_of_contents="n",
    )
    md_file.new_paragraph(
        """
**Non-Negative Least Squares (NNLS) Linear Regression** is used to estimate glue operation runtimes.
This model ensures all coefficients are non-negative, which is physically meaningful since
execution time cannot be negative.

Unlike the per-opcode models used for target operations, glue opcodes are estimated using a
**single model per client** that fits all glue opcode counts as features simultaneously. This means
the model estimates the runtime coefficients of all glue opcodes at the same time by solving:

`runtime = intercept + coef_1 × opcode_1_count + coef_2 × opcode_2_count + ... + coef_n × opcode_n_count`

where each `coef_i` represents the estimated per-execution runtime of the corresponding glue opcode.
This joint estimation approach accounts for correlations between glue opcode counts across tests,
producing more accurate estimates than fitting each glue opcode independently.

Only warm CALL variants are included in the model (cold CALL tests are excluded).
"""
    )

    md_file.new_header(
        level=2, title="Model Quality Metrics", add_table_of_contents="n"
    )
    md_file.new_paragraph(
        """
Each model reports two key metrics to assess the quality of the fit:

**R² (R-squared / Coefficient of Determination)**
- Ranges from 0 to 1 (or can be negative for very poor fits)
- Measures how well the model explains the variance in the data
- **Interpretation**:
  - R² > 0.9: Excellent fit - the model explains >90% of the variance
  - R² > 0.7: Good fit - the model captures most of the relationship
  - R² > 0.5: Acceptable fit - the model has predictive power but notable variance remains
  - R² < 0.5: Poor fit - the model may not be reliable

**p-value**
- Tests the statistical significance of each coefficient, based on a bootstrap sample estimation
- **Interpretation**:
  - p < 0.05: Statistically significant - the parameter has a real effect on runtime
  - p ≥ 0.05: Not significant - the parameter's effect cannot be distinguished from random noise

We also plot some diagnostic graphs for each operation and client combination to visually assess the model fit.
"""
    )
    # Get list of glue opcodes
    glue_opcodes_by_test = get_glue_opcodes_by_test(
        trace_df, glue_group_by=glue_group_by
    )
    glue_opcodes_by_test.to_csv(
        os.path.join(out_dir, f"glue_opcodes_by_test.csv"), index=False
    )
    glue_opcodes = get_all_glue_opcodes_for_target_opcodes(
        target_opcodes, glue_opcodes_by_test
    )
    aux_glue_opcodes = list(set(glue_opcodes).difference(set(target_opcodes)))
    # get opcode counts for all glue opcodes
    glue_df = trace_df[trace_df["test_opcode"].isin(aux_glue_opcodes)][
        ["test_title"] + aux_glue_opcodes
    ].fillna(0.0)
    glue_df = gas_bench_df[
        ["test_title", "client_name", "test_params", "run_duration_ms"] + glue_group_by
    ].merge(glue_df, on="test_title", how="inner")
    # Estimate runtime for all glue opcodes together
    out_list = estimate_run_time_for_glue_opcodes(
        glue_df, aux_glue_opcodes, out_dir, md_file
    )
    # Create and save output dataframe
    out_df = pd.DataFrame(out_list)
    out_df.to_csv(os.path.join(out_dir, f"glue_results.csv"), index=False)
    # Finish and save markdown file
    md_file.new_table_of_contents(depth=1)
    md_file.create_md_file()
