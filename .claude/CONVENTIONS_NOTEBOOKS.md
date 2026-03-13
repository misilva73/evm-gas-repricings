# Notebook Conventions

When creating or editing Jupyter notebooks in the `notebooks/` folder, follow these conventions:

## Naming

- Use the format `{major}.{minor}-{descriptive_snake_case_name}.ipynb` (e.g., `2.6-eip-8037-agg-function-analysis.ipynb`). Increment the major number for new topic areas, minor for new notebooks within a topic. Use a `_v2`, `_v3` suffix for revised versions of the same analysis.

## Structure

- **First cell**: A markdown cell with a `# Title` heading describing the analysis. Include `#### Maria Silva, {Month Year}` as a byline when creating new notebooks.
- **Second cell**: Imports cell — import all libraries upfront (os, numpy, pandas, seaborn, matplotlib, warnings, plus any project-specific modules). Suppress warnings with `warnings.filterwarnings("ignore")`.
- **Third cell**: Set the seaborn plotting theme and define directory paths:

  ```python
  sns.set_theme(style="whitegrid", palette="Set2", rc={"figure.dpi": 500, "axes.titlesize": 15})

  current_path = os.getcwd()
  repo_dir = os.path.abspath(os.path.join(current_path, ".."))
  ```

  For notebooks that import from `src/`, also add `sys.path.append(src_dir)`.
- **Section headers**: Use markdown cells with `## Section Title` to separate logical sections of the analysis. Use `###` subsections within sections.
- **Narrative markdown cells**: Add brief markdown cells between code cells to explain findings, flag anomalies, or motivate the next analysis step. Keep these concise — a sentence or two, or a small markdown table summarizing results.
- **Summary cell**: End investigative notebooks with a markdown cell summarizing key findings, often using markdown tables and bullet points.

## Plotting

- Use **seaborn** as the primary plotting library (`sns.boxplot`, `sns.barplot`, `sns.relplot`, `sns.stripplot`, `sns.heatmap`), with matplotlib for layout (`plt.subplots`, `plt.figure`).
- Always set descriptive `plt.title()`, `plt.xlabel()`, and `plt.ylabel()`.
- Use `plt.tight_layout()` before `plt.show()`.
- For multi-panel figures, use `plt.subplots(nrows, ncols, figsize=(...))`.
- Use LaTeX in labels where appropriate (e.g., `r"State price elasticity ($\varepsilon_s$)"`).
- When saving figures, use `plt.savefig(path, bbox_inches="tight")`.

## Data handling

- Use **pandas** for all data manipulation. Load data with `pd.read_csv()` from paths relative to `repo_dir`.
- Use `df.info()`, `display()`, and `df.describe()` to show data summaries.
- Use `groupby().agg()` patterns for summaries, `melt()` for reshaping, `pivot_table()` for cross-tabulations.
- When filtering or processing data, assign to new variables rather than modifying in place (e.g., `compute_df = df[df["test_opcode"].isin(compute_ops_list)]`).

## Code style

- Define helper functions within the notebook when reused across cells, with docstrings.
- Use f-strings for print statements with descriptive labels.
- Use `round()` or `.round()` when displaying numeric results.
