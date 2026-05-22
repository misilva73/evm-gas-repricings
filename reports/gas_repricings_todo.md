# Master List of ToDo's For Glamsterdam Repricings

## Rollout milestones

End of April:

- 🟡 we have final numbers for all EIPs
- 🔴 we have a BAL + repricings devnet, and we start testing
- 🟡 we have kicked-off an internal security review with final numbers

End of May:

- ⚪ we have final numbers for EIP-8038
- ⚪ we have a backward compatibility analysis for 7904 and 8037
- ⚪ we have a page in our website where the ecosystem can check if their contract is affected by 7904 and 8037
- ⚪ we have reached out to all affected entities from the 7904 and 8037 backward compatibility analysis
- ⚪ we have reviewed the benchmark tests to insure we have a good coverage of the repriced operations
- ⚪ we have kicked-off an external security review with final numbers

End of June:

- ⚪ we have run the full benchmark suite against the BAL + repricings branch and have no operations performing at less than 100Mgas/s
- ⚪ we have a backward compatibility analysis for 8038 and 2780
- ⚪ we have a page in our website where the ecosystem can check if their contract is affected by 8038 and 2780
- ⚪ we have reached out to all affected entities from the 8038 and 2780 backward compatibility analysis
- ⚪ we have a public devnet with final numbers that the community can test

## Current workstreams - goals for end of May

### Benchmarking

- [ ] [Carlos] Follow-up with clients on performance improvements from interop
  - Reth: account and storage writes
  - Nethermind: storage reads
  - Geth: storage writes
  - Besu: account and storage writes
  - Erigon: everything
- [ ] Investigate failing clients:
  - [Stefan] Compute - Keep track of Erigon to see if it works
  - [Jochem + Stefan] Stateful - Reth, Besu, Erigon (keep track)
- [X] [Jochem] Improve infra for clients to test optimization performance (reach out to clients)
- [X] [Louis] Make repricing benchmark release for bal-devnet-7
- [X] [Rafael] Do larger run on bal-devnet-7
- [ ] [Maria] Analyze bal-devnet-7 results and compare with interop numbers
- [ ] [Louis] Review entire benchmark suite and ensure we are not missing worst cases (we should ask help from clients)
- [ ] [Carlos] Move bloatnet to bal-devnet-7 + EIP-8038 + EIP-7904 and run stress test
- [ ] [Louis] Create full benchmarking release for bal-devnet-7 + EIP-8038 + EIP-7904
- [ ] [Rafael] Run full benchmarks for bal-devnet-7 + EIP-8038 + EIP-7904 (need client implementations)
- [X] [Carlos] Finish State Actor tool
- [ ] [Carlos] Run State Actor tool to create a mainnet-size snapshot with all the relevant tests for the repricings
  - Contract sizes: 1 mb, 50 mb, 1 gb, 5 gb, 10 gb, 20 gb
- [ ] [Rafael] Take a look into schelk when Rafael gets back and move away from ZFS

### Security and community outreach

- [ ] [Carl] Run backward compatibility analysis for:
  - [ ] ~~7904 with interop numbers~~
  - [ ] 8037 with bal-devnet-7 spec
- [ ] [Carl] Update website with new backward compatibility analysis
- [ ] [Butta] Reach out to affected entities
- [ ] [Tyler] Kick-off internal security review on all repricing EIPs

### EIPs & Devnet integration

- [X] [Maria + Spencer] Investigate and fix missing edge cases for 8037
  - [Tracking Issue](https://github.com/ethereum/execution-specs/issues/2804#event-25277615905)
- [ ] [Maria] Update EIPs with interop numbers (7904 + partial 8038 + partial 2780)
  - [7904 PR](https://github.com/ethereum/EIPs/pull/11622)
  - [Partial 8038 PR](https://github.com/ethereum/EIPs/pull/11623)
- [ ] [Maria] Review and update 2780 EIP
- [ ] [Guru] Finish and merge spec and tests for 2780
- [ ] [Maria] Update EIP-8038 with final numbers
- [ ] [Spencer] Finish and merge spec and tests for 8038

## EIP trackers

- [7904](https://github.com/ethereum/execution-specs/issues/1879)
- [8038](https://github.com/ethereum/execution-specs/issues/1941)
- [2780](https://github.com/ethereum/execution-specs/issues/1940)
- [7976](https://github.com/ethereum/execution-specs/issues/1942)
- [7981](https://github.com/ethereum/execution-specs/issues/1943)
- [8037](https://github.com/ethereum/execution-specs/issues/2040)
