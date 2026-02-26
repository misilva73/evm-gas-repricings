import sys
import pandas as pd
from pathlib import Path
from typing import Dict, List

sys.path.append(str(Path(__file__).parent))

from data import process_test_trace_data


def get_glue_opcodes_by_test(
    user: str,
    password: str,
    db_name: str,
    opcodes_sample: List[str],
    eps: float = 0.05,
) -> Dict[str, Dict[str, float]]:
    df = process_test_trace_data(user, password, db_name, opcodes_sample)
    # Compute pct diffs
    sorted_df = df.sort_values(
        by=["test_file", "test_name", "test_opcode", "test_params", "opcount"]
    )
    grouping_cols = ["test_file", "test_name", "test_opcode", "test_params"]
    opcode_cols = df.drop(
        columns=grouping_cols + ["test_title", "opcount", "block_limit_million"]
    ).columns.tolist()
    pct_diff_df = (
        sorted_df.drop(columns=["test_title", "block_limit_million"])
        .groupby(grouping_cols)
        .pct_change()
    )
    pct_diff_df = pd.concat([sorted_df[grouping_cols], pct_diff_df], axis=1)
    # Compute glue_opcodes_by_test dict based on glie opcodes with the same diffs as the test opcode
    glue_opcodes_by_test = {}
    for glue_opcode in opcode_cols:
        counts_with_similar_diffs_df = (
            pct_diff_df[
                pct_diff_df["opcount"].between(
                    pct_diff_df[glue_opcode] * (1 - eps),
                    pct_diff_df[glue_opcode] * (1 + eps),
                )
            ]
            .groupby(grouping_cols)
            .size()
        )
        filter_index = counts_with_similar_diffs_df[
            counts_with_similar_diffs_df > 5
        ].index
        filtered_df = df.copy().set_index(grouping_cols).loc[filter_index]
        glue_opcode_counts = (
            filtered_df[glue_opcode] / filtered_df["opcount"]
        ).drop_duplicates()
        for test, glue_count in glue_opcode_counts.items():
            if test[2] != glue_opcode:
                glue_opcodes_by_test[test] = glue_opcodes_by_test.get(test, dict())
                glue_opcodes_by_test[test][glue_opcode] = glue_count
    return glue_opcodes_by_test


def generate_glue_opcode_report():
    pass
