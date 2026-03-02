import sys
import numpy as np
import pandas as pd
from typing import Dict, List
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from data import get_current_gas_cost
from glue import compute_glue_adjustment


def select_worst_case_estimates(
    results_df: pd.DataFrame,
    params: List[str],
    group_by: List[str],
    anchor_rate: float,
    params_multipliers: Dict[str, float],
    glue_results_df: pd.DataFrame = None,
    glue_opcodes_by_test: pd.DataFrame = None,
) -> tuple:
    """Select worst-case runtime estimates and compute new gas costs.

    For each (opcode, param, client), selects the worst-case runtime across
    test configurations. If any configuration has a statistically significant
    fit (p-value < 0.05), the worst case among significant fits is used.
    Otherwise, the worst case from all configurations is used.

    When glue_results_df and glue_opcodes_by_test are provided, the slope
    (constant parameter) is adjusted by subtracting the estimated runtime
    of glue opcodes that scale with the main opcode count in each test.

    Also tracks poor fit models (R² <= 0.5).

    Returns:
        (new_gas_df, poor_fit_dict) where new_gas_df is a DataFrame with
        new gas cost estimates and poor_fit_dict maps (opcode, param) tuples
        to sets of client names with poor fits.
    """
    # Apply glue adjustment to slope before worst-case selection
    if glue_results_df is not None and glue_opcodes_by_test is not None:
        results_df = results_df.copy()
        glue_adj = compute_glue_adjustment(glue_results_df, glue_opcodes_by_test)
        results_df = results_df.merge(
            glue_adj, on=["test_name", "opcode", "client_name"], how="left"
        )
        results_df["glue_adjustment"] = results_df["glue_adjustment"].fillna(0.0)
        results_df["slope"] = (
            results_df["slope"] - results_df["glue_adjustment"]
        ).clip(lower=0)
        results_df["slope_conf_int_low"] = (
            results_df["slope_conf_int_low"] - results_df["glue_adjustment"]
        ).clip(lower=0)
        results_df["slope_conf_int_high"] = (
            results_df["slope_conf_int_high"] - results_df["glue_adjustment"]
        ).clip(lower=0)
    all_params = ["slope"] + params
    new_gas_df = pd.DataFrame()
    poor_fit_dict = dict()
    for param in all_params:
        if param not in results_df.columns:
            continue
        pvalue_col = param + "_pvalue"
        conf_low_col = param + "_conf_int_low"
        conf_high_col = param + "_conf_int_high"
        selected_rows = []
        for (opcode, client), group_df in results_df.groupby(["opcode", "client_name"]):
            valid = group_df[group_df[param].notna()]
            if valid.empty:
                continue
            good_fits = valid[valid[pvalue_col] < 0.05]
            if len(good_fits) > 0:
                selected = good_fits.loc[good_fits[param].idxmax()]
            else:
                selected = valid.loc[valid[param].idxmax()]
                if (opcode, param) not in poor_fit_dict:
                    poor_fit_dict[(opcode, param)] = {client}
                else:
                    poor_fit_dict[(opcode, param)].add(client)
            selected_rows.append(selected)
        if not selected_rows:
            continue
        param_df = pd.DataFrame(selected_rows)[
            ["opcode", param, conf_low_col, conf_high_col] + group_by
        ]
        param_df = param_df.rename(
            columns={
                param: "runtime_ms",
                conf_low_col: "conf_int_low",
                conf_high_col: "conf_int_high",
            }
        )
        multiplier = params_multipliers.get(param, 1.0)
        param_df["new_gas"] = (anchor_rate * param_df["runtime_ms"] * multiplier) / 1e3
        param_df["new_gas_rounded"] = np.ceil(param_df["new_gas"])
        param_df["new_gas_conf_int_low"] = np.ceil(
            (anchor_rate * param_df["conf_int_low"]) / 1e3
        )
        param_df["new_gas_conf_int_high"] = np.ceil(
            (anchor_rate * param_df["conf_int_high"]) / 1e3
        )
        param_df["param"] = "constant" if param == "slope" else param
        new_gas_df = pd.concat([new_gas_df, param_df], ignore_index=True)
    # Track poor fitted models (R² <= 0.5)
    poor_fit_model_df = results_df[(results_df["rsquared"] <= 0.5)][
        ["opcode", "client_name"]
    ].dropna()
    for row in poor_fit_model_df.itertuples():
        if (row.opcode, "Model") not in poor_fit_dict:
            poor_fit_dict[(row.opcode, "Model")] = {row.client_name}
        else:
            poor_fit_dict[(row.opcode, "Model")].add(row.client_name)
    return new_gas_df, poor_fit_dict


