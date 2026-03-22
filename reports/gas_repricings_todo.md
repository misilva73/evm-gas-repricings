# Master List of ToDo's For Glamsterdam Repricings

## Rollout milestones

End of February:

- 🔴 we have preliminary numbers for all EIPs (missing for 8038)
- 🔴 we have a preliminary backward compatibility analysis (missing for 8038)
- 🟡 we have all BAL optimizations in client branches
- 🟢 we can benchmark state and compute operations with BALs
- 🟡 we can input gas changes into client branches and run benchmarks
- 🔴 we have execution specs for all EIPs (missing for 8038 and 7904)
- 🟢 we have reached out to all affected entities to collect their feedback on initial numbers

End of March:

- ⚪ we have benchmarks for BAL worst-case blocks
- ⚪ we have a BAL + repricings devnet, and we start testing
- ⚪ we have reached out to all affected entities to collect their feedback on final numbers
- ⚪ we have done an internal security review with preliminary numbers

End of April:

- ⚪ we have collected community feedback on the final numbers
- ⚪ we have done an external security review with preliminary numbers
- ⚪ we need to have everything ready for interop

## Current workstreams - goals for end of March

### Benchmarking

- [ ] [Louis Tsai + Jochem Brouwer] Missing tests/configs:
  - [X] `test_mod` not appearing in Kamil's data -> are we missing a flag?
  - [X] Missing configs for storage access operations ([PR](https://github.com/ethereum/execution-specs/pull/2327))
  - [X] Missing configs for account access operations
    - [Create address calculation helper](https://github.com/ethereum/execution-specs/pull/2353)
    - [EOA/contract query tests](https://github.com/ethereum/execution-specs/pull/2399)
  - [X] Bloat new ERC20 contracts and deterministic addresses
  - [X] Investigate caching issue with `test_alt_bn128_benchmark` and `test_ecrecover`.
    - The inputs are repeated, so for clients that cache results, the run-time will be much faster than a real ecPairing calculation without cache. I think we may need to update this test to vary the inputs
- [X] [Rafael Matias] Make data from Benchmarkoor SQL-queryable
- [ ] [Maria Silva] Run empirical analysis to derive preliminary numbers for EIP-8038 and EIP-2780:
  - [X] Kamil fills stateful tests with perf-devnet-3 snapshots
  - [X] Rafael runs new test suite on benchmarkoor
  - [X] Maria updates the repricings analysis code and run it with new data
  - [ ] Rafael finishes all clients syncing and takes new snapshot
- [ ] [Louis Tsai] Make tests compatible with Amsterdam so that we can run benchmarks on BAL-optimized clients
- [ ] [Rafael Matias] Run amsterdam-compatible tests on BAL-optimized clients (both compute and stateful)
  - How many cores should we target? Ask ethpandaops for it. We should anchor it to the validating node spec
- [ ] [Maria Silva] Run empirical analysis to derive final numbers for EIP-7904, EIP-8038 and EIP-2780
- [ ] Review repricing marker to reduce test runtime

### Security and community outreach

- [ ] [Carl Beekhuizen] Run backward compatibility analysis
  - [ ] EIP-8038 with preliminary numbers
  - [ ] EIP-7904 with final numbers
  - [ ] EIP-8038 with final numbers
  - [ ] EIP-2780 with final numbers
- [ ] [Butta] Contact affected entities from backward compatibility analysis
- [ ] [Butta] Contact affected entities from Call data analysis from Toni
- [ ] [Butta] Contact entities how replied to first survey

### EIPs & Devnet integration

- [ ] [Maria Silva] Update EIPs
  - [ ] Preliminary numbers for EIP-8038 + BAL data cost
  - [ ] Final numbers for 7904
  - [ ] Final numbers for 8038
  - [ ] Final numbers for 2780
- [ ] Create specs + devnet tests:
  - [ ] [7904](https://github.com/ethereum/execution-specs/issues/1879)
    - [spec + tests](https://github.com/ethereum/execution-specs/pull/2175)
  - [ ] [8038](https://github.com/ethereum/execution-specs/issues/1941)
  - [ ] [2780](https://github.com/ethereum/execution-specs/issues/1940)
    - [spec + tests](https://github.com/ethereum/execution-specs/pull/2175)
  - [X] [7976](https://github.com/ethereum/execution-specs/issues/1942)
    - [spec](https://github.com/ethereum/execution-specs/pull/2159)
  - [X] [7981](https://github.com/ethereum/execution-specs/issues/1943)
    - [spec + tests](https://github.com/ethereum/execution-specs/pull/2144)
  - [X] [8037](https://github.com/ethereum/execution-specs/issues/2040)
    - [spec + tests](https://github.com/ethereum/execution-specs/pull/2181)
- [ ] [Toni Wahrstätter] Implement BAL optimizations in all the major clients
  - [ ] State writes: parallel state root calculation
    - Missing clients: Erigon and Reth
  - [ ] State reads: batch reads
    - Missing clients: Nethermind, Erigon and Reth
  - [ ] Compute: parallel execution
    - Missing clients: Nethermind
