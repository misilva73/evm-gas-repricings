# Master List of ToDo's For Glamsterdam Repricings

## Rollout milestones

End of April:

- ⚪ we have final numbers for all EIPs
- ⚪ we have a BAL + repricings devnet, and we start testing
- ⚪ we have kicked-off an internal security review with final numbers

End of May:

- ⚪ we have reviewed the benchmark tests to insure we have a good coverage of the repriced operations
- ⚪ we have run the full benchmark suite against the BAL + repricings branch and have no operations performing at less than 100Mgas/s
- ⚪ we have a backward compatibility analysis with final numbers
- ⚪ we have a page in our website where the ecosystem can check if their contract is affected by the repricings
- ⚪ we have kicked-off an external security review with final numbers

End of June:

- ⚪ we have reached out to all affected entities from the backward compatibility analysis
- ⚪ we have a public devnet with final numbers that the community can test

## Key goals for interop

- [Kamil] Investigate why `test_ec_pairing` is failing and fix it
- [Kamil] Investigate why reth is crashing in the middle of the mainnet-24350000-amsterdam-compute runs and fix it
- [Toni] Stabilize optimizations for all clients and merge them into bal-devnet-3
- [Louis] Update tests and benchmarking tooling to run on bal-devnet-3
- [Jochem] Update mainnet snapshot with the needed contracts and accounts to run stateful tests
- [Rafael] Do the following runs (once all the above is done):
  - mainnet-amsterdam-compute
  - mainnet-amsterdam-stateful
  - perf-devnet-3-amsterdam-stateful
- [Maria] Analyse results and derive final numbers for EIP-7904, EIP-8038 and EIP-2780

## Current workstreams - goals for end of April

### Benchmarking

- [X] [Louis] Investigate and fix issues with `test_account_access`
- [X] [Jochem] Investigate and fix issues with `SSTORE` and `SLOAD` benchmarks
- [X] [Rafael] Run stateful tests on Osaka + perf-devnet-3
- [X] [Maria] Run empirical analysis to derive preliminary numbers for EIP-8038 and EIP-2780
- [X] [Rafael] Run amsterdam-compatible tests on BAL-optimized clients (both compute and stateful)
- [ ] [Maria] Run empirical analysis to derive final numbers for EIP-7904, EIP-8038 and EIP-2780
- [ ] [Jochem + Carlos] Improve State Actor tool
- [ ] [Jochem + Carlos] Run State Actor tool to create a mainnet snapshot with all the relevant tests for the repricings

### Security and community outreach

NA

### EIPs & Devnet integration

- [X] [Maria] Investigate state_gas refill mechanism for 8037
- [X] [Maria + Spencer] Review 8037 EIP, spec and tests and align everything for bal-devnet-4
- [ ] [Maria] Update EIPs with final numbers
  - [ ] 7904
  - [ ] 8038
  - [ ] 2780
- [ ] [Guru] Finish and merge spec and tests for 2780
- [ ] [Spencer] Finish and merge spec and tests for 8038
- [ ] [Toni] Implement BAL optimizations in all the major clients
- [ ] [Toni] Decide if state reads remain in BAL

## EIP trackers

- [7904](https://github.com/ethereum/execution-specs/issues/1879)
- [8038](https://github.com/ethereum/execution-specs/issues/1941)
- [2780](https://github.com/ethereum/execution-specs/issues/1940)
- [7976](https://github.com/ethereum/execution-specs/issues/1942)
- [7981](https://github.com/ethereum/execution-specs/issues/1943)
- [8037](https://github.com/ethereum/execution-specs/issues/2040)