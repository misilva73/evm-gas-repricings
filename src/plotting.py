import os
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import statsmodels.api as sm
from scipy.stats import probplot
from typing import List


def create_and_save_new_gas_plot(new_gas_df: pd.DataFrame, out_dir: str) -> None:
    # Create the plot
    fig, ax = plt.subplots(figsize=(10, max(8, len(new_gas_df) * 0.05)))
    # Create a combined label for opcode_param for better visualization
    new_gas_df["opcode_param"] = new_gas_df["opcode"] + " (" + new_gas_df["param"] + ")"
    # Sort by opcode and param for better organization
    plot_df = new_gas_df.sort_values(["opcode", "param"]).reset_index(drop=True)
    # Get unique combinations and clients
    unique_combos = plot_df["opcode_param"].unique()
    clients = plot_df["client"].unique()
    # Create color palette
    palette = sns.color_palette("husl", n_colors=len(clients))
    client_colors = dict(zip(clients, palette))
    # Plot each client's data
    for idx, client in enumerate(clients):
        client_data = plot_df[plot_df["client"] == client].copy()
        # Create y-positions with slight offsets for each client to avoid overlap
        y_positions = []
        for opcode_param in client_data["opcode_param"]:
            base_pos = np.where(unique_combos == opcode_param)[0][0]
            # Offset based on client index to spread them out
            offset = (idx - len(clients) / 2) * 0.15
            y_positions.append(base_pos + offset)
        # Plot points and error bars
        ax.errorbar(
            client_data["new_gas_rounded"],
            y_positions,
            xerr=[
                client_data["new_gas_rounded"] - client_data["new_gas_conf_int_low"],
                client_data["new_gas_conf_int_high"] - client_data["new_gas_rounded"],
            ],
            fmt="o",
            label=client,
            color=client_colors[client],
            markersize=6,
            capsize=3,
            capthick=1.5,
            alpha=0.8,
        )
    # Set logarithmic scale for x-axis to handle different scales
    ax.set_xscale("log")
    # Set y-axis labels
    ax.set_yticks(range(len(unique_combos)))
    ax.set_yticklabels(unique_combos)
    ax.set_xlabel("New Gas Cost (Rounded) - Log Scale", fontsize=12)
    ax.set_ylabel("Operation (Parameter)", fontsize=12)
    ax.set_title(
        "New Gas Costs by Client with Confidence Intervals",
        fontsize=14,
        fontweight="bold",
    )
    ax.legend(title="Client", bbox_to_anchor=(1.05, 1), loc="upper left")
    ax.grid(axis="x", alpha=0.3, linestyle="--", which="both")
    ax.grid(axis="y", alpha=0.1, linestyle="-")
    plt.tight_layout()
    plot_path = os.path.join(out_dir, "figs", "gas_costs_by_client.png")
    plt.savefig(plot_path, dpi=144, bbox_inches="tight")
    plt.close()


def create_and_save_1dim_regression_plot(
    op_df: pd.DataFrame,
    result: sm.regression.linear_model.RegressionResultsWrapper,
    opcode: str,
    client: str,
    out_dir: str,
) -> None:
    intercept = result.params["const"]
    slope = result.params["opcount"]
    # Plot scatterplot with data
    fig = plt.figure(figsize=(10, 4))
    sns.scatterplot(data=op_df, x="opcount", y="run_duration_ms")
    # Plot OLS regression line
    X_range = np.linspace(op_df["opcount"].min(), op_df["opcount"].max(), 100)
    X_range_with_const = np.column_stack([np.ones(len(X_range)), X_range])
    y_pred = result.predict(X_range_with_const)
    plt.plot(X_range, y_pred, color="red", linewidth=2, label="OLS Regression line")
    plt.xlabel("Opcode Count")
    plt.ylabel("Run Duration (ms)")
    plt.title(
        f"OLS Linear Regression for {opcode} in {client}\nIntercept: {intercept:.2f}, Slope: {slope:.2e}"
    )
    # Save plot
    fig.savefig(
        os.path.join(out_dir, "figs", f"{opcode}_{client}_regression.png"),
        dpi=144,
        bbox_inches="tight",
    )
    plt.close("all")


