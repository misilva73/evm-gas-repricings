# EVM gas repricing analysis

Empirical analysis of EVM gas costs and opcode runtimes, used to derive
repricing proposals for upcoming EIPs (EIP-7904, EIP-8037, EIP-8038, ...).
The analysis combines client benchmark data (Benchmarkoor / gas-bench) with
mainnet state and history measurements to estimate per-opcode execution
times and translate them into proposed gas schedules.

## Repository layout

- **`src/`** — Core Python modules.
  - `data.py` — pulls and processes benchmark data from the gas-bench DB
    and the Benchmarkoor API.
  - `runtime_estimation.py`, `nnls.py`, `glue.py` — opcode runtime
    estimation (NNLS regression and glue-opcode handling).
  - `proposal.py`, `operation_gas_costs.py`, `operation_types.py` —
    repricing-proposal construction and operation metadata.
  - `reports.py`, `plotting.py` — report and figure generation.
  - `estimate_7904_repricings.py`, `estimate_8038_repricings.py` —
    top-level entry points that run the full pipeline for a given EIP.
- **`notebooks/`** — Jupyter notebooks for exploratory analysis, numbered
  by topic (`0.x` = EDA, `1.x` = opcode timing, `2.x` = repricing
  analysis, `3.x` = EIP-8038 state access).
- **`reports/`** — Markdown reports organized by EIP (`eip-7904/`,
  `eip-8037/`, `eip-8038/`), plus standalone reports. Figures live in
  `reports/figures/`.
- **`data/`** — Benchmark and mainnet data files used by the notebooks
  (not checked into git).
- **`tests/`** — Pytest suite mirroring `src/`.
- **`presentations/`** — Slides and supporting material.
- **`requirements.txt`** — Pinned Python dependencies.
- **`secrets.json`** — Local credentials for the Benchmarkoor API (gitignored, see below).

## Running the gas repricing analysis

The end-to-end pipeline for a given EIP is driven by
[src/estimate_7904_repricings.py](src/estimate_7904_repricings.py) and
[src/estimate_8038_repricings.py](src/estimate_8038_repricings.py). They
query benchmark data, fit per-opcode runtime models, and write a full
report (CSVs + figures + markdown) to `reports/eip-<n>/runtime_estimation/`.

### 1. Python environment

The analysis is developed against **Python 3.12**. The recommended setup
is a conda environment named `evm-gas-simulator`:

```bash
conda create -n evm-gas-simulator python=3.12
conda activate evm-gas-simulator
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure credentials

The pipeline reads credentials from a `secrets.json` file at the repo
root. The file is gitignored — create it locally with the following
shape:

```json
{
    "benchmarkoor_bearer_token": "<benchmarkoor bearer token>"
}
```

To obtain a **Benchmarkoor** bearer token:

1. Sign in at [benchmarkoor.com](https://benchmarkoor.com).
2. Open your account settings and create an API key. The key is
   prefixed with `bmk_...`.
3. Paste it as the value of `benchmarkoor_bearer_token` in
   `secrets.json`.

### 4. Set the run parameters

Open the `estimate_*` script for the EIP you want to analyze and edit
the parameters at the top of the `__main__` block. By default, for each
`(network, fork)` combination configured here, the script pulls the most
recent Benchmarkoor suite and filters all runs after `start_date`. To
pin a specific run instead, pass one or more suite hashes via
`compute_suites` / `stateful_suites` — when either list is non-empty,
the `(network, fork)` lookup is skipped for that test type and the
listed suites are loaded directly.

| Parameter          | Meaning                                                                                                                                                          |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `compute_network`  | Snapshot for the compute test suite (`"perf_devnet_3"`, `"jochemnet"`, or `"mainnet"`). Ignored when `compute_suites` is set.                                    |
| `stateful_network` | Snapshot for the stateful test suite (`"perf_devnet_3"`, `"jochemnet"`, or `"mainnet"`). Ignored when `stateful_suites` is set.                                  |
| `compute_suites`   | Optional list of Benchmarkoor suite hashes for the compute runs. When non-empty, these suites are loaded directly and `compute_network` / `fork` are ignored.    |
| `stateful_suites`  | Optional list of Benchmarkoor suite hashes for the stateful runs. When non-empty, these suites are loaded directly and `stateful_network` / `fork` are ignored.  |
| `start_date`       | First date to include when querying Benchmarkoor (`YYYY-MM-DD`). The most recent runs from `start_date` to today are pulled.                                     |
| `fork`             | Fork to filter on: `"osaka"`, `"amsterdam"`, or `None` (no filter). Ignored for any test type that uses an explicit suite list.                                  |
| `run_type`         | Benchmark run mode: `"full"`, `"nobatchio"`, `"sequential"`, or `None`.                                                                                          |
| `anchor_rate`      | Target gas/sec rate used to convert runtimes into gas costs.                                                                                                     |
| `target_token`     | (8038 only) Storage size bucket to evaluate, e.g. `"10GB"`.                                                                                                      |

The output directory is derived automatically from `start_date` and the
current date and lands under
`reports/eip-<n>/runtime_estimation/<start_date>_<today>/`.

### 5. Run

From the repo root, with the conda environment activated:

```bash
python src/estimate_7904_repricings.py
# or
python src/estimate_8038_repricings.py
```

Each script pulls the raw benchmark data, writes `gas_bench_data.csv`
and `trace_data.csv` to the output directory, fits runtime models, and
generates the runtime, glue-opcode, and repricing markdown reports
alongside their figures.

## Testing

```bash
python -m pytest tests/ -v
```

## Formatting

All Python code (`src/`, `tests/`) and notebooks (`notebooks/`) use
[**black**](https://black.readthedocs.io/) with default settings.
