# EIP-8037 Reservoir Gas Shift: Analysis

Under EIP-8037's reservoir model, a sequence of `SSTORE 0 → x` followed by `SSTORE x → 0` (in separate frames) lets a transaction shift gas from `gas_left` into `state_gas_reservoir`. This note characterizes the behavior, quantifies it at `CPSB = 1174`, and explores its implications.

## 1. Simplified example

Toy costs: SSTORE regular = 1, state = 6. Calls free.

Initial: `gas_left = 10`, `state_gas_reservoir = 5`.

| Step | gas_left | reservoir |
|---|---|---|
| start | 10 | 5 |
| `SSTORE 0 → x` opcode (regular −1) | 9 | 5 |
| Call 1 frame end: charge 6 state-gas (reservoir drained, 1 spills to gas_left) | 8 | 0 |
| `SSTORE x → 0` opcode (regular −1) | 7 | 0 |
| Call 2 frame end: refund 6 directly to reservoir | 7 | 6 |

The reservoir grew by 1 even though state-gas charge and refund cancel. The asymmetry: when the reservoir is too small at charge time, the charge spills into `gas_left`; when the matching refund returns, it goes entirely to the reservoir, never back to `gas_left`.

## 2. Real costs (CPSB = 1174)

`STATE_BYTES_PER_STORAGE_SET × CPSB = 32 × 1174 = 37,568` state gas per new slot.

| Operation | Regular | State |
|---|---|---|
| `SSTORE 0 → x` (cold) | 5,000 (2,100 + 2,900) | 37,568 (charged at frame end) |
| `SSTORE x → 0` (warm) | 3,000 (100 + 2,900) | refund 37,568 to reservoir |

One cycle on a fresh slot, starting from `reservoir = 0`:

- `gas_left` decreases by **45,568** (8,000 regular + 37,568 state-gas spillover)
- `state_gas_reservoir` increases by **37,568**
- `tx_gas_used` increases by **8,000**

Each fresh slot can be cycled exactly once for the full 37,568 shift. To shift `N × 37,568` gas, the attacker needs `N` distinct slots and pays `N × 8,000` regular gas.

## 3. Implications

### 3.1 Self-paying users — no value extraction

A self-paying user gains nothing from the shift. The reservoir is strictly less flexible than `gas_left`: it covers state-gas charges only, while `gas_left` covers both. Moving gas to the reservoir reduces flexibility and costs 8,000 regular gas per cycle. The trick is strictly suboptimal for any user paying for their own transaction.

The shift only matters when the cost lands on one party while the consumed `gas_left` belongs to another — i.e., when the gas pool is shared (§3.3).

### 3.2 DDoS vector — limited

The trick is bounded by:

- **Real fee cost.** Each cycle burns 8,000 regular gas and contributes to `block_regular_gas_used` and base fee pressure. No amplification — the attacker pays the full regular-gas price.
- **Per-slot exhaustion.** Each slot only shifts once; subsequent cycles on the same slot are no-ops. Scaling requires more distinct storage slots.
- **Net-zero block accounting.** Charge and refund cancel in `block_state_gas_used` and `execution_state_gas_used`. Block-level resource accounting is unaffected.

Compared to ordinary regular-gas burning (e.g., a Keccak loop), the trick provides no new amplification at the block level. It is not a meaningful DDoS vector against the network.

### 3.3 EIP-4337 bundles — drain attack on co-bundled user operations

**This is the meaningful concern.** All user operations in a bundle execute inside one transaction and **share a single `state_gas_reservoir`**. The `EntryPoint` enforces per-userop budgets via `gasleft()` deltas, but `gasleft()` cannot observe the reservoir.

#### Attack

1. A malicious user operation runs the SSTORE cycle on `K` distinct slots within its declared `callGasLimit`. The `EntryPoint` observes a `gasleft()` drop of `K × 45,568` and charges the attacker accordingly.
2. The transaction's `gas_left` has been drained by `K × 45,568`, while `K × 37,568` of that drained budget has migrated into the shared reservoir.
3. Subsequent honest user operations execute against a `gas_left` that is `K × 45,568` smaller than they planned for. State-gas charges in those user operations are silently funded from the reservoir (the attacker subsidized them), but **regular-gas operations** have to come from the depleted `gas_left`.
4. Honest user operations whose regular-gas needs exceed the post-drain `gas_left` **OOG and revert**, even though the bundle's `tx.gas` budget is intact — the missing budget is sitting in the reservoir, unreachable for regular operations.

The attacker pays `K × 45,568 × gasPrice` for the attack, similar in cost to a plain regular-gas drain. What the reservoir model adds is:

- **EntryPoint accounting drift.** Per-userop gas attribution via `gasleft()` reports `K × 45,568` of consumption, but `tx_gas_used` only reflects `K × 8,000`. The bundler is implicitly over-refunded; the difference came out of the attacker's account.
- **Cross-userop subsidy.** State-creating honest user operations later in the bundle execute their state-gas charges for "free" from the reservoir, paid for by the attacker. This violates the per-userop independence the `EntryPoint` is supposed to enforce.

#### Mitigations

For bundlers and `EntryPoint` implementations:

- Track per-userop state-gas charges and refunds explicitly, not via `gasleft()` deltas.
- Reject user operations whose net state-gas reservoir contribution at frame-end accounting exceeds a per-userop bound.
- Pad `gas_left` headroom margins for user operations from senders or paymasters that have not been simulated.

For the EIP itself, the cleanest fix is to make refunds symmetric with their original charge: if a state-gas charge spilled `S` units into `gas_left`, the matching refund should restore up to `S` to `gas_left` first, with any excess going to the reservoir. This eliminates the shift at the source, leaving only the reservoir size that was set at transaction start.
