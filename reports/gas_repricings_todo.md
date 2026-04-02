# Master List of ToDo's For Glamsterdam Repricings

## Rollout milestones

End of April:

- ⚪ we have final numbers for all EIPs
- ⚪ we have a BAL + repricings devnet, and we start testing
- ⚪ we have kicked-off an internal security review with final numbers

End of May:

- ⚪ we have a backward compatibility analysis with final numbers
- ⚪ we have a page in our website where the ecosystem can check if their contract is affected by the repricings
- ⚪ we have kicked-off an external security review with final numbers

End of June:

- ⚪ we have reached out to all affected entities from the backward compatibility analysis
- ⚪ we have a public devnet with final numbers that the community can test

## Current workstreams - goals for end of April

### Benchmarking

- [ ] [Louis] Investigate and fix issues with `test_account_query`
- [ ] [Jochem] Investigate and fix issues with `SSTORE` and `SLOAD` benchmarks
- [ ] [Rafael] Run stateful tests on Osaka + perf-devnet-3
- [ ] [Maria] Run empirical analysis to derive preliminary numbers for EIP-8038 and EIP-2780
- [ ] [Rafael] Run amsterdam-compatible tests on BAL-optimized clients (both compute and stateful)
- [ ] [Maria] Run empirical analysis to derive final numbers for EIP-7904, EIP-8038 and EIP-2780

### Security and community outreach

NA

### EIPs & Devnet integration

- [ ] [Maria] Investigate state_gas refill mechanism for 8037
- [ ] [Maria + Spencer] Review 8037 EIP, spec and tests and align everything for bal-devnet-4
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