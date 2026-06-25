# Master List of ToDo's For Glamsterdam Repricings

## Rollout milestones

End of April:

- 🟡 we have final numbers for all EIPs
- 🔴 we have a BAL + repricings devnet, and we start testing
- 🟡 we have kicked-off an internal security review with final numbers

End of May:

- 🔴 we have final numbers for EIP-8038
- 🟡 we have a backward compatibility analysis for 7904 and 8037
- 🟡 we have a page in our website where the ecosystem can check if their contract is affected by 7904 and 8037
- 🔴 we have reached out to all affected entities from the 7904 and 8037 backward compatibility analysis
- 🟡 we have reviewed the benchmark tests to insure we have a good coverage of the repriced operations
- 🔴 we have kicked-off an external security review with final numbers

End of June:

- ⚪ we have finalized EIP-8038 and EIP-2780
- ⚪ we have run the full benchmark suite against the BAL + repricings branch and have no operations performing at less than 100Mgas/s
- ⚪ we have a backward compatibility analysis for 8037, 8038 and 2780
- ⚪ we have a page in our website where the ecosystem can check if their contract is affected by 8037, 8038 and 2780
- ⚪ we have reached out to all affected entities from the 8037, 8038 and 2780 backward compatibility analysis
- ⚪ we have a public devnet with final numbers that the community can test

## Current workstreams - goals for end of June

### Benchmarking

- [X] [Rafael] Move benchmarkoor infra to schelk and test
- [ ] [Rafael + Jochem] Integrate State Actor to benchmarkoor and test
- [X] [Louis] Improvements on `test_account_access`: move it to `CREATE2` + add `KECCAK` test for target size input
- [ ] [Louis] Review entire benchmark suite and ensure we are not missing worst cases (we should ask help from clients)
  - Fix tests after bal-devnet-7 merge
  - Improve CREATE worst cases: ([Issue](https://github.com/ethereum/execution-specs/issues/1577))
- [ ] [Carlos] Move bloatnet to bal-devnet-7 + EIP-8038 + EIP-7904 and run stress test
- [ ] [Louis] Create full benchmarking release for bal-devnet-7 + EIP-8038 + EIP-7904
- [ ] [Rafael] Run full benchmarks for bal-devnet-7 + EIP-8038 + EIP-7904 (need client implementations)

### Security and community outreach

- [ ] [Carlos] Run backward compatibility analysis for:
  - [X] 8037 with bal-devnet-7 spec
  - [X] 8038 with latest numbers (testing)
  - [ ] 2780 with final numbers
- [ ] [Maria] Figure out the best way to serve backward compatibility analysis to community
- [ ] [Butta] Reach out to affected entities
- [ ] [Nikos] Kick-off internal security review on all repricing EIPs

### EIPs & Devnet integration

- [X] [Maria] Update 8038 + 2780 spec shape for glamsterdam-devnet-7
- [X] [Maria] Update EIP-8038 with final numbers
- [X] [Maria] Update 2780 EIP with final numbers
- [X] [Guru] Finish and merge spec and tests for 2780
- [X] [Spencer] Finish and merge spec and tests for 8038
- [X] [Spencer + Guru + Maria] Add all EIPs to glamsterdam-devnet-7

## EIP trackers

- [7904](https://github.com/ethereum/execution-specs/issues/1879)
- [8038](https://github.com/ethereum/execution-specs/issues/1941)
- [2780](https://github.com/ethereum/execution-specs/issues/1940)
- [7976](https://github.com/ethereum/execution-specs/issues/1942)
- [7981](https://github.com/ethereum/execution-specs/issues/1943)
- [8037](https://github.com/ethereum/execution-specs/issues/2040)
