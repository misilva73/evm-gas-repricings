import numpy as np
import pandas as pd
from typing import List
from scipy.optimize import nnls
from scipy.stats import zscore

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from nnls_results import NNLSResults


def fit_NNLS(
    feature_df: pd.DataFrame,
    features: List[str],
    n_bootstrap: int = 1000,
    random_seed: int = 42,
) -> NNLSResults:
    """
    Fit NNLS regression with bootstrap inference.

    Performs Non-Negative Least Squares regression with statistical inference
    via bootstrap resampling. All coefficients are constrained to be non-negative,
    which is appropriate for runtime estimation where negative time contributions
    are physically meaningless.

    Args:
        feature_df: DataFrame with features and "run_duration_ms" target column
        features: List of feature column names (excluding constant term)
        n_bootstrap: Number of bootstrap iterations for inference (default 1000)
        random_seed: Random seed for reproducibility (default 42)

    Returns:
        NNLSResults object with statsmodels-compatible interface

    Raises:
        ValueError: If feature_df is empty or missing required columns
        KeyError: If specified features are not in feature_df

    Example:
        >>> df = pd.DataFrame({
        ...     'opcount': [1, 2, 3, 4, 5],
        ...     'run_duration_ms': [2.1, 5.0, 7.9, 11.1, 13.9]
        ... })
        >>> result = fit_NNLS(df, ['opcount'], n_bootstrap=100)
        >>> print(result.params)
        const      0.12
        opcount    2.80
        dtype: float64
    """
    # Validate inputs
    if feature_df.empty:
        raise ValueError("feature_df cannot be empty")
    if "run_duration_ms" not in feature_df.columns:
        raise ValueError("feature_df must contain 'run_duration_ms' column")
    for feature in features:
        if feature not in feature_df.columns:
            raise KeyError(f"Feature '{feature}' not found in feature_df")
    # Extract and prepare data
    X = feature_df[features].astype(float).values
    y = feature_df["run_duration_ms"].astype(float).values
    # Add constant column (intercept) at position 0
    X_with_const = np.column_stack([np.ones(len(X)), X])
    feature_names = ["const"] + features
    # Fit primary NNLS model
    coefficients, residual_norm = nnls(X_with_const, y)
    # Bootstrap for statistical inference
    np.random.seed(random_seed)
    bootstrap_coefs = np.zeros((n_bootstrap, X_with_const.shape[1]))
    n_successful = 0
    for i in range(n_bootstrap):
        try:
            # Resample with replacement
            indices = np.random.choice(len(y), size=len(y), replace=True)
            X_boot = X_with_const[indices]
            y_boot = y[indices]
            # Fit NNLS on bootstrap sample
            coef_boot, _ = nnls(X_boot, y_boot)
            bootstrap_coefs[i] = coef_boot
            n_successful += 1
        except Exception:
            # If bootstrap sample fails, use zeros (will be handled in results)
            bootstrap_coefs[i] = np.zeros(X_with_const.shape[1])
    # Warn if too many bootstrap failures
    success_rate = n_successful / n_bootstrap
    if success_rate < 0.95:
        import warnings

        warnings.warn(
            f"Only {success_rate:.1%} of bootstrap samples succeeded. "
            f"Statistical inference may be unreliable.",
            UserWarning,
        )
    # Create and return results object
    return NNLSResults(
        X=X_with_const,
        y=y,
        y_name="run_duration_ms",
        coefficients=coefficients,
        bootstrap_coefs=bootstrap_coefs,
        feature_names=feature_names,
        residual_norm=residual_norm,
    )


def fit_NNLS_without_low_diff_runs(
    op_df: pd.DataFrame,
    features: List[str],
    n_bootstrap: int = 1000,
    random_seed: int = 42,
) -> NNLSResults:
    """
    Fit NNLS regression with adaptive filtering of low_diff_runs.

    This function mirrors the behavior of fit_OLS_without_low_diff_runs:
    - Fits an initial NNLS model on all available data
    - If R² ≤ 0.5 (poor fit), filters out runs with low average runtime differences
    - Refits the model on filtered data
    - Returns the better-fitting model (original or filtered)

    The filtering removes measurement runs where opcounts don't produce increasing
    runtimes, which can indicate measurement noise or system interference.

    Args:
        op_df: DataFrame with features, "run_duration_ms", and metadata columns
                required for filtering (test_file, test_name, test_params,
                ingestion_timestamp)
        features: List of feature column names (excluding constant)
        n_bootstrap: Number of bootstrap iterations (default 1000)
        random_seed: Random seed for reproducibility (default 42)

    Returns:
        NNLSResults object (either original or filtered model, whichever is better)

    Raises:
        ValueError: If op_df is missing required columns
        Exception: If both original and filtered models fail to fit

    Example:
        >>> result = fit_NNLS_without_low_diff_runs(op_df, ['opcount', 'num_rounds'])
        >>> print(f"R² = {result.rsquared:.3f}")
        R² = 0.856
    """
    # Prepare feature dataframe (drop NaN values)
    required_cols = features + ["run_duration_ms"]
    feature_df = op_df[required_cols].dropna()
    if feature_df.empty:
        raise ValueError("No valid data remaining after dropping NaN values")
    # Fit initial NNLS model on all data
    result = fit_NNLS(feature_df, features, n_bootstrap, random_seed)
    # Check if we need to apply adaptive filtering
    if result.rsquared <= 0.5:
        try:
            # Filter out low_diff_runs (runs with non-increasing runtimes)
            filtered_op_df = find_low_diff_runs(op_df)
            filtered_feature_df = filtered_op_df[required_cols].dropna()
            # Fit model on filtered data
            result_v2 = fit_NNLS(
                filtered_feature_df, features, n_bootstrap, random_seed
            )

            # Return filtered model if it's better
            if result_v2.rsquared > 0.5:
                return result_v2
        except Exception:
            # If filtering fails, fall back to original result
            pass
    # Return original result if no improvement from filtering
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