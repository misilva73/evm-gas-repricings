---
marp: true
title: Glamsterdam repricings — EF townhall
author: Maria Silva
footer: Glamsterdam repricings · EF townhall · June 2026
theme: gaia
---

<!-- _class: lead invert -->

# Glamsterdam repricings

## Where we are & what's next

# ⛽

---

<style scoped>
section { font-size: 34px; }
h2 { font-size: 50px; }
</style>

## The goal

- **Scale Ethereum L1 — safely**
- Today's gas costs were set for a much smaller chain
  - Some opcodes are **over-priced** → leaving throughput on the table
  - Some are **under-priced** → creating bottlenecks to increase the block limit
- Repricings anchor gas costs to **measured client performance**

> Without repricings, raising the gas limit risks DoS and unbounded state growth.

---

## What's changing

Glamsterdam ships a **Repricing Meta EIP** — a bundle of changes across four areas:

- **State growth**: make new state more expensive (EIP-8037)
- **State access**: re-price `SLOAD` / `SSTORE` / `*CALL` (EIP-8038)
- **Intrinsic tx cost**: re-price tx base + value transfer (EIP-2780)
- **Compute**: re-price opcodes & precompiles (EIP-7904)
- **Data**: add access-list data cost + increase floor cost (EIP-7976, EIP-7981)

---

<!-- _class: lead invert -->

# Current status

# 📍

---

<style scoped>
section { font-size: 28px; }
h2 { font-size: 44px; }
</style>

## Where each EIP stands

| EIP | Area | Status |
|---|---|---|
| **EIP-8037** | State growth | ✅ In **glamsterdam-devnet** |
| **EIP-7976 / 7981** | Data | ✅ In **glamsterdam-devnet** |
| **EIP-7904** | Compute | 🟢 **Not needed** — BAL optimizations brought all operations **below** current Osaka costs |
| **EIP-8038** | State access | 🟡 Waiting on **BAL optimizations** |
| **EIP-2780** | Intrinsic tx | 🟡 Waiting on **BAL optimizations** |

---

<!-- _class: lead invert -->

# Next steps

# 🛠️

---


<style scoped>
section { font-size: 33px; }
h2 { font-size: 50px; }
</style>

## Three workstreams in flight

1. **Finalize numbers for 8038 + 2780**
   - Land remaining BAL & client optimizations
   - Re-run benchmarks → lock proposed gas tables

2. **Get the rest of the EIPs onto devnet**
   - 8038 and 2780 need to join 8037 + data EIPs

3. **Backwards-compat & review**
   - Backward-compatibility analysis across the full bundle
   - Deeper security review + full benchmarking

---

<!-- _class: lead invert -->

# 🐈

## Thank you

### Questions?
