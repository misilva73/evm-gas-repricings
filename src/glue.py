import pandas as pd
from typing import Dict


def get_glue_opcodes_by_test(
    trace_df: pd.DataFrame,
    eps: float = 0.05,
) -> Dict[str, Dict[str, float]]:
    # Define columns lists
    grouping_cols = [
        "test_file",
        "test_name",
        "test_opcode",
        "test_params",
        "block_limit_million",
    ]
    opcode_cols = trace_df.drop(
        columns=grouping_cols + ["test_title", "opcount"]
    ).columns.tolist()
    # filter tests with less than 5 runs (pearson correlation is not reliable)
    filtered_trace_df = trace_df.groupby(grouping_cols).filter(lambda g: len(g) > 5)
    # Compute correlation by group
    grouped = filtered_trace_df.groupby(grouping_cols)
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
    result_df = result_df.rename(columns={"level_5": "glue_opcode"})
    # Filter low correlations and self-correlations
    result_df = result_df[
        result_df["corr"].notna()
        & (result_df["corr"] >= 1 - eps)
        & (result_df["test_opcode"] != result_df["glue_opcode"])
    ]
    return result_df


def generate_glue_opcode_report():
    pass
