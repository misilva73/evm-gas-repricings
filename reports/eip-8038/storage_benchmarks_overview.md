# An overview of SSTORE / SLOAD Benchmark Tests

## Compute benchmarks — `tests/benchmark/compute/instruction/test_storage.py`

| Test | Repricing | Summary |
|------|-----------|---------|
| `test_storage_access_cold` | No | Benchmarks **cold** SLOAD/SSTORE using EIP-7702 delegation. Parametrized by `storage_action` (READ / WRITE_SAME_VALUE / WRITE_NEW_VALUE), `absent_slots` (whether slots are pre-populated), and `tx_result` (SUCCESS / REVERT / OUT_OF_GAS). Measures worst-case cold access costs with different transaction outcomes. |
| `test_storage_access_cold_benchmark` | Yes | Simpler cold SLOAD/SSTORE benchmark using `ExtCallGenerator`. Each iteration accesses a different slot (incrementing key via `Op.GAS`) to guarantee cold access. Parametrized by `storage_action` (READ / WRITE_SAME_VALUE / WRITE_NEW_VALUE). |
| `test_storage_access_warm` | No | Benchmarks **warm** SLOAD/SSTORE by deploying a contract that first does an SLOAD to warm the slot, then loops the target operation on slot 0. Parametrized by `storage_action` (READ / WRITE_SAME_VALUE / WRITE_NEW_VALUE). |
| `test_storage_access_warm_benchmark` | Yes | Simpler warm SLOAD/SSTORE benchmark using `ExtCallGenerator`. Accesses a fixed slot (`PUSH0`) so all accesses are warm. Parametrized by `storage_action` (READ / WRITE_SAME_VALUE / WRITE_NEW_VALUE). |

**Notes:**

- The `test_storage_access_warm_benchmark` and `test_storage_access_cold_benchmark` with the `WRITE_SAME_VALUE` config writes 0 -> 0 many times. This is not the same as writing the same value to an existent slot (e.g., 1 -> 1). In this case, the slot 0 was never set, so it doesn't exist in the storage trie. The client may short-circuit — it sees the slot is absent (default zero) and the new value is also zero, so there's nothing to do.

## Stateful bloatnet — single opcode — `tests/benchmark/stateful/bloatnet/test_single_opcode.py`

| Test | Repricing | Summary |
|------|-----------|---------|
| `test_sload_empty_erc20_balanceof` | Yes | Benchmarks **SLOAD** via ERC20 `balanceOf()` calls on a bloatnet stub contract. Each call forces a cold SLOAD on a likely-empty storage slot (keccak-hashed random address). Parametrized by `token_name` (different ERC20 stubs). |
| `test_sstore_erc20_approve` | Yes | Benchmarks **SSTORE** via ERC20 `approve()` calls on a bloatnet stub contract. Each call writes to a new allowance storage slot (cold SSTORE). Parametrized by `token_name`. |
| `test_sstore_variants` | Yes | Comprehensive **SSTORE** benchmark using EIP-7702 delegation. Parametrized by `access_warm` (cold vs warm via access lists), `sloads_before_sstore` (whether to SLOAD before SSTORE), and `initial_value`/`write_value` transitions: zero→zero, zero→nonzero, nonzero→different, nonzero→same. |
| `test_storage_sload_benchmark` | Yes | Comprehensive **SLOAD** benchmark using EIP-7702 delegation. Parametrized by `access_warm` (cold vs warm via access lists) and `storage_keys_pre_set` (whether slots have existing values). |
| `test_storage_sload_same_key_benchmark` | Yes | Benchmarks **SLOAD** of the **same key** repeatedly (warm after first access). Measures best-case warm SLOAD throughput. Parametrized by `storage_keys_pre_set` (whether the key holds a nonzero value). |

**Notes:**

- Using Access Lists to pre-warm slots is likely to lead to wrong measurements. Clients may not be pre-fetching the slots and, in that case, the runtime of cold vs. warm configs will be the same.
- The ECR20 tests allow us to measure the impact of different-sized storage on I/O performance. We have the following tokens:
  - IMT (small)
  - USDC (medium)
  - XEN (large)
  - 30GB_ERC20 (very large)

