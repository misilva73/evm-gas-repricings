---
marp: true
title: Repricing update — 2026-08-03
author: Maria Silva
footer: Repricing update · August 2026
theme: gaia
---

<!-- _class: lead invert -->

# Repricing update

## ACDT #90, August 3rd, 2026

# 📊

---

## What changed in the benchmarks

- **New account test cases** — `test_account_access` and ether transfers now cover contracts of different byte sizes (`MINIMAL`, `SAME_MAX`, `DIFF_MAX`, `JUMPDEST`) and **delegated** (7702) accounts
- **State Actor snapshot** — benchmarks now run against a worst-case DB
- **glamsterdam-devnet-7**

---

## Key impacts on the repricing numbers

- **Account cases got more expensive** 📈 — both for access and ETH transfers
- **ETH transfers cannot get more expensive** 🔒 — 21000 is a hard ceiling
- **So the anchor moves: 100 → 75 Mgas/s** ⚓ — the only lever left to absorb the more expensive account cases
- **Storage operations can get cheaper** 💿 — with a lower anchor, storage reads can be made cheaper

---

<style scoped>
table { font-size: 30px; }
</style>

## New goals at 75 Mgas/s — what changes

| Param | EIP | Current EIP | New goal | Δ |
|---|---|---:|---:|---:|
| `COLD_STORAGE_ACCESS` | 8038 | 3 000 | **2 100** | **−30%** |
| `ACCOUNT_WRITE` | 8038 | 8 000 | **9 000** | **+13%** |
| `COLD_ACCOUNT_ACCESS` | 8038 | 3 000 | 3 000 | — |
| `STORAGE_WRITE` | 8038 | 10 000 | 10 000 | — |
| `WARM_ACCESS` | 8038 | 100 | 100 | — |
| `TX_BASE_COST` | 2780 | 12 000 | 12 000 | — |
| `TX_VALUE_COST` | 2780 | 6 000 | 6 000 | — |

---

<!-- _class: lead invert -->

# Repricing results

# 📊

---

<style scoped>
table { font-size: 20px; }
</style>

## Repricing results at 75 Mgas/s - EIP-2780

| Goal | Target | Besu | Erigon | Ethrex | Geth | Nethermind | Reth |
|---|---:|---:|---:|---:|---:|---:|---:|
| Transfer to self | 12,000 | 🟩 10,583 | 🟨 13,616 (+13.5%) | 🟩 3,446 | 🟩 8,999 | 🟩 11,454 | 🟩 3,207 |
| No-value transfer | 15,000 | 🟩 14,326 | 🟥 24,453 (+63.0%) | 🟩 11,408 | 🟩 13,051 | 🟨 15,286 (+1.9%) | 🟩 5,212 |
| Transfer | 21,000 | 🟨 24,543 (+16.9%) | 🟥 35,087 (+67.1%) | 🟩 13,433 | 🟨 21,817 (+3.9%) | 🟩 17,956 | 🟩 7,437 |
| No-value transfer to delegated account | 18,000 | 🟩 14,071 | 🟨 22,675 (+26.0%) | 🟩 11,267 | 🟩 13,531 | 🟩 15,122 | — |
| Transfer to delegated account | 24,000 | 🟩 20,483 | 🟨 32,582 (+35.8%) | 🟩 13,649 | 🟩 19,217 | 🟩 17,504 | — |

---

<style scoped>
table { font-size: 20px; }
</style>

## Repricing results at 50 Mgas/s - EIP-2780

| Goal | Target | Besu | Erigon | Ethrex | Geth | Nethermind | Reth |
|---|---:|---:|---:|---:|---:|---:|---:|
| Transfer to self | 12,000 | 🟩 7,055 | 🟩 9,078 | 🟩 2,297 | 🟩 5,999 | 🟩 7,636 | 🟩 2,138 |
| No-value transfer | 15,000 | 🟩 9,551 | 🟨 16,302 (+8.7%) | 🟩 7,605 | 🟩 8,701 | 🟩 10,191 | 🟩 3,475 |
| Transfer | 21,000 | 🟩 16,362 | 🟨 23,391 (+11.4%) | 🟩 8,956 | 🟩 14,545 | 🟩 11,971 | 🟩 4,958 |
| No-value transfer to delegated account | 18,000 | 🟩 9,381 | 🟩 15,117 | 🟩 7,512 | 🟩 9,021 | 🟩 10,081 | — |
| Transfer to delegated account | 24,000 | 🟩 13,656 | 🟩 21,721 | 🟩 9,099 | 🟩 12,812 | 🟩 11,670 | — |

---

<style scoped>
table { font-size: 20px; }
</style>

