# State Project Roadmap

## Goals

Two key changes make us rethink how Ethereum handles state:

- **zkevm**: once proofs are mandatory in-protocol, every block ships with a proof by default. Attesting and fully-validating nodes then verify a proof and sample data via PeerDAS instead of re-executing. They no longer need to hold state, so far fewer nodes have a reason to.
- **state growth**: as we scale toward gigagas, holding and serving the full state gets harder. State grows ~100 GB/yr today. Even a conservative ~20x target implies ~2 TB/yr, or ~8 TB after four years. Pricing and new state types help, but pricing alone cannot hold growth flat while also scaling throughput. So the operational work of holding, serving, and syncing has to keep pace.

**Target.** Support a ~20x gas-limit increase (toward gigagas). Keep it feasible to build, serve, and partially-validate state on home-staker and home-builder hardware. Preserve a decentralized, non-custodial path to head-state access.

### Who still needs state after mandatory proofs

The set of state-holders shrinks to those who structurally require it:

- **Builders** (including local "home" builders running vanilla software). They need the full state to build any block.
- **FOCIL includers**. They need the **VOPS** state ([Validity-Only Partial Statelessness](https://ethresear.ch/t/a-pragmatic-path-towards-validity-only-partial-statelessness-vops/22236)) to produce inclusion lists. This is much smaller: under 1 TB even with no changes, plausibly under 512 or 256 GB, and optimizable further.
- **Users / RPC**. Anyone executing against head state. Today this requires the whole DB, which is why users fall back to centralized providers.

**Who we are building for.** In practice the work targets the **~10k reachable nodes** on the network today (per [Etherscan](https://etherscan.io/nodetracker), [ethernodes](https://ethernodes.org/), [MigaLabs/monitoreth](https://monitoreth.io/nodes), and the [500k-validator milestone](https://blockworks.co/news/ethereum-to-reach-500000-validators)). Within that group, home stakers are the core target. They are the operators most aligned with where we want things to go. Most run validators out of interest or altruism rather than profit. Solo staking pays full rewards with no pool fee, but it carries far higher reward variance ([CF Benchmarks](https://blog.cfbenchmarks.com/content/files/2024/10/Ethereum-Staking-Reward-Dynamics---CF-Benchmarks.pdf): variance falls exponentially as an operator's validator count grows) plus the burden of running a machine. So pooling via Lido is the easier economic choice. This shapes the incentives discussion below.

**State is not a blocker for VOPS.** Today total state is ~293 GB (account tree ~60 GB, VOPS state ~15–18 GB). Partial-stateful implementations are proven and documented, and full VBS support in Geth is ~1 month of work. State size is not currently a blocker for a node to run or act as an includer. The real entry barrier is having to run and maintain a machine at all. At today's sizes the CL state (Prism, ~100–200 GB) is already larger than the account state, so FOCIL includers are not our biggest issue. This assumes that we keep the current state growth rate. However, before increasing the growth rate, we need to figure out the state serving. Also, for syncing (which we need to ensure remains viable), the solutions for builder syncing can be used for includers as well.

**Account abstraction is a growth risk to watch.** AA stores extra data per account on top of the account tree. If it grows unchecked, it inflates VOPS. A partial-stateless node can hold the account tree plus the first N storage slots of each account's subtree. This stays viable only if N is small (2–3), so we need to keep AA scoped.

### What we want to avoid

- Users having no alternative to centralized providers (Infura, Alchemy, etc.) for state access.
- New builders barred from joining because they cannot sync or store the full state.
- FOCIL includers barred from joining because they cannot sync the VOPS state.

## How we work

- **De-risk open questions first.** Where a decision hinges on something we don't yet know, we resolve the uncertainty before committing — assess benefit before building (hot/cold separation), confirm necessity before speccing (binary tree), and benchmark before pricing (EIP-8037-style). The point is to avoid sinking effort into work that a later answer could invalidate.
- **Ship iteratively.** Prefer near-term, net-positive steps that stand on their own over big-bang changes — e.g. the centralized "Nginx-like" aggregator before a fully distributed state network, and DB optimizations that pay off independently of the trie migration.
- **Parallel, loosely-coupled workstreams.** The five near-term tracks proceed largely in parallel and unconditionally; we keep dependencies explicit so they can move independently until the points where they genuinely must converge.
- **Open collaboration.** The project is large, the team is small, and the changes span the whole stack, so this has to be an ecosystem effort. We leverage collaborations with aligned teams and individuals, and focus our own effort on the high-leverage tasks and on coordination rather than trying to build everything ourselves.

## What do we need to solve?

The work breaks into **six workstreams**. Five are near-term and proceed largely in parallel and unconditionally; the sixth — the binary tree — is deferred and conditional on an external trigger. They share dependencies but can largely proceed independently until the trie migration.

**Priorities.** If forced to rank, the order is:

1. **State serving / RPC-decentralization**. Raising growth targets and scaling throughput deepens centralization unless a decentralized retrieval path exists first. Highest priority and most under-explored. The infrastructure for serving state (tx-submission APIs, latency, small-enough proofs) is the same whether or not serving is incentivized, so this track proceeds regardless of how the incentives question resolves.
2. **DB optimizations & state-growth control**. Near-term, net-positive work that is largely independent of the trie migration. Hot/cold separation lowers operational cost and raises throughput. Multidimensional pricing and new state types control the growth rate. Lower risk and largely additive.
3. **State-serving incentives**. A mid-term, first-principles research question (mandate holding vs. make serving profitable). We do not need to solve it by end of 2026. We have time because growth stays controllable through existing pricing machinery (keeping EIP-8037 in place).
4. **Binary tree + zk-friendly hash** 🤔. It remains our best long-term tree design, but it is **not** a near-term state-project priority on its own merits. Whether we start now is **gated on the ZKVM team confirming it is a hard blocker for ZKVM's ship date**.

The single thing we most need to get right is **state serving**. It is both the hardest and the least-understood, and it bounds how aggressively everything else can move.

The first five workstreams share an umbrella goal: keep building, serving, and partially-validating state feasible on home-staker and home-builder hardware, even under gigagas throughput. The sixth ships a trie built for a post-zkevm, gigagas chain.

### State serving / RPC decentralization

Goal: a decentralized path for users to *retrieve* head state without defaulting to centralized RPC, and keep syncing that state permissionless. The hard one, and a prerequisite (not an afterthought) for letting state grow.

- **State serving workflow.** Today any full node can already serve everything a normal user needs: balances, call simulation, gas estimation, and proofs. Only archive is missing, and almost no one needs that. The real gap is **discovery**. Users don't know which node to ask, so they fall back to Infura/Alchemy. We frame this as a **"state network" work stream** with phases:
  - *Near-term first phase:* a more centralized **"Nginx-like" aggregator/load-balancer** that existing full nodes subscribe to, distributing user requests across peers. This lets the thousands of nodes already holding state (and doing nothing with it beyond SnapSync) actually serve users. A no-brainer we should do regardless. Likely pursued via a DappNode collaboration or grant.
  - *End-game:* a truly distributed state network (DHT / IPFS / Portal-like). This is far enough out, and underspecified enough, that it should **not** drive current design decisions.

  The infrastructure (sharded state, small-enough proofs, latency, the user-facing API) is the same whether serving is altruistic or incentivized, so this work proceeds independently of the incentives question. Note: serving state to users covers the RPC calls needed to submit transactions. It is distinct from being a full public RPC, which additionally implies profit-seeking and broad discoverability.
- **Syncing.** Being a builder must stay permissionless and not unreasonable to set up. Even at perfect efficiency, syncing multi-TB state is slow and can hit bandwidth caps. Use BAL-assisted / executionless sync and P2P improvements.

### DB optimizations

Goal: client DBs that stay cheap to operate at multi-TB state.

Present-day client DBs were not designed for multi-TB state. Each write updates $O(\log n)$ tree nodes, and each node update costs $O(\log n)$ DB operations, so per-write cost grows as $O(\log^2 n)$. The constant factors balloon once the state no longer fits in RAM ($n \gg$ RAM). We want to refine and adopt multi-TB-capable designs, with **hot/cold separation** so cold state can live in flat files (cheaper media) rather than the live DB. This is a near-term track independent of the trie migration. It lowers operational cost and raises throughput for the average machine, bringing down the cost of running a node. Before committing to full implementation (and any hot/cold data repricing), first assess what benefit it actually yields. Repricing in particular would resemble EIP-8037 (all clients implement, we benchmark, then price on the aggregate), so it should not start before we are confident it ships.

### State-growth control (pricing + new state types)

Goal: hold the growth rate controllable while throughput scales, without expiring existing state.

- **State pricing.** Move to multidimensional pricing (EIP-7999) and cap the growth rate on dynamic state. Review state clearing pricing.
- **New types of state** (instead of state expiry, see note below). Introduce cheaper, more restrictive tiers alongside existing state: **temporary storage** (a tree zeroed each period, e.g. monthly) and **UTXOs**, with out-of-order **resurrection** via per-period spent/unspent bitfields. Permanent storage stays for accounts, code, and core composable contracts. Balances, NFTs, and short-lived event state move to the cheaper tiers. Opt-in, app-by-app. Ref: [Hyper-scaling state by creating new forms of state](https://ethresear.ch/t/hyper-scaling-state-by-creating-new-forms-of-state/24052).
- **Flat-state-only contracts** 🤔 (Han's idea, worth exploring). An opt-in tier where a contract's state is stored as pure flat state with **no intermediate trie nodes**. Such contracts are cheaper to interact with and update, and they create far less state — a contract's flat data no longer drags along the doubling-in-size set of intermediate nodes. The trade-off: archives cannot produce historical Merkle proofs for this state (a ZKVM can still prove current state), so the app must self-serve any historical-proof needs. It is then up to each app to decide whether it wants the deal. The big win is large, heavily-used contracts (e.g. USDC) opting in and removing a very large slice of intermediate nodes from the network. This attacks intermediate-node growth specifically, which EIP-8037 (pure flat state) does not address. Needs due diligence on adoption before committing.

> **Note — no state expiry.** A decade of state-expiry designs all hit the same problem: proving *non-existence* (that nothing was ever created at an address/slot), which has no representation meaningfully smaller than the state itself. The address-period / CREATE3 mitigation isn't understood by existing ERC-20 storage layouts, so it isn't backwards-compatible. We therefore do **not** pursue automatic expiry of existing state. Instead we keep current state as-is but relatively pricier, and add new cheaper tiers that apps opt into.

### State-serving incentives

Goal: a sustainable answer to *why* nodes hold and serve state.

A separate, mid-term research question rather than a blocker. Two paths. (a) *Mandate holding*: make holding and serving a small slice of state (e.g. ~300 GB, not the whole thing) a condition for validator rewards, leaning on the power of defaults. (b) *Make serving profitable*: change the protocol so serving state earns a small recurring revenue (e.g. a market for ZK state proofs, which centralized providers can't serve at scale because proofs are expensive to generate). Path (b) is harder but the only long-term-sustainable option. We have time to research this from first principles because growth stays controllable via existing pricing (keeping EIP-8037 in place). It does not need to be solved by end of 2026. Target audience: the ~10,000–11,000 reachable nodes running today (home stakers being the core subset, see "Who we are building for" above).

### Partial statelessness (VOPS)

Goal: let validators and FOCIL includers operate on a small validity-only subset of state instead of the full set.

Partial-stateful implementations are proven and documented (see "State is not a blocker for VOPS" above). The binary tree, once triggered, makes witnesses small enough for this to be practical at scale.

### Binary tree — new trie structure (design + migration) 🤔

Goal: a trie built for small proofs and proving-friendliness on a post-zkevm, gigagas chain. Migration is part of this workstream, so design and rollout stay together.

- **Small proofs through a binary tree.** Two options: a full tree migration ([EIP-7864](https://eips.ethereum.org/EIPS/eip-7864)) or a [partial binary tree](https://cperezz.github.io/pbt-spec/) where we move everything except contract storage. Decide on the final design and prototype, but only once the necessity above is confirmed. Note that even a partial transition (accounts + code chunking, leaving the storage tree on MPT) will break a meaningful part of the ecosystem (e.g. CowSwap-style contracts needing upgrades).
- **zk-friendly hash.** BLAKE3 as the interim hash. Poseidon2 as the target, pending the dedicated Poseidon cryptanalysis effort. Tree finalization is gated on this go/no-go.
- **Code chunking.** Code lives in the tree, chunked so only touched chunks need witnesses. This needs updated pricing, and we can likely bump the contract size limit.
- **Friendly for partial statelessness.** Witnesses small enough that VOPS / partial-state operation is practical.
- **Migration.** MPT → binary tree is a one-time conversion over the full live state, historically the part that sinks timelines. Decide overlay-tree vs flag-day conversion, who bears conversion cost, and how long clients run dual trees. Witness format must agree with the zkEVM execution-witness / stateless-guest interface.

> **Validating viability with the ecosystem.** Alongside the necessity question, we want to actively surface any feedback that would make us *not* do the migration at all — e.g. a major app or wallet (Uniswap, MetaMask) for whom this is unworkable. We treat "things will break" not as a veto but as a signal of how much warning the ecosystem needs to adapt; a genuine blocker would be something stronger. We will consult client teams and major app/wallet/contract owners and use the answers to confirm or reconsider the project.

#### Should we do the partial binary tree before mandatory proofs?

The partial binary tree (PBT) is fundamentally a **tech-debt cleanup**. If we were designing Ethereum's state commitment today, we would not choose the MPT — a binary tree with a zk-friendly hash is the better long-term structure for small proofs and proving-friendliness. But we are not designing from scratch: we already have the MPT, with the entire ecosystem built on top of it. The decision is therefore not "MPT vs. PBT on the merits" but "is moving worth the cost, *now*, given that we are already here." On its own merits — i.e. absent an external blocker — we currently judge that the costs of migrating arguably outweigh the benefits, which is why this workstream stays deferred and conditional.

Two considerations qualify that conclusion and keep the question genuinely open rather than settled. First, **code chunking is a blocker for mandatory proofs**, so we will have to build a chunk-level overlay transition (and the associated tooling, testing, and migration practice) regardless of whether we ever do the full PBT. That means a meaningful slice of the PBT machinery is work we are committed to anyway, which lowers the marginal cost of going further. Second, **if the MPT's hashing performance turns out to be insufficient for the ZKVM** (the change the ZKVM team actually wants is the hash function, to cut proving time), then a tree transition becomes unavoidable — and at that point doing the PBT is the clear choice, because it is a hard blocker for something we must ship. These two points are the pivots: the first says part of the work is unconditional, the second says the whole decision flips the moment ZKVM confirms a hard dependency.

**Arguments for doing it sooner (before / alongside mandatory proofs):**

- **The migration only gets harder over time.** A one-time MPT → binary-tree conversion scales with the size of the live state. Even with EIP-8037 holding the growth rate down, the trie keeps growing, so the longer we wait the larger and slower the conversion — and some migration approaches feasible at today's state size may become infeasible later. The earlier we move, the more optionality we preserve.
- **Post-mandatory-proofs incentive risk.** Once proofs are mandatory, the trie migration falls off the critical path, but asking nodes to also carry the migration's extra work then adds an incentive for them to simply drop state. Doing the migration *before* that point avoids stacking a fresh reason-to-drop-state on top of the one mandatory proofs already creates.
- **Smaller proofs** — though this is a weak benefit in practice. PBT reduces witness/proof *size*, but proof *generation* time is roughly unchanged, so the gain is essentially bandwidth. Proof consumption today is near zero (SnapSync is effectively the only place, and it already syncs ~300 GB fully proven in ~4 hours), so we do not lean on this as a primary justification.

**Arguments against / for deferring:**

- **Limited ROI for end users.** A tree swap is invisible to users: after the migration they are in the same position, with no new features they can feel — unlike, say, Verkle's stateless scaling story. We would be spending the largest fork change yet (touching apps, wallets, RPCs, and many Solidity contracts) to deliver, in the best case, no perceptible user benefit — and in the worst case, breakage. The return on investment is poor unless the migration unlocks something genuinely blocked.
- **Validator burden.** An overlay transition requires validators to hold two trees at once — roughly double the disk — during the migration. In practice this forces history expiry first, and nodes that don't comply risk running out of space and crashing. Layered on top of EPBS's hardware demands, this is a real robustness risk for the home-staker hardware we are explicitly building for, and most of the hard problems here are operational and coordination problems rather than purely technical ones.

**Where this leaves us.** The decision hinges on the external trigger already noted above: if the ZKVM team confirms PBT (or the hash change) is a hard blocker, the case for doing it now is clear and we proceed. Absent that, the unconditional code-chunking work proceeds regardless, and we treat full PBT as a later, larger step we can sequence after mandatory proofs — accepting the "migration gets harder over time" cost as the price of not betting a years-long, high-risk effort on a change with limited user-facing payoff.

## Milestones

Note: the 🤔 emoji denotes topics we are not sure about

### Short term (end 2026)

- DB optimizations: explore if a cold/hot state breakdown is feasible. **First assess whether hot/cold separation is needed and what benefit it yields before committing to full implementation** (Carlos already prototyping). Explore optimizations for supporting the binary tree design.
- Look into BAL-supported snap sync (snap2) 🤔
- State pricing groundwork: finish multidimensional pricing and propose EIP-7999 for Hegota. Review storage create/clear pricing and accounting. Assess the necessity and benefit of hot/cold data repricing before committing (expect an EIP-8037-style path: all clients implement, benchmark, then price on the aggregate).
- Kickoff **state-serving / RPC-decentralization** track: explore the solution space and prototype the **near-term centralized first phase**, an "Nginx-like" aggregator/load-balancer letting existing full nodes serve state to users. Scope a DappNode collaboration or grant (pending leadership buy-in, not DappNode-only).
- Confirm binary-tree necessity 🤔: hold a stakeholder meeting (Justin, Ignasio, Kev, architecture team) to determine whether the migration is a hard blocker for ZKVM or privacy/AA. In parallel, consult client teams and major app/wallet teams to surface any feedback that would make us *not* do it. Proceed with spec/prototype work unless a genuine blocker emerges.
- VOPS: spec + prototype client running on the validity-only subset 🤔

### Medium term (middle 2027)

- DB optimizations: prototype and benchmark a new DB design based on results from early explorations.
- Binary tree 🤔: if confirmed as a blocker, finalize the spec (EIP-7864) and migration design and propose it. Otherwise keep MPT and revisit.
- State-serving incentives: research from first principles (mandate-holding vs. profitable-serving paths). Not required to be solved this period.
- First spec + prototype for new state types (temporary storage and/or UTXOs) with resurrection bitfields. Reference ERC-20 balance workflow on top.
- Partial-stateless (VOPS) clients in production, used by FOCIL includers 🤔
- Centralized state-serving first phase in beta. Measure performance as an RPC alternative and a syncing alternative. (A fully distributed state network, DHT/IPFS/Portal-like, remains a longer-term end-game.)

## Dependencies & sequencing

- **Binary tree is gated on external demand.** Whether we start the migration now depends on the ZKVM team confirming it is a hard blocker for their ship date (driven by proving time and the hash-function change), or on privacy/AA needing new protocol-level state types. Absent that confirmation, MPT stays and the other five workstreams proceed without it.
- **Binary tree precedes/accompanies statelessness.** VOPS and partial-state nodes need witnesses small enough to be practical, which the binary tree provides (relevant once the migration is triggered).
- **zk-friendly hash gates trie finalization.** We want to avoid two tree migrations, so we need to decide on the hash function before shipping the binary tree.
- **Mandatory proofs is the enabling event** for validators dropping state. The state project should be ready to exploit it, not blocked on it (the trie change does need a hardfork, opt-in proving does not).
- **New state types depend on the trie** being "friendly to new types of state."
- **State serving must exist before state grows.** Treat a deployed, decentralized state-retrieval path as a hard gate on raising state-growth targets, not a follow-up.
- **Trie witness format must match the zkEVM** execution-witness / stateless-guest interface (cross-team).

## Risks & how we de-risk

The ways this project can shoot itself in the foot, and how we avoid each:

- **Growing state faster than we can serve it.** Raising growth targets before a real state-serving path exists just hands more users to centralized RPC, the exact outcome we're trying to avoid. *De-risk:* treat a deployed state-serving path (starting with the centralized first-phase aggregator) as a hard gate on raising state-growth targets, not a follow-up.
- **Two tree migrations.** Shipping the binary tree on an interim hash and then re-migrating to the target hash would mean paying the most expensive, timeline-sinking step twice. *De-risk:* gate trie finalization on the zk-friendly-hash go/no-go (Poseidon2 cryptanalysis) so we migrate once.
- **Migration overruns the timeline.** A one-time MPT → binary-tree conversion over the full live state is historically the part that sinks these efforts. *De-risk:* if and when the migration is triggered, decide overlay-tree vs flag-day early, prototype the conversion in ≥2 clients, and settle who bears conversion cost and how long clients run dual trees before committing to a rollout date.
- **Reintroducing state expiry by another name.** Expiry designs repeatedly fail on proving non-existence and on backwards-compatibility with existing ERC-20 layouts. *De-risk:* do not expire existing state. Keep it as-is but relatively pricier, and add opt-in cheaper tiers instead (see the note above).
- **Witness/interface drift from the zkEVM.** A trie or witness format that doesn't match the zkEVM execution-witness / stateless-guest interface forces rework late. *De-risk:* coordinate the witness format cross-team before finalizing the spec.
- **Locking out builders / includers via sync cost.** If syncing multi-TB state becomes too slow or hits bandwidth caps, being a builder or FOCIL includer stops being permissionless. *De-risk:* invest in BAL-assisted / executionless sync and P2P improvements in parallel with growth, not after.
