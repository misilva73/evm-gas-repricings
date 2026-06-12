# Scaling in Hegota: using the ETH transfer to anchor execution and bandwidth

### Maria Silva, June 2026

This report works out what Hegota needs to change to keep scaling the gas limit after Glamsterdam. It builds on the propagation/execution crossover from our [block composition throughput report](./block_composition_throughput.md) and the floor/BAL pricing menu from the [Hegota bandwidth repricing report](./bandwidth_repricing_hegota.md), takes the [Glamsterdam repricing bundle](./glamsterdam_gas_repricing_bundles.md) as the frozen execution anchor, and informs the Hegota settings for the calldata floor (EIP-7976/7981), `CPSB` (EIP-8037), and bandwidth pricing (EIP-7999). The starting point is a single observation: the 21,000-gas ETH transfer bounds *both* dimensions of the slot.

- On the execution side, the Glamsterdam repricings pushed costs as far as the transfer cap permits, fixing worst-case execution at 100 Mgas/s.
- On the bandwidth side, a block full of transfers is itself a data payload (envelopes, signatures, and BAL entries) that no pricing instrument can touch without touching 21k.

We therefore use the transfer-full block as the *anchor block*. We derive its bandwidth performance, find the PTC deadline that maximizes the gas limit, compare it against the adversarial calldata + `SLOAD` block, and then ask what this implies for state growth, history, and memory.

## Key findings

- **The 21k ETH transfer anchors both sides of the slot.** It freezes worst-case execution at 100 Mgas/s *and* sets an irreducible byte density of ~0.0105 B/gas (221 B per transfer, worst-case) that no pricing instrument can undercut. The anchor block propagates at ~214 Mgas/s, so it is execution-bound, and solving both ceilings at a symmetric 25% buffer gives **~473M with the PTC deadline at ~5.7s**. We treat the 25% buffer as a guideline, not a hard floor, and relax it slightly to land on round numbers: we recommend **500M at $D = 5.5$s**, which runs the anchor block at a ~23% worst-case execution buffer and a ~17% propagation buffer. This number is gated on the bandwidth fix below: under Glamsterdam pricing the densest *priced* block — not the transfer — binds the slot and caps the limit at ~339M.
- **Hegota's bandwidth job is to bring every *priced* composition down to the transfer line.** Since we cannot reprice the transfer without touching the 21k cap, the goal is to make it the worst case by construction. Glamsterdam pricing fails this: the mixed calldata + `SLOAD` block sits at ~2.2× the line and pins the system at ~339M, ~134M below the anchor optimum. The solution is to raise the calldata floor again (64 → 96) plus coverage of BAL bytes, or introduce a single uniform calldata rate (~94) — trading mechanism complexity against incidence breadth. This is the fork's one open mechanism decision.
- **Below the transfer line, only further optimizations move the optimum.** Pricing can equalize compositions at the line but cannot go beneath it. Each 10% improvement in the propagation time per kb increases the gas limit by roughly +15–20M, up to a max of 693M. In parallel, improvements in the execution time of ETH transfers would allow higher execution anchors, thus permitting higher limits without changing the PTC deadline.
- **The remaining fork items are one constant each.** Re-derive `CPSB` (1,530 → ~5,100; otherwise state grows ~400 GiB/yr), make history expiry operational (~3.3 TB/yr at the new limit), consider repricing `LOGDATA` (currently 8 gas/byte), and change nothing for memory.

## Background

