# Project Instructions

## Python Environment

Always activate the conda environment before running Python commands:

```
conda activate evm-gas-simulator
```

## Testing

Use pytest for running tests. Tests live in the `tests/` directory.

```
python -m pytest tests/ -v
```

## Project Structure

- **`src/`** — Core Python modules for data processing, analysis, and report generation.
- **`notebooks/`** — Jupyter notebooks for exploratory analysis, numbered by topic area (0.x = EDA, 1.x = opcode timing, 2.x = repricing analysis, 3.x = EIP-8038)
- **`reports/`** — Markdown reports organized by EIP (`eip-7904/`, `eip-8037/`, `eip-8038/`), plus standalone reports. Figures in `reports/figures/`.
- **`tests/`** — Pytest tests mirroring `src/` module structure
- **`data/`** — Benchmark data files (not checked into git)

## Formatting

All Python code (`src/`, `tests/`) and notebooks (`notebooks/`) must use [**black**](https://black.readthedocs.io/) formatting with default settings.

## Conventions

- When editing **notebooks**, read `.claude/CONVENTIONS_NOTEBOOKS.md` first.
- When editing **reports**, read `.claude/CONVENTIONS_REPORTS.md` first.
