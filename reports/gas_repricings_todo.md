# Master List of ToDo's For Glamsterdam Repricings

## Rollout milestones

End of April:

- 🟢 we have final numbers for all EIPs
- 🔴 we have a BAL + repricings devnet, and we start testing
- 🟡 we have kicked-off an internal security review with final numbers

End of May:

- ⚪ we have reviewed the benchmark tests to insure we have a good coverage of the repriced operations
- ⚪ we have run the full benchmark suite against the BAL + repricings branch and have no operations performing at less than 100Mgas/s
- ⚪ we have a backward compatibility analysis with final numbers
- ⚪ we have a page in our website where the ecosystem can check if their contract is affected by the repricings
- ⚪ we have kicked-off an external security review with final numbers

End of June:

- ⚪ we have reached out to all affected entities from the backward compatibility analysis
- ⚪ we have a public devnet with final numbers that the community can test

## Current workstreams - goals for end of May

### Benchmarking

- [ ] [Louis] Update benchmark release for bal-devnet-5
- [ ] [Rafael] Do larger run on bal-devnet-5
- [ ] [Maria] Analyze bal-devnet-5 results and compare with interop numbers
- [ ] [Carlos] Move bloatnet to bal-devent-5 + EIP-8038 + EIP-7904 and run stress test
- [ ] [Louis] Create full benchmarking release for bal-devent-5 + EIP-8038 + EIP-7904
- [ ] [Rafael] Run full benchmarks for bal-devent-5 + EIP-8038 + EIP-7904 (need client implementations)
- [ ] [Jochem + Carlos] Improve State Actor tool
- [ ] [Jochem + Carlos] Run State Actor tool to create a mainnet snapshot with all the relevant tests for the repricings

### Security and community outreach

- [ ] Run backward compatibility analysis for:
  - [ ] 7904 with interop numbers
  - [ ] 8038 with interop numbers
  - [ ] 8037 with bal-devnet-5 spec
- [ ] Update Carl's tool with new backward compatibility analysis
- [ ] [Butta] Reach out to affected entities
- [ ] Kick-off internal security review on all repricing EIPs
- [ ] Create public testnet with all repricing EIPs for the community to test contract implementations

### EIPs & Devnet integration

- [ ] [Maria + Spencer] Investigate and fix missing edge cases for 8037
- [ ] [Maria] Update EIPs with interop numbers (7904 + 8038)
- [ ] [Maria] Review and update 2780 EIP
- [ ] [Guru] Finish and merge spec and tests for 2780
- [ ] [Spencer] Finish and merge spec and tests for 8038

## EIP trackers

- [7904](https://github.com/ethereum/execution-specs/issues/1879)
- [8038](https://github.com/ethereum/execution-specs/issues/1941)
- [2780](https://github.com/ethereum/execution-specs/issues/1940)
- [7976](https://github.com/ethereum/execution-specs/issues/1942)
- [7981](https://github.com/ethereum/execution-specs/issues/1943)
- [8037](https://github.com/ethereum/execution-specs/issues/2040)
