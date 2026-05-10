# Gas accounting walkthroughs: revert and exceptional halt

## Scenario

A top-level frame enters with `gas_left = 10`, `reservoir = 5`. It makes a nested call which inherits `gas_left = 10` and the shared `reservoir = 5`. The inner frame executes one `SSTORE 0 → x` (slot creation), with hypothetical costs: regular = 1, state = 6. We then vary which frame fails and how.

State-gas is **not** charged at SSTORE opcode time — only at a *successful* frame's boundary (see EIP-8037, "Frame-end state-gas accounting").

---

## Group 1 — Inner succeeds, outer fails

### Common steps (1–5)

| Step | Event | gas_left | reservoir | execution_state_gas_used |
|---|---|---|---|---|
| 1 | Outer enters | 10 | 5 | 0 |
| 2 | Inner enters (call cost = 0) | 10 | 5 | 0 |
| 3 | SSTORE regular cost 1 deducted from gas_left | 9 | 5 | 0 |
| 4 | Inner exits → frame-end charges 6 state-gas: 5 from reservoir, 1 from gas_left | 8 | 0 | 6 |
| 5 | Inner returns to outer | 8 | 0 | 6 |

### Case A — Outer **exceptionally halts**

- All state changes revert (the new slot is gone).
- The 6 state-gas charged by the successful inner frame is refunded directly to `reservoir` (refund lands in the reservoir regardless of which counter the original charge drew from). `execution_state_gas_used` returns to 0.
- Remaining `gas_left` is zeroed; `execution_regular_gas_used` is bumped by the consumed 8.

**Final: `gas_left = 0`, `reservoir = 6`.**

### Case B — Outer **reverts**

Same refund mechanics as Case A, but `gas_left` is **not** zeroed — consistent with standard EVM `REVERT` semantics, the caller keeps unused gas:

- State reverted.
- 6 state-gas refunded to `reservoir` (0 → 6); `execution_state_gas_used` returns to 0.
- `gas_left` preserved at 8.

**Final: `gas_left = 8`, `reservoir = 6`.**

---

## Group 2 — Inner fails

The inner call fails *before* its frame-end accounting fires, so no state-gas was ever charged. Per the EIP, "a reverted or halted child produces no debits or credits to the parent's `state_gas_reservoir`." The reservoir therefore stays untouched at 5.

### Common steps (1–3)

| Step | Event | inner.gas_left | reservoir | execution_state_gas_used |
|---|---|---|---|---|
| 1 | Outer enters: `gas_left=10`, `reservoir=5` | — | 5 | 0 |
| 2 | Inner enters (call cost = 0) | 10 | 5 | 0 |
| 3 | SSTORE regular cost 1 deducted | 9 | 5 | 0 |

### Case C — Inner **exceptionally halts**

- All inner state changes roll back; the slot creation never happens.
- No frame-end state-gas accounting fires (only successful frames trigger it). Reservoir stays at 5.
- Inner's remaining `gas_left = 9` is zeroed; `execution_regular_gas_used` increases by 9 (the SSTORE's 1 plus the 9 burned).
- Control returns to outer with `gas_left = 0`. Assuming outer then exits successfully with no further state changes, the top-level frame-end accounting has nothing to charge.

**Final: `gas_left = 0`, `reservoir = 5`.**

### Case D — Inner **reverts**

Same as Case C, except inner's remaining `gas_left = 9` is preserved and returned to outer (standard `REVERT` semantics):

- State rolled back; no state-gas accounting; reservoir stays at 5.
- Outer continues with `gas_left = 9`. If it then exits successfully with no further changes, no further accounting fires.

**Final: `gas_left = 9`, `reservoir = 5`.**

---

## Sanity check

With `tx.gas = 15` (= initial 10 + 5):

| Case | What failed | gas_left | reservoir | tx_gas_used | What the user paid for |
| --- | --- | --- | --- | --- | --- |
| A | Outer halts | 0 | 6 | 9 | 1 SSTORE regular + 8 burned by halt |
| B | Outer reverts | 8 | 6 | 1 | 1 SSTORE regular |
| C | Inner halts | 0 | 5 | 10 | 1 SSTORE regular + 9 burned by halt |
| D | Inner reverts | 9 | 5 | 1 | 1 SSTORE regular |

In all four cases, no slot survives in the final state and the user pays **zero** net state-gas. The cases differ only in how much `gas_left` was burned by an exceptional halt.
