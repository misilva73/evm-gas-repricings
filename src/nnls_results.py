import numpy as np
import pandas as pd
from typing import Union, List


class NNLSResults:
    """
    Results wrapper for NNLS regression that mimics statsmodels interface.

    This class provides a statsmodels-compatible interface for NNLS (Non-Negative
    Least Squares) regression results, enabling drop-in replacement of OLS methods
    in existing code. Statistical inference is performed via bootstrap.

    Attributes:
        params (pd.Series): Coefficient estimates (including "const" for intercept)
        pvalues (pd.Series): Bootstrap-based p-values for each coefficient
        rsquared (float): R-squared value
        rsquared_adj (float): Adjusted R-squared value
        nobs (int): Number of observations
        fittedvalues (np.ndarray): Predicted values for training data
        resid (np.ndarray): Residuals (observed - fitted)
    """

    def __init__(
        self,
        X: np.ndarray,
        y: np.ndarray,
        y_name: str,
        coefficients: np.ndarray,
        bootstrap_coefs: np.ndarray,
        feature_names: List[str],
        residual_norm: float,
    ):
        """
        Initialize NNLS results wrapper.

        Args:
            X: Feature matrix with constant column (n_obs × n_features)
            y: Target values (n_obs,)
            coefficients: NNLS coefficient estimates (n_features,)
            bootstrap_coefs: Bootstrap coefficient samples (n_bootstrap × n_features)
            feature_names: Names of features including "const"
            residual_norm: Residual norm from NNLS optimization
        """
        self._X = X
        self._y = y
        self._coefficients = coefficients
        self._bootstrap_coefs = bootstrap_coefs
        self._feature_names = feature_names
        self._residual_norm = residual_norm
        self._dep_var = y_name

        # Compute fitted values and residuals
        self._fittedvalues = X @ coefficients
        self._resid = y - self._fittedvalues

        # Compute R-squared
        ss_res = np.sum(self._resid**2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        self._rsquared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Compute adjusted R-squared
        n = len(y)
        k = len(coefficients) - 1  # Exclude intercept
        if n > k + 1:
            self._rsquared_adj = 1 - (1 - self._rsquared) * (n - 1) / (n - k - 1)
        else:
            self._rsquared_adj = self._rsquared

        # Compute additional metrics
        self._rmse = np.sqrt(np.mean(self._resid**2))
        self._mae = np.mean(np.abs(self._resid))

        # Lazy-initialized attributes
        self._influence = None
        self._params_series = None
        self._pvalues_series = None
        self._std_errors = None

    @property
    def params(self) -> pd.Series:
        """Coefficient values as Series with feature names as index."""
        if self._params_series is None:
            self._params_series = pd.Series(
                self._coefficients, index=self._feature_names
            )
        return self._params_series

    @property
    def pvalues(self) -> pd.Series:
        """P-values from bootstrap test"""
        if self._pvalues_series is None:
            p_vals = self._calculate_bootstrap_pvalues()
            self._pvalues_series = pd.Series(p_vals, index=self._feature_names)
        return self._pvalues_series

    @property
    def rsquared(self) -> float:
        """R-squared value."""
        return self._rsquared

    @property
    def rsquared_adj(self) -> float:
        """Adjusted R-squared value."""
        return self._rsquared_adj

    @property
    def nobs(self) -> int:
        """Number of observations."""
        return len(self._y)

    @property
    def fittedvalues(self) -> np.ndarray:
        """Fitted values (predictions on training data)."""
        return self._fittedvalues

    @property
    def resid(self) -> np.ndarray:
        """Residuals (observed - fitted)."""
        return self._resid

    def _calculate_bootstrap_pvalues(self) -> np.ndarray:
        """
        Calculate p-values from bootstrap distribution using percentile method.

        Returns:
            Array of p-values for each coefficient
        """
        eps = 1e-12  # Small constant to avoid division by zero
        # Calculate standard errors from bootstrap (for summary table)
        std_errors = np.std(self._bootstrap_coefs, axis=0)
        self._std_errors = std_errors
        p_values = []
        for i, coef in enumerate(self._coefficients):
            boot_dist = self._bootstrap_coefs[:, i]
            if coef == 0:
                # Coefficient constrained to zero by NNLS
                p_val = 1.0
            else:
                p_val = np.mean(boot_dist <= eps)
            p_values.append(p_val)
        return np.array(p_values)

    def conf_int(self, alpha: float = 0.05) -> pd.DataFrame:
        """
        One-sided confidence interval using bootstrap percentile method.

        Args:
            alpha: Significance level (default 0.05 for 95% CI)

        Returns:
            DataFrame with columns [0, 1] for lower and upper bounds
        """
        lower_percentile = 100 * (alpha / 2)
        upper_percentile = 100 * (1 - alpha / 2)
        conf_intervals_low = np.percentile(
            self._bootstrap_coefs, lower_percentile, axis=0
        )
        conf_intervals_high = np.percentile(
            self._bootstrap_coefs, upper_percentile, axis=0
        )
        ci_df = pd.DataFrame(
            {0: conf_intervals_low, 1: conf_intervals_high}, index=self._feature_names
        )
        return ci_df

    def summary(self) -> str:
        """
        Generate formatted summary table (statsmodels-style).

        Returns:
            Multi-line string with regression summary
        """
        width = 78
        lines = []

        # Header
        lines.append("=" * width)
        lines.append(f"{'NNLS Regression Results':^{width}}")
        lines.append("=" * width)
        lines.append(
            f"Dep. Variable:          {self._dep_var}"
            f"{'R-squared:':>{width - 54}}{self.rsquared:>15.3f}"
        )
        lines.append(
            f"Model:                  NNLS"
            f"{'Adj. R-squared:':>{width - 43}}{self.rsquared_adj:>15.3f}"
        )
        lines.append(
            f"No. Observations:       {self.nobs:<7}"
            f"{'RMSE:':>{width - 46}}{self._rmse:>15.2f}"
        )
        lines.append(
            f"Df Residuals:           {self.nobs - len(self.params):<7}"
            f"{'MAE:':>{width - 46}}{self._mae:>15.2f}"
        )
        lines.append(f"Df Model:               {len(self.params) - 1:<7}")
        lines.append("=" * width)

        # Coefficient table
        lines.append(
            f"{'':>14}{'coef':>12}{'std err':>12}{'P-value':>12}{'[0.025':>12}{'0.975]':>12}"
        )
        lines.append("-" * width)

        ci = self.conf_int()
        for name in self._feature_names:
            coef = self.params[name]
            pval = self.pvalues[name]
            ci_low = ci.loc[name, 0]
            ci_high = ci.loc[name, 1]
            se = self._std_errors[self._feature_names.index(name)]

            lines.append(
                f"{name:>14}{coef:>12.4f}{se:>12.4f}{pval:>12.3f}"
                f"{ci_low:>12.4f}{ci_high:>12.4f}"
            )

        lines.append("=" * width)
        lines.append(
            f"Notes: Non-negative least squares with bootstrap inference "
            f"({len(self._bootstrap_coefs)} iterations)"
        )
        lines.append("=" * width)

        return "\n".join(lines)

    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Make predictions on new data.

        Args:
            X: Feature matrix (may or may not include constant column)

        Returns:
            Array of predictions
        """
        # Convert DataFrame to array if needed
        if isinstance(X, pd.DataFrame):
            X = X.values

        # Check if X has constant column
        if X.shape[1] == len(self._feature_names) - 1:
            # No constant column - add it
            X_with_const = np.column_stack([np.ones(len(X)), X])
        else:
            X_with_const = X

        return X_with_const @ self._coefficients
