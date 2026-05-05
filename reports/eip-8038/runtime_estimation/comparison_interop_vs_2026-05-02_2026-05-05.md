# EIP-8038 Runtime Estimation: Run Comparison

Comparison of `new_gas_rounded` between two runtime-estimation runs:

- **interop**: `reports/eip-8038/runtime_estimation/2026-04-28_2026-05-01_interop/new_gas.csv`
- **latest**: `reports/eip-8038/runtime_estimation/2026-05-02_2026-05-05/new_gas.csv`

Δ = latest − interop. %Δ relative to interop. Erigon excluded.

`GAS_WARM_ACCESS` only appears in the latest run, not in the interop run.

## GAS_COLD_STORAGE_ACCESS

| Client     |     interop |      latest |          Δ |     %Δ |
|------------|------------:|------------:|-----------:|-------:|
| besu       |         892 |       2,630 |     +1,738 |  +195% |
| geth       |       3,110 |       3,652 |       +542 |   +17% |
| nethermind |       1,429 |      16,096 |    +14,667 | +1,027%|
| reth       |       1,420 |         182 |     −1,238 |   −87% |

## GAS_COLD_STORAGE_WRITE

| Client     |    interop |      latest |          Δ |       %Δ |
|------------|-----------:|------------:|-----------:|---------:|
| besu       |      1,092 |      10,922 |     +9,830 |    +900% |
| geth       |      2,637 |     179,722 |   +177,085 |  +6,716% |
| nethermind |        615 |       5,582 |     +4,967 |    +808% |
| reth       |      1,887 |      28,116 |    +26,229 |  +1,390% |

## GAS_COLD_ACCOUNT_NOCODE_ACCESS

| Client     | interop | latest |     Δ |   %Δ |
|------------|--------:|-------:|------:|-----:|
| besu       |   2,628 |  2,795 |  +167 |  +6% |
| geth       |   4,007 |  4,147 |  +140 |  +3% |
| nethermind |   2,849 |  2,691 |  −158 |  −6% |
| reth       |     155 |    153 |    −2 |  −1% |

## GAS_COLD_ACCOUNT_CODE_ACCESS

| Client     | interop | latest |     Δ |   %Δ |
|------------|--------:|-------:|------:|-----:|
| besu       |   4,967 |  4,551 |  −416 |  −8% |
| geth       |   4,007 |  4,147 |  +140 |  +3% |
| nethermind |   5,304 |  4,960 |  −344 |  −6% |
| reth       |   6,084 |  6,458 |  +374 |  +6% |

## GAS_COLD_ACCOUNT_WRITE

| Client     | interop | latest |       Δ |    %Δ |
|------------|--------:|-------:|--------:|------:|
| besu       |  10,836 | 10,508 |    −328 |   −3% |
| geth       |   6,713 |  6,196 |    −517 |   −8% |
| nethermind |   3,997 |  2,934 |  −1,063 |  −27% |
| reth       |  25,644 | 28,143 |  +2,499 |  +10% |

## Differences between the two runs

To localize where the parameter shifts originate, we drilled into `test_sstore_bloated` — the test that drives the cold-storage parameters — and compared its three input artefacts across the two runs.

### Trace data is identical

For `test_sstore_bloated`, both runs contain the same 20 fixture rows (10 × `update_0` + 10 × `update_1`, all `NO_CACHE`, `existing_slots=True`). A cell-by-cell comparison across all 147 numeric per-opcode columns in `trace_data.csv` shows zero differences (`abs_diff_sum = 0` on every column). Total `opcount` per row matches exactly.

### Glue opcode ratios are identical

The per-test glue ratios in `glue_opcodes_by_test.csv` for `test_sstore_bloated` are identical to the precision stored:

| glue_opcode | interop ratio | latest ratio |
|-------------|--------------:|-------------:|
| DUP1        |      2.000000 |     2.000000 |
| DUP2        |      1.999719 |     1.999719 |
| JUMPDEST    |      1.000000 |     1.000000 |
| JUMPI       |      0.999860 |     0.999860 |
| LT          |      0.999860 |     0.999860 |
| PUSH1       |      1.953613 |     1.953613 |
| SWAP1       |      0.880795 |     0.880795 |

### Bench timings moved drastically

The shift is concentrated in `gas_bench_data.csv` `run_duration_ms`. Per-(client, `test_params`) mean run duration:

| Client     | Params   | interop n | interop mean (ms) | latest n | latest mean (ms) |   ×change |
|------------|----------|----------:|------------------:|---------:|-----------------:|----------:|
| besu       | update_0 |        80 |           1,160.5 |      150 |          2,752.1 |  **2.4×** |
| besu       | update_1 |        80 |           1,149.4 |      150 |          5,356.5 |  **4.7×** |
| geth       | update_0 |       110 |           1,471.5 |      160 |          2,803.6 |  **1.9×** |
| geth       | update_1 |       110 |           1,474.4 |      160 |         53,853.1 | **36.5×** |
| nethermind | update_0 |        70 |             415.8 |       90 |         12,639.3 | **30.4×** |
| nethermind | update_1 |        70 |             424.8 |       90 |          7,734.4 | **18.2×** |
| reth       | update_0 |        30 |           1,030.4 |       90 |            156.6 |  **0.2×** |
| reth       | update_1 |        30 |           1,073.3 |       90 |          9,800.1 |  **9.1×** |

**Key observations:**

- **The blow-up is in the bench measurements, not in fixture selection or the trace.** Trace counts and glue ratios are byte-identical, so the headline parameter shifts propagate from `run_duration_ms` alone.
- **Sample count grew** from 600 → 980 rows (per-fixture `n` roughly doubles), so the moves are not driven by a small noisy resample — the latest run has more repeats and the means still moved by 1.9× to 36.5×.
- **The two extreme movers — geth `update_1` (×36.5) and nethermind `update_0` (×30.4)** — line up with the headline-table extremes for `GAS_COLD_STORAGE_WRITE` (geth ×68) and `GAS_COLD_STORAGE_ACCESS` (nethermind ×11), consistent with the parameter shifts being a direct consequence of the timing shifts.
- **Reth's split** (update_0 0.2× / update_1 9.1×) mirrors the headline reth quirk where cold-storage *access* fell while *write* spiked.