## Stateful bloatnet — multi opcode — `tests/benchmark/stateful/bloatnet/test_multi_opcode.py`

| Test | Repricing | Summary |
|------|-----------|---------|
| `test_mixed_sload_sstore` | No | Benchmarks a **mixed SLOAD+SSTORE** workload on bloatnet. Runs `balanceOf()` calls (SLOAD) followed by `approve()` calls (SSTORE) in configurable ratios: 10/90, 30/70, 50/50, 70/30, 90/10. Parametrized by `token_name` and `sload_percent`/`sstore_percent`. |

## Stateful bloatnet — depth benchmarks — `tests/benchmark/stateful/bloatnet/depth_benchmarks/test_deep_branch.py`

| Test | Repricing | Summary |
|------|-----------|---------|
| `test_worst_depth_stateroot_recomp` | No | Worst-case **SSTORE** attack benchmark targeting Patricia Merkle Trie depth. Uses CREATE2 to deploy contracts at pre-mined addresses with shared prefixes, maximizing trie traversal. Each attack writes to deep storage slots. Parametrized by `storage_depth` (10–12) and `account_depth` (3–7). |

## Configuration matrices

**Bold** marks dimensions that are parametrized (varied); regular text marks fixed values.

### SLOAD

| Test | Cold/Warm | Storage Size | New/Existing Slot |
|------|-----------|--------------|-------------------|
| `test_storage_access_cold_benchmark` | Cold | Just created | New |
| `test_storage_access_warm_benchmark` | Warm | Just created | New |
| `test_sload_empty_erc20_balanceof` | Cold | **Varies** (`token_name`) | New |
| `test_storage_sload_benchmark` | Depends on `storage_keys_pre_set`³ | Just created | **Varies** (`storage_keys_pre_set`)³ |
| `test_storage_sload_same_key_benchmark` | Warm | Just created | **Varies** (`storage_keys_pre_set`)³ |

### SSTORE

| Test | Cold/Warm | Storage Size | New/Existing Slot | Same/Different Value |
|------|-----------|--------------|-------------------|----------------------|
| `test_storage_access_cold_benchmark` | Cold | Just created | New | 0→0; 0→diff |
| `test_storage_access_warm_benchmark` | Warm | Just created | New | 0→0⁴; 0→diff |
| `test_sstore_erc20_approve` | Cold | **Varies** (`token_name`) | New | 0→diff |
| `test_sstore_variants` | Depends on `initial_value`³ | Just created | **Varies** (`initial_value`) | **Varies** (`write_value`) |

### Notes

**¹** `test_storage_access_warm` warms the slot via an initial SLOAD before looping. With `WRITE_SAME_VALUE`, this produces 0→0 repeatedly on a never-set slot — clients may short-circuit this as a no-op, so it does not measure the same thing as writing an existing nonzero value back to itself (nz→same).

**²** `access_warm` uses access lists to pre-warm slots. Clients may not actually pre-fetch these slots, so cold and warm configs could yield identical runtimes. Thus, for now, we should only use the cold version of these tests.

**³** `storage_keys_pre_set=True` pre-populates the storage slots before the benchmark, which also warms them. As a result, this variant will always measure warm access regardless of the `access_warm` setting. the same happens with the `initial_value` different from 0 in `test_sstore_variants`.

**⁴** There is a [PR](https://github.com/ethereum/execution-specs/pull/2255) aiming to fix `test_storage_access_warm_benchmark`, so it does 1→1 instead of 0→0.

### Coverage gaps

| Dimension cross | Missing |
|-----------------|---------|
| SLOAD × cold × existing slot × storage size | `test_sload_empty_erc20_balanceof` only reads random slots (likely empty); no token-parametrized test reads pre-set slots; we also don't have a cold SLOAD to existing slots |
| SSTORE × cold × existing slot × storage size | `test_sstore_variants` varies transitions but not storage size; `test_sstore_erc20_approve` varies storage size but is fixed at 0→nonzero |