# Estimating state access parameters for EIPs 8038 and 2780

#### Maria Silva, February 2026

## Parameter overview

For EIP-8038 and EIP-2780, we need the following parameters:

| Parameter | Description | Current value | Operations affected |
|:---:|:---|:---:|:---:|
| `GAS_COLD_STORAGE_ACCESS` | Cold touch of a storage slot | 2,100 | `SSTORE` and `SLOAD` |
| `GAS_COLD_ACCOUNT_CODE_ACCESS` | Cold touch of an account with code | 2,600 | `*CALL` opcodes, `BALANCE`, `SELFDESTRUCT`, `EXT*` opcodes and ETH transfers |
| `GAS_COLD_ACCOUNT_NOCODE_ACCESS` | Cold touch of an account without code | 2,600 | `*CALL` opcodes, `BALANCE`, `SELFDESTRUCT`, `EXT*` opcodes and ETH transfers |
| `GAS_WARM_ACCESS` | Touch of an already-warm account or storage slot | 100 | `SSTORE`, `SLOAD`, `*CALL` opcodes, `BALANCE`, `EXT*` opcodes and ETH transfers |
| `GAS_COLD_STORAGE_WRITE` | Surcharge for when writing to a storage slot changes its value for the first time | 5,000 | `SSTORE` |
| `GAS_COLD_ACCOUNT_WRITE` | Surcharge for when writing to an account changes one account leaf value for the first time | 6,700<sup>1</sup> | `*CALL` opcodes and ETH transfers |
| `GAS_STORAGE_CLEAR_REFUND` | Gas refunded when a storage slot is reset to zero | 4,800 | `SSTORE` |
| `ACCESS_LIST_STORAGE_KEY_COST` | Gas charged per storage key included in a transaction's access list | 1,900 | `SSTORE` and `SLOAD` |
| `ACCESS_LIST_ADDRESS_COST` | Gas charged per address included in a transaction's access list | 2,400 | `*CALL` opcodes, `BALANCE`, `SELFDESTRUCT` and `EXT*` opcodes |

<sup>1</sup> 6,700 = positive_value_cost (9,000) - stipend (2,300)

## Benchmarks and parameter estimation

For each operation and client, an NNLS (non-negative least squares) linear regression model is fitted to estimate the operation runtime as a function of the operation count and other operation-specific parameters. The model estimates runtime as a linear combination of:

- **Constant term (intercept)**: Base overhead for executing the test, which includes setup and teardown time.
- **Operation count (slope)**: Number of times the operation is executed in the test. This parameter is the one that allows us to estimate the per-operation runtime.
- **Operation-specific parameters**: Binary or continuous variables that capture the cost of different access patterns. For EIP-8038 operations, the parameters are: `new` (existing vs non-existing account/slot), `cold` (warm vs cold access), `update` (value change), `storage_size`, `mem_size` (per 32-byte word), `code_size` (per 32-byte word), and `value_sent`.

For simple operations (no varying parameters), the model estimates:

`runtime = intercept + slope × opcount`

For variable operations, the model estimates:

`runtime = intercept + slope × opcount + param1_coef × opcount × param1 + param2_coef × opcount × param2 + ...`

The per-operation runtime coefficients map directly to gas cost components. For example, the `cold` coefficient gives the cold access surcharge (the delta between cold and warm access), and the `update` coefficient gives the surcharge for accessing a non-existing account or slot versus an existing one.

The general estimation strategy is:

1. Estimate `GAS_WARM_ACCESS` from the base slope of warm operation benchmarks — it is the baseline for all access operations.
2. Estimate cold access surcharges from the `cold` coefficient: `GAS_COLD_*_ACCESS ∝ cold_coef`.
3. Estimate write surcharges from the `update` and the `value_sent`: `GAS_COLD_*_WRITE ∝ update_coef`. Note that the `value_sent` coefficient is the update coefficient for the account benchmarks.
4. Assess sensitivity of all storage parameters to state size via the `storage_size` coefficient.

We will run this estimation for both mainnet and 2x mainnet size to see how the performance scales with varying state sizes.

### `GAS_WARM_ACCESS`

The minimum-cost access path; represents in-memory lookup after the slot or account has already been touched.

#### Test overview