def compute_worst_gas_proposal(new_gas_df: pd.DataFrame) -> pd.DataFrame:
    """Compute worst-case gas costs across all clients.

    Groups by (opcode, param), takes the max new_gas_rounded per group,
    adds current gas costs, and computes relative change.

    Returns:
        DataFrame with columns: opcode, param, new_gas_rounded, current_gas, change.
    """
    worst_gas_df = (
        new_gas_df.groupby(["opcode", "param"])["new_gas_rounded"]
        .max()
        .reset_index()
        .sort_index()
    )
    worst_gas_df["current_gas"] = worst_gas_df.apply(
        lambda row: get_current_gas_cost(row["opcode"], row["param"]), axis=1
    )
    worst_gas_df["change"] = (
        worst_gas_df["new_gas_rounded"] / worst_gas_df["current_gas"] - 1
    )
    worst_gas_df["change"] = worst_gas_df["change"].round(2)
    return worst_gas_df


def find_poor_fit_glue_opcodes(
    glue_results_df: pd.DataFrame,
    glue_opcodes_by_test: pd.DataFrame,
    target_operations: List[str] = [],
) -> Dict[str, Dict[str, List[str]]]:
    """Find glue opcodes with poor fit and the test opcodes they affect.

    A glue opcode has poor fit when its p_value >= 0.05 for a given client,
    meaning its runtime could not be reliably estimated. Test opcodes that
    use such glue opcodes will not have their slope adjusted for that glue
    opcode's contribution.

    Args:
        target_operations: If provided, only report test opcodes that are
            in this list. Glue opcodes with no matching target test opcodes
            are excluded from the result.

    Returns:
        Dict mapping glue_opcode -> {"clients": sorted list of clients,
        "test_opcodes": sorted list of affected test opcodes}.
        Only includes glue opcodes that appear in glue_opcodes_by_test.
    """
    poor_fit_glue = glue_results_df[glue_results_df["p_value"] >= 0.05]
    if poor_fit_glue.empty:
        return {}
    # Get unique test opcodes per glue opcode from the mapping
    test_opcodes_by_glue = (
        glue_opcodes_by_test.groupby("glue_opcode")["test_opcode"]
        .apply(lambda x: sorted(x.unique()))
        .to_dict()
    )
    target_set = set(target_operations)
    result = {}
    for glue_opcode, group in poor_fit_glue.groupby("glue_opcode"):
        if glue_opcode not in test_opcodes_by_glue:
            continue
        test_opcodes = test_opcodes_by_glue[glue_opcode]
        if target_set:
            test_opcodes = sorted(op for op in test_opcodes if op in target_set)
        if not test_opcodes:
            continue
        result[glue_opcode] = {
            "clients": sorted(group["client"].unique()),
            "test_opcodes": test_opcodes,
        }
    return dict(sorted(result.items()))


def find_missing_client_estimations(results_df: pd.DataFrame) -> Dict[str, List[str]]:
    """Find opcodes that are missing estimations for some clients.

    Checks against the expected set of 5 clients (geth, reth, nethermind,
    besu, erigon) and returns which clients are missing per opcode.

    Returns:
        Dict mapping opcode -> sorted list of missing client names.
        Empty dict if all opcodes have all 5 clients.
    """
    estimation_by_client = results_df.groupby("opcode")["client_name"].nunique()
    all_clients = {"geth", "reth", "nethermind", "besu", "erigon"}
    opcodes_with_missing_clients = estimation_by_client[estimation_by_client < 5].index
    missing_clients_by_opcode = {}
    for opcode in opcodes_with_missing_clients:
        present_clients = set(
            results_df[results_df["opcode"] == opcode]["client_name"].unique()
        )
        missing_clients = all_clients - present_clients
        missing_clients_by_opcode[opcode] = sorted(missing_clients)
    return missing_clients_by_opcode
