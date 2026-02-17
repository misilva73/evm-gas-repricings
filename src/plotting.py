import os
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib
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


def create_and_save_1dim_nnls_regression_plot(
    op_df: pd.DataFrame,
    result,  # NNLSResults type
    opcode: str,
    client: str,
    out_dir: str,
) -> None:
    """
    Create and save 1D regression plot for NNLS model.

    Args:
        op_df: Original data with "opcount" and "run_duration_ms"
        result: NNLS regression results
        opcode: Operation code name for title
        client: Client name for title
        out_dir: Output directory for saving plot
    """
    intercept = result.params["const"]
    slope = result.params["opcount"]
    # Plot scatterplot with data
    fig = plt.figure(figsize=(10, 4))
    sns.scatterplot(data=op_df, x="opcount", y="run_duration_ms")
    # Plot NNLS regression line
    X_range = np.linspace(op_df["opcount"].min(), op_df["opcount"].max(), 100)
    X_range_df = pd.DataFrame({"opcount": X_range})
    y_pred = result.predict(X_range_df)
    plt.plot(X_range, y_pred, color="red", linewidth=2, label="NNLS Regression line")
    plt.xlabel("Opcode Count")
    plt.ylabel("Run Duration (ms)")
    plt.title(
        f"NNLS Linear Regression for {opcode} in {client}\n"
        f"Intercept: {intercept:.2f}, Slope: {slope:.2e}\n"
        f"Non-negative coefficients constraint"
    )
    plt.legend()
    # Save plot
    fig.savefig(
        os.path.join(out_dir, "figs", f"{opcode}_{client}_regression.png"),
        dpi=144,
        bbox_inches="tight",
    )
    plt.close("all")


def create_and_save_multidim_nnls_regression_plot(
    op_df: pd.DataFrame,
    result,  # NNLSResults type
    opcode: str,
    client: str,
    out_dir: str,
    all_features: List[str],
) -> None:
    """
    Create and save multi-dimensional regression plot for NNLS model.

    Args:
        op_df: Original data
        result: NNLS regression results
        opcode: Operation code name
        client: Client name
        out_dir: Output directory
        all_features: All features including "opcount"
    """
    features = list(set(all_features).difference(set(["opcount"])))
    # Process regression features
    feature_df = op_df.copy()
    feature_df[features] = feature_df[features].astype(float)
    # Get regression slope and intercept
    intercept = result.params["const"]
    slope = result.params["opcount"]
    # Create grid plot
    fig, axes = plt.subplots(
        1, len(features), figsize=(4 * len(features), 4), constrained_layout=True
    )
    # for each feature, plot the actual vs. fitted
    for i, feature in enumerate(features):
        ax = axes[i] if len(features) > 1 else axes
        unique_param_values = sorted(feature_df[feature].unique())
        colors = matplotlib.color_sequences["Set2"][: len(unique_param_values)]
        for idx, param_val in enumerate(unique_param_values):
            subset = feature_df[feature_df[feature] == param_val]
            ax.scatter(
                subset["opcount"],
                subset["run_duration_ms"],
                alpha=0.6,
                s=20,
                color=colors[idx],
                label=f"{feature}={param_val}",
            )
            # Plot fitted line for this parameter value
            x_range = np.array([subset["opcount"].min(), subset["opcount"].max()])
            y_fit = (
                result.params["const"]
                + result.params["opcount"] * x_range
                + result.params[feature] * param_val * x_range
            )
            ax.plot(x_range, y_fit, "--", color=colors[idx], alpha=0.8, linewidth=2)
        ax.set_xlabel("opcount")
        ax.set_ylabel("run_duration_ms")
        ax.set_title(f"{feature}: {result.params[feature]:.2e}")
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)
    plt.suptitle(
        f"NNLS: Run duration vs opcount by feature ({opcode} - {client})\n"
        f"Intercept: {intercept:.2f}, Slope: {slope:.2e}"
    )
    # Save plot
    fig.savefig(
        os.path.join(out_dir, "figs", f"{opcode}_{client}_regression.png"),
        dpi=144,
        bbox_inches="tight",
    )
    plt.close("all")