def create_and_save_multidim_regression_plot(
    op_df: pd.DataFrame,
    result: sm.regression.linear_model.RegressionResultsWrapper,
    opcode: str,
    client: str,
    out_dir: str,
    all_features: List[str],
) -> None:
    features = list(set(all_features).difference(set(["opcount"])))
    # Process regression features
    feature_df = op_df.copy()
    feature_df[features] = feature_df[features].astype(float)
    # Get regression slope and intercept
    intercept = result.params["const"]
    slope = result.params["opcount"]
    # Create grid plot
    fig, axes = plt.subplots(1, len(features), figsize=(4 * len(features), 4))
    for i, feature in enumerate(features):
        ax = axes[i] if len(features) > 1 else axes
        sns.lineplot(
            data=feature_df,
            x="opcount",
            y="run_duration_ms",
            hue=feature,
            ax=ax,
            errorbar="sd",
            palette="Set2",
        )
        ax.set_title(f"{feature}: {result.params[feature]:.2e}")
    plt.suptitle(
        f"Run duration vs opcount by feature ({opcode} - {client})\nIntercept: {intercept:.2f}, Slope: {slope:.2e}"
    )
    plt.tight_layout()
    # Save plot
    fig.savefig(
        os.path.join(out_dir, "figs", f"{opcode}_{client}_regression.png"),
        dpi=144,
        bbox_inches="tight",
    )
    plt.close("all")


def create_and_save_diagnostic_plots(
    result: sm.regression.linear_model.RegressionResultsWrapper,
    opcode: str,
    client: str,
    out_dir: str,
) -> None:
    # Calculate diagnostic values
    fitted_values = result.fittedvalues
    residuals = result.resid
    influence = result.get_influence()
    standardized_residuals = influence.resid_studentized_internal
    leverage = influence.hat_matrix_diag
    cooks_d = influence.cooks_distance[0]
    # Create 2x2 diagnostic plot panel
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    # Plot 1 (top-left): Residuals vs Fitted Values
    ax1 = axes[0, 0]
    sns.scatterplot(x=fitted_values, y=residuals, alpha=0.6, ax=ax1)
    ax1.axhline(y=0, color="red", linestyle="--", linewidth=1)
    sns.regplot(
        x=fitted_values,
        y=residuals,
        lowess=True,
        scatter=False,
        color="blue",
        ax=ax1,
        line_kws={"linewidth": 2},
    )
    ax1.set_xlabel("Fitted values")
    ax1.set_ylabel("Residuals")
    ax1.set_title("Residuals vs Fitted")
    ax1.grid(True, alpha=0.3)
    # Plot 2 (top-right): Q-Q Plot
    ax2 = axes[0, 1]
    probplot(residuals, dist="norm", plot=ax2)
    ax2.set_title("Normal Q-Q")
    ax2.set_xlabel("Theoretical Quantiles")
    ax2.set_ylabel("Sample Quantiles")
    ax2.grid(True, alpha=0.3)
    # Plot 3 (bottom-left): Scale-Location Plot
    ax3 = axes[1, 0]
    sqrt_abs_std_resid = np.sqrt(np.abs(standardized_residuals))
    sns.scatterplot(x=fitted_values, y=sqrt_abs_std_resid, alpha=0.6, ax=ax3)
    sns.regplot(
        x=fitted_values,
        y=sqrt_abs_std_resid,
        lowess=True,
        scatter=False,
        color="red",
        ax=ax3,
        line_kws={"linewidth": 2},
    )
    ax3.set_xlabel("Fitted values")
    ax3.set_ylabel("√|Standardized residuals|")
    ax3.set_title("Scale-Location")
    ax3.grid(True, alpha=0.3)
    # Plot 4 (bottom-right): Residuals vs Leverage
    ax4 = axes[1, 1]
    sns.scatterplot(x=leverage, y=standardized_residuals, alpha=0.6, ax=ax4)
    ax4.axhline(y=0, color="grey", linestyle="--", linewidth=0.8)
    # Add Cook's distance contours (optional - for points with high influence)
    # Highlight points with high Cook's distance (> 0.5)
    high_cooks_mask = cooks_d > 0.5
    if high_cooks_mask.any():
        high_leverage_idx = np.where(high_cooks_mask)[0]
        for idx in high_leverage_idx:
            ax4.annotate(
                f"{idx}",
                xy=(leverage[idx], standardized_residuals[idx]),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
            )
    ax4.set_xlabel("Leverage")
    ax4.set_ylabel("Standardized Residuals")
    ax4.set_title("Residuals vs Leverage")
    ax4.grid(True, alpha=0.3)
    # Add overall title
    plt.suptitle(f"Diagnostic Plots for {opcode} ({client})", fontsize=16, y=1.00)
    plt.tight_layout()
    # Save plot
    fig.savefig(
        os.path.join(out_dir, "figs", f"{opcode}_{client}_diagnostics.png"),
        dpi=144,
        bbox_inches="tight",
    )
    plt.close("all")