Glamsterdam ships ePBS ([EIP-7732](https://eips.ethereum.org/EIPS/eip-7732)), BALs ([EIP-7928](https://eips.ethereum.org/EIPS/eip-7928)), and the repricing bundle, including the data-pricing EIPs [7976](https://eips.ethereum.org/EIPS/eip-7976) (calldata floor 64/64, standard 4/16) and [7981](https://eips.ethereum.org/EIPS/eip-7981) (access-list bytes at the floor rate). The repricings targeted a worst-case execution performance of 100 Mgas/s. This target cannot be raised further: doing so would require repricing the gas cost of an ETH transfer to go above its 21,000, which would break functionality in some hardware wallets. So for Hegota, the 100 Mgas/s execution anchor is frozen, and additional scale has to come from the optimizations (both in execution and propagation), changes in the PTC deadline, and (separately) from making overpriced compute operations cheaper. That last option is analyzed in parallel and only enters this report through one interaction noted later.

The assumptions used throughout:

| Parameter | Value | Notes |
|---|---:|---|
| Execution anchor $R$ | 100 Mgas/s | Frozen by the 21k transfer cap |
| Slot end $T_3$ | 12 s | |
| Beacon-block attestation deadline $T_1$ | 2 s (pinned) | Earliest payload propagation start under ePBS; 2s vs 3s still open (sensitivity ~51M per second) |
| Safety buffers | 25% on both the execution and propagation windows | Guideline, not a hard floor; the recommended 500M/5.5s point runs ~23% execution / ~17% propagation |
| Propagation model | $t = 569 + 0.443 \cdot \text{KB}$ ms (p90, MEV-boost) | From Toni's [worst-case block-size analysis](https://github.com/nerolation/glamsterdam-worst-case-block-size/blob/main/payload_propagation.ipynb); snappy-compressed size, measured after release ($p_{90} - \min$). Transfer block treated as incompressible (post-snappy ≈ raw) |
| Cold `SLOAD` | 3,000 | Assumed EIP-8038 landing; unchanged in Hegota |
| Cold account access (`BALANCE`) | 3,300 | Assumed post-Glamsterdam landing; unchanged in Hegota |
| Cold `SSTORE` | 13,000 | Assumed post-Glamsterdam landing; unchanged in Hegota |
| Calldata pricing | 64/64 floor, 4/16 standard | EIP-7976/7981 |
| State creation | `CPSB = 1530`, fixed | Latest [EIP-8037](https://eips.ethereum.org/EIPS/eip-8037) spec (150M reference, 120 GiB/yr) |
| BAL encoding | RLP, minimal-length, per-account | [EIP-7928](https://eips.ethereum.org/EIPS/eip-7928), confirmed |

## A map of the resources

It helps to organize the resources by the *kind* of constraint that bounds them, since that determines how each one responds to a higher gas limit:

| Resource | Constraint type | What happens at a higher limit (Glamsterdam pricing) | Hegota action |
|---|---|---|---|
| Execution | Per-slot, after $D$ | Worst-case execution time grows with $G$; traded against propagation via $D$ | No upward repricing (by assumption) |
| Bandwidth | Per-slot, before $D$ | Worst-case payload grows with $G$; BAL bytes are unpriced | Fork change (this report's core) |
| State growth | Cumulative (disk) | Growth rate grows with $G$ because `CPSB` is fixed | Re-derive `CPSB` (fork item) |
| History | Cumulative (disk + serving) | Grows with $G$ | Expiry prerequisite; `LOGDATA` review |
| Memory | Per-transaction (RAM) | Does not grow with $G$ (bounded per tx by [EIP-7825](https://eips.ethereum.org/EIPS/eip-7825)) | None |

The next sections cover the per-slot trade-off (which sets the gas limit), and we return to the cumulative resources at the end.

## The transfer block as the anchor block

### How many bytes does a transfer carry?

A transfer writes no storage and runs no opcodes, but it still ships bytes: its envelope and signature, plus the records EIP-7928 keeps for it in the BAL.

A type-2 transfer's envelope is ~110 B realistically: the signature (`r`, `s` at 32 B each, plus `y_parity`) is ~65 B and the 20-byte recipient address ~21 B once RLP-framed, leaving ~25 B for the nonce, the two fee fields, gas limit, value, chain id, and the empty access list. We round up to 130 B in the table as a worst-case envelope across current transaction types.

For the BAL, a transfer touches two accounts (sender: balance + nonce; recipient: balance). Because RLP encodes balances minimal-length (≤ 11 B, bounded by total ETH supply, not 32) and nonces in 1–2 B, the worst-case marginal contribution is ~91 B.

| Scenario | Construction | B per transfer | $\beta_t$ (bytes/gas) |
|---|---|---:|---:|
| **Worst-case accounting** | 130 envelope + 91 BAL | 221 | 0.01052 |

The propagation model is calibrated on *post-snappy* bytes, so we map this raw 221 B onto the wire by treating the transfer block as **incompressible** (post-snappy ≈ raw). This is worst-case-safe — signatures are random bytes snappy cannot touch — and is the report's single most consequential assumption: any real compression only loosens the bound and raises the achievable gas limit. Measuring the compressed marginal byte slope on real encoded blocks is the most consequential data task this report identifies.

### Where should the PTC deadline go?

The deadline $D$ splits the slot into a propagation window, from $T_1 = 2$s to $D$, and an execution window, from $D$ to 12s. Holding the 25% buffer guideline on both, a gas limit $L$ is feasible when the anchor block can both propagate and execute in time:

$$ L \le 0.75 \cdot R \cdot (12 - D) \qquad \text{(execution)} $$

$$ 0.443 \cdot \beta_t \cdot \frac{L}{1000} + 569 \;\le\; 0.75 \cdot (D - T_1) \cdot 1000 \qquad \text{(propagation)} $$

The first ceiling falls as $D$ moves later; the second rises. The optimum is the crossover:

| Scenario | $D^*$ (s) | $L^*$ | Payload at $L^*$ |
|---|---:|---:|---:|
| **Worst-case accounting (221 B)** | **5.70** | **473M** | **4.97 MB** |

The transfer-anchored optimum, holding the 25% guideline on *both* windows, is **~473M at $D \approx 5.7$s**. The 25% buffer is a guideline rather than a hard floor, so we relax it slightly to recommend round operating numbers — **500M at $D = 5.5$s**, just above the optimum. The execution buffer barely moves; the propagation buffer absorbs the shortfall, dropping from 25% to ~17% — the anchor block then uses 83% of the propagation window instead of 75%:

| Operating point | Execution buffer | Propagation buffer |
|---|---:|---:|
| 473M @ 5.7s (symmetric optimum) | 25% | 25% |
| **500M @ 5.5s (recommended)** | **~23%** | **~17%** |

The residual uncertainty is in the propagation fit (the p90 percentile and Toni's tail-emphasized versus conservative $\sqrt{n\cdot\text{size}}$ weighting) and the post-snappy compression assumption. Propagation improvements (below) would restore the symmetric 25% buffer at 500M, or push the limit higher.

## The adversarial block

### The transfer block is not the worst case

The transfer block anchors the slot, but it is not the densest block we can build — its $\beta_t \approx 0.0105$ B/gas is a floor, not a ceiling. Since we cannot price the transfer block without touching the 21k cap, our goal is to make it the worst case by construction: **every composition the protocol prices should carry at most $\beta_t$ bytes per gas**. Any priced block above $\beta_t$ binds the slot before the transfer block does and pulls $L^*$ below 473M, so we check each one.

A single-resource block's byte density is its per-operation byte footprint over its gas cost, $\beta = b/c$:

- $1/F$ for calldata at the floor
- $32/c$ for a cold `SLOAD` (32-byte BAL key)
- $20/c$ for a cold account access such as `BALANCE` (20-byte address)
- $64/c$ for a cold `SSTORE` (32-byte key + 32-byte value in the BAL)

The mixed block adds the densest cheap calldata it can — the 16 gas/byte standard rate, up to the share that still stays under the 7976 floor — and fills the rest with cold `SLOAD`s:

$$ \beta(F, c) = \frac{1 - 512/c}{F} + \frac{32}{c} $$

Evaluating the menu at the assumed prices for Glamsterdam (cold `SLOAD` 3,000, cold account access 3,300, cold `SSTORE` 13,000, calldata floor $F = 64$), we get:

| Block | Construction | $\beta$ (B/gas) | × transfer line |
|---|---|---:|---:|
| ETH transfer (anchor) | 221 B / 21,000 gas | 0.01052 | 1.00× |
| Cold `SSTORE` | 64 B / 13,000 | 0.00492 | 0.47× |
| Cold `BALANCE` | 20 B addr / 3,300 | 0.00606 | 0.58× |
| Cold `SLOAD` | 32 B key / 3,000 | 0.01067 | 1.01× |
| Calldata at floor | $1/F$, $F = 64$ | 0.01563 | 1.49× |
| Mixed 25% calldata@16 + 75% `SLOAD` | $\beta(64, 3000)$ | 0.02363 | 2.25× |

**Key observations:**

- **Only cold `SLOAD` rivals the transfer line.** A cold `BALANCE` writes only its 20-byte address to the BAL at 3,300 gas (0.58×), and a cold `SSTORE` writes a 64-byte key+value at 13,000 gas (0.47×) — both comfortably under. The 32-byte storage key paid for by cold `SLOAD`'s 3,000 gas is the byte-densest thing state access can add per gas, which is why the adversarial blocks are built from cold `SLOAD`.
- **Cold `SLOAD` sits essentially on the line.** At 3,000 gas its 32-byte key gives 0.01067 B/gas, 1% above $\beta_t$; the line is reached exactly at $c = 3{,}041$. The assumed EIP-8038 value is within a whisker, so the pure-`SLOAD` block is — for practical purposes — already at the target.
- **Two priced blocks exceed the line: pure calldata (1.49×) and the mixed block (2.25×).** Both overshoot for the same root cause — calldata priced below the transfer line — but, as we show next, they need different fixes.

### The smallest lever: re-raise the calldata floor

The pure-calldata block is over the line for a one-line reason: the EIP-7976 floor of 64 gas/byte implies $1/64 = 0.0156$ B/gas, 49% above $\beta_t$. The floor was sized against execution throughput, not against the transfer's byte density, and it lands too low. The fix is a single constant — raise the floor to

$$ F^* = \left\lceil 1 / \beta_t \right\rceil = \lceil 1 / 0.01052 \rceil = \lceil 95.06 \rceil = 96 \text{ gas/byte}, $$

the smallest floor at which a priced calldata byte costs at least as much gas as a transfer byte. At $F = 96$ the pure-calldata block lands at $1/96 = 0.0104$ B/gas (0.99×), on the line. This is Hegota's cheapest bandwidth change: re-raise the floor 64 → 96.

However, **this still does not fix the mixed block.** Raising $F$ shrinks the cheap-calldata share (from $16/64 = 25\%$ to $16/96 = 16.7\%$) but cannot remove it, and the cold-`SLOAD` remainder keeps riding into the BAL unpriced: $\beta(96, 3000) = 0.0193$ B/gas, still 1.84× the line, with the $F \to \infty$ asymptote pinned at $32/c$ — the `SLOAD` channel itself. No finite calldata floor brings the mixed block down, because the bytes that make it heavy are BAL bytes, not calldata bytes.

### Three ways to tame the mixed block

The residual is the mixed block, at 1.84× the line. We have three options. The first two **price the BAL bytes** the calldata floor cannot see, layered on top of the 64 → 96 floor bump just derived; the third **leaves the BAL unpriced** and instead removes the dual-rate calldata structure the mixed block exploits.

**Option 1: BAL bytes in the floor.** The obvious solution is to start including the BAL bytes in the floor calculation. [This proposal from Toni](https://github.com/ethereum/EIPs/compare/master...nerolation:EIPs:toni/data-repricing) extends the 7623-style floor to every payload byte, including the BAL bytes. Every priced byte then yields at most $1/96$ bytes per gas, with no `SLOAD` change at all. The cost is a new gas-accounting mechanism that keeps a runtime floor accumulator touching every cold-access path. This acts on the floor side only, so normal users and the 21k transfer are untouched.

**Option 2: An intrinsic data surcharge.** Add an explicit data component to every BAL-contributing operation (cold access, cold storage, etc.), with transfers excluded automatically since they run no opcodes. This is constants-only, the simplest mechanism on top of the floor. But pricing the BAL bytes this way is a de facto state-access repricing: bringing the mixed block to the line requires raising cold-state-access costs substantially, which sits awkwardly with the frozen-anchor rationale even though it is execution-safe — and it further misprices the pure-opcode blocks, which are already under the line.

**Option 3: A uniform calldata price, no BAL pricing.** The mixed block works only because calldata has two rates — the cheap 16 gas/byte standard rate, ridden up to the floor share, and the floor above it. Give calldata a single rate $p$ and the exploit vanishes: every calldata byte costs $p$, so the calldata block is bounded at $1/p$ and mixing it into a state block only dilutes the density. The worst case then reverts to the densest unpriced state op — cold `SLOAD` at $32/c$, on the transfer line after EIP-8038, with every other state op well below it (table above). So $p$ only needs to stop pure calldata from beating `SLOAD`:

$$ \frac{1}{p} \le \frac{32}{c} \;\Rightarrow\; p \ge \frac{c}{32} \approx 94 \text{ gas/byte} \quad (c = 3{,}000). $$

This is barely under the floor's 96: **dropping the floor changes who pays, not the rate.** A floor of 96 bites only data-heavy transactions; a uniform 94 charges every calldata byte the floor rate — a ~6× rise on the 16 standard rate. In exchange it is the simplest mechanism (one rate, no BAL accounting, no `max()`).

The choice is between mechanism complexity and incidence breadth. Option 1 has the smallest impact on users — it only affects blocks that exceed the calldata floor — but it introduces a new gas-accounting and OOG mechanism that will likely not be needed after [EIP-7999](https://eips.ethereum.org/EIPS/eip-7999). Options 2 and 3 are both constants-only changes, but they affect every user of BAL-affecting operations (option 2) or every user of calldata (option 3). Option 3 is the cleanest and most defensible, since the operations that produce BAL bytes already have the correct price for both their execution and their bandwidth cost. The mixed block only exploits the dual-rate structure of calldata, so removing that is a direct fix without needing to touch the BAL bytes at all.

## What if propagation gets faster?

Pricing can equalize compositions at the transfer line but cannot go below it. Past that point, only the propagation model itself can move, through mempool-based payload reconstruction (most payload bytes already sit in peers' mempools), gossip and topology improvements, or erasure-coded dissemination. Re-running the central crossover with an $x\%$ better slope:

| Slope improvement | $D^*$ (s) | $L^*$ |
|---:|---:|---:|
| — (0.443 ms/KB) | 5.70 | 473M |
| −10% | 5.49 | 488M |
| −20% | 5.27 | 505M |
| −30% | 5.03 | 523M |
| −40% | 4.78 | 542M |
| −50% | 4.51 | 562M |
| Overhead halved (569 → 285 ms) only | 5.44 | 492M |

The pattern is roughly **+15–20M of gas limit per 10% of slope improvement**, with the deadline drifting earlier in step; the $D = 5$s neighborhood arrives at about −30%, worth ~523M, and −40% reaches ~542M. Halving the fixed overhead (569 → 285 ms) is worth about one slope-decile on its own (~+19M). Note that transfer-heavy payloads are the least compressible shape (signatures are random bytes), so compression-based improvements help the adversarial tail more than the anchor block itself.

The hard ceiling of this whole framing is execution: as $D$ approaches $T_1$ plus the fixed overhead, the execution window saturates at ~9.2s, i.e. **693M** at 75% of 100 Mgas/s. Going beyond that requires raising real execution throughput, which is what the parallel analysis on repricing overpriced compute operations addresses. That work couples back to this report in one place: cheaper execution pushes more transactions onto the calldata floor, so floor incidence at $F = 96$ should be evaluated against post-repricing execution costs.

## Implications for the other resources

### State growth: re-derive `CPSB`

The latest EIP-8037 spec fixes `CPSB = 1530`, derived at a 150M reference limit for a 120 GiB/yr target, and explicitly defers re-derivation to a subsequent fork. Left at 1,530, the target-rate growth at a 500M limit would be ~400 GiB/yr. Using the spec's own derivation at the new limits, we get:

| Operating point | `CPSB` | New slot (64 B) | New account (120 B) | 24 KiB deploy |
|---:|---:|---:|---:|---:|
| 500M | ~5,100 | 326k | 612k | 125M state-gas |
| 562M (p2p stretch) | ~5,730 | 367k | 688k | 141M state-gas |

The transfer is untouched either way, since only new-account creation pays state gas, in the separate dimension with the reservoir model.

There is also the question of how real demand will respond to the higher block limit and increased `CPSB`. The final value will likely be different once we observe how users adapt to the Glamsterdam fork.

### History: expiry becomes a prerequisite

At 500M, average payload history runs ~3.3 TB/yr before expiry (scaling the ~90 kB-at-36M average linearly). This counts transaction payload only: the ~90 kB baseline predates BALs, so the figure above omits them. BALs (EIP-7928) are a second history channel of comparable size — ~41% of a transfer block's bytes, and dominant for the state-access-heavy compositions — but EIP-7928 permits pruning stored BALs to their hash root, so their *durable* contribution depends on the retention window (full during the serving window, hash-commitment only afterward).

At these history growth rates, rolling history expiry (EIP-4444-family) therefore needs to be operational before the limit moves. Separately, `LOGDATA` at 8 gas/byte is now the cheapest byte in the system and exempt from every floor, because logs live in receipts rather than the payload. We may want to price it more accurately. The organizing principle is to price bytes by lifetime: payload bytes at the floor, history bytes consistently with the expiry horizon, state bytes at `CPSB`.

### Memory: nothing to do

Worst-case EVM memory is a per-transaction quantity: quadratic expansion cost against the EIP-7825 cap bounds a single frame at ~3–4 MB, and memory is freed between sequentially executed transactions. A higher block limit adds transactions per block, not concurrent memory. This only changes if the 7825 cap is raised or linear-memory pricing (EIP-7923/7686) ships without a compensating limit.

## What Hegota actually ships

| # | Item | Type |
|---|---|---|
| 1 | Gas limit → ~500M, $D = 5.5$s | Validator coordination, gated on 2–5 |
| 2 | Calldata floor 64 → 96 | One constant (7976/7981) |
| 3 | Mixed-block fix: BAL floor pair, intrinsic surcharge, or uniform calldata price (~94) | The one open mechanism decision |
| 4 | `CPSB` re-derivation: 1,530 → ~5,100 (~5,730 at p2p stretch) | One constant, per the 8037 spec's process |
| 5 | History expiry operational | Networking/client prerequisite |
| 6 | `LOGDATA` 8 → ? | One-constant candidate, after measurement |
| 7 | p2p slope/overhead improvements | Non-fork track: +15–20M per 10% slope, up to ~562M |
| 8 | Downward compute repricings | Fork item, parallel analysis |

## Limitations

- All propagation numbers inherit Toni's **p90 MEV-boost** fit ($569 + 0.443 \cdot \text{KB}$ ms, snappy-compressed size, measured after release as $p_{90} - \min$) and the $T_1 = 2$s pin; both are choices, not givens. Toni's conservative $\sqrt{n\cdot\text{size}}$ weighting gives a steeper slope (and the Local / higher-percentile fits steeper still), each of which pulls the optimum down; the crossovers move ~51M per second of $T_1$ and proportionally with the slope.
- The per-transfer byte figure is derived from the confirmed RLP minimal-length encoding, so framing overhead is resolved; but Toni's propagation model is calibrated on *post-snappy* bytes and we assume the transfer block is **incompressible** (post-snappy ≈ raw 221 B). Real wire compression and the `block_access_index` width's growth with transaction count remain unmodeled and move every headline number — compression in particular only loosens the bound and raises $L^*$.
- The crossover model treats propagation and execution as strictly serial with hard 25% buffers; pipelining or overlapping validation would shift the optimum outward.
- The 8037 figures follow the live spec (`CPSB = 1530`); the local EIPs repo still carries the older auto-scaling draft, whose numbers do not apply.
- History projections scale today's average payload linearly with the gas limit; composition shifts (blob adoption, real BAL sizes) will move them.