| Benchmark | Variant | What it measures | Slot/account state | Warming method |
|---|---|---|---|---|
| `test_storage_access_warm_benchmark` | `READ` | Warm SLOAD (fixed slot, loop) | Non-existing slot (slot 0, never written) | First-touch in same execution context |
| `test_storage_sload_same_key_benchmark` | `storage_keys_pre_set=True` | Best-case warm SLOAD (same key, repeated) | Existing slot (set in pre-state) | First-touch in same execution context |
| `test_storage_sload_same_key_benchmark` | `storage_keys_pre_set=False` | Best-case warm SLOAD (same key, repeated) | Non-existing slot (never written) | First-touch in same execution context |
| `test_ext_account_query_warm` | all opcodes × account types | Warm BALANCE, EXTCODESIZE, EXTCODEHASH, CALLs | Parametrized: absent, existing EOA, existing contract | First-touch in same execution context |
| `test_extcodecopy_warm` | all `copy_size` values | Warm EXTCODECOPY | Existing contract (deployed in pre-state) | First-touch in same execution context |
| `test_account_query` | `access_warm=True` | Warm account queries against CREATE2 contracts | Existing contracts (deployed in setup phase) | **Access list** |
| `test_ether_transfers` | `warm_access=True` | Warm ETH transfers (transaction-level) | Existing EOAs (created via `fund_eoa` in pre-state) | **Access list** |

#### Estimation

`GAS_WARM_ACCESS` covers the cost of loading anything from cache, that being a storage data or account data. Because of this, we will estimate warm access through a wide set of operations and take the worst time. This includes getting a model estimation for each client and for all combinations of:

- Target opcode: SLOAD, BALANCE, EXTCODESIZE, EXTCODEHASH, and CALL opcodes
- Existing/non-existing

From the available tests, we cannot use the tests warmed through the Access List strategy as it is not a reliable way to ensure the data is cached, which excludes `test_account_query` and `test_ether_transfers`. As for the remaining tests, all cases query the same slot/account repetitively. For a first-level estimation, we can use `test_storage_sload_same_key_benchmark` and `test_storage_access_warm_benchmark` for SLOAD and `test_ext_account_query_warm` for BALANCE, EXTCODESIZE, EXTCODEHASH, and CALL opcodes. However, we should check whether querying different warm accounts/slots results in significantly different runtimes from querying the same account/slot.

### `GAS_COLD_STORAGE_ACCESS`

Cost of the cold trie traversal to reach a storage slot.

#### Test overview

| Benchmark | Variant | What it measures | Slot state | Warming method |
|---|---|---|---|---|
| `test_storage_access_cold_benchmark` | `READ` | Cold SLOAD on clean state | Non-existing slots (uses `Op.GAS` as key — unique per iteration, never written) | N/A (each iteration hits a different slot) |
| `test_storage_access_cold` | `absent_slots=True`, `READ` | Cold SLOAD via EIP-7702 delegation | Non-existing slots | N/A (each iteration hits a different slot) |
| `test_storage_access_cold` | `absent_slots=False`, `READ` | Cold SLOAD via EIP-7702 delegation | **Existing slots** (initialized in setup block via SSTORE) | **Always warm** (setup SSTORE caches the slot) |
| `test_sload_empty_erc20_balanceof` | per `token_name` | Cold SLOAD on bloatnet (IMT / USDC / XEN / 30GB_ERC20) | Non-existing slots (random addresses → likely zero balances) | N/A (each call targets a different slot); ERC20 **account** pre-warmed via access list |
| `test_storage_sload_benchmark` | `storage_keys_pre_set=False`, cold | Cold SLOAD via EIP-7702 delegation | Non-existing slots | N/A (each iteration hits a different slot) |
| `test_storage_sload_benchmark` | `storage_keys_pre_set=True`, cold | Cold SLOAD via EIP-7702 delegation | **Existing slots** (initialized in setup block) | **Always warm** (setup SSTORE caches the slot) |

#### Estimation

We expect the storage size to have a significant impact on the runtime of a cold SLOAD. Because of this, we need to use `test_sload_empty_erc20_balanceof` to estimate `GAS_COLD_STORAGE_ACCESS`. However, this test works only over non-existing slots, and thus we need another test that implements cold accesses to existing slots to varying-sized contracts.

In this case, we would have one model estimation per storage size for `test_sload_empty_erc20_balanceof` test (the non-existing variant) and another model per storage size for a new `test_sload_exising_erc20_balanceof` test (which still needs to be implemented).

