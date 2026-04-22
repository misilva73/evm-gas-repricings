import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Set, Tuple
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from data import get_current_gas_cost
from glue import (
    compute_glue_adjustment,
    add_state_glue_results,
    add_state_missing_glues,
)


# EIP-8038 state access parameter current gas costs
_STATE_ACCESS_CURRENT_GAS = {
    "GAS_WARM_ACCESS": 100,
    "GAS_COLD_STORAGE_ACCESS": 2_200,
    "GAS_COLD_ACCOUNT_CODE_ACCESS": 2_600,
    "GAS_COLD_ACCOUNT_NOCODE_ACCESS": 2_600,
    "GAS_COLD_STORAGE_WRITE": 2_800,
    "GAS_COLD_ACCOUNT_WRITE": 6_700,
    "GAS_STORAGE_CLEAR_REFUND": 4_800,
    "ACCESS_LIST_STORAGE_KEY_COST": 1_900,
    "ACCESS_LIST_ADDRESS_COST": 2_400,
}

# Maps gas parameter -> list of (filter_dict, coefficient_column) pairs.
# filter_dict keys: exact match (col=val) or exclusion (col__ne=val).
_STATE_ACCESS_PARAM_SOURCES: Dict[str, List[Tuple[dict, str]]] = {
    "GAS_WARM_ACCESS": [
        ({"test_name": "test_storage_sload_same_key_benchmark"}, "slope"),
        (
            {
                "test_name": "test_sload_bloated",
                "cache_strategy": "CACHE_TX",
                "existing_slots": True,
            },
            "slope",
        ),
        (
            {
                "test_name": "test_sload_bloated",
                "cache_strategy": "CACHE_PREVIOUS_BLOCK",
                "existing_slots": True,
            },
            "slope",
        ),
        (
            {
                "test_name": "test_sstore_bloated",
                "cache_strategy": "CACHE_TX",
                "existing_slots": True,
            },
            "slope",
        ),
        (
            {
                "test_name": "test_sstore_bloated",
                "cache_strategy": "CACHE_PREVIOUS_BLOCK",
                "existing_slots": True,
            },
            "slope",
        ),
        ({"test_name": "test_ext_account_query_warm"}, "slope"),
        ({"test_name": "test_account_access", "cache_strategy": "CACHE_TX"}, "slope"),
        (
            {
                "test_name": "test_account_access",
                "cache_strategy": "CACHE_PREVIOUS_BLOCK",
            },
            "slope",
        ),
    ],
    "GAS_COLD_STORAGE_ACCESS": [
        (
            {"test_name": "test_sload_bloated", "cache_strategy": "NO_CACHE"},
            "slope",
        ),
        (
            {"test_name": "test_sstore_bloated", "cache_strategy": "NO_CACHE"},
            "slope",
        ),
    ],
    "GAS_COLD_STORAGE_WRITE": [
        (
            {"test_name": "test_sstore_bloated", "cache_strategy": "NO_CACHE"},
            "update",
        ),
    ],
    "GAS_COLD_ACCOUNT_NOCODE_ACCESS": [
        (
            {
                "test_name": "test_account_access",
                "cache_strategy": "NO_CACHE",
                "account_mode__ne": "EXISTING_CONTRACT",
            },
            "slope",
        ),
    ],
    "GAS_COLD_ACCOUNT_CODE_ACCESS": [
        (
            {
                "test_name": "test_account_access",
                "cache_strategy": "NO_CACHE",
                "account_mode__ne": "EXISTING_EOA",
            },
            "slope",
        ),
    ],
    "GAS_COLD_ACCOUNT_WRITE": [
        (
            {
                "test_name": "test_account_access",
                "cache_strategy": "NO_CACHE",
                "account_mode__ne": "EXISTING_CONTRACT",
            },
            "update",
        ),
        (
            {
                "test_name": "test_account_access",
                "cache_strategy": "NO_CACHE",
                "account_mode__ne": "EXISTING_EOA",
            },
            "update",
        ),
    ],
}


def _apply_filter(df: pd.DataFrame, filter_dict: dict) -> pd.DataFrame:
    """Apply filter conditions; supports `col__ne` suffix for inequality."""
    mask = pd.Series(True, index=df.index)
    for key, val in filter_dict.items():
        if key.endswith("__ne"):
            col = key[:-4]
            if col in df.columns:
                mask &= df[col] != val
        else:
            if key in df.columns:
                mask &= df[key] == val
    return df[mask]


