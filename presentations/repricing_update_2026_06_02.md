---
marp: true
title: Repricing update — 2026-06-02
author: Maria Silva
footer: Repricing update · June 2026
theme: gaia
---

<!-- _class: lead invert -->

# Repricing update

## New dashboards & latest results

# 📊

---

<!-- _class: lead invert -->

# What's new

# 🧰

---

## New repricing dashboards

- [EIP-2780 — `TX_BASE` & `VALUE_GAS`](https://misilva73.github.io/eip-2780-repricing/index.html)
- [EIP-7904 — opcode & precompile repricing](https://misilva73.github.io/eip-7904-repricing/index.html)
- [EIP-8038 — state-access repricing](https://misilva73.github.io/eip-8038-repricing/index.html)

> Each: NNLS fits per client, worst-case selection, 100 Mgas/s anchor, trends across runs.

---

## More polished Python tools

- [`benchmarkoor-fetch`](https://github.com/misilva73/benchmarkoor-fetch) — pulls benchmark runs from the upstream API
- [`evm-gasfit`](https://github.com/misilva73/evm-gasfit) — regression + worst-case selection that produces the proposed-gas tables

> The pipeline behind every dashboard above.

---

<!-- _class: lead invert -->

# EIP-7904

## Geth optimizations have landed

# ⚡

---

## EIP-7904 — headline

- **16 of 18** priced parameters could be **reduced** vs. current Osaka
- Only 1 needs an increase (`PRECOMPILE_BLAKE2F_BASE`, 0 → 43), but we can likely ignore it for now

> Signal we wanted: optimizations are performing better than the EIP target

---

## EIP-7904 — caveats before closing

- **Still waiting on Erigon runs to finish** — full client coverage missing
- Several geth fits land as "poor fit" winners (low R²) — they drive the proposal but want firming up
- Need more runs to confirm trends and rule out noise

---

<!-- _class: lead invert -->

# EIP-8038

## Biggest movers since last run

# 💿

---

<style scoped>
section { font-size: 26px; }
h2 { font-size: 44px; }
</style>

## EIP-8038 — trend deltas (prev → latest)

| Parameter | Prev | Latest | Δ | Note |
|---|---:|---:|---:|---|
| `ACCOUNT_WRITE` | 198 390 | 32 261 | **−84%** | erigon got much faster |
| `WARM_ACCESS` | 124 | 78 | **−37%** | flipped from over-priced → under-priced (led by Besu optimizations) |
| `STORAGE_WRITE` | 210 762 | 164 496 | −22% | erigon got much faster; worst-case erigon → geth |
| `COLD_STORAGE_ACCESS` | 2 635 | 3 186 | +21% | worst-case nethermind → geth |
| `COLD_ACCOUNT_*_ACCESS` | 10 353 | 10 256 | flat | erigon still the outlier (2.76×) |

---

<style scoped>
section { font-size: 26px; }
h2 { font-size: 44px; }
</style>

## EIP-8038 — second worst client

| Gas param | Current | New (2nd worst) | Δ% | Client |
|---|---:|---:|---:|---|
| `COLD_STORAGE_ACCESS` | 2 100 | 2 372 | +13% | nethermind |
| `STORAGE_WRITE` | 2 800 | 17 122 | **+511%** | reth |
| `COLD_ACCOUNT_NOCODE_ACCESS` | 2 600 | 3 721 | +43% | reth |
| `ACCOUNT_WRITE` | 6 700 | 16 384 | **+145%** | reth |
| `COLD_ACCOUNT_CODE_ACCESS` | 2 600 | 3 721 | +43% | reth |
| `WARM_ACCESS` | 100 | 66 | −34% | besu |

> Worst clients are geth on storage and erigon on accounts; Writes are still expensive, even ignoring the worst clients.

---

<!-- _class: lead invert -->

# EIP-2780

## Biggest movers since last run

# 💸

---

<style scoped>
section { font-size: 28px; }
h2 { font-size: 44px; }
</style>

## EIP-2780 — worst case is flat

| Parameter | Prev | Latest | Δ |
|---|---:|---:|---:|
| `TX_BASE` | 222 627 | 224 114 | +0.7% |
| `VALUE_GAS` | 733 611 | 735 113 | +0.2% |
| `VALUE_TRANSFER` | 956 237 | 959 227 | +0.3% |

> Driver unchanged: **besu / Contract (unique code)**.

---

<style scoped>
section { font-size: 26px; }
h2 { font-size: 44px; }
</style>

## EIP-2780 — the real movement is one level down

**Erigon got dramatically faster on Contract / Non-existent cases**

| Client / case | Param | Prev | Latest | Δ |
|---|---|---:|---:|---:|
| erigon / Contract | `VALUE_GAS` | 222 629 | 35 960 | **−84%** |
| erigon / Non-existent | `VALUE_GAS` | 174 605 | 22 943 | **−87%** |
| erigon / Contract | `VALUE_TRANSFER` | 235 804 | 66 158 | **−72%** |

**Geth re-entered the run** — now sits second-worst with `VALUE_TRANSFER` ~173k–232k.

---

<style scoped>
section { font-size: 28px; }
h2 { font-size: 44px; }
</style>

## EIP-2780 — who clears the 21,000 baseline?

Worst-case `VALUE_TRANSFER` per client:

| Client | Range across cases | Status |
|---|---|---|
| besu | 461k – 959k | way over |
| geth | 173k – 232k | way over |
| erigon | 37k – 66k | over |
| reth | 23k – 26k | just over |
| **nethermind** | **12k – 17k** | **below 21k in every case** |

---

<!-- _class: lead invert -->

# 🐈

## Thank you

### misilva73.github.io/eip-{2780,7904,8038}-repricing
