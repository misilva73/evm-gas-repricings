# EIP-8037 state_gas accounting review

#### Maria Silva, April 2026

Here we try to summarize some open questions regarding EIP-8037. This is not an exhaustive review of all implementation details, but rather a focused review of gas accounting of state gas and its edge cases.

We use the latest EIP-8037 specification, its EELS implementation (branch `eips/amsterdam/eip-8037`), and the execution-spec-tests release `bal@v5.6.1`. The goal is to identify edge cases or specification gaps that violate the EIP's guiding principle that **state gas should be consumed if and only if new state is created**. We explicitly flag where this principle conflicts with current EVM design.

The recommendations try to target keeping the principle intact. However, when there are clear deviations from current EVM behavior, we also list options. The goal is to open the discussion and decide on the best path forward.

Here is the summary table:

| # | Issue | Principle Violation? | Status | Test coverage |
|---|-------|:---:|:---:|:---:|
| 1 | Top-level reservoir refund | Yes | Known (EIPs#11476) | None |
| 2 | 0→x→0 storage reservoir refill | Yes | Known (no PR) | Partial |
| 3 | GAS_CREATE state gas: pre-outcome charge and EIP text | Yes (but matches pre-8037 EVM) | **New** | Partial |
| 4 | SELFDESTRUCT of same-tx account: no GAS_CREATE refund | Yes | Known (no PR) | Partial |
| 5 | CALL w/ value to self-destructed account | No (correct) | **New** | None |
| 6 | Mutable intrinsic_state_gas | No | **New** | Indirect |

Next, we discuss each issue in more detail, including the problem, principle violation, recommendations, and test coverage.

**Caveat**. Test coverage assessments were generated with Claude Code. We need to double-check this info.

## 1. Top-Level Reservoir Refund

**Problem**: When a subcall reverts or halts, `incorporate_child_on_error` correctly returns all state gas (both reservoir and spilled) to the parent's reservoir. However, at the **top level**, the sender still pays for state gas even though all state changes were rolled back.

**Current behavior in EELS**: On top-level exceptional halt, `process_message` sets `evm.gas_left = 0` but preserves `evm.state_gas_left`. On revert, both `gas_left` and `state_gas_left` are preserved. Then in `fork.py`:

```python
tx_gas_used_before_refund = tx.gas - tx_output.gas_left - tx_output.state_gas_left
```

The `state_gas_left` (reservoir) is subtracted, so any remaining reservoir is returned. But `state_gas_used` is not zeroed and feeds into `tx_state_gas = intrinsic_state_gas + tx_output.state_gas_used`, which feeds `block_state_gas_used`.

**Principle violation**: On top-level failure, no state is created, but `block_state_gas_used` still reflects the state gas consumed during the failed execution. This violates the guiding principle.

**Recommendation**: On top-level exceptional halt or revert, reset `state_gas_used` to zero and return all consumed state gas to the reservoir.

**Test coverage**: None. The test suite covers child-level reservoir recovery via `test_reservoir_returned_on_revert` and `test_reservoir_returned_on_oog`, which verify that `incorporate_child_on_error` correctly restores state gas to the parent. However, no test targets the **top-level** failure path specifically — where the entire transaction reverts and `state_gas_used` persists into `block_state_gas_used` despite all state changes being rolled back.

## 2. 0 → x → 0 Storage Reservoir Refill

**Problem**: The SSTORE implementation adds a refund to `refund_counter` when `original_value == 0` and `new_value == original_value` (i.e., 0 → x → 0 restoration):

```python
evm.refund_counter += int(
    state_gas_storage_set
    + GAS_STORAGE_UPDATE - GAS_COLD_STORAGE_ACCESS - GAS_WARM_ACCESS
)
```

This adds the state gas amount to the **undimensioned** `refund_counter`, which only reduces `tx_gas_used_before_refund` at the end of the transaction and is capped at 20% of gas used before refund. This means a contract performing many `0 → x → 0` patterns will run out of reservoir even though the net state effect is zero. Also, the 20% cap may prevent the full state gas from being refunded for many restorations.

**Principle violation**: The state gas reservoir is depleted during execution despite no net state creation. The refund only comes at the end and is capped at 20% of gas used before refund, which may not fully restore the state gas for many restorations.

**Recommendation**: Instead of the refund counter, at the point of the `0 → x → 0` restoration, restore the state gas directly to `state_gas_used` and decrement the `state_gas_used` counter by the same amount. In implementations where `state_gas` is local to each call frame, a subcall performing `x → 0` on a slot set in the parent can cause the frame-local `state_gas` to go negative, since the subcall "returns" more state gas than it consumed in its own scope. Both the reservoir and the consumed counter need to be adjusted for the principle to hold. In addition, clients may want to make `state_gas_used` global across frames. This requires careful handling of reverts.

**Test coverage**: Partial. The SSTORE restoration refund is tested via `test_sstore_restoration_refund` (which verifies the `refund_counter` path works correctly for the 0→x→0 pattern). However, there is no test targeting the **mid-execution reservoir depletion** scenario — where repeated 0→x→0 cycles drain the reservoir during execution even though the net state effect is zero, and subsequent legitimate state-creating operations fail due to insufficient reservoir.

## 3. GAS_CREATE State Gas: Pre-Outcome Charge and EIP Text

**Problem**: In `create()` and `create2()`, state gas is charged **unconditionally** at the opcode level, in the **caller's** frame, before the child frame is spawned:

```python
charge_gas(evm, REGULAR_GAS_CREATE + extend_memory.cost + init_code_gas)
charge_state_gas(evm, STATE_BYTES_PER_NEW_ACCOUNT * cost_per_state_byte)
```

This has two consequences:

1. **Silent failure still consumes state gas.** `generic_create()` may fail silently (returning 0 on the stack) for several reasons — insufficient balance, nonce overflow, stack depth limit, or address collision. In all these cases, no account is created, but `STATE_BYTES_PER_NEW_ACCOUNT * cost_per_state_byte` of state gas has already been consumed. On the balance/nonce/depth failure path, `generic_create` restores both regular gas and the state gas reservoir. On the address collision path, only the state gas reservoir is restored — regular gas is not. In either case, the upfront `charge_state_gas` at the opcode level has already been deducted and is not undone.

2. **Revert does not undo the caller-frame charge.** The EIP states: "State gas charged for account creation (CREATE, CALL to new account, and EOA delegation) is consumed even if the frame reverts." Meanwhile, the general rule says: "On child revert or exceptional halt, all state gas consumed by the child [...] is restored to the parent's reservoir." These two statements are in tension. The resolution in the EELS implementation is that `incorporate_child_on_error` restores all **child** state gas, but the `charge_state_gas` for `GAS_CREATE` happened in the **parent** frame before the child was spawned — so the parent already paid regardless of child outcome. The EIP text is misleading: "consumed even if the frame reverts" makes it sound like a deliberate policy choice, when actually it's a consequence of where the charge happens (caller frame, not child frame). This is different from `GAS_NEW_ACCOUNT` in CALL, which also charges in the caller frame but is a post-state cost — only triggered when the target account genuinely doesn't exist.

**Principle violation**: State gas is consumed but no new state may be created. This applies both to silent `generic_create` failures (a) and to child reverts after successful creation begins (b).

**Note on current EVM precedent**: Pre-8037, `GAS_CREATE` (32,000) was also charged unconditionally. So this is consistent with existing EVM behavior. However, it **violates the guiding principle**. The state gas component should ideally only be charged if account creation actually succeeds.

**Suggestion**: Once we decide how to address CREATE state costs on failure, we should update the EIP text accordingly. There are four viable paths:

1. **Accept and document**: keep the current behavior, explicitly note `GAS_CREATE` as a deliberate deviation from the principle, and rewrite the revert-behavior section to clarify that `GAS_CREATE` is charged in the caller's frame (not "consumed despite revert").
2. **Defer the charge**: move the state gas charge into `generic_create`, after the early-exit checks but before `process_create_message`, so state gas is only consumed when account creation actually proceeds to initcode execution. This narrows the principle violation to just the initcode-reverts case. Note that this option pairs with whatever decision is made on issue #1 — the initcode-revert case has the same DoS trade-off as the top-level revert case, so both should be resolved consistently.
3. **Post-state charge**: charge `GAS_CREATE` state gas only on successful account creation (alongside `GAS_CODE_DEPOSIT`). This fully aligns with the principle but requires running initcode before payment, which conflicts with the EVM's pay-before-execute model.
4. **Charge upfront, refund on failure**: keep the upfront `charge_state_gas` in the caller's frame (preserving pay-before-execute), but refund the state gas back to the reservoir when deployment fails (whether due to early-exit checks in `generic_create` or initcode revert/exceptional halt).

Option (1) is the simplest and most conservative; option (2) is a reasonable middle ground that eliminates the most egregious violations (silent failures) without breaking pay-before-execute; option (4) preserves pay-before-execute while fully aligning with the principle.

**Test coverage**: Partial. The `test_create2_address_collision` test covers the address collision path. However, the other three early-exit failure modes in `generic_create` — insufficient balance, nonce overflow, and stack depth limit — are untested for state gas accounting. Tests covering the caller-frame charge behavior (such as `test_reservoir_returned_on_revert`) indirectly demonstrate the revert semantics.

## 4. SELFDESTRUCT of Same-TX-Created Account Does Not Refund GAS_CREATE State Gas

**Problem**: When a contract is created and then self-destructs within the same transaction (allowed by EIP-6780), the net state effect is zero — the account was created and then destroyed. However:

1. `CREATE` charges `112 × cost_per_state_byte` state gas for the new account
2. `SELFDESTRUCT` does **not** refund the `112 × cost_per_state_byte` state gas

**Principle violation**: Net zero state creation, full state gas payment. This is analogous to the `0 → x → 0` SSTORE pattern, but, unlike the SSTORE case, there's no refund mechanism at all for CREATE's `GAS_CREATE` state gas.

**Note on current EVM precedent**: Pre-8037, SELFDESTRUCT *did* carry a gas refund (24,000 gas), but EIP-3529 (London) explicitly removed it to reduce protocol complexity and eliminate refund-based gas token exploits. Adding a state gas refund here — even one scoped to same-TX destruction — would be the only SELFDESTRUCT refund post-London, setting a new precedent for what is a fairly niche pattern (same-TX CREATE + SELFDESTRUCT). This would partially reverse the direction set by EIP-3529.

**Recommendation**: Two options:

1. Add a state gas refund (preferably to reservoir) when SELFDESTRUCT destroys an account created in the same transaction. Note that this would introduce the only SELFDESTRUCT refund post-London, a new precedent that partially reverses EIP-3529's direction — for a pattern that is likely rare in practice.
2. Accept the principle violation and document it as a deliberate design choice consistent with EIP-3529's simplification goals.

**Test coverage**: Partial. The `test_selfdestruct_to_self_in_create_tx` test exists and covers the SELFDESTRUCT-in-same-TX scenario, but it does not verify whether the `GAS_CREATE` state gas is or is not refunded when the account is destroyed. The test focuses on the SELFDESTRUCT mechanics, not on whether the net-zero state outcome produces a corresponding net-zero state gas charge.

## 5. CALL with Value to Self-Destructed (Same-TX) Account

**Problem**: When account A is created and then self-destructed in the same transaction (EIP-6780), and then a CALL with value targets A:

- `is_account_alive(tx_state, to)` returns `false` (account was destroyed)
- The CALL charges `GAS_NEW_ACCOUNT` state gas (`112 × cost_per_state_byte`)
- A new account is created for A

This is correct as new state is created. But consider the **inverse**: if A was self-destructed but the beneficiary was itself (A), then A's balance is zero but the account may still exist in some client implementations depending on when the destruction is processed. The EELS implementation handles this correctly by checking `is_account_alive`, but the EIP text doesn't discuss this interaction.

**Recommendation**: This edge case should be explicitly documented in the EIP text to ensure all client implementations handle it consistently.

**Test coverage**: None. There is no test covering the interaction between EIP-6780 self-destruct and EIP-8037's `GAS_NEW_ACCOUNT` charge. Specifically, no test verifies that a CALL with value to an account that was created and self-destructed within the same transaction correctly charges `GAS_NEW_ACCOUNT` state gas (because `is_account_alive` returns false after destruction).

## 6. EIP-7702 Authorization: Mutating intrinsic_state_gas During Execution

**Problem**: In `set_delegation()`:

```python
if account_exists(tx_state, authority):
    refund = STATE_BYTES_PER_NEW_ACCOUNT * cost_per_state_byte
    message.tx_env.intrinsic_state_gas -= refund
    message.state_gas_reservoir += refund
```

This mutates `intrinsic_state_gas` (a value that was set during transaction validation) during execution. This is architecturally unusual because `intrinsic_state_gas` is supposed to be a static, pre-execution quantity.

However, doing this through the refund counter would limit the amount of refund possible due to the 20% cap, and it would also delay the refund until the end of the transaction rather than applying it immediately during execution. This would go against the principle of only consuming state gas when new state is created.

**Note on current EVM precedent**: There is no precedent in the EVM for mutating intrinsic gas during execution. Intrinsic gas has always been a static, pre-execution quantity. Specifically, EIP-7702 solves the same problem using the refund counter pattern: it charges the worst case (`PER_EMPTY_ACCOUNT_COST` per auth) as intrinsic gas, then adds `PER_EMPTY_ACCOUNT_COST - PER_AUTH_BASE_COST` to the global `refund_counter` if the account already exists. The intrinsic value is never touched. EIP-8037 broke from EIP-7702's own design by replacing the refund counter with direct mutation of `intrinsic_state_gas`.

**Recommendation**: Two options:

1. Instead of mutating `intrinsic_state_gas`, introduce two counters: `max_intrinsic_state_gas` (the worst-case amount assuming all authorizations create new accounts, checked by the txpool for validity) and `real_intrinsic_state_gas` (the actual amount determined during execution when the EIP-7702 authorization list is applied, and we learn which accounts already exist). `max_intrinsic_state_gas` remains immutable after transaction validation; `real_intrinsic_state_gas` is computed during execution and feeds into final gas accounting. The difference between the two goes back to the reservoir, avoiding both the mutation of a "should-be-static" value and the capped refund counter path.
2. Keep the logic of mutating `intrinsic_state_gas`, but clearly state this as a deliberate design choice in the EIP, with a brief rationale explaining why this approach was chosen over the refund counter pattern (immediate refund application, no cap).

**Test coverage**: Indirect. The `test_existing_account_refund` test in `test_state_gas_set_code.py` covers the functional behavior of the existing-account refund mechanism (reservoir is increased, intrinsic cost is decreased). However, no test explicitly verifies the **mutation** of `intrinsic_state_gas` itself — e.g., by checking that the final `tx_state_gas` computation reflects the modified intrinsic value rather than the original.