def compute_state_access_gas_params(
    results_df: pd.DataFrame,
    anchor_rate: float,
    glue_results_df: pd.DataFrame,
    glue_opcodes_by_test: pd.DataFrame,
    group_by: List[str] = ["client_name", "test_name"],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Set[str]]]:
    """Estimate state access gas parameters from NNLS model outputs.

    Maps model results to gas parameters:
    - Directly estimated: GAS_WARM_ACCESS, GAS_COLD_STORAGE_ACCESS,
      GAS_COLD_STORAGE_WRITE, GAS_COLD_ACCOUNT_NOCODE_ACCESS,
      GAS_COLD_ACCOUNT_CODE_ACCESS, GAS_COLD_ACCOUNT_WRITE.
    - Derived: GAS_STORAGE_CLEAR_REFUND, ACCESS_LIST_STORAGE_KEY_COST,
      ACCESS_LIST_ADDRESS_COST.

    For each gas parameter and client, the worst-case runtime is selected
    across all matching test configurations. If any configuration has a
    statistically significant fit (p-value < 0.05), the worst case among
    significant fits is used; otherwise the overall worst case is used.

    Returns:
        (params_df, derived_df, poor_fit_dict) where:
        - params_df: per-client worst-case estimates for directly estimated parameters.
        - derived_df: computed derived parameters with new_gas_rounded values.
        - poor_fit_dict: maps gas_param to the set of client names with no significant fit.
    """
    glue_results_df = add_state_glue_results(results_df, glue_results_df)
    glue_opcodes_by_test = add_state_missing_glues(glue_opcodes_by_test)
    # Apply glue adjustment to slope columns
    if glue_results_df is not None and glue_opcodes_by_test is not None:
        glue_adj = compute_glue_adjustment(
            glue_results_df, glue_opcodes_by_test, group_by
        )
        merge_keys = list(
            set(glue_adj.columns) & set(results_df.columns) - {"glue_adjustment"}
        )
        results_df = results_df.merge(glue_adj, on=merge_keys, how="left")
        results_df["glue_adjustment"] = results_df["glue_adjustment"].fillna(0.0)
        for col in ["slope", "slope_conf_int_low", "slope_conf_int_high"]:
            if col in results_df.columns:
                results_df[col] = (
                    results_df[col] - results_df["glue_adjustment"]
                ).clip(lower=0)

    rows = []
    poor_fit_dict: Dict[str, Set[str]] = {}
    all_params_df = pd.DataFrame()

    for gas_param, sources in _STATE_ACCESS_PARAM_SOURCES.items():
        candidates = []
        for filter_dict, coef in sources:
            subset = _apply_filter(results_df, filter_dict)
            if subset.empty:
                continue
            pvalue_col = f"{coef}_pvalue"
            conf_low_col = f"{coef}_conf_int_low"
            conf_high_col = f"{coef}_conf_int_high"
            valid = subset[subset[coef].notna()]
            if valid.empty:
                continue
            for _, row in valid.iterrows():
                glue_adj_val = (
                    row.get("glue_adjustment", 0.0) if coef == "slope" else 0.0
                )
                cand = {
                    "gas_param": gas_param,
                    "client_name": row["client_name"],
                    "runtime_ms": row[coef],
                    "pvalue": row.get(pvalue_col, 1.0),
                    "conf_int_low": row.get(conf_low_col, 0.0),
                    "conf_int_high": row.get(conf_high_col, 0.0),
                    "test_name": row["test_name"],
                    "opcode": row.get("opcode", ""),
                    "coef": coef,
                    "glue_adjustment": glue_adj_val,
                }
                for col in group_by:
                    if col not in ("client_name", "test_name") and col in row.index:
                        cand[col] = row[col]
                candidates.append(cand)
        if not candidates:
            continue

        cand_df = pd.DataFrame(candidates)
        all_params_df = pd.concat([all_params_df, cand_df], ignore_index=True)
        for client, grp in cand_df.groupby("client_name"):
            good = grp[grp["pvalue"] < 0.05]
            if not good.empty:
                sel = good.loc[good["runtime_ms"].idxmax()]
            else:
                sel = grp.loc[grp["runtime_ms"].idxmax()]
                poor_fit_dict.setdefault(gas_param, set()).add(client)
            row_dict = {
                "gas_param": sel["gas_param"],
                "client_name": sel["client_name"],
                "runtime_ms": sel["runtime_ms"],
                "conf_int_low": sel["conf_int_low"],
                "conf_int_high": sel["conf_int_high"],
                "selected_test": sel["test_name"],
                "selected_opcode": sel["opcode"],
                "selected_coef": sel["coef"],
                "glue_adjustment": sel.get("glue_adjustment", 0.0),
            }
            for col in group_by:
                if col not in ("client_name", "test_name") and col in sel.index:
                    row_dict[f"selected_{col}"] = sel[col]
            rows.append(row_dict)

    if not rows:
        return pd.DataFrame(), pd.DataFrame(), poor_fit_dict

    # Compute new gas for the worst runtime per client
    params_df = pd.DataFrame(rows)
    params_df["new_gas"] = (anchor_rate * params_df["runtime_ms"]) / 1e3
    params_df["new_gas_rounded"] = np.ceil(params_df["new_gas"])
    params_df["new_gas_conf_int_low"] = np.ceil(
        (anchor_rate * params_df["conf_int_low"]) / 1e3
    )
    params_df["new_gas_conf_int_high"] = np.ceil(
        (anchor_rate * params_df["conf_int_high"]) / 1e3
    )

    # compute the same features for all_params
    all_params_df["new_gas"] = (anchor_rate * all_params_df["runtime_ms"]) / 1e3
    all_params_df["new_gas_rounded"] = np.ceil(all_params_df["new_gas"])
    all_params_df["new_gas_conf_int_low"] = np.ceil(
        (anchor_rate * all_params_df["conf_int_low"]) / 1e3
    )
    all_params_df["new_gas_conf_int_high"] = np.ceil(
        (anchor_rate * all_params_df["conf_int_high"]) / 1e3
    )

    return params_df, all_params_df, poor_fit_dict


