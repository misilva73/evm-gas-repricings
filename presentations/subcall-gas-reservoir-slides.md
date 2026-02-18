---
title: Subcall Gas Semantics for 2D Metering
tags: EIP-8037, gas, metering
type: slide
---

<style>
.reveal {
  font-size: 36px;
}
</style>

# EIP-8037: Subcall Gas Metering

### Glamsterdam Repricings #2

### Feb 18th, 2026

---

## Context: EIP-8037 Metering

Each execution frame carries **two gas pools**:

| Pool | Purpose | Bound |
|---|---|---|
| **`gas_left`** | Regular (non-state) operations | `TX_MAX_GAS_LIMIT` |
| **`reservoir`** | State-creation operations only | Unbounded (excess beyond cap) |

A user's `tx.gas` funds both pools.

---

## The Design Question

When a `CALL` is made, the caller specifies a **single gas value `g`**.

Need to define:

1. **Forwarding** — How much of each pool does the subcall receive?
2. **Success** — How are unused portions returned?
3. **Failure** — What happens on REVERT vs. exceptional halt?

---

## Option 1 — Forward all reservoir; return on any failure

- **Forwarded:**
  - `call_gas_left = min(g, 63/64 · caller.gas_left)`
  - `call_reservoir = caller.reservoir` *(all of it)*
- **Success:** return unused `gas_left` + unused `reservoir`
- **REVERT:** return unused `gas_left` + unused `reservoir`
- **Exceptional halt:** consume `gas_left`, **return** unused `reservoir`

> State changes are reverted on failure — no state was grown, so reservoir isn't "consumed."

---

## Option 2 — Forward all reservoir; consume on exceptional halt

- **Forwarded:**
  - `call_gas_left = min(g, 63/64 · caller.gas_left)`
  - `call_reservoir = caller.reservoir` *(all of it)*
- **Success:** return unused `gas_left` + unused `reservoir`
- **REVERT:** return unused `gas_left` + unused `reservoir`
- **Exceptional halt:** consume **both** `gas_left` **and** `reservoir` *(zeroed)*

---

## Option 3 — Forward reservoir proportional to gas fraction

- **Forwarded:**
  - `call_gas_left = min(g, 63/64 · caller.gas_left)`
  - `call_reservoir = caller.reservoir × (call_gas_left / caller.gas_left)`
- **Success:** return unused portions of both
- **REVERT:** return unused portions of both
- **Exceptional halt:** consume `gas_left`, **return** unused `reservoir`

> Sending half your gas → sending half your reservoir.

---

## Option 4 — Forward reservoir capped at `g`

- **Forwarded:**
  - `call_gas_left = min(g, 63/64 · caller.gas_left)`
  - `call_reservoir = min(g, caller.reservoir)`
- **Success:** return unused portions of both
- **REVERT:** return unused portions of both
- **Exceptional halt:** consume `gas_left`, **return** unused `reservoir`

> Total subcall spending ≤ 2g (at most `g` from each pool).

---

## Trade-offs Summary

| | Reservoir forwarded | Spending bound | Factory support | Composability |
|---|---|---|---|---|
| **Opt 1** | All | Unbounded | Full | Poor |
| **Opt 2** | All | Unbounded | Full | Very poor |
| **Opt 3** | Proportional | ~2× fraction | Partial | Good |
| **Opt 4** | min(g, res) | ≤ 2g | Partial | Good |

**Opt 1–2:** Simple forwarding, full reservoir access — but `g` no longer bounds spending, untrusted callees can drain the reservoir. Opt 2 is additionally punishing: OOG wipes the entire state budget.

**Opt 3–4:** Caller retains control via `g` — but state-heavy subcalls (factories) may be starved. Opt 3 ties reservoir to gas fraction; Opt 4 caps reservoir at `g`.

---

## Discussion

- What should the default subcall semantics be?
- Option 1 seems better than option 2. Can someone reason for this not to be true?
- Can someone think of any additional problems with any of the options?
