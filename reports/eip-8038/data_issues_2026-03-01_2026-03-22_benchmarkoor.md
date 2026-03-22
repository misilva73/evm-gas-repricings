# Data Issues — 2026-03-01 to 2026-03-22 Benchmarkoor Run

Analysis of the runtime estimation results from
`./runtime_estimation/2026-03-01_2026-03-22_benchmarkoor/`.

## 1. Nethermind: Severely Undersampled + Anomalous Runtimes

- Only **10 observations** per variant (vs 30 for other clients), and 809 total
  `test_account_access` rows vs 2430 for others.
- `EXISTING_CONTRACT` variants show **near-zero runtimes** (~4–28 ms mean)
  compared to other account modes (~80–2500 ms), resulting in essentially zero
  slopes and poor R² values (0.0–0.78). This suggests the benchmark is not
  actually exercising cold account access for this variant on nethermind.
- Paradoxically, `EXISTING_EOA` shows very high runtimes (~2400 ms for
  `CACHE_TX`/`NO_CACHE`) — **much higher than `EXISTING_CONTRACT`** — which is
  the opposite of what you'd expect (accessing a contract should be at least as
  expensive as accessing an EOA).

## 2. Reth: `EXISTING_CONTRACT` Anomaly

- For `CACHE_TX` and `NO_CACHE` with `EXISTING_CONTRACT`, reth shows **huge
  intercepts** (~3600–4200 ms) and **low R²** (~0.42–0.81). This suggests a
  large fixed overhead unrelated to opcount, making the linear model a poor fit.
- CALL/CALLCODE slopes (~0.10 ms/op) are **~2x higher** than
  BALANCE/EXTCODESIZE/DELEGATECALL/STATICCALL (~0.05 ms/op) in the same variant.
  This divergence doesn't appear in other clients where these opcodes have
  similar cold-access costs.
- `CACHE_PREVIOUS_BLOCK` behaves normally (small intercepts, high R², slopes
  ~0.001) — the issue is specific to the uncached variants.

## 3. `GAS_WARM_ACCESS` Dominated by Glue Adjustment

For `GAS_WARM_ACCESS`, the glue adjustment often **exceeds or nearly equals** the
raw slope:

| Client     | Runtime (ms) | Glue Adj. (ms) | Ratio (glue/runtime) |
| ---------- | ------------ | --------------- | -------------------- |
| besu       | 0.024        | 0.096           | 4.0x                 |
| geth       | 0.041        | 0.051           | 1.3x                 |
| nethermind | 0.020        | 0.019           | 1.0x                 |
| reth       | 0.046        | 0.056           | 1.2x                 |

The warm access cost estimate is essentially `slope − glue`, where glue is large
and uncertain. The resulting value of **2731 gas** (26x increase from 100) is
highly sensitive to glue estimation errors.

## 4. `GAS_COLD_ACCOUNT_WRITE` — Mostly Non-Significant

The `update` coefficient (used for write cost) is **zero with p-value = 1.0** for
besu, geth, and reth across all variants. Only nethermind shows a non-zero value
(~0.001 ms). The benchmark cannot distinguish the write cost from zero for 3 of 4
clients — the `GAS_COLD_ACCOUNT_WRITE = 59` proposal is based entirely on
nethermind.

## 5. `GAS_COLD_STORAGE_WRITE` — Large Spread Across Clients

| Client     | New Gas (Rounded) |
| ---------- | ----------------- |
| reth       | 2736              |
| geth       | 251               |
| besu       | 177               |
| nethermind | 71                |

A **39x spread** between reth and nethermind. The final proposal (2736) is
entirely driven by reth, and the besu and nethermind fits are flagged as
non-significant.

## 6. EXTCODECOPY Slopes Are ~30–40x Lower Than Other Opcodes

In `test_account_access`, EXTCODECOPY slopes are dramatically lower than
BALANCE/EXTCODESIZE/etc. (e.g., besu NO_CACHE EXISTING_CONTRACT: 0.006 vs ~0.20).
This is expected if EXTCODECOPY measures something different (data copy rather
than account lookup), but it means this test may not be providing useful
cold-access data for EXTCODECOPY.

## 7. Besu Worst-Case Drives Final Proposals

Besu is the worst-case client for 4 of 6 parameters:

- `GAS_COLD_ACCOUNT_CODE_ACCESS` (11636 gas, besu)
- `GAS_COLD_ACCOUNT_NOCODE_ACCESS` (9474 gas, besu)
- `GAS_COLD_STORAGE_ACCESS` (6106 gas, besu)
- `GAS_WARM_ACCESS` (1438 gas, besu — though reth is worst overall at 2731)

Besu slopes are often **5–10x higher** than geth for the same test. The final
proposal is therefore essentially a "besu proposal" for most parameters.
