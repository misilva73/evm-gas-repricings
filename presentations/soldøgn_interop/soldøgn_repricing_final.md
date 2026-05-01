---
marp: true
title: Soldøgn benchmarking results
author: Maria Silva
footer: ❄️ Soldøgn Interop 2026
theme: gaia
---

<!-- _class: lead invert -->

# Soldøgn interop

## Benchmarking results

# 🔎

---

<!-- _class: lead invert -->

# How we estimate gas costs for EIP-7904 and EIP-8038?

# 🤔

---

## Methodology recap

- Per-client NNLS regression on benchmark data → per-op runtime (ms)
- Glue-opcode contribution subtracted from the slope
- Worst-case across tests → worst-case across clients
- Gas = `anchor_rate × runtime_ms / 1000`
  - **Amsterdam anchor**: 100 M gas/s → 🧑‍⚖️

---

<!-- _class: lead invert -->

# EIP-7904 numbers

# 🗃️

---

<style scoped>
section { font-size: 28px; }
h2 { font-size: 48px; }
</style>

## EIP-7904 proposed gas

| Opcode | Param | Current | New | Change |
|---|---|---:|---:|---:|
| ECRECOVER | constant | 3 000 | 4 088 | **+0.36** |
| KECCAK256 | constant | 30 | 38 | **+0.27** |
| P256VERIFY | constant | 6 900 | 7 179 | **+0.04** |
| POINT_EVALUATION | constant | 50 000 | 91 456 | **+0.83** |
| MULMOD | constant | 8 | 12 | **+0.50** |
| MOD / SDIV / SMOD | constant | 5 | 6 | **+0.20** |

**Note:** `BLS12_G1ADD`,`BLS12_G2ADD`, `BLAKE2F`, `ECADD`, `ECPAIRING`, `ADDMOD`, `DIV` have no changes

---

## Where the worst-case is driven by one client

<style scoped>
section { font-size: 28px; }
h2 { font-size: 48px; }
</style>

| Opcode | Worst client | Worst gas | 2nd worst | 2nd gas | Ratio |
|---|---|---:|---|---:|---:|
| POINT_EVALUATION | erigon | 91 456 | reth | 22 085 | **4.14×** |
| P256VERIFY | erigon | 7 179 | geth | 1 106 | **6.49×** |
| ECRECOVER | erigon | 4 088 | geth | 734 | **5.57×** |

---

<!-- _class: lead invert -->

# EIP-8038 numbers

# 💿

---

<style scoped>
section { font-size: 30px; }
h2 { font-size: 48px; }
</style>

## EIP-8038 proposed gas

| Parameter | Current | New | Change |
|---|---:|---:|---:|
| ACCOUNT_CODE_ACCESS | 2 600 | 69 526 | **+26.7×** |
| ACCOUNT_NOCODE_ACCESS | 2 600 | 40 023 | **+15.4×** |
| ACCOUNT_WRITE | 6 700 | 43 830 | +6.5× |
| STORAGE_ACCESS | 2 200 | 36 027 | **+16.4×** |
| STORAGE_WRITE | 2 800 | 45 366 | **+16.2×** |

> The needed increases are significant... But they are driven by a single client.

---

<style scoped>
section { font-size: 30px; }
h2 { font-size: 48px; }
</style>

## EIP-8038 proposed gas — second-worst client

| Parameter | Current | New | Change | 2nd-worst client |
|---|---:|---:|---:|---|
| ACCOUNT_CODE_ACCESS | 2 600 | 6 084 | **+2.3×** | reth |
| ACCOUNT_NOCODE_ACCESS | 2 600 | 4 007 | +1.5× | geth |
| ACCOUNT_WRITE | 6 700 | 25 644 | **+3.8×** | reth |
| STORAGE_ACCESS | 2 200 | 3 110 | +1.4× | geth |
| STORAGE_WRITE | 2 800 | 2 637 | ×0.94 | geth |

> Pricing by second-worst client, the increases shrink dramatically: `STORAGE_WRITE` would actually *decrease*, and most others land at 1.4–3.8× rather than 15–27×.

---

## Gains to be had still...

- Reth and Besu improve account writes → `ACCOUNT_WRITE` drops to ~6700 (no cost increase)

- Reth improves account reads to contracts → `ACCOUNT_CODE_ACCESS` drops to ~5000 (1.9x increase)

---

<!-- _class: lead invert -->

# 🐈

## Thank you