### `GAS_COLD_ACCOUNT_CODE_ACCESS`

Cost of the cold trie traversal to reach an account that has code, on top of the warm access cost.

#### Test overview

| Benchmark | Variant | What it measures | Account state | Warming method |
|---|---|---|---|---|
| `test_account_query` | `access_warm=False`, all opcodes | Cold access to CREATE2-deployed contracts | Existing contracts (deployed in setup phase) | **Always warm** (setup deploys the contracts, caching them) |
| `test_ether_transfers` | `delegated_account`, `warm_access=False` | Cold ETH transfer to delegated accounts (transaction-level) | Existing delegated EOA with balance=0 (created via `fund_eoa` with delegation to a contract) | **Always warm** (setup creates accounts via `fund_eoa`, caching them) |

#### Estimation

None of the tests in this section can be used for estimating a cold touch to an account with code reliably. The issue is that both tests have a setup phase where they create the accounts being accessed. Because of this setup phase, these accounts will likely be cached, and thus the run time will be similar to a warm access.

Because of this, we need a new test that makes sure the slots being accessed is not cached. This test would be a non-cached, non-value sending version of `test_account_query` that still has the existing/non-existing variants. Then, to estimate `GAS_COLD_ACCOUNT_CODE_ACCESS` we would fit one model per client for each existing/non-existing variant and opcode (BALANCE, EXTCODESIZE, EXTCODEHASH, and CALL opcodes), and take the worst-case.

### `GAS_COLD_ACCOUNT_NOCODE_ACCESS`

Cost of the cold trie traversal to reach an account without code.

#### Test overview

| Benchmark | Variant | What it measures | Account state | Warming method |
|---|---|---|---|---|
| `test_ether_transfers` | `non_empty_account`, `warm_access=False` | Cold ETH transfer to EOAs (transaction-level) | Existing EOA with balance=1 (created via `fund_eoa`) | **Always warm** (setup creates accounts via `fund_eoa`, caching them) |
| `test_ether_transfers` | `empty_account`, `warm_access=False` | Cold ETH transfer to EOAs (transaction-level) | Existing EOA with balance=0 (created via `fund_eoa` — **not truly absent**) | **Always warm** (setup creates accounts via `fund_eoa`, caching them) |
| `test_ext_account_query_cold` | `BALANCE`, `absent_accounts=True` | Cold BALANCE on absent EOAs | **Absent accounts** (computed addresses, never allocated) | N/A (each iteration targets a different address) |
| `test_ext_account_query_cold` | `BALANCE`, `absent_accounts=False` | Cold BALANCE on existing EOAs | Existing EOAs (created via CALL with value in setup block) | **Always warm** (setup creates accounts via CALL with value, caching them) |
| `test_contract_calling_many_addresses` | `transfer_amount=0`, `access_warm=False` | Cold CALL to non-existent addresses (opcode-level) | **Absent accounts** (addresses starting at 2^80-1, never allocated) | N/A (each iteration targets a different address) |

#### Estimation

A majority of tests has the setup-caching issue with discussed in the previous section, and thus, they are not reliable measures for this parameters. The `test_ext_account_query_cold` and `test_contract_calling_many_addresses` could be used to estimate the access cost for the non-existing variant for BALANCE and CALL. However, we are still missing the existing variant.

With both variants, we would fit one model per client for each existing/non-existing variant and each opcode (BALANCE and CALL) and take the worst-case.

**Note:** the `test_ether_transfers` "empty_account" variant creates receivers via `fund_eoa(0)` — these are existing accounts with zero balance, not truly absent accounts. For absent-account behavior, use `test_ext_account_query_cold` (`absent_accounts=True`) or `test_contract_calling_many_addresses`. The `test_ether_transfers` warm baseline uses access-list warming.

### `GAS_COLD_STORAGE_WRITE`

Additional cost when an SSTORE changes a slot's value for the first time, beyond the cold access cost. Represents the trie-insertion or trie-modification overhead.

#### Test overview

| Benchmark | Variant | What it measures | Slot state | Warming method |
|---|---|---|---|---|
| `test_storage_access_cold_benchmark` | `WRITE_NEW_VALUE` | Cold SSTORE; 0→nonzero | Non-existing slots (uses `Op.GAS` as key — unique per iteration) | N/A (each iteration hits a different slot) |
| `test_sstore_erc20_approve` | per `token_name` | Cold SLOAD + warm SSTORE OR cold SSTORE; 0→nonzero on bloatnet | Non-existing slots (new allowance entries) | Each iteration an SSTORE on different slots. Some ERC20 contracts add SLOADs before |
| `test_sstore_variants` | `initial_value=0, write_value=nonzero`, `access_warm=False` | Cold SSTORE; 0→nonzero via EIP-7702 | Non-existing slots | N/A (each iteration hits a different slot) |
| `test_sstore_variants` | `initial_value=nonzero, write_value=diff`, `access_warm=False` | Cold SSTORE; nonzero→different via EIP-7702 | **Existing slots** (initialized in setup phase) | N/A (each iteration hits a different slot) |
| `test_sstore_variants` | `initial_value=nonzero, write_value=same`, `access_warm=False` | Cold SSTORE nonzero→same via EIP-7702 (no value change — baseline) | **Existing slots** (initialized in setup phase) | N/A (each iteration hits a different slot) |

#### Estimation

Similarly to a cold access to storage, we expect the size of contract's storage to have a significant impact on the run time of writing to a storage slot. With this in mind, we need tests like `test_sstore_erc20_approve` that target different storage sizes. However, this test only targets non-existing slots, which means we are missing the existing slot variant.

With both variants of `test_sstore_erc20_approve`, we would fit one model per client and for each existing/non-existing variant and take the worst-case. We would do this analysis for each storage size to map how performance scales with increasing storage.

An important caveat is that whether an SLOAD precedes the SSTORE depends on the actual ERC20 contract executed, not on the test code itself. The test deploys a stub that resolves to a real on-chain contract (e.g. IMT, USDC, etc.) whose bytecode is fetched at execution time. In practice, standard ERC20 `approve` implementations (OpenZeppelin, ERC20Bloater) do read the allowance slot before writing it, so the SSTORE executes on a warm slot. This means the test measures cold SLOAD + warm SSTORE, not a pure cold SSTORE — the cold-read cost must be subtracted to isolate the write surcharge. However, if we use our own bloated ERC20 contracts (as is the case for the 30GB ERC20Bloater), then we can define the approve function to only do an SSTORE.

### `GAS_COLD_ACCOUNT_WRITE`

Surcharge when a transaction or CALL changes an account's balance (or creates a new account) for the first time.

#### Test overview

| Benchmark | Variant | What it measures | Account state | Warming method |
|---|---|---|---|---|
| `test_ether_transfers` | `transfer_amount=1`, `non_empty_account` | ETH transfer to existing EOA | Existing EOA with balance=1 (created via `fund_eoa`) | **Always warm** (setup creates accounts via `fund_eoa`, caching them) |
| `test_ether_transfers` | `transfer_amount=1`, `empty_account` | ETH transfer to zero-balance EOA | Existing EOA with balance=0 (created via `fund_eoa` — **not truly absent**) | **Always warm** (setup creates accounts via `fund_eoa`, caching them) |
| `test_contract_calling_many_addresses` | `transfer_amount=1`, `access_warm=False` | Cold value-bearing CALL creating accounts (opcode-level) | **Absent accounts** (addresses starting at 2^80-1, never allocated) | N/A (each iteration targets a different address) |

#### Estimation

Once again, the `test_ether_transfers` only produces a warm write to existing accounts. We need also the variant for non-existing accounts. As for `test_contract_calling_many_addresses`, we have the cold write to a non-existing account, and we are missing the existing account variant. 

Assuming we have both variants for `test_ether_transfers` and `test_contract_calling_many_addresses`, we we would fit one model per client and operation (ETH transfer and CALL) and for each existing/non-existing variant, and take the worst-case.

### `GAS_STORAGE_CLEAR_REFUND`

Refund when SSTORE resets a nonzero slot back to zero. The refund should be priced consistently with `GAS_COLD_STORAGE_WRITE`. We can define the refund proportionally as we do today:

```python
GAS_STORAGE_CLEAR_REFUND = GAS_COLD_STORAGE_WRITE * (4800/5000)
```

### `ACCESS_LIST_STORAGE_KEY_COST` and `ACCESS_LIST_ADDRESS_COST`

Intrinsic gas costs for pre-warming via EIP-2930 access lists. These are typically set so that pre-warming costs approximately the same gas as encountering the cold access during execution, preventing gas arbitrage. Thus, we don't need to have a specific benchmark for them. We can price them at the same cost as `GAS_COLD_ACCOUNT_CODE_ACCESS` and `GAS_COLD_STORAGE_ACCESS`, for accounts and storage slots respectively.

## Coverage summary

| Parameter | Usable benchmarks | Needs implementation |
|---|---|---|
| `GAS_WARM_ACCESS` | `test_storage_sload_same_key_benchmark` (both `storage_keys_pre_set`), `test_storage_access_warm_benchmark` (READ) for SLOAD; `test_ext_account_query_warm` for BALANCE, EXTCODESIZE, EXTCODEHASH, and CALLs | Benchmarks querying **different** warm accounts/slots (current tests repeat the same key) to verify no cache-locality bias |
| `GAS_COLD_STORAGE_ACCESS` | `test_sload_empty_erc20_balanceof` (non-existing slots, one model per storage size) | `test_sload_existing_erc20_balanceof` — cold SLOAD to **existing slots on bloatnet** (needed to capture full trie traversal to an existing leaf) |
| `GAS_COLD_ACCOUNT_CODE_ACCESS` | None — `test_account_query` and `test_ether_transfers` both deploy/create accounts in setup, so targets are likely cached | New non-cached, non-value-sending variant of `test_account_query` with existing/non-existing account variants for BALANCE, EXTCODESIZE, EXTCODEHASH, and CALLs |
| `GAS_COLD_ACCOUNT_NOCODE_ACCESS` | `test_ext_account_query_cold` (`absent_accounts=True`) for BALANCE non-existing; `test_contract_calling_many_addresses` (`transfer_amount=0`) for CALL non-existing | Existing-account variants for both BALANCE and CALL — `test_ext_account_query_cold` (`absent_accounts=False`) is unreliable due to setup caching |
| `GAS_COLD_STORAGE_WRITE` | `test_sstore_erc20_approve` (non-existing slots, one model per storage size; caveat: some ERC20 contracts prepend an SLOAD — cold-read cost must be subtracted) | `test_sstore_erc20_approve` variant for **existing slots** on bloatnet (nonzero→different with realistic state) |
| `GAS_COLD_ACCOUNT_WRITE` | `test_contract_calling_many_addresses` (`transfer_amount=1`, non-existing accounts) | Existing-account variant of `test_contract_calling_many_addresses` — `test_ether_transfers` is unreliable due to setup caching |
| `GAS_STORAGE_CLEAR_REFUND` | Derived: `GAS_COLD_STORAGE_WRITE × (4800/5000)` | — |
| `ACCESS_LIST_STORAGE_KEY_COST` | Derived: set equal to `GAS_COLD_STORAGE_ACCESS` | — |
| `ACCESS_LIST_ADDRESS_COST` | Derived: set equal to `GAS_COLD_ACCOUNT_CODE_ACCESS` | — |

### Key gaps

1. **Setup-caching invalidates many tests** — Tests that create or deploy target accounts/slots in a setup phase (`test_account_query`, `test_ether_transfers`, `test_storage_access_cold` with `absent_slots=False`, `test_storage_sload_benchmark` with `storage_keys_pre_set=True`, `test_ext_account_query_cold` with `absent_accounts=False`) leave targets cached. These cannot reliably measure cold-access costs and are excluded from the estimation.

2. **Access-list warming is unreliable** — `test_account_query` (`access_warm=True`) and `test_ether_transfers` (`warm_access=True`) use access-list pre-warming, which may not trigger actual pre-fetching in all clients. These are excluded from `GAS_WARM_ACCESS` estimation.

3. **No bloatnet test for cold access to existing slots/accounts** — All bloatnet storage tests (`test_sload_empty_erc20_balanceof`, `test_sstore_erc20_approve`) target non-existing slots. No bloatnet test exercises full trie traversal to an existing leaf, which may be slower on a large trie. Similarly, no bloatnet benchmark exists for cold access to code-bearing or codeless accounts.

4. **No cold account access (code) benchmark at all** — Both available tests (`test_account_query`, `test_ether_transfers`) are invalidated by setup caching. A new test is needed from scratch.

5. **Warm-access cache-locality bias** — All usable warm benchmarks query the same slot or account repeatedly. It is unknown whether accessing different warm targets produces significantly different runtimes due to cache-locality effects.
