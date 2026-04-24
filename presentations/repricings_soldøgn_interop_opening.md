---
marp: true
title: Glamsterdam Repricings @ Soldøgn
author: Maria Silva & Toni Wahrstätter
footer: ❄️ Soldøgn Interop 2026
theme: gaia
---

<!-- _class: lead invert -->

# Soldøgn Kickoff

## Execution Layer Track

# ⛽ 💙 ⚽

Maria Silva & Toni Wahrstätter

---

## EIP Overview ✅

- **bal-devenet-4** already includes BALs (EIP-7928) and some repricing EIPs:
  - State growth: EIP-8037
  - Data: EIP-7976, EIP-7981
  - Refunds: EIP-7778

- The spec is mostly **stable**
- We are still working through some details of 8037

---

## EIP Overview 🔨

- **3 Repricing EIPs** are not yet finalized:
  - Compute: EIP-7904
  - State Access: EIP-8038
  - ETH Transfers: EIP-2780 (depends on 8038)

- We are **prelim numbers**, but there is still work to do to finalize them → more info on extended slides

---

<!-- _class: lead invert -->

# What to expect from this week?

# :dart:

---

## Stabilize EIP-8037 (State Growth)

1. We discuss and agree on **open questions** by Monday

2. We update **specs** and EIP by Tuesday

3. We expand **test coverage** by Wednesday

4. We update **client implementations** and merge to glamsterdam-devnet-1 by Thursday

5. We **test and finalize** implementation details by Friday

---

## Stabilize EIP-7928 (BAL)

