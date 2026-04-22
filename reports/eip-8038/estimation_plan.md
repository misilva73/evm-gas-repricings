# Estimating state access parameters for EIPs 8038 and 2780

#### Maria Silva, April 2026

## Parameter overview

For EIP-8038 and EIP-2780, we need the following parameters:

| Parameter | Description | Current value | Operations affected |
|:---:|:---|:---:|:---:|
| `GAS_COLD_STORAGE_ACCESS` | Cold touch of a storage slot | 2,200<sup>1</sup>  | `SSTORE` and `SLOAD` |
| `GAS_COLD_ACCOUNT_CODE_ACCESS` | Cold touch of an account with code | 2,600 | `*CALL` opcodes, `BALANCE`, `SELFDESTRUCT`, `EXT*` opcodes and ETH transfers |
| `GAS_COLD_ACCOUNT_NOCODE_ACCESS` | Cold touch of an account without code | 2,600 | `*CALL` opcodes, `BALANCE`, `SELFDESTRUCT`, `EXT*` opcodes and ETH transfers |
| `GAS_WARM_ACCESS` | Touch of an already-warm account or storage slot | 100 | `SSTORE`, `SLOAD`, `*CALL` opcodes, `BALANCE`, `EXT*` opcodes and ETH transfers |
| `GAS_COLD_STORAGE_WRITE` | Surcharge for when writing to a storage slot changes its value for the first time | 2,800<sup>2</sup> | `SSTORE` |
| `GAS_COLD_ACCOUNT_WRITE` | Surcharge for when writing to an account changes one account leaf value for the first time | 6,700<sup>3</sup> | `*CALL` opcodes and ETH transfers |
| `GAS_STORAGE_CLEAR_REFUND` | Gas refunded when a storage slot is reset to zero | 4,800 | `SSTORE` |
| `ACCESS_LIST_STORAGE_KEY_COST` | Gas charged per storage key included in a transaction's access list | 1,900 | `SSTORE` and `SLOAD` |
| `ACCESS_LIST_ADDRESS_COST` | Gas charged per address included in a transaction's access list | 2,400 | `*CALL` opcodes, `BALANCE`, `SELFDESTRUCT` and `EXT*` opcodes |

<sup>1</sup> 2,200 = `GAS_COLD_SLOAD` (2,100) + `GAS_WARM_ACCESS` (100) -> this assumes the worst case storage access, which is achieved via `SSTORE`

<sup>2</sup> 2,800 = `GAS_STORAGE_UPDATE` (5,000) - `GAS_COLD_SLOAD` (2,100) - `GAS_WARM_ACCESS` (100)

<sup>3</sup> 6,700 = positive_value_cost (9,000) - stipend (2,300)

## Tests by parameter

### `GAS_WARM_ACCESS`

The minimum-cost access path; represents in-memory lookup after the slot or account has already been touched.

#### Test overview

| Benchmark | Variant | What it measures | Slot/account state | Warming method |
|---|---|---|---|---|
| `test_storage_sload_same_key_benchmark` | `storage_keys_pre_set=True` | Best-case warm SLOAD (same key, repeated) | Existing slot (set in pre-state) | First-touch in same execution context |
| `test_storage_sload_same_key_benchmark` | `storage_keys_pre_set=False` | Best-case warm SLOAD (same key, repeated) | Non-existing slot (never written) | First-touch in same execution context |
| `test_ext_account_query_warm` | all opcodes × account types | Warm BALANCE, EXTCODESIZE, EXTCODEHASH, CALLs | Parametrized: absent, existing EOA, existing contract | First-touch in same execution context |
| `test_sload_bloated` | `existing_slots=True/False`, `cache_strategy=CACHE_TX`, per `storage_size` | Two SLOAD to different slots (first is cold, second is warm) on bloatnet | Existing or non-existing slots; setup done beforehand in bespoke contract | **In-transaction**: first SLOAD warms slot |
| `test_sload_bloated` | `existing_slots=True/False`, `cache_strategy=CACHE_PREVIOUS_BLOCK`, per `storage_size` | EVM-cold but client-cached SLOAD on bloatnet | Existing or non-existing slots; setup done beforehand in bespoke contract | **Previous block**: setup block reads slots and populates cache; depends on client implementation -> less reliable |
| `test_sstore_bloated` | `cache_strategy=CACHE_TX`, `existing_slots=True/False`, `update=True/False`, per `storage_size` | Warm SSTORE with many variants on bloatnet | Existing or non-existing ERC20 balance slots | **In-transaction**: SLOAD warms slot before SSTORE writes it |
| `test_sstore_bloated` | `cache_strategy=CACHE_PREVIOUS_BLOCK`, `existing_slots=True/False`, `update=True/False`, per `storage_size` | Warm SSTORE with many variants on bloatnet | Existing or non-existing ERC20 balance slots | **Previous block**: setup block reads slots and populates cache; depends on client implementation -> less reliable |
| `test_account_access` | all opcodes × account types, `value_sent=0`, `cache_strategy=CACHE_TX`  | Warm BALANCE, EXTCODESIZE, EXTCODEHASH, CALLs on bloatnet | Existing contracts (`CreatePreimageLayout`, ENS registry seed), existing EOAs (Spamoor, from `0x1000`), absent accounts (`keccak256("random")` seed) | **In-transaction**: `BALANCE` pre-call warms address |
| `test_account_access` |  all opcodes × account types, `value_sent=0`, `cache_strategy=CACHE_PREVIOUS_BLOCK` | EVM-cold but client-cached access to accounts on bloatnet | Existing contracts (deployed by ENS registry, iterated via `CreatePreimageLayout`) or Existing EOAs (previously initialized in bloatnet) | **Previous block**: setup block reads accounts and populates cache; depends on client implementation -> less reliable |

#### Estimation

`GAS_WARM_ACCESS` covers the cost of loading anything from cache, that being a storage data or account data. Because of this, we will estimate warm access through a wide set of operations and take the worst time. This includes getting a model estimation for each client and for all combinations of:

- Target opcode: SLOAD, SSTORE, BALANCE, EXTCODESIZE, EXTCODEHASH, and CALL opcodes
- Existing/non-existing

We will consider the following tests:

- `test_storage_sload_same_key_benchmark` with `storage_keys_pre_set=True` will be used to benchmark warm SLOADs to the same slot. This should be a lower bound for accessing a warm slot.
- `test_ext_account_query_warm` will be used to benchmark warm account accesses (BALANCE, CALL opcodes, and EXTCODE* opcodes) to the same account. Our benchmarks are only collecting data for existing EOAs (i.e., the variant `initial_storage=True`, `initial_balance=True`, and `empty_code=True`), so this should also be a lower bound for accessing a warm account.
- `test_sload_bloated` will be used to benchmark warm SLOAD to different slots on bloatnet. We will consider both warming strategies (`CACHE_TX` and `CACHE_PREVIOUS_BLOCK`), filtering to `existing_slots=True` so that the warm read observes a populated slot. We will also use the different `storage_size`'s to check whether warm performance is affected by storage size (although we expect it not to have an impact).
- `test_sstore_bloated` will be used to benchmark warm SSTORE to different slots on bloatnet. We will consider both warming strategies (`CACHE_TX` and `CACHE_PREVIOUS_BLOCK`), filtering to `existing_slots=True` so that the warm write observes a populated slot. We will also use the different `storage_size`'s to check whether warm performance is affected by storage size.
- `test_account_access` with `value_sent=0` will be used to benchmark warm account accesses (BALANCE, CALL opcodes, and EXTCODE* opcodes) to different accounts. Similarly to slots, we will consider both warming strategies (`CACHE_TX` and `CACHE_PREVIOUS_BLOCK`) and all account types (existing EOA, existing contract, non-existing account) and compare the difference.

### `GAS_COLD_STORAGE_ACCESS`

Cost of the cold trie traversal to reach a storage slot.

#### Test overview

| Benchmark | Variant | What it measures | Slot state | Warming method |
|---|---|---|---|---|
| `test_sload_bloated` | `existing_slots=True/False`, `cache_strategy=NO_CACHE`, per `storage_size` | Cold SLOAD on bloatnet to different slots | Both existing and non-existing slots | N/A (each call targets a different slot + setup is done on bloatnet) |
| `test_sstore_bloated` | `existing_slots=True/False`, `update=True/False`, `cache_strategy=NO_CACHE`, per `storage_size` | Cold SSTORE on bloatnet to different slots; slope captures the cold access portion | Both existing and non-existing slots | N/A (each call targets a different slot + setup is done on bloatnet) |

#### Estimation

We expect the storage size to have a significant impact on the runtime of a cold SLOAD. Because of this, we need to use the bloatnet tests (`test_sload_bloated` and `test_sstore_bloated`) to estimate `GAS_COLD_STORAGE_ACCESS`. In this case, we will fit one model per slot status (existing/non-existing) for each test with `cache_strategy=NO_CACHE`; the slope captures the cold access component in both tests. We will also use the different `storage_size`'s to check how much cold performance deteriorates with storage size.

### `GAS_COLD_ACCOUNT_CODE_ACCESS`

Cost of the cold trie traversal to reach an account that has code, on top of the warm access cost.

#### Test overview

| Benchmark | Variant | What it measures | Account state | Warming method |
|---|---|---|---|---|
| `test_account_access` | `account_mode=EXISTING_CONTRACT or NON_EXISTING_ACCOUNT`, `value_sent=0`, all EXT* + CALL opcodes, `cache_strategy=NO_CACHE` | Cold access to contracts on bloatnet via BALANCE, EXTCODESIZE, EXTCODEHASH, CALLs | Existing contracts (deployed by ENS registry, iterated via `CreatePreimageLayout`) | N/A (each iteration targets a different contract address) |

#### Estimation

`test_account_access` is the test used for estimating a cold touch to an account with code. To estimate `GAS_COLD_ACCOUNT_CODE_ACCESS` we will fit one model for each existing/non-existing variant (`account_mode=EXISTING_CONTRACT` vs. `account_mode=NON_EXISTING_ACCOUNT`) and opcode (BALANCE, EXTCODESIZE, EXTCODEHASH, and CALL opcodes). We will use `value_sent=0` to avoid any account writes.

### `GAS_COLD_ACCOUNT_NOCODE_ACCESS`

Cost of the cold trie traversal to reach an account without code.

#### Test overview

| Benchmark | Variant | What it measures | Account state | Warming method |
|---|---|---|---|---|
| `test_account_access` | `account_mode=EXISTING_EOA or NON_EXISTING_ACCOUNT`, `value_sent=0`, BALANCE + CALL opcodes, `cache_strategy=NO_CACHE` | Cold access to existing EOAs on bloatnet | Existing EOAs (Spamoor-created, addresses starting at `0x1000`) or absent accounts (addresses starting at `keccak256("random")`, never allocated) | N/A (each iteration targets a different address) |

#### Estimation

We use `test_account_access` for this parameter as well. Similarly to `GAS_COLD_ACCOUNT_CODE_ACCESS`, we will fit one model for each existing/non-existing variant (`account_mode=EXISTING_EOA` vs. `account_mode=NON_EXISTING_ACCOUNT`) and opcode (BALANCE + CALL opcodes). We will use `value_sent=0` to avoid any account writes.

### `GAS_COLD_STORAGE_WRITE`

Additional cost when an SSTORE changes a slot's value for the first time, beyond the cold access cost. Represents the trie-insertion or trie-modification overhead.

#### Test overview

| Benchmark | Variant | What it measures | Slot state | Warming method |
|---|---|---|---|---|
| `test_sstore_bloated` | `existing_slots=False`, `update=True`, `cache_strategy=NO_CACHE`, per `storage_size` | Cold SSTORE; 0→nonzero via `mint()` on bloatnet | Non-existing ERC20 balance slots (incrementing addresses from `keccak256("random")`) | N/A (each iteration targets a different slot) |
| `test_sstore_bloated` | `existing_slots=True`, `update=True`, `cache_strategy=NO_CACHE`, per `storage_size` | Cold SSTORE; nonzero→different via `mint()` on bloatnet | **Existing** ERC20 balance slots (address counter starts at 1, hitting populated slots) | N/A (each iteration targets a different slot) |
| `test_sstore_bloated` | `update=False`, `cache_strategy=NO_CACHE`, per `storage_size` | Cold SSTORE with no value change; isolates cold access from the write surcharge | Both existing and non-existing slots | N/A (each iteration targets a different slot) |

#### Estimation

Similarly to a cold access to storage, we expect the size of contract's storage to have a significant impact on the run time of writing to a storage slot. With this in mind, we will focus on `test_sstore_bloated` with `cache_strategy=NO_CACHE`, as it is the most flexible that targets different storage sizes.

The regression fits both the slope (captures cold access) and the `update` coefficient (captures the write surcharge) simultaneously. `GAS_COLD_STORAGE_WRITE` is derived from the `update` coefficient. We will do this analysis for each storage size to map how performance scales with increasing storage.

### `GAS_COLD_ACCOUNT_WRITE`

Surcharge when a transaction or CALL changes an account's balance (or creates a new account) for the first time.

#### Test overview

| Benchmark | Variant | What it measures | Account state | Warming method |
|---|---|---|---|---|
| `test_account_access` | `account_mode=EXISTING_EOA`, `value_sent=1`, CALL + CALLCODE, `cache_strategy=NO_CACHE` | Cold value-bearing CALL to existing EOAs on bloatnet | Existing EOAs (Spamoor-created, addresses starting at `0x1000`) | N/A (each iteration targets a different address) |
| `test_account_access` | `account_mode=EXISTING_CONTRACT`, `value_sent=1`, CALL + CALLCODE, `cache_strategy=NO_CACHE` | Cold value-bearing CALL to existing contracts on bloatnet | Existing contracts (deployed by ENS registry, iterated via `CreatePreimageLayout`) | N/A (each iteration targets a different address) |
| `test_account_access` | `account_mode=NON_EXISTING_ACCOUNT`, `value_sent=1`, CALL + CALLCODE, `cache_strategy=NO_CACHE` | Cold value-bearing CALL creating absent accounts on bloatnet | **Absent accounts** (addresses starting at `keccak256("random")`, never allocated) | N/A (each iteration targets a different address) |

#### Estimation

`test_account_access` is the test used for estimating this parameter. We will focus on the variant `cache_strategy=NO_CACHE`. The regression fits both the slope (captures cold access) and the `update` coefficient (captures the write surcharge when `value_sent=1`) simultaneously. `GAS_COLD_ACCOUNT_WRITE` is derived from the `update` coefficient, so the cold access component does not need to be subtracted after the fact.

We fit separate models for the nocode-access path (`account_mode != EXISTING_CONTRACT`) and the code-access path (`account_mode != EXISTING_EOA`), and take the worst case across them.

### `GAS_STORAGE_CLEAR_REFUND`

Refund when SSTORE resets a nonzero slot back to zero. The refund should be priced consistently with `GAS_COLD_STORAGE_WRITE` and `GAS_COLD_STORAGE_ACCESS`. We can define the refund proportionally as we do today:

```python
GAS_STORAGE_CLEAR_REFUND = (GAS_COLD_STORAGE_WRITE+GAS_COLD_STORAGE_ACCESS) * (4800/5000)
```

### `ACCESS_LIST_STORAGE_KEY_COST` and `ACCESS_LIST_ADDRESS_COST`

Intrinsic gas costs for pre-warming via EIP-2930 access lists. These are typically set so that pre-warming costs approximately the same gas as encountering the cold access during execution, preventing gas arbitrage. Thus, we don't need to have a specific benchmark for them. We can price them at the same cost as `GAS_COLD_ACCOUNT_CODE_ACCESS` and `GAS_COLD_STORAGE_ACCESS`, for accounts and storage slots respectively.

## Parameter estimation

For each benchmark test, opcode and client, an NNLS (non-negative least squares) linear regression model is fitted to estimate the operation runtime as a function of the operation count and other test-specific parameters. The model estimates runtime as a linear combination of:

- **Constant term (intercept)**: Base overhead for executing the test, which includes setup and teardown time.
- **Operation count (slope)**: Number of times the operation is executed in the test. This parameter is the one that allows us to estimate the per-operation runtime.
- **Test-specific parameters**: Binary or continuous variables that capture the cost of different access patterns.

The model estimates:

`runtime = intercept + slope × opcount + param1_coef × opcount × param1 + param2_coef × opcount × param2 + ...`

The regression coefficients have units of milliseconds per operation. To convert to gas units, we use an **anchor rate** — a fixed number of gas units per second of wall-clock time — applied uniformly across all clients:

```
new_gas = (anchor_rate × runtime_ms) / 1000
```

**Glue opcode adjustment:** Each benchmark test includes auxiliary "glue" opcodes (e.g., PUSH, CALL) that scale linearly with the main opcode count. Because the regression model's slope coefficient captures the combined runtime of both the target opcode and its glue opcodes, we subtract the estimated glue opcode runtime to isolate the true per-execution cost of the target opcode:

```
adjusted_slope = slope - sum(ratio_i × glue_runtime_i)
```

Where `ratio_i` is the average number of executions of glue opcode *i* per execution of the target opcode, and `glue_runtime_i` is the estimated per-execution runtime of glue opcode *i* for the given client. Only glue opcodes with a statistically significant fit (p-value < 0.05) are included in the adjustment. The adjusted slope is clipped to a minimum of zero.

When a measurement bundles multiple components (e.g., a cold read followed by a warm write), the relevant coefficient is obtained by subtracting the independently estimated component. The final gas parameter is the **maximum across all clients and configurations**.

### Models to build

#### Storage opcodes

To estimate the storage access parameters, we will fit the following models for each slot mode (`existing_slots=True/False`), storage size (`storage_size`) and client combination:

| Test | Filter | Additional regression variables | What is estimated |
|:---|:---|:---|:---|
| `test_storage_sload_same_key_benchmark` | — | — | `GAS_WARM_ACCESS` |
| `test_sload_bloated` | `cache_strategy=CACHE_TX`, `existing_slots=True` | - | `GAS_WARM_ACCESS` |
| `test_sload_bloated` | `cache_strategy=CACHE_PREVIOUS_BLOCK`, `existing_slots=True` | - | `GAS_WARM_ACCESS` |
| `test_sstore_bloated` | `cache_strategy=CACHE_TX`, `existing_slots=True` | - | `GAS_WARM_ACCESS` |
| `test_sstore_bloated` | `cache_strategy=CACHE_PREVIOUS_BLOCK`, `existing_slots=True` | - | `GAS_WARM_ACCESS` |
| `test_sload_bloated` | `cache_strategy=NO_CACHE` | - | `GAS_COLD_STORAGE_ACCESS` |
| `test_sstore_bloated` | `cache_strategy=NO_CACHE` | `update` | `GAS_COLD_STORAGE_ACCESS`, `GAS_COLD_STORAGE_WRITE` |

#### Account opcodes

To estimate the account access parameters, we will fit the following models for each opcode (`*CALL` opcodes, `BALANCE`, `SELFDESTRUCT`, `EXTCODE*` opcodes), account mode (`account_mode=NON_EXISTING_ACCOUNT` vs. `account_mode!=NON_EXISTING_ACCOUNT`) and client combination:

| Test | Filter | Additional regression variables | Primary coefficient |
|:---|:---|:---|:---|
| `test_ext_account_query_warm` | `initial_storage=True`, `initial_balance=True`,`empty_code=True` | - | `GAS_WARM_ACCESS` |
| `test_account_access` | `cache_strategy=CACHE_TX`, `value_sent=0` | - | `GAS_WARM_ACCESS` |
| `test_account_access` | `cache_strategy=CACHE_PREVIOUS_BLOCK`, `value_sent=0` | - | `GAS_WARM_ACCESS` |
| `test_account_access` | `account_mode!=EXISTING_CONTRACT`, `cache_strategy=NO_CACHE` |  `update` (`value_sent=1`) | `GAS_COLD_ACCOUNT_NOCODE_ACCESS`, `GAS_COLD_ACCOUNT_WRITE` |
| `test_account_access` | `account_mode!=EXISTING_EOA`, `cache_strategy=NO_CACHE` | `update` (`value_sent=1`) | `GAS_COLD_ACCOUNT_CODE_ACCESS`, `GAS_COLD_ACCOUNT_WRITE` |

### Mapping coefficients to gas parameters

- `GAS_WARM_ACCESS`: this is derived from the slope of all the models estimating this parameter. If `cache_strategy=CACHE_TX`, then we will have a SLOAD or BALANCE as glue opcodes. In this case, we know these opcodes are cold, and thus we will discount the runtime of the respective cold variants.
- `GAS_COLD_STORAGE_ACCESS`: this is derived from the slope of the `test_sload_bloated` and `test_sstore_bloated` models.
- `GAS_COLD_ACCOUNT_NOCODE_ACCESS`: this is derived from the slope of the `test_account_access` models filtered by `account_mode!=EXISTING_CONTRACT`.
- `GAS_COLD_ACCOUNT_CODE_ACCESS`: this is derived from the slope of the `test_account_access` models filtered by `account_mode!=EXISTING_EOA`.
- `GAS_COLD_STORAGE_WRITE`: this is derived from the coefficient of the `update` parameter from the `test_sstore_bloated` models.
- `GAS_COLD_ACCOUNT_WRITE`: this is derived from the coefficient of the `update` parameter from the `test_account_access` models.
- `GAS_STORAGE_CLEAR_REFUND`: is derived from `GAS_COLD_STORAGE_WRITE` and `GAS_COLD_STORAGE_ACCESS` (`GAS_STORAGE_CLEAR_REFUND = (GAS_COLD_STORAGE_WRITE+GAS_COLD_STORAGE_ACCESS) * (4800/5000)`)
- `ACCESS_LIST_STORAGE_KEY_COST`: is set to `GAS_COLD_STORAGE_ACCESS`
- `ACCESS_LIST_ADDRESS_COST`: is set to `GAS_COLD_ACCOUNT_CODE_ACCESS`

At the end of the model estimation and mapping, we will have a set of different runtime estimations for a single client. To estimate the final parameter, we will use the worst case runtime (i.e., the slowest). The only exception is storage size configuration. For this case, the user will have the option to pre-select a size in which the final parameters should be based on. The final reports will focus on the results from this storage size, but we will add a new report that compares how storage access scales with storage size.
