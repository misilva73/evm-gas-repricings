# Master List of ToDo's For Glamsterdam Repricings

## Rollout milestones

Middle of February:

- we have preliminary numbers for all EIPs
- we have a preliminary backward compatibility analysis

End of February:

- we have all BAL optimizations in client branches
- we can benchmark state and compute operations with BALs
- we can input gas changes into client branches and run benchmarks
- we have execution specs for all EIPs (final for EIP-8037, with possible number changes for all the others)
- we have reached out to all affected entities to collect their feedback on initial numbers

End of March:

- we have benchmarks for BAL worst-case blocks
- we have a BAL + repricings devnet, and we start testing
- we have reached out to all affected entities to collect their feedback on final numbers
- we have done an internal security review with preliminary numbers

End of April:

- we have collected community feedback on the final numbers
- we have done an external security review with preliminary numbers
- we need to have everything ready for interop

## Current workstreams - gals for end of Feb

### Benchmarking

- [ ] [Jochem Brouwer + Louis Tsai] Review tests:
  - [ ] Why are repricing tests for `ECPAIRING`, `ECRECOVER`, `KECCAK256`, and `SMOD` leading to cost decreases?
  - [ ] Do we have all the cases in the ETH transfer tests for EIP-2780?
  - [ ] Do we have all the configurations for EIP-8038?
- [ ] [Kamil Chodola] Run stateful tests on top on mainnet and bloatnet with Nethermind's tool
- [ ] [Rafael Matias] Finish Benchmarkoor and run stateful and compute benchmarks
- [ ] [Maria Silva] Run emprical analysis to derive preliminary numbers:
  - [x] EIP-7904
  - [ ] EIP-8038
  - [ ] EIP-2708

### Security and community outreach

- [ ] [Carl Beekhuizen] Run backward compatibility analysis
  - [ ] EIP-7904 with preliminary numbers
  - [ ] EIP-8038 with preliminary numbers
  - [ ] EIP-2708 with preliminary numbers
  - [ ] EIP-8037
- [ ] [Butta] Update repricings website with current numbers
- [ ] [Butta] Do a broad community outreach to ask for feedback
- [ ] [Butta] Contact affected entities from backward compatibility analysis

### EIP and spec

- [ ] [Maria Silva] Update EIPs
  - [X] Operations to reprice in EIP-7904
  - [X] Preliminary numbers for EIP-7904
  - [ ] Preliminary numbers for EIP-8038
- [ ] [Maria Silva + ?] Resolve 8037 open questions:
  - [ ] Which aggregation function to use to avoid [failure modes](https://ethresear.ch/t/failure-modes-in-eip-8037-and-state-gas-scaling/23975)?
  - [ ] Which stake growth rate (and cost increase) to target?
  - [ ] Which rounding base for `cost_per_byte` to use?
  - [ ] How to split the `CREATE` costs?
  - [ ] How to deal with tx receipts? What should cumulative gas be?
  - [ ] Is the design compatible with BALs?
  - [ ] `TX_MAX_GAS_LIMIT` enforcement: clarify that we want to enforce that max(intrinsic_regular_gas, calldata_floor_gas_cost) < `TX_MAX_GAS_LIMIT`, and leave `TX_MAS_GAS_LIMIT` - intrinsic_regular_gas available during execution. And what to do with the call data floor cost?
  - [ ] What about refunds, shouldn’t that be discounted from state gas? And how to integrate it with EIP-7778?
- [ ] Create specs:
  - [ ] [Maria Silva] EIP-7904
  - [ ] [Maria Silva] EIP-8038
  - [ ] [Ben Adams] EIP-2708
  - [ ] [?] EIP-8037
  - [ ] [Toni Wahrstätter] EIP-7976 + EIP-7981 ([PR](https://github.com/ethereum/execution-specs/pull/2133))
- [ ] [Maria Silva] Estimate how much gas each byte of calldata should cost
  - [ ] How can we translate bytes into propagation time?
    - Check [block-propagation-size](https://observatory.ethp2p.dev/latest/block-propagation-size) and [data](https://observatory.ethp2p.dev/data)
  - [ ] How much time relative to execution will we have after ePBS?

### Devnet integration

- [ ] [Toni Wahrstätter] Implement BAL optimizations in all the major clients
  - [ ] State writes: parallel state root calculation
    - Missing clients:
  - [ ] State reads: batch reads
    - Missing clients:
  - [ ] Compute: parallel execution
    - Missing clients:
