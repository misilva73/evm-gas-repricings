# Master List of ToDo's For Glamsterdam Repricings

#### Maria Silva, January 2025

## [EIP-7904](https://eips.ethereum.org/EIPS/eip-7904): General Repricing

This proposal raises the cost of all operations performing worse than 60Mgas/s, thus removing these bottlenecks and allowing a higher block limit.

- [ ] Decide on the list of operations to reprice
- [ ] Compute the new gas costs for each operation (assuming 60Mgas/s)
- [ ] Update EIP
- [ ] Write execution specs
- [ ] Run backward compatibility analysis
- [ ] Do community outreach for affected stakeholders
- [ ] Implement new gas schedule in all clients
- [ ] Run benchmarks to find bottlenecks and correct numbers if needed
- [ ] Integrate gas schedule into BAL devnet and test
- [ ] Derive possible block limit after BALs and ePBS

## [EIP-8038](https://eips.ethereum.org/EIPS/eip-8038): State-access gas cost update

This proposal updates the costs of state access operations, thus removing state access as a scaling bottleneck.

- [ ] Add `GAS_COLD_ACCOUNT_WRITE` parameter
- [ ] Finish data collection for stateful tests. We need:
  - [ ] Warm slot access (SLOAD)
  - [ ] Cold slot access (SLOAD)
  - [ ] Warm account access (BALANCE, CALL, transfer)
  - [ ] Cold account access (BALANCE, CALL, transfer)
  - [ ] Cached code access (EXTCODESIZE, EXTCODEHASH, EXTCODECOPY)
  - [ ] Non-cached code access (EXTCODESIZE, EXTCODEHASH, EXTCODECOPY)
  - [ ] Account write (transfer, ?)
  - [ ] Slot write (SSTORE)
- [ ] Decide on how to approach gains from BALs
- [ ] Compute the new gas costs for each operation (assuming 60Mgas/s? this depends on expected gains from BALs)
- [ ] Update EIP
- [ ] Write execution specs
- [ ] Run backward compatibility analysis
- [ ] Do community outreach for affected stakeholders
- [ ] Implement new gas schedule in all clients
- [ ] Run benchmarks to find bottlenecks and correct numbers if needed
- [ ] Integrate gas schedule into BAL devnet and test

## [EIP-2780](https://eips.ethereum.org/EIPS/eip-2780): Reduce intrinsic transaction gas

This proposal aligns the cost of ETH transfers with the rest of the compute and state operations, thus increasing the throughput of ETH transfers and aligning their cost with similar operations.

- [ ] Port costs from EIP-7904, EIP-8038 and EIP-8037
- [ ] Update EIP
- [ ] Write execution specs
- [ ] Run backward compatibility analysis
- [ ] Do community outreach for affected stakeholders
- [ ] Implement new gas schedule in all clients
- [ ] Run benchmarks to find bottlenecks and correct numbers if needed
- [ ] Integrate gas schedule into BAL devnet and test

## [EIP-7976](https://eips.ethereum.org/EIPS/eip-7976): Increase Calldata Floor Cost

This proposal increases calldata cost for data-heavy transactions, thus lowering the worst-case block size achieved through call data. Depending on the final parameters for the remaining resources, we may also need to adjust the base cost of calldata for all transactions.

- [ ] Estimate how much gas each byte of calldata should cost
  - [ ] How can we translate bytes into propagation time?
  - [ ] How much time relative to execution will we have after ePBS
- [ ] Update EIP (if needed)
- [ ] Do community outreach to affected stakeholders
- [ ] Write execution specs
- [ ] Implement new gas schedule in all clients
- [ ] Integrate gas schedule into BAL devnet and test

## [EIP-7981](https://eips.ethereum.org/EIPS/eip-7981): Increase access list cost

This proposal charges access lists for their data footprint, thus lowering the worst-case block size achieved through call data.

- [ ] Align costs with EIP-2780
- [ ] Update EIP (if needed)
- [ ] Do community outreach to affected stakeholders
- [ ] Write execution specs
- [ ] Implement new gas schedule in all clients
- [ ] Integrate gas schedule into BAL devnet and test

## [EIP-8037](https://eips.ethereum.org/EIPS/eip-8037): State Creation Gas Cost Increase

This proposal introduces a dynamic cost for state creation operations that depends on the block limit and meters state creation gas costs independently of all the other gas costs.

- [ ] Write execution specs and figure out open questions:
  - [ ] How to split the CREATE costs?
  - [ ] How to deal with tx receipts?
- [ ] Update EIP
- [ ] Do community outreach to affected stakeholders
- [ ] Implement new gas schedule in all clients
- [ ] Create tests and prep devnet
- [ ] Integrate gas schedule into BAL devnet