def create_and_save_nnls_diagnostic_plots(
    result,  # NNLSResults type
    opcode: str,
    client: str,
    out_dir: str,
) -> None:
    """
    Create and save 2x2 diagnostic plot panel for NNLS model.
    """
    # Get values and fits
    y = result._y
    y_pred = result._fittedvalues
    residuals = result._resid
    # Start figure
    fig, axes = plt.subplots(2, 2, figsize=(10, 10))
    # 1. Actual vs Predicted
    axes[0, 0].scatter(y, y_pred, alpha=0.5, s=10)
    axes[0, 0].plot([y.min(), y.max()], [y.min(), y.max()], "r--", lw=2)
    axes[0, 0].set_xlabel("Actual run_duration_ms")
    axes[0, 0].set_ylabel("Predicted run_duration_ms")
    axes[0, 0].set_title("Actual vs Predicted")
    axes[0, 0].grid(True, alpha=0.3)
    # 2. Residuals vs Predicted
    axes[0, 1].scatter(y_pred, residuals, alpha=0.5, s=10)
    axes[0, 1].axhline(y=0, color="r", linestyle="--", lw=2)
    axes[0, 1].set_xlabel("Predicted run_duration_ms")
    axes[0, 1].set_ylabel("Residuals")
    axes[0, 1].set_title("Residuals vs Predicted")
    axes[0, 1].grid(True, alpha=0.3)
    # 3. Residuals histogram
    axes[1, 0].hist(residuals, bins=50, edgecolor="black", alpha=0.7)
    axes[1, 0].axvline(x=0, color="r", linestyle="--", lw=2)
    axes[1, 0].set_xlabel("Residuals")
    axes[1, 0].set_ylabel("Frequency")
    axes[1, 0].set_title("Residual Distribution")
    axes[1, 0].grid(True, alpha=0.3)
    # 4. Q-Q plot
    probplot(residuals, dist="norm", plot=axes[1, 1])
    axes[1, 1].set_title("Normal Q-Q Plot")
    axes[1, 1].grid(True, alpha=0.3)
    # Dynamic title based on configuration
    title = f"NNLS Model Diagnostics for {opcode}"
    if client:
        title += f" ({client})"
    plt.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    # Save plot
    fig.savefig(
        os.path.join(out_dir, "figs", f"{opcode}_{client}_diagnostics.png"),
        dpi=144,
        bbox_inches="tight",
    )
    plt.close("all")


def create_and_save_nnls_bootstrap_diagnostic(
    result,  # NNLSResults type
    opcode: str,
    client: str,
    out_dir: str,
) -> None:
    """
    Create and save bootstrap coefficient distribution plot.

    Shows histogram of bootstrap coefficients with confidence intervals.
    This helps visualize coefficient stability and the effect of the
    non-negativity constraint.

    Args:
        result: NNLS regression results with bootstrap_coefs
        opcode: Operation code name
        client: Client name
        out_dir: Output directory
    """
    # Access bootstrap coefficients
    bootstrap_coefs = result._bootstrap_coefs
    feature_names = result._feature_names
    coefficients = result._coefficients
    ci = result.conf_int()
    # Create grid of histograms
    n_features = len(feature_names)
    fig, axes = plt.subplots(1, n_features, figsize=(4 * n_features, 4))
    # Handle single feature case
    if n_features == 1:
        axes = [axes]
    for i, feature_name in enumerate(feature_names):
        ax = axes[i]
        # Plot histogram of bootstrap coefficients
        unique_samples = len(np.unique(bootstrap_coefs[:, i]))
        if len(np.unique(bootstrap_coefs[:, i])) > 1:
            ax.hist(
                bootstrap_coefs[:, i],
                bins=min(50, int(unique_samples/2)),
                alpha=0.7,
                edgecolor="black",
                color="skyblue",
            )
        # Add vertical lines for actual coefficient and CI bounds
        ax.axvline(
            coefficients[i],
            color="red",
            linewidth=2,
            label=f"Estimate: {coefficients[i]:.4f}",
        )
        ax.axvline(
            ci.loc[feature_name, 0],
            color="orange",
            linestyle="--",
            linewidth=1.5,
            label=f"95% CI",
        )
        ax.axvline(
            ci.loc[feature_name, 1], color="orange", linestyle="--", linewidth=1.5
        )
        ax.set_xlabel("Coefficient Value")
        ax.set_ylabel("Frequency")
        ax.set_title(f"{feature_name}")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    plt.suptitle(
        f"Bootstrap Coefficient Distributions for {opcode} ({client})",
        fontsize=14,
        fontweight="bold",
    )
    plt.tight_layout()
    # Save plot
    fig.savefig(
        os.path.join(out_dir, "figs", f"{opcode}_{client}_bootstrap.png"),
        dpi=144,
        bbox_inches="tight",
    )
    plt.close("all")
