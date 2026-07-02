# State Project Roadmap

## Goals

Two key changes make us rethink how Ethereum handles state:

- **zkevm**: once proofs are mandatory in-protocol, every block ships with a proof by default. Attesting and fully-validating nodes then verify a proof and sample data via PeerDAS instead of re-executing. They no longer need to hold state, so far fewer nodes have a reason to.
- **state growth**: as we scale toward gigagas, holding and serving the full state gets harder. State grows ~100 GB/yr today. Even a conservative ~20x target implies ~2 TB/yr, or ~8 TB after four years. Pricing and new state types help, but pricing alone cannot hold growth flat while also scaling throughput. So the operational work of holding, serving, and syncing has to keep pace.

**Target.** Support a ~20x gas-limit increase (toward gigagas). Keep it feasible to build, serve, and partially-validate state on home-staker and home-builder hardware. Preserve a decentralized, non-custodial path to head-state access.

### What we want out of state

The desiderata we hold every workstream accountable to — each phrased so a workstream can *fail* it, not as a slogan:

- **Small and fast proofs — per state tier, not globally.** Today's MPT proofs are terribly big and costly, in bandwidth and compute. The base tier's proofs must get much smaller, and proofs must become attractive enough to actually be *used* (see verified serving below). Meanwhile, some state tiers may deliberately trade proof-optimality away to optimize storage density or access speed instead. Proof performance is a per-tier design axis.
- **Cheaply storeable.** Prevent forced hardware upgrades for node operators, and give big, slow, cheap disks (HDDs) a job — the cold tier should tolerate them.
- **Geographically distributed.** Under three threat models: no single jurisdiction can cut off or seize state access; no correlated datacenter/provider failure (Hetzner, OVH, AWS) takes out most holders; and users worldwide have a nearby server for fast reads.
- **Syncing feasible long-term.** Sync cost must never gate joining the network — as builder, includer, or server.
- **Throughput.** The ~20x target above.
- **Different types of state, not monolithic.** Heterogeneity as a design principle: each tier picks its own point on the (proof size, proof speed, storage cost, update cost) frontier, rather than one structure serving every need badly.
- **Held by as many machines, and served by as many entities, as possible.** The north star, operationalized: permissionless entry at low hardware cost; a minimum independent replication of every state slice; defaults that keep holding-and-serving the common behavior; and measurability of all of the above (see "Validate demand and measure the base" below). The EF's [Future of Ethereum's State](https://blog.ethereum.org/en/2025/12/16/future-of-state) warns that state otherwise concentrates with builders, RPC providers, and specialist operators — this goal is the counterweight.

**Scope note.** We assume rolling history expiry works and ships: at gigagas, history grows ~2.2 TiB/yr (see the [Hegota scaling exploration](./hegota_scaling_exploration.md)), which would dominate disk budgets before state does.

### Who still needs state after mandatory proofs

The set of state-holders shrinks to those who structurally require it:

- **Builders** (including local "home" builders running vanilla software). They need the full state to build any block.
- **FOCIL includers**. They need the **VOPS** state ([Validity-Only Partial Statelessness](https://ethresear.ch/t/a-pragmatic-path-towards-validity-only-partial-statelessness-vops/22236)) to produce inclusion lists. This is much smaller: under 1 TB even with no changes, plausibly under 512 or 256 GB, and optimizable further.
- **Users / RPC**. Anyone executing against head state. Today this requires the whole DB, which is why users fall back to centralized providers.

**Who we are building for.** In practice the work targets the **~10k reachable nodes** on the network today (per [Etherscan](https://etherscan.io/nodetracker), [ethernodes](https://ethernodes.org/), [MigaLabs/monitoreth](https://monitoreth.io/nodes), and the [500k-validator milestone](https://blockworks.co/news/ethereum-to-reach-500000-validators)). Within that group, home stakers are the core target. They are the operators most aligned with where we want things to go. Most run validators out of interest or altruism rather than profit. Solo staking pays full rewards with no pool fee, but it carries far higher reward variance ([CF Benchmarks](https://blog.cfbenchmarks.com/content/files/2024/10/Ethereum-Staking-Reward-Dynamics---CF-Benchmarks.pdf): variance falls exponentially as an operator's validator count grows) plus the burden of running a machine. So pooling via Lido is the easier economic choice. This shapes the incentives discussion below.

**State is not a blocker for VOPS.** Today total state is ~293 GB (account tree ~60 GB, VOPS state ~15–18 GB). Partial-stateful implementations are proven and documented, and full VBS support in Geth is ~1 month of work. State size is not currently a blocker for a node to run or act as an includer. The real entry barrier is having to run and maintain a machine at all. At today's sizes the CL state (Prysm, ~100–200 GB) is already larger than the account state, so FOCIL includers are not our biggest issue. This assumes that we keep the current state growth rate. However, before increasing the growth rate, we need to figure out the state serving. Also, for syncing (which we need to ensure remains viable), the solutions for builder syncing can be used for includers as well.

**Account abstraction is a growth risk to watch.** AA stores extra data per account on top of the account tree. If it grows unchecked, it inflates VOPS. A partial-stateless node can hold the account tree plus the first N storage slots of each account's subtree. This stays viable only if N is small (2–3), so we need to keep AA scoped.

### What we want to avoid

- Users having no alternative to centralized providers (Infura, Alchemy, etc.) for (verified/trustless) state access.
- New builders barred from joining because they cannot sync or store the full state.
- FOCIL includers barred from joining because they cannot sync the VOPS state.

## How we work

- **De-risk open questions first.** Where a decision hinges on something we don't yet know, we resolve the uncertainty before committing — assess benefit before building (hot/cold separation), confirm necessity before speccing (binary tree), and benchmark before pricing (EIP-8037-style). The point is to avoid sinking effort into work that a later answer could invalidate.
- **Validate demand and measure the base.** The same de-risking discipline, applied to the demand side. Several load-bearing assumptions are currently unmeasured: whether node operators actually want to serve state, whether apps would adopt new state tiers, what hardware the ~10k reachable nodes actually run, and why light clients haven't taken off. Before investing, we check — operator hardware surveys, consultations with the top state-creating apps, and user-demand checks are part of the plan, not afterthoughts.
- **Ship iteratively.** Prefer near-term, net-positive steps that stand on their own over big-bang changes — e.g. the centralized "Nginx-like" aggregator before a fully distributed state network, and DB optimizations that pay off independently of the trie migration.
- **Parallel, loosely-coupled workstreams.** The five near-term tracks proceed largely in parallel and unconditionally; we keep dependencies explicit so they can move independently until the points where they genuinely must converge.
- **Open collaboration.** The project is large, the team is small, and the changes span the whole stack, so this has to be an ecosystem effort. We leverage collaborations with aligned teams and individuals, and focus our own effort on the high-leverage tasks and on coordination rather than trying to build everything ourselves.
- **Keep exploration on always.** We should always have a window every X period of time to dedicate to stay up to date with ecosystem improvements, perform tightly-scoped exploration and in general, be able to keep up the innovation & research (strictly necessary to carry our duties on the most informed way possible) while at the same time not allowing this to induce lag or delays on our priority work for each fork.

## What do we need to solve?

The work breaks into **six workstreams**. Five are near-term and proceed largely in parallel and unconditionally; the sixth — the binary tree — is deferred and conditional on quantitative re-entry triggers. They share dependencies but can largely proceed independently until the trie migration.

**Priorities.** If forced to rank, the order is:

1. **State serving / RPC-decentralization**. Raising growth targets and scaling throughput deepens centralization unless a decentralized retrieval path exists first. Highest priority and most under-explored. The infrastructure for serving state (tx-submission APIs, latency, small-enough proofs) is the same whether or not serving is incentivized, so this track proceeds regardless of how the incentives question resolves.
2. **DB optimizations & state-growth control**. Near-term, net-positive work that is largely independent of the trie migration. Hot/cold separation lowers operational cost and raises throughput. Multidimensional pricing and new state types control the growth rate. Lower risk and largely additive.
3. **State-serving incentives**. A mid-term, first-principles research question (mandate holding vs. make serving profitable). We do not need to solve it by end of 2026. We have time because growth stays controllable through existing pricing machinery (keeping EIP-8037 in place).
4. **Binary tree + zk-friendly hash** 🤔. It remains a strong long-term tree design, but it is **not** a near-term state-project priority on its own merits — and ZKEVM does not change that: realtime proving was achieved on today's keccak MPT, and no zkEVM milestone conditions mandatory proofs on a tree change. Whether we ever start is **gated on quantitative re-entry triggers** (see the binary-tree section), not on a stakeholder confirming a blocker.

The single thing we most need to get right is **state serving**. It is both the hardest and the least-understood, and it bounds how aggressively everything else can move.

The first five workstreams share an umbrella goal: keep building, serving, and partially-validating state feasible on home-staker and home-builder hardware, even under gigagas throughput. The sixth ships a trie built for a post-zkevm, gigagas chain.

### State serving / RPC decentralization

Goal: a decentralized path for users to *retrieve* head state without defaulting to centralized RPC, and keep syncing that state permissionless. The hard one, and a prerequisite (not an afterthought) for letting state grow.

- **State serving workflow.** Today any full node can already serve everything a normal user needs: balances, call simulation, gas estimation, and proofs. Only archive is missing, and almost no one needs that. The real gap is **discovery**. Users don't know which node to ask, so they fall back to Infura/Alchemy. We frame this as a **"state network" work stream** with phases:
  - *Near-term first phase:* a more centralized **"Nginx-like" aggregator/load-balancer** that existing full nodes subscribe to, distributing user requests across peers. This lets the thousands of nodes already holding state (and doing nothing with it beyond SnapSync) actually serve users. Very likely a no-brainer — but we treat it as a hypothesis until operator outreach confirms nodes will actually opt in (see "Validate demand and measure the base"). Phase-1 design must also consider read privacy: users' queries expose address-level interest to whichever operator serves them, so IP stripping and query mixing belong in the aggregator spec (see Risks). Likely pursued via a DappNode collaboration or grant.
  - *Middle phase:* state sharded among home nodes with the **aggregator doing the routing** — each serving node holds a slice plus the account trie (see partial-stateful serving below), so the collective covers the full state without any single machine holding it all.
  - *End-game:* a truly distributed state network (DHT / IPFS-like). This is far enough out, and underspecified enough, that it should **not** drive current design decisions. The [Portal Network](https://ethportal.net/resources/faq) is the cautionary tale: its state network never left early development and [trin is no longer maintained](https://github.com/ethereum/trin) — evidence for the centralized-first phasing, not against the end goal.

  The infrastructure (sharded state, small-enough proofs, latency, the user-facing API) is the same whether serving is altruistic or incentivized, so this work proceeds independently of the incentives question. Note: serving state to users covers the RPC calls needed to submit transactions. It is distinct from being a full public RPC, which additionally implies profit-seeking and broad discoverability.
- **Verified serving — proofs as first-class products.** Every state response should be able to carry a proof, verifiable against a head state root that mandatory proofs make universally trustworthy. **SNARK-wrapping MPT branches gives ~constant-size query proofs without any tree change** — generation cost and latency are the things to benchmark. This is also the moat versus centralized RPC: serving proofs at scale is what centralized providers can't do cheaply (see incentives below). And it has anchor customers today: **L2s and bridges are the biggest real consumers of state proofs** (and the loudest breakage victims of any commitment change), so they belong in this workstream's design loop. 🤔 Related research: **proof-carried trie updates** — proofs or BAL extensions that ship the updated intermediate nodes along touched paths, so trie-holding nodes skip re-hashing and flat-state nodes stay current entirely from proven diffs (ZKEVM or MPT).
- **Partial-stateful serving nodes.** A node holding the full account trie (~60 GB — enough to keep *generating* account and hot-state proofs) while shedding the multi-TB contract-storage long tail can serve most user needs. This lowers the hardware bar to join the serving set, directly serving "served by as many entities as possible."
- **Onboarding new home-nodes** 🤔. Beyond defending the existing ~10k, can we grow the set? Candidate value propositions: self-sovereign RPC, read privacy, staking. A hypothesis to test via outreach before we invest.
- **Archive-node satellites as backstop.** A handful of well-known heavy/archive operators pinned as sync-bootstrap seeders of last resort, so syncing never dies even if regular serving decays. Archive/history serving also needs an owner for the resurrection path of expiring state tiers (era files / torrents — see new state types).
- **Syncing.** Being a builder must stay permissionless and not unreasonable to set up. Even at perfect efficiency, syncing multi-TB state is slow and can hit bandwidth caps. Use BAL-assisted / executionless sync and P2P improvements. The artifacts now exist: [EIP-7928](https://eips.ethereum.org/EIPS/eip-7928) block-level access lists (a Glamsterdam headliner), [EIP-8159](https://eips.ethereum.org/EIPS/eip-8159) (eth/71 BAL exchange), and [EIP-8189](https://eips.ethereum.org/EIPS/eip-8189) (snap/2, BAL-based state healing). 🤔 We should also set a quantified sync budget (e.g. fresh sync ≤ N days on home bandwidth at target state size) so "viable" stays measurable.

### DB optimizations

Goal: client DBs that stay cheap to operate at multi-TB state.

Present-day client DBs were not designed for multi-TB state. Each write updates $O(\log n)$ tree nodes, and each node update costs $O(\log n)$ DB operations, so per-write cost grows as $O(\log^2 n)$. The constant factors balloon once the state no longer fits in RAM ($n \gg$ RAM). We want to refine and adopt multi-TB-capable designs, with **hot/cold separation** so cold state can live in flat files (cheaper media) rather than the live DB. This is a near-term track independent of the trie migration. It lowers operational cost and raises throughput for the average machine, bringing down the cost of running a node. Before committing to full implementation (and any hot/cold data repricing), first assess what benefit it actually yields. Repricing in particular would resemble EIP-8037 (all clients implement, we benchmark, then price on the aggregate), so it should not start before we are confident it ships.

The hot/cold hypothesis now has published legs: [EIP-8188](https://eips.ethereum.org/EIPS/eip-8188) specifies last-written-block hot/cold metadata (deliberately with no gas changes), and weiihann's empirical work shows ~94% of storage writes hit state written within the last 30 days, while the top 1% of accounts absorb 96–98% of reads ([Hot-Cold Storage Separation in Practice](https://ethresear.ch/t/hot-cold-storage-separation-in-practice/25119), [The Anatomy of Ethereum's State Access](https://ethresear.ch/t/the-anatomy-of-ethereum-s-state-access/25317)). Cold state should explicitly target **HDDs** — big, slow, cheap disks need a job (see "What we want out of state"). And since client teams already invest heavily in DB engineering, this track should coordinate and harvest that work rather than parallel-build (see "Open collaboration").

The pricing side of hot/cold separation: [EIP-8038](https://eips.ethereum.org/EIPS/eip-8038) raises cold-access costs, [EIP-8057](https://eips.ethereum.org/EIPS/eip-8057) discounts recently-touched state (accesses within the last 32 blocks cost near-warm, tracked via BALs), and 🤔 **witness-carrying transactions** could earn a discount for shipping witnesses of the cold state they touch — compensating the network for state nobody had to hold hot. We keep the assess-first stance, with one caveat named: temporal-locality pricing makes gas depend on recent-block access history — pricing becomes stateful, which BALs make trackable, but the edge cases get subtler.

Two post-mandatory-proofs directions to explore:

- **Flat-state-only clients.** 🤔 Once every block carries a validity proof and a [BAL](https://eips.ethereum.org/EIPS/eip-7928), a node can hold flat KV state only — no trie at all — staying current by applying proven BAL diffs. This is the cheapest possible state-holding node (intermediate trie nodes are roughly half the DB) and a big win for "held by as many machines as possible." The honest caveat: such nodes cannot generate Merkle proofs or serve snap-sync range proofs, so trie-keeping nodes (partial-stateful servers, archive satellites) remain necessary — the tiers complement rather than replace each other.
- **Lthash flat state roots** 🤔. Tempo's [TIP-1078](https://tips.sh/1078) replaces the MPT state root with a flat homomorphic accumulator (BLAKE3-based lthash16): one lattice element per account/slot, and root updates are subtract-old + add-new — no intermediate nodes, no re-hashing, order-independent. It has **no membership proofs**, which is exactly why it only becomes viable under mandatory proofs: proof-chain induction replaces per-access authentication. If it works, it removes intermediate-node storage, most of the state share of in-guest proving cost, *and* the tree-migration problem (a background shadow pass builds the accumulator — no structural conversion). The costs are real: a new consensus-critical cryptographic assumption needing dedicated cryptanalysis, and it breaks every MPT-proof consumer (bridges, L2s) — so SNARK query proofs (see verified serving) must exist first. Worth exploring, not a committed direction.

### State-growth control (pricing + new state types)

Goal: hold the growth rate controllable while throughput scales, without expiring existing state.

- **State pricing.** [EIP-7999](https://eips.ethereum.org/EIPS/eip-7999) for the unified fee market — and cap the growth rate on dynamic state. Review state clearing pricing.
- **New types of state** (instead of state expiry, see note below). Introduce cheaper, more restrictive tiers alongside existing state: **temporary storage** (a tree zeroed each period, e.g. monthly) and **UTXOs**, with out-of-order **resurrection** via per-period spent/unspent bitfields. Permanent storage stays for accounts, code, and core composable contracts. Balances, NFTs, and short-lived event state move to the cheaper tiers. Opt-in, app-by-app. Ref: [Hyper-scaling state by creating new forms of state](https://ethresear.ch/t/hyper-scaling-state-by-creating-new-forms-of-state/24052).
- **Write-once state** 🤔. An opt-in tier for state written once and never mutated (no proposal exists under this name; the closest relatives are the UTXO variant in [Hyper-scaling state](https://ethresear.ch/t/hyper-scaling-state-by-creating-new-forms-of-state/24052). The properties compound: never re-hashed on update, friendly to append-only accumulators, ideal for cold/HDD media — and **proofs of write-once state never invalidate**, so they can be cached, replicated, and CDN'd indefinitely: serving this tier trivializes. Open design questions: enforcement (tier declaration at creation) and pricing (pay-once-store-forever must be priced honestly). Crucially this is **opt-in for new state only** — never a forced conversion of existing state, which would be expiry by another name (see the note below).
- **Privacy-tailored state.** Privacy protocols are the strongest concrete customer for the new tiers: commitment trees are append-only, and nullifier sets are write-once *by construction*. Designing for them turns privacy from a hypothetical trigger into a named consumer. The honest note: nullifier sets grow forever by design, so the tier they live in must meter and structurally handle unbounded growth (accumulators, epoching).
- **Multi-roots in the block** 🤔. The enabling mechanism for all of the above: the header commits to one root per state tier, and each tier picks its own commitment scheme — its own point on the (proof size, proof speed, storage cost, update cost) frontier. No standalone proposal exists; the idea appears embedded in overlay-migration designs ([EIP-7612](https://eips.ethereum.org/EIPS/eip-7612)) and implicitly in [Hyper-scaling state](https://ethresear.ch/t/hyper-scaling-state-by-creating-new-forms-of-state/24052). Costs to spec honestly: header/engine-API changes, cross-tier transaction atomicity, and per-tier tooling/wallet complexity. (Vitalik's [2018 multi-root analysis](https://ethresear.ch/t/detailed-analysis-of-stateless-client-witness-size-and-gains-from-batching-and-multi-state-roots/862) found negligible *witness* savings — that targeted a different goal and doesn't refute the storage-model use.)

> **Note — no state expiry.** A decade of state-expiry designs all hit the same problem: proving *non-existence* (that nothing was ever created at an address/slot), which has no representation meaningfully smaller than the state itself. The address-period / CREATE3 mitigation isn't understood by existing ERC-20 storage layouts, so it isn't backwards-compatible. We therefore do **not** pursue automatic expiry of existing state. Instead we keep current state as-is but relatively pricier, and add new cheaper tiers that apps opt into.

### State-serving incentives

Goal: a sustainable answer to *why* nodes hold and serve state.

A separate, mid-term research question rather than a blocker. Two paths. (a) *Mandate holding*: make holding and serving a small slice of state (e.g. ~300 GB, not the whole thing) a condition for validator rewards, leaning on the power of defaults. (b) *Make serving profitable*: change the protocol so serving state earns a small recurring revenue (e.g. a market for ZK state proofs, which centralized providers can't serve at scale because proofs are expensive to generate). Path (b) is harder but the only long-term-sustainable option. We have time to research this from first principles because growth stays controllable via existing pricing (keeping EIP-8037 in place). It does not need to be solved by end of 2026. Target audience: the ~10,000–11,000 reachable nodes running today (home stakers being the core subset, see "Who we are building for" above).

There is also a pragmatic third path that needs no protocol change and can start now: **out-of-protocol revenue sharing via the aggregator** — premium access (API keys, SLAs) with revenue kicked back to the home nodes serving behind it. [Lava Network](https://www.lavanet.xyz/) shows out-of-protocol RPC markets work at scale. This doubles as a live experiment feeding the long-term research. One requirement is non-negotiable from day one: **sybil resistance** — the moment serving pays, fake serving follows (self-dealt queries, sybil backends), and as the EF's [Future of Ethereum's State](https://blog.ethereum.org/en/2025/12/16/future-of-state) puts it, "there's currently no good way to prove entities actually serve state." Note also that the power of defaults, which path (a) leans on, is one of the operational mechanisms under "What we want out of state" above.

### Partial statelessness (VOPS)

Goal: let validators and FOCIL includers operate on a small validity-only subset of state instead of the full set.

Partial-stateful implementations are proven and documented (see "State is not a blocker for VOPS" above). Post-BALs and mandatory proofs, partial nodes keep their slice current by applying **proven BAL diffs** — no Merkle witnesses sit on their critical path (witnesses matter mainly for snap-sync range proofs and for serving). The binary tree is therefore *not* a prerequisite here (see the binary-tree section).

### Binary tree — new trie structure (design + migration) 🤔

Goal: a trie built for small proofs and proving-friendliness on a post-zkevm, gigagas chain. Migration is part of this workstream, so design and rollout stay together.

- **Small proofs through a binary tree.** Two options: a full tree migration ([EIP-7864](https://eips.ethereum.org/EIPS/eip-7864)) or a [partial binary tree](https://cperezz.github.io/pbt-spec/) where we move everything except contract storage. Decide on the final design and prototype, but only once a re-entry trigger fires (see below). Note that even a partial transition (accounts + code chunking, leaving the storage tree on MPT) will break a meaningful part of the ecosystem (e.g. CowSwap-style contracts needing upgrades).
- **zk-friendly hash.** BLAKE3 as the interim hash. Poseidon2 as the target, pending the dedicated Poseidon cryptanalysis effort. Tree finalization is gated on this go/no-go.
- **Code chunking.** Code lives in the tree, chunked so only touched chunks need witnesses. This needs updated pricing, and we can likely bump the contract size limit.
- **Friendly for heavy witness consumers.** Witnesses small enough that serving and sync-range proofs stay practical at scale. (Note: VOPS itself no longer depends on this — post-BALs, partial nodes update from proven diffs; see partial statelessness.)
- **Migration.** MPT → binary tree is a one-time conversion over the full live state, historically the part that sinks timelines. Decide overlay-tree vs flag-day conversion, who bears conversion cost, and how long clients run dual trees. Witness format must agree with the zkEVM execution-witness / stateless-guest interface.

> **Validating viability with the ecosystem.** Alongside the trigger question, we want to actively surface any feedback that would make us *not* do the migration at all — e.g. a major app or wallet (Uniswap, MetaMask) for whom this is unworkable. We treat "things will break" not as a veto but as a signal of how much warning the ecosystem needs to adapt; a genuine blocker would be something stronger. We will consult client teams and major app/wallet/contract owners and use the answers to confirm or reconsider the project.

#### Should we do the partial binary tree before mandatory proofs?

The partial binary tree (PBT) is fundamentally a **tech-debt cleanup**. If we were designing Ethereum's state commitment today, we would not choose the MPT. But we are not designing from scratch: we have the MPT with the entire ecosystem built on top of it, so the decision is not "MPT vs. PBT on the merits" but "is moving worth the cost *now*, given that we are already here?" 
 Our answer is **no — and we say so directly rather than hiding it behind a conditional trigger**. The migration is a massive amount of work, complexity, and risk — the largest fork change Ethereum would ever attempt — for benefits that are not deal-breaking. If the team can only push a few things, the PBT crowds out the higher-ROI work above; and if the PBT were the last thing we shipped, the end user and the protocol would be in essentially the same position — state just as heavy, serving just as unsolved.

**ZKEVM and the PBT are mostly orthogonal** Realtime proving was achieved at the end of 2025 on today's keccak hexary MPT: 99% of mainnet blocks proven in under 10 s on ≤$100k hardware, with witness verification *inside* the guest ([EF zkEVM update](https://blog.ethereum.org/2025/12/18/zkevm-security-foundations)), and [Pico Prism 2.0](https://blog.brevis.network/2026/05/12/pico-prism-2-0-a-5-3x-efficiency-leap-in-real-time-ethereum-proving/) now averages 6.1 s at the 60M gas limit.

Two considerations keep the question genuinely open. First, **code chunking is a blocker for mandatory proofs**, so we will build a chunk-level overlay transition (with its tooling, testing, and migration practice) regardless of whether we ever do the full PBT. A meaningful slice of the PBT machinery is therefore work we are committed to anyway, which lowers the marginal cost of going further. Second, **if the MPT's hashing performance turns out to be insufficient for the ZKVM** (the ZKVM team's real ask is the hash function, to cut proving time), a tree transition becomes unavoidable. At that point the PBT is the clear choice, because it is a hard blocker for something we must ship. These are the two pivots. The first says part of the work is unconditional. The second says the whole decision flips the moment ZKVM confirms a hard dependency.

**Small proofs don't need tree surgery either.** PBT's other benefit — smaller state proofs — is consumed today almost solely by SnapSync (which already syncs ~300 GB fully proven in ~4 hours). Two tree-agnostic developments cap its value further: **SNARK-wrapping** gives ~constant-size query proofs over the *existing* MPT (see verified serving), and the post-mandatory-proofs design space contains candidates that leapfrog trees entirely — e.g. flat homomorphic state roots ([Lthash / TIP-1078](https://tips.sh/1078); see DB optimizations). Migrating now risks paying the biggest change in Ethereum's history to land on the wrong target.



**Arguments for doing it sooner:**

- **The migration only gets harder over time.** A one-time MPT → binary-tree conversion scales with the size of the live state; the longer we wait, the larger and slower the conversion, and some approaches feasible today may become infeasible later. We accept this consciously as the price of not betting a years-long, high-risk effort on a change with limited user-facing payoff.
- **Post-mandatory-proofs incentive risk.** Once proofs are mandatory, asking nodes to also carry migration work gives them a fresh incentive to drop state. If a trigger fires late, this cost is real.

**Arguments against**

- **Limited ROI for end users.** A tree swap is invisible to users. After the migration they are in the same position, with no new features they can feel, unlike Verkle's stateless scaling story. We would spend the largest fork change yet (touching apps, wallets, RPCs, and many Solidity contracts) to deliver, at best no perceptible user benefit, at worst breakage. The ROI is poor unless the migration unlocks something genuinely blocked.
- **Validator burden.** An overlay transition requires validators to hold two trees at once, roughly double the disk, during the migration. In practice this forces history expiry first, and nodes that don't comply risk running out of space and crashing. Layered on top of EPBS's hardware demands, this is a real robustness risk for the home-staker hardware we are building for. Most of the hard problems here are operational and coordination problems, not purely technical ones.

**Where this leaves us.** The decision hinges on the external trigger noted above. If the ZKVM team confirms PBT (or the hash change) is a hard blocker, the case for doing it now is clear and we proceed. Absent that, the unconditional code-chunking work proceeds regardless, and we treat full PBT as a later, larger step to sequence after mandatory proofs. We accept the "migration gets harder over time" cost as the price of not betting a years-long, high-risk effort on a change with limited user-facing payoff.

## Milestones

Note: the 🤔 emoji denotes topics we are not sure about

### Short term (end 2026)

- DB optimizations: explore if a cold/hot state breakdown is feasible. **First assess whether hot/cold separation is needed and what benefit it yields before committing to full implementation** (Carlos already prototyping). Explore optimizations for supporting the binary tree design.
- Look into BAL-supported snap sync (snap2) 🤔
- State pricing groundwork: finish multidimensional pricing and propose EIP-7999 for Hegota. Review storage create/clear pricing and accounting. Assess the necessity and benefit of hot/cold data repricing before committing (expect an EIP-8037-style path: all clients implement, benchmark, then price on the aggregate).
- Kickoff **state-serving / RPC-decentralization** track: explore the solution space and prototype the **near-term centralized first phase**, an "Nginx-like" aggregator/load-balancer letting existing full nodes serve state to users. Scope a DappNode collaboration or grant (pending leadership buy-in, not DappNode-only). Validate operator demand as part of the scoping, and scope the out-of-protocol revenue-share experiment alongside.
- Reframe the binary-tree question quantitatively 🤔: hold the stakeholder meeting (Justin, Ignacio, Kev, architecture team) but ask the measurable question — at what gas limit, on what hardware envelope, does keccak-MPT in-circuit witness verification cap proving? In parallel, consult client teams and major app/wallet/L2-bridge teams on migration viability. The spec stays warm on paper; no prototype commitment unless a re-entry trigger fires.
- VOPS: spec + prototype client running on the validity-only subset 🤔

### Medium term (middle 2027)

- DB optimizations: prototype and benchmark a new DB design based on results from early explorations.
- Binary tree 🤔: revisit the re-entry triggers against a year of dashboard data. If one fired, finalize the spec (EIP-7864 or PBT) and migration design and propose it. Otherwise keep MPT and keep tracking.
- State-serving incentives: research from first principles (mandate-holding vs. profitable-serving paths). Not required to be solved this period.
- First spec + prototype for new state types (temporary storage and/or UTXOs) with resurrection bitfields. Reference ERC-20 balance workflow on top.
- Partial-stateless (VOPS) clients in production, used by FOCIL includers 🤔
- Centralized state-serving first phase in beta, **including verified serving (proof-carrying responses)**. Measure performance as an RPC alternative and a syncing alternative. (A fully distributed state network, DHT/IPFS-like, remains a longer-term end-game.)

## Dependencies & sequencing

- **Binary tree is gated on quantitative triggers.** Whether we ever start the migration depends on measured re-entry triggers (in-circuit proving share capping target gas; witness bandwidth capping sync/serving — see the binary-tree section), or on privacy/AA needing new protocol-level state types. Absent a fired trigger, MPT stays and the other five workstreams proceed without it.
- **Statelessness no longer waits on the binary tree.** Post-BALs + mandatory proofs, VOPS and partial-state nodes stay current via proven BAL diffs; witnesses matter mainly for snap-range proofs and serving. (This reverses an earlier assumption in this document.)
- **zk-friendly hash gates trie finalization.** We want to avoid two tree migrations, so we need to decide on the hash function before shipping the binary tree.
- **Mandatory proofs is the enabling event** for validators dropping state. The state project should be ready to exploit it, not blocked on it (the trie change does need a hardfork, opt-in proving does not).
- **New state types need a commitment home** — either the main trie being "friendly to new types of state," or per-tier roots via multi-roots in the block (see state-growth control).
- **State serving must exist before state grows.** Treat a deployed, decentralized state-retrieval path as a hard gate on raising state-growth targets, not a follow-up.
- **Trie witness format must match the zkEVM** execution-witness / stateless-guest interface (cross-team).
- **SNARK query proofs precede any commitment change.** L2 bridges and apps verify state proofs against the L1 root; any change to the commitment (PBT, Lthash) needs a proof-continuity story first (see verified serving).
- **Fork context.** BALs and ePBS are Glamsterdam headliners; EIP-8025 (optional execution proofs) and EIP-7999 are proposed for Hegotá. The milestones above inherit these dates.

## Risks & how we de-risk

The ways this project can shoot itself in the foot, and how we avoid each:

- **Growing state faster than we can serve it.** Raising growth targets before a real state-serving path exists just hands more users to centralized RPC, the exact outcome we're trying to avoid. *De-risk:* treat a deployed state-serving path (starting with the centralized first-phase aggregator) as a hard gate on raising state-growth targets, not a follow-up.
- **Two tree migrations.** Shipping the binary tree on an interim hash and then re-migrating to the target hash would mean paying the most expensive, timeline-sinking step twice. A variant of the same risk: migrating to a tree whose raison d'être the post-mandatory-proofs world no longer needs (SNARK-wrapped query proofs, flat homomorphic roots) — paying the biggest change for the wrong target. *De-risk:* gate trie finalization on the zk-friendly-hash go/no-go (Poseidon2 cryptanalysis) so we migrate once, keep the re-entry triggers quantitative, and keep the alternatives research (Lthash, SNARK query proofs) alive before any migration decision.
- **Migration overruns the timeline.** A one-time MPT → binary-tree conversion over the full live state is historically the part that sinks these efforts. *De-risk:* if and when the migration is triggered, decide overlay-tree vs flag-day early, prototype the conversion in ≥2 clients, and settle who bears conversion cost and how long clients run dual trees before committing to a rollout date.
- **Reintroducing state expiry by another name.** Expiry designs repeatedly fail on proving non-existence and on backwards-compatibility with existing ERC-20 layouts. *De-risk:* do not expire existing state. Keep it as-is but relatively pricier, and add opt-in cheaper tiers instead (see the note above).
- **Witness/interface drift from the zkEVM.** A trie or witness format that doesn't match the zkEVM execution-witness / stateless-guest interface forces rework late. *De-risk:* coordinate the witness format cross-team before finalizing the spec.
- **Locking out builders / includers via sync cost.** If syncing multi-TB state becomes too slow or hits bandwidth caps, being a builder or FOCIL includer stops being permissionless. *De-risk:* invest in BAL-assisted / executionless sync and P2P improvements in parallel with growth, not after.
- **The aggregator becomes the new Infura.** The centralized first phase concentrates discovery/routing power: whoever runs it can deprioritize or censor. *De-risk:* open protocol, multiple independent aggregator instances, and node-side multi-homing from day one.
- **Paying for serving invites fake serving.** Sybil backends and self-dealt queries appear the moment revenue flows. *De-risk:* treat sybil-resistance / verifiable serving as a day-one design requirement of the revenue-share experiment, not a patch.
- **Decentralized serving leaks read patterns.** Routing user queries to random home operators exposes address-level interest to strangers — a different trust surface than one big provider, not automatically a better one. *De-risk:* IP stripping and query mixing in the phase-1 aggregator spec.