def compute_derived_state_access_params(params_df: pd.DataFrame) -> Dict[str, int]:
    """Compute derived state access gas parameters from directly estimated ones.

    Args:
        params_df: Per-client worst-case estimates DataFrame with columns
            ``gas_param`` and ``new_gas_rounded``.

    Returns:
        Dict mapping derived parameter names to their new gas values.
    """
    worst = params_df.groupby("gas_param")["new_gas_rounded"].max().to_dict()
    cold_storage_access = worst.get("GAS_COLD_STORAGE_ACCESS", 0)
    cold_storage_write = worst.get("GAS_COLD_STORAGE_WRITE", 0)
    cold_account_code_access = worst.get("GAS_COLD_ACCOUNT_CODE_ACCESS", 0)
    return {
        "GAS_STORAGE_CLEAR_REFUND": int(
            np.ceil((cold_storage_write + cold_storage_access) * (4800 / 5000))
        ),
        "ACCESS_LIST_STORAGE_KEY_COST": int(cold_storage_access),
        "ACCESS_LIST_ADDRESS_COST": int(cold_account_code_access),
    }


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
        keep_cols = ["opcode", param, conf_low_col, conf_high_col] + group_by
        if "glue_adjustment" in results_df.columns:
            keep_cols = keep_cols + ["glue_adjustment"]
        param_df = pd.DataFrame(selected_rows)[keep_cols]
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
        if "glue_adjustment" not in param_df.columns:
            param_df["glue_adjustment"] = 0.0
        if param != "slope":
            param_df["glue_adjustment"] = 0.0
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


def find_missing_client_estimations(
    results_df: pd.DataFrame, required_opcodes: List[str] = []
) -> Dict[str, List[str]]:
    """Find opcodes that are missing estimations for some clients.

    Checks against the expected set of 5 clients (geth, reth, nethermind,
    besu, erigon) and returns which clients are missing per opcode.

    Args:
        results_df: DataFrame with columns 'opcode' and 'client_name'.
        required_opcodes: If provided, opcodes in this list that are entirely
            absent from results_df are included in the result with all 5
            clients listed as missing.

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
    # Add missing opcodes, i.e., no clients have an estimation for it
    opcodes_with_at_least_one_client = set(results_df["opcode"].unique().tolist())
    missing_opcodes = list(
        set(required_opcodes).difference(opcodes_with_at_least_one_client)
    )
    for opcode in missing_opcodes:
        missing_clients_by_opcode[opcode] = sorted(all_clients)
    return missing_clients_by_opcode