## Repricing results at 75 Mgas/s - EIP-8038

| Operation | Goal | Besu | Erigon | Ethrex | Geth | Nethermind | Reth |
|---|---:|---:|---:|---:|---:|---:|---:|
| COLD_STORAGE_ACCESS | 3,000 | 🟢 1,489 | 🟢 471 | 🟢 988 | 🟢 1,615 | 🟢 686 | 🟢 305 |
| STORAGE_WRITE | 10,000  | 🟢 7,354 | 🟡 14,371 | 🟢 0 | 🟢 7,106 | 🟢 2,662 | 🟢 90 |
| COLD_ACCOUNT_ACCESS (CODE) | 3,000 | 🟡 3,564 | 🔴 11,682 | 🔴 7,680 | 🟡 3,164 | 🟢 2,843 | 🟢 1,777 |
| COLD_ACCOUNT_ACCESS (NOCODE) | 3,000 | 🟢 2,544 | 🟢 655 | 🟢 1,380 | 🟢 1,621 | 🟢 831 | 🟢 357 |
| ACCOUNT_WRITE (CODE) | 8,000  | 🟡 10,426 | 🔴 15,555 | 🟢 6,986 | 🟡 8,923 | 🟢 4,434 | 🟢 1,315 |
| ACCOUNT_WRITE (NOCODE) | 8,000  | 🟡 10,426 | 🔴 14,589 | 🟢 616 | 🟡 8,923 | 🟢 4,434 | 🟢 1,079 |
| WARM_ACCESS | 100 | 🟢 34 | 🟢 9 | 🟢 8 | 🟢 14 | 🟢 37 | 🟢 5 |

---

<style scoped>
table { font-size: 20px; }
</style>

## Repricing results at 50 Mgas/s - EIP-8038

| Operation | Goal | Besu | Erigon | Ethrex | Geth | Nethermind | Reth |
|---|---:|---:|---:|---:|---:|---:|---:|
| COLD_STORAGE_ACCESS | 3,000 | 🟢 993 | 🟢 314 | 🟢 659 | 🟢 1,077 | 🟢 458 | 🟢 204 |
| STORAGE_WRITE | 10,000  | 🟢 3,903 | 🟢 8,581 | 🟢 0 | 🟢 3,738 | 🟢 775 | 🟢 0 |
| COLD_ACCOUNT_ACCESS (CODE) | 3,000 | 🟢 2,376 | 🔴 7,788 | 🟡 5,120 | 🟢 2,110 | 🟢 1,895 | 🟢 1,185 |
| COLD_ACCOUNT_ACCESS (NOCODE) | 3,000 | 🟢 1,696 | 🟢 437 | 🟢 920 | 🟢 1,081 | 🟢 554 | 🟢 238 |
| ACCOUNT_WRITE (CODE) | 8,000  | 🟢 5,951 | 🟡 11,370 | 🟢 3,657 | 🟢 4,949 | 🟢 1,956 | 🟢 0 |
| ACCOUNT_WRITE (NOCODE) | 8,000  | 🟢 5,951 | 🟡 10,726 | 🟢 0 | 🟢 4,949 | 🟢 1,956 | 🟢 0 |
| WARM_ACCESS | 100 | 🟢 23 | 🟢 6 | 🟢 5 | 🟢 10 | 🟢 25 | 🟢 3 |

---

<style scoped>
section { font-size: 25px; }
h2 { font-size: 38px; }
table { font-size: 23px; }
</style>

## Full suite: who clears 75 Mgas/s?

| Client | Compute below (of 2038) | Stateful below (of 374) | Slowest test |
|---|---:|---:|---:|
| reth | 0 | 0 | 120 Mgas/s |
| nethermind | 0 | 14 (3.7%) | 68 |
| ethrex | 1 | 25 (6.7%) | 29 |
| geth | 0 | 38 (10.2%) | 50 |
| erigon | 6 | 71 (19.0%) | 1.1 |
| besu | 0 | 87 (23.3%) | 40 |

- **Cold account access dominates** — 12 tests fail for 5+ clients, all `test_account_access`. Note: this was with current EIP numbers
- **Ether transfers to on-chain receivers** are marginal for besu (32), erigon (32), geth (10), nethermind (2).

---

## Next steps

- **Freeze the repricing numbers** for 8038 and 2780 at the 75 Mgas/s anchor ❄️
- **Expand the full benchmark suite** to nail down the gas limit for Glamsterdam 📈
  - issue tracker: https://github.com/ethereum/execution-specs/issues/3281

---

<!-- _class: lead invert -->

# 🐈

## Thank you

### misilva73.github.io/eip-{2780,8038}-repricing
