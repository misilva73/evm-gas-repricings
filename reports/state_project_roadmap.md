# State Project Roadmap

## Goals

Two key changes make us rethink how Ethereum handles state:

- **zkevm**: once proofs are mandatory in-protocol (every block ships with a proof by default), attesting/fully-validating nodes verify a proof + sample data via PeerDAS instead of re-executing. They no longer need to hold state, so far fewer nodes are incentivized to do so.
- **state growth**: as we scale toward gigagas, holding and serving the entire state gets harder and harder. State today grows ~100 GB/yr; even a conservative ~20x state target implies ~2 TB/yr and ~8 TB after four years. We can somwhat control this through 

### Who still needs state after mandatory proofs

The set of state-holders shrinks to those who structurally require it:

- **Builders** (including local/"home" builders running vanilla software) — need the full state to build any block.
- **FOCIL includers** — need the **VOPS** state ([Validity-Only Partial Statelessness](https://ethresear.ch/t/a-pragmatic-path-towards-validity-only-partial-statelessness-vops/22236)) to produce inclusion lists. This is much smaller — under 1 TB even with no changes, plausibly under 512 or 256 GB, and optimizable further.
- **Users / RPC** — anyone executing against head state. Today this requires the whole DB, which is why users fall back to centralized providers.

### What we want to avoid

- Users having no alternative to centralized providers (Infura, Alchemy, etc.) for state access.
- New builders barred from joining because they cannot sync or store the full state.
- FOCIL includers barred from joining because they cannot sync the VOPS state.

## What do we need to solve?

Two parallel arcs: an **operational** arc (make state manageable to hold and serve) and a **trie design** arc (ship a structure built for a post-zkevm gigagas chain). They share dependencies but can largely proceed in parallel until the migration.

### Arc 1 — Make holding & serving state manageable

Goal: keep building, serving, and partially-validating state feasible on home-staker / home-builder hardware, even under gigagas throughput.

- **DB optimizations.** Present-day client DBs were not designed for multi-TB state: each write updates $O(\log n)$ tree nodes, and each node update costs $O(\log n)$ DB operations, so per-write cost grows as $O(\log^2 n)$ — and the constant factors balloon once the state no longer fits in RAM ($n \gg$ RAM). Refine and adopt multi-TB-capable designs, with hot/cold separation so cold state can live in flat files (cheaper media) rather than the live DB.
- **State pricing.** Move to multidimensional pricing (EIP-7999) and cap the growth rate on dynamic state. Review state clearing pricing.
- **New types of state** (instead of state expiry — see note below). Introduce cheaper, more restrictive tiers alongside existing state: **temporary storage** (a tree zeroed each period, e.g. monthly) and **UTXOs**, with out-of-order **resurrection** via per-period spent/unspent bitfields. Permanent storage for accounts, code, and core composable contracts; balances/NFTs/short-lived event state move to the cheaper tiers. Opt-in, app-by-app. Ref: [Hyper-scaling state by creating new forms of state](https://ethresear.ch/t/hyper-scaling-state-by-creating-new-forms-of-state/24052).
- **State serving workflow & incentives.** The hard one, and a prerequisite (not an afterthought) for letting state grow: a decentralized way to *serve and retrieve* head state — partial-state P2P network (each node keeps ~1/N), and/or a PIR sidecar over existing nodes for private, censorship-resistant retrieval. Without a real, deployed alternative to centralized RPC, growing the state just deepens the centralization we're trying to avoid.
- **Syncing.** Being a builder must stay permissionless and not unreasonable to set up. Even at perfect efficiency, syncing multi-TB state is slow and can hit bandwidth caps. Use BAL-assisted / executionless sync and P2P improvements.
- **Partial stateless nodes (VOPS).** Let validators / FOCIL includers operate on a small validity-only subset of state instead of the full set.

> **Note — no state expiry.** A decade of state-expiry designs all hit the same problem: proving *non-existence* (that nothing was ever created at an address/slot), which has no representation meaningfully smaller than the state itself; the address-period / CREATE3 mitigation isn't understood by existing ERC-20 storage layouts and so isn't backwards-compatible. We therefore do **not** pursue automatic expiry of existing state. Instead: keep current state as-is but relatively pricier, and add new cheaper tiers that apps opt into.

### Arc 2 — New trie structure (design + migration)

Goal: a trie built for small proofs and proving-friendliness on a post-zkevm, gigagas chain. Migration is part of this arc — design and rollout stay together.

- **Small proofs through a binary tree.** Two options: full tree migration with([EIP-7864](https://eips.ethereum.org/EIPS/eip-7864)) or [partial binary tree](https://cperezz.github.io/pbt-spec/) where we move everything except contract storage. Decide on final design and prototype.
- **zk-friendly hash.** BLAKE3 as the interim hash; Poseidon2 as the target pending the dedicated Poseidon cryptanalysis effort. Tree finalization is gated on this go/no-go.
- **Code chunking.** Code lives in the tree, chunked so only touched chunks need witnesses. Required updated pricing and we can likely bump the contract size limit.
- **Friendly for partial statelessness.** Witnesses small enough that VOPS / partial-state operation is practical.
- **Migration.** MPT → binary tree is a one-time conversion over the full live state — historically the part that sinks timelines. Decide overlay-tree vs flag-day conversion, who bears conversion cost, and how long clients run dual trees. Witness format must agree with the zkEVM execution-witness / stateless-guest interface.

## Milestones

Note: the 🤔 emoji denotes topics we are not sure about

### Short term (end 2026)

- DB optimizations: explore if cold/hot state breakdown is feasible; explore optimizations for supporting the binary tree design.
- Look into BAL-supported snap sync (snap2) 🤔
- State pricing groundwork: finish multidimensional pricing and propose EIP-7999 for Hegota; review storage create/clear pricing and accounting.
- Finalize binary-tree spec (EIP-7864) and the migration/transition design. Prototype in 2 clients.
- Kickoff **state-serving / RPC-decentralization** track: explore solution space and prototype a minimal P2P network for partial-state serving.
- VOPS: spec + prototype client running on the validity-only subset 🤔

### Medium term (middle 2027)

- DB optimizations: prototype based on results from early explorations, prototype and benchmarks new DB design
- Propose binary tree for I*
- First spec + prototype for a new state types (temporary storage and/or UTXOs) with resurrection bitfields; reference ERC-20 balance workflow on top.
- Partial-stateless (VOPS) clients in production used by FOCIL includers 🤔
- Decentralized state-serving network in beta; measure performance as a RPC alternative + syncing alternative.

## Dependencies & sequencing

- **Binary tree precedes/accompanies statelessness** — VOPS and partial-state nodes need witnesses small enough to be practical, which the binary tree provides.
- **zk-friendly hash gates trie finalization** — we want to avoid two tree migrations, so we need to decide on the hash function before shipping the binary tree.
- **Mandatory proofs is the enabling event** for validators dropping state; the state project should be ready to exploit it, not blocked on it (the trie change *does* need a hardfork; opt-in proving does not).
- **New state types depend on the trie** being "friendly to new types of state."
- **State serving must exist before state grows** — treat a deployed, decentralized state-retrieval path as a hard gate on raising state-growth targets, not a follow-up.
- **Trie witness format must match the zkEVM** execution-witness / stateless-guest interface (cross-team).
