import pandas as pd
import statsmodels.api as sm
from scipy.stats import zscore

from typing import List

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