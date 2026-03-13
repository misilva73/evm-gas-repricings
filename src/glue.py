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

    Parameters:
        glue_results_df: Per-client glue opcode runtimes. Columns: client,
            glue_opcode, runtime, p_value.
        glue_opcodes_by_test: Per-test glue opcode ratios. Columns: test_name,
            test_opcode, glue_opcode, ratio, plus any extra ``group_by`` columns.
        group_by: Output grouping columns (using output names: ``client_name``
            for client, ``opcode`` for test_opcode).

    Returns:
        DataFrame with columns: *group_by, opcode, glue_adjustment
    """
    # Columns in glue_opcodes_by_test use source names; map output names back
    _RENAME = {"opcode": "test_opcode", "client_name": "client"}
    _RENAME_INV = {v: k for k, v in _RENAME.items()}

    output_cols = np.unique(group_by + ["opcode"]).tolist()
    source_cols = [_RENAME.get(c, c) for c in output_cols]

    # glue_opcodes_by_test has all group_by cols except "client"
    ratio_group_cols = [c for c in source_cols if c != "client"]

    # Average ratios across test_params per (ratio_group_cols, glue_opcode)
    avg_ratios = (
        glue_opcodes_by_test.groupby(ratio_group_cols + ["glue_opcode"], dropna=False)[
            "ratio"
        ]
        .mean()
        .reset_index()
    )

    # Keep only glue opcodes with a statistically significant fit
    significant_glue = glue_results_df.loc[
        glue_results_df["p_value"] < 0.05, ["client", "glue_opcode", "runtime"]
    ]

    # Inner merge on glue_opcode brings in per-client runtimes
    merged = avg_ratios.merge(significant_glue, on="glue_opcode", how="inner")
    merged["glue_adjustment"] = merged["ratio"] * merged["runtime"]

    # Sum contributions per output group
    result = (
        merged.groupby(source_cols, dropna=False)["glue_adjustment"].sum().reset_index()
    )
    return result.rename(columns=_RENAME_INV)


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


def add_state_glue_results(
    results_df: pd.DataFrame, glue_results_df: pd.DataFrame
) -> pd.DataFrame:
    """Add stateful glue results for cold BALANCE to glue results."""
    # cold balance
    balance_df = results_df[
        (results_df["opcode"] == "BALANCE")
        & (results_df["test_name"] == "test_account_access")
        & (results_df["cache_strategy"] == "NO_CACHE")
    ]
    # warm CALL
    call_df = results_df[
        (results_df["opcode"] == "CALL")
        & (results_df["test_name"] == "test_ext_account_query_warm")
        & (results_df["cache_strategy"] == "NO_CACHE")
    ]
    # cold SLOAD
    sload_df = results_df[
        (results_df["test_name"] == "test_sload_erc20_balanceof")
        & (results_df["cache_strategy"] == "NO_CACHE")
    ]
    # Join all cases
    state_glue_results_df = pd.concat([balance_df, call_df, sload_df], ignore_index=True)
    if state_glue_results_df.empty:
        return glue_results_df
    # Fix columns
    state_glue_results_df = state_glue_results_df[
        [
            "client_name",
            "opcode",
            "slope",
            "slope_pvalue",
            "rsquared",
            "account_mode",
        ]
    ]
    state_glue_results_df = state_glue_results_df.rename(
        columns={
            "client_name": "client",
            "opcode": "glue_opcode",
            "slope": "runtime",
            "slope_pvalue": "p_value",
        }
    )
    return pd.concat([glue_results_df, state_glue_results_df], ignore_index=True)


def add_state_missing_glues(glue_opcodes_by_test: pd.DataFrame) -> pd.DataFrame:
    """Add missing state glue opcodes (e.g. BALANCE for CACHE_TX tests)."""
    # Add a balance to the balance CACHE_TX tests
    if "cache_strategy" not in glue_opcodes_by_test.columns:
        balance_cache_tests = pd.DataFrame()
    else:
        balance_cache_tests = (
            glue_opcodes_by_test[
                (glue_opcodes_by_test["test_opcode"] == "BALANCE")
                & (glue_opcodes_by_test["cache_strategy"] == "CACHE_TX")
            ]
            .drop(columns=["glue_opcode", "corr", "ratio"])
            .drop_duplicates()
        )
        balance_cache_tests["glue_opcode"] = "BALANCE"
        balance_cache_tests["corr"] = 1.0
        balance_cache_tests["ratio"] = 1.0
    # Add a sload to the sload CACHE_TX tests
    if "cache_strategy" not in glue_opcodes_by_test.columns:
        sload_cache_tests = pd.DataFrame()
    else:
        sload_cache_tests = (
            glue_opcodes_by_test[
                (glue_opcodes_by_test["test_opcode"] == "SLOAD")
                & (glue_opcodes_by_test["cache_strategy"] == "CACHE_TX")
            ]
            .drop(columns=["glue_opcode", "corr", "ratio"])
            .drop_duplicates()
        )
        sload_cache_tests["glue_opcode"] = "SLOAD"
        sload_cache_tests["corr"] = 1.0
        sload_cache_tests["ratio"] = 1.0
    # join all new glues
    glue_opcodes_by_test = pd.concat(
        [glue_opcodes_by_test, balance_cache_tests, sload_cache_tests], ignore_index=True
    )
    return glue_opcodes_by_test


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
    # Make sure we use warm CALLs for glue opcodes
    filtered_gas_bench_df = gas_bench_df[
        (
            (gas_bench_df["test_name"] == "test_ext_account_query_warm")
            & (gas_bench_df["test_opcode"].isin(operation_types.CALL))
        )
        | (~gas_bench_df["test_opcode"].isin(operation_types.CALL))
    ]
    glue_df = filtered_gas_bench_df[
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
