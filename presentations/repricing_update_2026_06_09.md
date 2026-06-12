---
marp: true
title: Repricing update — 2026-06-09
author: Maria Silva
footer: Repricing update · June 2026
theme: gaia
---

<!-- _class: lead invert -->

# Repricing update

## Latest results — 7904, 8038, 2780

# 📊

---

## This week in one slide

- **EIP-7904** — results are stable, full client coverage. **Recommend dropping the EIP.** ✅
- **EIP-8038** — writes are still expensive across the board. 💿
- **EIP-2780** — **3 of 5 clients now clear the 21k baseline** for ETH transfers. 💸
- **Cross-cutting** — latest 8038 & 2780 runs use the new **schelk** suite; mixed results

> Dashboards: misilva73.github.io/eip-{2780,7904,8038}-repricing

---

<!-- _class: lead invert -->

# EIP-7904

## Stable — time to drop it

# ⚡

---

## EIP-7904 — headline

- **16 of 18** priced parameters **reduced** vs. current Osaka
- Only **1 increase**: `PRECOMPILE_BLAKE2F_BASE` (0 → 94) — still negligible
- **Full client coverage now** — erigon runs have landed (was the open blocker)
- Only **1 poor-fit selection** left (`BLAKE2F_PER_ROUND` / reth)

> Results have held steady across runs → **recommend closing EIP-7904**.

---

<!-- _class: lead invert -->

# EIP-8038

## Writes are still expensive

# 💿

---

<style scoped>
section { font-size: 30px; }
h2 { font-size: 44px; }
</style>

## EIP-8038 — writes + code access still high

| Gas param | Current | Proposed | Diff % | 2nd-worst |
|---|---:|---:|---:|---:|
| `STORAGE_WRITE` | 2 800 | 15 391 (reth) | **+450%** | 13 948 (erigon) |
| `ACCOUNT_WRITE` | 6 700 | 22 866 (erigon) | **+241%** | 9 047 (reth) |
| `COLD_ACCOUNT_CODE_ACCESS` | 2 600 | 9 131 (erigon) | +251% | 3 484 (besu) |

> Even dropping the worst client, writes stay **3–5× current**. All other parameters require milder increases, so they are fine.

> Can we improve accesses to accounts with code?

---

<style scoped>
section { font-size: 25px; }
h2 { font-size: 42px; }
</style>

## EIP-8038 — schelk run: mixed movements

Per-client selected gas, **prev → latest (schelk)**. **Bold = worst-case client driving the proposal:**

| Param | besu | erigon | geth | nethermind | reth |
|---|---:|---:|---:|---:|---:|
| `COLD_STORAGE_ACCESS` | −2% | −2% | **−10%** | −39% | +3% |
| `COLD_ACCOUNT_NOCODE` | +33% | −2% | **−22%** | −14% | +14% |
| `STORAGE_WRITE` | −16% | −12% | −87% | −14% | **−10%** |
| `ACCOUNT_WRITE` | −6% | **−20%** | +26% | −12% | −45% |

> Movements are mixed, not one client. besu and reth each slow on two params; geth improves sharply on `STORAGE_WRITE` (−87%) but worsens on `ACCOUNT_WRITE` (+26%). **Worst-case drivers are unchanged — geth and erigon; besu drives none of these.**

---

<!-- _class: lead invert -->

# EIP-2780

## 3 clients now clear 21k

# 💸

---

<style scoped>
section { font-size: 24px; }
h2 { font-size: 42px; }
</style>

## EIP-2780 — who clears the 21,000 baseline?

`VALUE_TRANSFER` per client across cases (latest schelk run):

| Client | Range across cases | Worst case | Status |
|---|---|---|---|
| besu | 24k – 26k | Contract (unique code) | over |
| erigon | 41k – 65k | Contract | over |
| **geth** | 15k – 20k | Contract | **below** |
| **nethermind** | 11k – 16k | Contract (unique code) | **below** |
| **reth** | 12k – 18k | Contract (unique code) | **below** |

> Worst-case overall flipped to **erigon** (was besu). geth dropped **−73%** vs the previous run.

---

<style scoped>
section { font-size: 26px; }
h2 { font-size: 44px; }
</style>

## EIP-2780 — schelk run: top of the field slows slightly

Worst-case per client, **prev → latest (schelk)**. **Bold = worst-case driver:**

| Client | `TX_BASE` | `VALUE_TRANSFER` |
|---|---:|---:|
| **erigon** | **35 268 (+14%)** | **65 322 (+3%)** |
| besu | 13 744 → 16 771 (+22%) | 23 690 → 26 330 (+11%) |
| geth | 61 189 → 9 757 (−84%) | 73 366 → 19 744 (−73%) |
| nethermind | −4% | −7% |
| reth | +9% | −32% |

> besu and erigon both slow at the top (besu by more), but **erigon stays the worst case on all three params**. geth improves dramatically (−73% to −84%), dropping below 21k.

---

## EIP-2780 — way forward

- How much can clients optimize on the worst cases?
- Do we need to reframe to EIP?
  - Can ETH transfers be cheaper than 21k?

**What needs to be done:**

- `TX_BASE` targets 10,000
- `VALUE_GAS` targets 7,000

---

<style scoped>
section { font-size: 30px; }
h2 { font-size: 40px; }
</style>

## EIP-2780 — `TX_BASE` target 10,000

| Client | Worst-case gas | Binding case | Status |
| --- | ---: | --- | --- |
| reth | 16,663 | jumpdest contract | ❌ must optimize |
| besu | 16,771 | jumpdest contract | ❌ must optimize |
| nethermind | 13,405 | jumpdest contract | ❌ must optimize |
| erigon | 35,268 | jumpdest contract | ❌ must optimize |
| **geth** | **9,757** | jumpdest contract | ✅ already under 10k |

> The binding case is `diff_to_unique_code_jumpdest_contract` - can we improve accesses to accounts with code?

---

<style scoped>
section { font-size: 30px; }
h2 { font-size: 40px; }
</style>

## EIP-2780 — `VALUE_GAS` target 7,000

| Client | Worst-case gas | Binding case | Status |
| --- | ---: | --- | --- |
| **reth** | **5,820** | diff_to_contract | ✅ already under 7k |
| **nethermind** | **4,009** | diff_to_nonexistent | ✅ already under 7k |
| geth | 10,434 | diff_to_contract | ❌ must optimize |
| besu | 13,726 | diff_to_nonexistent | ❌ must optimize |
| erigon | 31,020 | diff_to_contract | ❌ must optimize |

> Improving on writes again

---

<!-- _class: lead invert -->

# 🐈

## Thank you

### misilva73.github.io/eip-{2780,7904,8038}-repricing