1. **Review rough benchmarks** on the [bal-dashboard](https://nerolation.github.io/bal-dashboard/) by Monday — sanity-check results and fix obvious bugs

2. **Deep-dive individual optimizations** by Tuesday, with main focus on **batch I/O** (directly shapes repricings downstream: 8038, 8037, 2780, …)

3. Cut **stable optimization releases** by Wednesday → unblocks meaningful benchmarks for the 7904 / 8038 repricings

---

## Get final numbers on EIP-7904 and EIP-8038

1. Clients work on **optimizations** and merge to bal-devenet-3 by Wednesday (BAL + client outliers)

2. We make all **testing and benchmarking tooling** ready by Wednesday (bal-devnet-3 transition + Jochemnet)

3. We collect **data** during Thursday

4. We decide on a target performance anchor by Thursday (e.g. 100M gas/s)

5. We analyze and agree on **final numbers** by Friday

---

<!-- _class: lead invert -->

# 🐈

## Thank you

---

<!-- _class: lead invert -->

# Soldøgn breakout

## EIP-8037

# 💽

Maria Silva

---

## To-do's for EIP-8037

1. Discuss alternatives and trade-offs for the dynamic `cpsb`. Make a final decision.

2. To journal or not to journal?

3. Review byte sizes - are they representative of the clients' DB?

4. Expand and harden tests for 8037, adding more edge cases and worst-case scenarios

---

<!-- _class: lead invert -->

# 1. Dynamic `cpsb`. Wat do?

# 📈

---

<style scoped>
h1 { text-align: center; font-size: 48px;}
</style>

## What's the problem?

- EIP-8037 makes `state_gas_per_byte` a function of `block.gas_limit`
- **Fixture pipeline** for testing execution specs **wasn't designed** for prices that depend on header fields

# ↓

- We require one fixture per gas limit
- Anything that randomizes `env.gas_limit` at consume time is only correct by accident

---

<style scoped>
section { font-size: 22px; }
h2 { font-size: 44px; }
table { width: 100%; }
</style>

## Options

| Option | Pros | Cons |
|---|---|---|
| **Dynamic `cpsb`** (current spec) | Auto-tracks gas-limit changes; bounds state growth without a new EIP each bump | More complicated for testing infra; transitional feature; couple gas costs with block limit |
| **Fixed `cpsb`** (flat repricing) | Constant within a fork → existing fixture pattern works; simpler spec and implementation; best wallet UX | highest risk of over/undershooting cost increase; no growth guarantee under price-inelastic demand |
| **Scheduled `cpsb`** (BPO-style bumps) | Constant within a fork → existing fixture pattern works; still allows `cpsb` to adapt to gas limits; derisked by BPO forks | need to pre-commit to gas limit schedule; requires building the SGPO tooling; coordination burden on clients for minor forks |
| **Fixed `cpsb`** + ad hoc forks | Constant within a fork → existing fixture pattern works; the most flexible to adapt to gas limits and observed demand | Highest coordination burden on clients and testing for forks; need monitoring tooling and decision matrix for when to fork |

---

<!-- _class: lead invert -->

# 2. To journal or not to journal?

# 📰

---

## What's the problem?

- **Guiding principle:** state gas is only charged when **state is actually created**
- Reverts, SSTORE resets, and delete-and-recreate patterns all touch state without creating it
- devnet-3/4 handles each case with an **explicit refund rule** → rule list grows every time a new edge case surfaces
- Alternative: let a **journal / state diff** reconcile net change automatically

---

<style scoped>
section { font-size: 25px; }
h2 { font-size: 50px; }
table { width: 100%; }
h4 { text-align: center; font-size: 40px;}
</style>

## Options

| Option | Pros | Cons |
|---|---|---|
| **1. Explicit refund rules** (current spec) | Already implemented in clients; No spec changes | Test surface grows per edge case; Harder for new EIPs that touch refunds |
| **2. State diff at frame return** (Pawel's proposal) | Single refund rule; More contained bug surface; Mid-execution reservoir stays accurate per frame | Requires a per-frame journal diff in client implementations; More bookkeeping at each frame return |
| **3. State diff at tx end** | Single refund rule; More contained bug surface; More efficient implementation | No mid-tx refund; Txs require higher gas limits to avoid OOG |

#### What do clients think?

---

<!-- _class: lead invert -->

# 3. State byte sizes

# 👁️

---

<style scoped>
section { font-size: 28px; }
h2 { font-size: 44px; }
h4 { text-align: center; font-size: 40px;}
table { width: 100%; }
</style>

## Current costs set by bloatnet measurements

| State entry | Size | Notes |
|---|---|---|
| New account | 112 B | Size of the RLP-encoded account leaf added to the MPT: address-path + nonce + balance + `storageRoot` + `codeHash` + framing |
| New slot | 32 B | Size of RLP-encoded slot value (up to 32 B). Ignores the 32 B slot key stored alongside as the leaf's path. Should it be 64 B? |
| Authorization | 23 B | Byte-exact: delegation designator `0xef0100 ‖ address` (3 + 20 B) written to the authority's code slot by EIP-7702 |

---

#### Does this look correct? 🤔


<!-- _class: lead invert -->

# 🐈

## Thank you

---

<style scoped>
section { font-size: 20px; }
h2 { font-size: 40px; }
table { width: 100%; }
</style>

## Breakdown of the 112B new-account leaf

| Component | Size | Derivation |
|---|---|---|
| **address-path** (HP-encoded) | ~16–33 B | Trie key is `keccak256(address)` = 64 nibbles. After N branch levels, the remaining `64−N` nibbles are hex-prefix encoded into `⌈(64−N)/2⌉ + 1` bytes, plus a 1 B RLP byte-string prefix. Typical mainnet depth ~10 → ~28 B |
| **nonce** (RLP int) | 1 B | Nonce 0 → `0x80`. Small non-zero nonces also 1 B; up to 9 B at max uint64 |
| **balance** (RLP int) | 1–9 B | 0 → 1 B. ~10¹⁸ wei → 8 B int + 1 B RLP prefix = 9 B |
| **`storageRoot`** (RLP 32 B hash) | 33 B | 32 B hash + 1 B RLP prefix (`0xa0`). Equals `EMPTY_TRIE_ROOT` for fresh account |
| **`codeHash`** (RLP 32 B hash) | 33 B | 32 B hash + 1 B RLP prefix (`0xa0`). Equals `keccak256("")` for fresh EOA |
| **framing** (2 RLP list headers) | ~4 B | Account body list `[nonce, balance, storageRoot, codeHash]` ≈ 76 B → 2 B header. Leaf node list `[path, value]` ≈ 110 B → 2 B header |
| **Total** | **~88–113 B** | Two 32 B hashes dominate (~60%); present even with no code / no storage |

---

<!-- _class: lead invert -->

# Soldøgn extra slides

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
  - **Osaka anchor**: 60 M gas/s
  - **Amsterdam anchor**: 100 M gas/s → 🧑‍⚖️

---

<!-- _class: lead invert -->

# Preliminary EIP-7904 numbers

# 🗃️

---

<style scoped>
section { font-size: 25px; }
h2 { font-size: 48px; }
</style>

## EIP-7904 proposed gas - Osaka @ 60Mgas/s

| Opcode | Param | Current | New | Change |
|---|---|---:|---:|---:|
| BLAKE2F | constant | 0 | 48 | NA |
|BLAKE2F|num_rounds|1|1|0.0|
| ECADD | constant | 150 | 382 | +1.55 |
| ECRECOVER | constant | 3000 | 2812 | −0.06 |
| MOD / SDIV / SMOD | constant | 5 | 6 | +0.20 |
| MULMOD | constant | 8 | 12 | +0.50 |
| **P256VERIFY** | constant | 6900 | 15958 | +1.31 |
| POINT_EVALUATION | constant | 50000 | 84081 | +0.68 |

**Note:** `ADDMOD`, `BLS12_G1ADD`, `BLS12_G2ADD`, `DIV`, `KECCAK256`, and `ECRECOVER` have no price changes. `ECPAIRING` had no good fit on this run.

---

## Where the worst-case is driven by one client

<style scoped>
section { font-size: 30px; }
h2 { font-size: 48px; }
</style>

| Opcode | Worst client | Worst gas | 2nd worst | 2nd gas | Ratio |
|---|---|---:|---|---:|---:|
| BLAKE2F | reth | 48 | besu | 17 | **2.8×** |
| ECADD | reth | 382 | erigon | 183 | **2.1×** |
| P256VERIFY | reth | 15958 | geth | 4583 | **3.5×** |

- Three precompiles (BLAKE2F, ECADD, P256VERIFY) are **set by reth**:
  - 2–3.5× above the next client
  - Need to investigate if this can be optimized.
- All other operations have more stable costs across clients.

---

<!-- _class: lead invert -->

# EIP-7904 — Amsterdam vs Osaka

# 🚀

---

<style scoped>
section { font-size: 32px; }
h2 { font-size: 48px; }
</style>

## Amsterdam vs Osaka — besu runtimes (ms)

| Opcode (param) | Osaka | Amsterdam | Osaka/Amst |
|---|---:|---:|---:|
| ECRECOVER | 0.0408 | 0.0111 | 3.7× |
| POINT_EVALUATION | 1.2667 | 0.3787 | 3.3× |
| KECCAK256 (const) | 0.0005 | 0.0001 | ~3.4× |
| ECADD | 0.0001 | 0.0000 | — |
| ADDMOD / MULMOD / DIV | ≤ 0.0002 | ≤ 0.0002 | ~1.5–1.9× |

> Amsterdam runs **~3–4× faster** on heavy precompiles, but only **~1.5–2×** on cheap arithmetic.

---

<style scoped>
section { font-size: 32px; }
h2 { font-size: 48px; }
</style>

## Amsterdam vs Osaka — geth runtimes (ms)

| Opcode (param) | Osaka | Amsterdam | Osaka/Amst |
|---|---:|---:|---:|
| ECRECOVER | 0.0461 | 0.0127 | 3.6× |
| POINT_EVALUATION | 1.3487 | 0.3655 | 3.7× |
| ECADD | 0.0029 | 0.00004 | **80×** |
| KECCAK256 (const) | 0.0004 | 0.0001 | 4.4× |
| MULMOD / MOD | ≤ 0.0002 | ≤ 0.0000 | ~3.6–3.8× |

> geth speed-up is uniform **~3.5–4×** across all ops (vs besu, which is only ~1.5–2× on cheap arithmetic). `ECADD` is an outlier.

---

## Amsterdam vs Osaka — takeaways

- BAL-optimised runs are **~3–4× faster** on compute-heavy precompiles for both besu and geth.

- For these heavy ops, the +67% anchor rate does **not** compensate → Amsterdam worst-case gas is **~0.5×** Osaka's.

- On **cheap arithmetic opcode**  besu's speed-up is only **~1.5–2×**, so the anchor bump roughly cancels out → gas stays **flat or slightly up**.

---

<!-- _class: lead invert -->

# Preliminary EIP-8038 numbers

---

<style scoped>
section { font-size: 32px; }
h2 { font-size: 48px; }
</style>

## EIP-8038 proposed gas - Osaka @ 60Mgas/s

| Parameter | Current | New | Change |
|---|---:|---:|---:|
| ACCOUNT_CODE_ACCESS | 2 600 | 21 457 | +7.3× |
| ACCOUNT_NOCODE_ACCESS | 2 600 | 10 591 | +3.1× |
| ACCOUNT_WRITE | 6 700 | 224 268 | **+32.5×** |
| STORAGE_ACCESS | 2 200 | 191 667 | **+86×** |
| STORAGE_WRITE | 2 800 | 149 032 | **+52×** |

> Increases are significant! But they are measured from bloatnet and don't take BALs into account...

---

<style scoped>
section { font-size: 22px; }
h2 { font-size: 44px; }
table { width: 100%; }
</style>

## Slow vs fast clients per parameter

| Parameter | Slow group | Fast group | Slow/Fast |
|---|---|---|---:|
| ACCOUNT_CODE_ACCESS | besu<br>21 457 | reth, geth, nethermind, erigon<br>271 – 5 496 | **~9×** |
| ACCOUNT_NOCODE_ACCESS | besu, nethermind<br>10 366 – 10 591 | geth, erigon, reth<br>83 – 2 531 | **~11×** |
| ACCOUNT_WRITE ¹ | erigon, reth<br>117 838 – 224 268 | geth, nethermind<br>4 550 – 5 056 | **~36×** |
| STORAGE_ACCESS | erigon, reth<br>184 711 – 191 667 | geth, nethermind, besu<br>9 925 – 12 722 | **~17×** |
| STORAGE_WRITE ¹ | erigon, reth<br>104 522 – 149 032 | geth, nethermind<br>3 890 – 8 389 | **~21×** |

> Each parameter splits clients into a slow and fast group **~10–35× apart**. The slow group is **besu (± nethermind)** on account access and **erigon + reth** on writes / storage access.

¹ besu excluded (no statistically significant fit).

---

## EIP-8038 — takeaways

- Per-client spread is **much larger** than for 7904: orders of magnitude between fastest and slowest.

- Proposal is driven by **different outlier clients per parameter** — besu, erigon, nethermind and reth each drive at least one worst-case.

---

<!-- _class: lead invert -->

# 🐈

## Thank you
