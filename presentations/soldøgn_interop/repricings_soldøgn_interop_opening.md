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

- **bal-devnet-4** already includes BALs (EIP-7928) and some repricing EIPs:
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

- We **have prelim numbers**, but there is still work to do to finalize them → more info on extended slides

---

<!-- _class: lead invert -->

# What to expect from this week?

# :dart:

---

## Stabilize EIP-8037 (State Growth)

1. Discuss and agree on **open questions** by Monday

2. Update **specs** and EIP by Tuesday

3. Expand **test coverage** by Wednesday

4. Update **client implementations** and merge to glamsterdam-devnet-1 by Thursday

5. **Test and finalize** implementation details by Friday

---

<style scoped>
section { font-size: 33px; }
</style>

## Stabilize EIP-7928 (BAL)

1. **Review rough benchmarks** on the [bal-dashboard](https://nerolation.github.io/bal-dashboard/) by Monday: sanity-check results and fix obvious bugs

2. **Deep-dive individual optimizations** by Tuesday, with main focus on **batch I/O** (directly shapes repricings downstream: 8038, 8037, 2780, …)

3. Cut **stable optimization releases** by Wednesday → unblocks meaningful benchmarks for the 7904 / 8038 repricings

4. Confirm **eth/71 (EIP-8159)** status, and optionally **snap/2 (EIP-8189)**, by Thursday → enables sync testing (snap/2 not required yet)

---

## Get final numbers on EIP-7904 and EIP-8038

1. Work on **optimizations** and merge to bal-devnet-3 by Wednesday (BAL + client outliers)

2. Make all **testing and benchmarking tooling** ready by Wednesday (bal-devnet-3 transition + Jochemnet)

3. Collect **data** during Thursday

4. Decide on a target performance anchor by Thursday (e.g. 100M gas/s)

5. Analyze and agree on **final numbers** by Friday

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

<style scoped>
section { font-size: 30px; display: flex; flex-direction: column; }
h2 { font-size: 48px; }
h1 { text-align: center; font-size: 40px; margin: 0; }
.fistbump { flex: 1; display: flex; align-items: center; justify-content: center; font-size: 110px; }
</style>

## Why are we here?

1. Discuss spec gaps, any open issues and questions.
2. Highlight current key pain points discovered when testing the EIP.
3. Collaborate and harden the EIP-8037 spec.

<div class="fistbump">🛠️🤝</div>

# End goal: finalize the EIP-8037 spec!

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
| **Fixed `cpsb`** + ad hoc forks | Constant within a fork → existing fixture pattern works; the most flexible to adapt to gas limits and observed demand | highest coordination burden on clients and testing for forks; need monitoring tooling and decision matrix for when to fork |

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
section { font-size: 24px; }
h2 { font-size: 40px; }
table { width: 100%; }
</style>

## Key testing issue: refunding into the reservoir

State gas refunds always fill the reservoir, including original charge from compute gas via the spillover mechanism!

### Test matrix = `refund rules × rule combinations × cpsb bands`

| Dimension | Today | Trend |
|---|---|---|
| **Refund rules** | 8 | growing every devnet |
| **Rule combinations** | ~10 worth testing | grows with rule count |
| **cpsb bands** | 17 discrete (100M–1G block_gl) | set by 8037 quantization scheme |

- Each cpsb band can change the execution path for each test.
- Future EIPs that touch state accounting further compound the matrix.
- **Is the best solution journaling?** Defer state accounting checks to end of call/create frame (or end of tx). Removes the need for these rules!

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

#### Does this look correct? 🤔

---

<!-- _class: lead invert -->

# 🐈

## Thank you

---

<style scoped>
section { font-size: 18px; padding-top: 40px; }
h2 { font-size: 36px; margin-bottom: 12px; }
table { width: 100%; font-size: 17px; }
th, td { padding: 6px 10px; }
table th:nth-child(2), table td:nth-child(2) { white-space: nowrap; min-width: 90px; }
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