# Comparing Two Designs for Raising the Block Limit Under Multidimensional Gas

When the regular-gas block limit is raised by a factor of 3, the protocol has to decide what happens to the second resource (state) and to the single base fee that prices both. Two designs come up naturally:

- **Design 1 — reprice the state ops.** Multiply the state-gas cost of each state-touching op by 3, and keep the block limit symmetric (same numerical limit on each resource).
- **Design 2 — keep op costs, shrink the state share of the block.** Leave op costs unchanged, but make state count 3× more heavily against the block limit.

Both keep a single base fee, updated from a single congestion signal. They look similar at the validity-layer; the question is whether they are actually equivalent for users and for price discovery.

## Toy example

To make the algebra concrete, work with a stripped-down EVM that has only two opcodes:

- `op1` consumes 1 regular gas.
- `op2` consumes 1 state gas.

The current block limit is 5 (each resource), and we want to raise it to 15. Let `R` and `S` denote the number of `op1` and `op2` ops in a block.

**Design 1.**
- `op1` costs 1 regular gas, `op2` costs **3** state gas.
- Validity: `max(R, 3S) ≤ 15`.
- Single base fee `b`, updated from `max(R, 3S)` against a target of 7.5.

**Design 2.**
- `op1` costs 1 regular gas, `op2` costs 1 state gas (unchanged).
- Validity: `max(R, 3S) ≤ 15` (state counts triple against the limit).
- Single base fee `b'`, updated from `max(R, 3S)` against a target of 7.5.

## What's the same

The physical block constraint and the base-fee adjustment signal are **identical** in the two designs: both depend on `max(R, 3S)` against limit 15 and target 7.5. A validator looking only at "is this block valid?" or "should base fee go up or down?" sees the same behavior in both designs.

## What's different — user-facing price

The price each op pays at the same base fee is not the same:

|     | Design 1 cost per op | Design 2 cost per op |
|-----|----------------------|----------------------|
| op1 | `b`                  | `b'`                 |
| op2 | `3b`                 | `b'`                 |

In Design 1, `op2`'s price is locked to 3× `op1`'s price because `op2` consumes 3 units of gas. In Design 2, both ops are priced at the same rate per op even though `op2` consumes 3× the constrained "state" resource per op.

## Equilibrium comparison

Assume usage settles so `max(R, 3S) = 7.5` in both designs. There are two regimes, depending on which resource binds.

**State-binding** (`3S = 7.5`, regular slack):
- Design 1: `D2(3b) = 2.5` pins some `b`. `op1` cost `= b`, `op2` cost `= 3b`.
- Design 2: `D2(b') = 2.5`, so `b' = 3b`. `op1` cost `= 3b`, `op2` cost `= 3b`.
- ⇒ **`op2` cost identical, `op1` is 3× more expensive in Design 2.** Regular-gas users subsidize the state-side congestion signal.

**Regular-binding** (`R = 7.5`, state slack):
- Design 1: `D1(b) = 7.5`. `op1` cost `= b`, `op2` cost `= 3b`.
- Design 2: `D1(b') = 7.5`, so `b' = b`. `op1` cost `= b`, `op2` cost `= b`.
- ⇒ **`op1` cost identical, `op2` is 3× cheaper in Design 2.** State usage is under-priced and can be opportunistically pushed up to the 5-op state limit, at which point the regime can flip.

## Why Design 1 is well-behaved

Design 1 is just the existing "gas" abstraction with re-weighted op costs: a single price per unit of gas, where each op's gas count reflects its resource consumption. The base fee is the marginal price of the binding resource, and each op pays in proportion to how much of that resource it uses.

Design 2 keeps op-level prices uniform while making the limit non-uniform. That mismatch is the source of the cross-subsidy: the base fee is forced to clear the binding resource, but `op1` and `op2` don't pay in proportion to the resource they actually consume — so one side is always over- or under-charged relative to the efficient price.

If the goal is "raise the regular-gas limit 3× without changing how much state work fits in a block," Design 1 is the mechanically equivalent move. Design 2 looks similar at the block-validity layer but distorts prices.