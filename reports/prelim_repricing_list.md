# Preliminary list of repricing changes - 7904, 8038 and 2780

The following costs correspond to our latest estimates of gas costs, using compute and stateful repricing benchmarks. The primary numbers below were estimated on the **Osaka** fork (which does not include BAL optimizations) using an anchor of **60 Mgas/s**. For EIP-7904, we also include a comparison against an **Amsterdam** run, which uses an anchor of **100 Mgas/s** reflecting the higher throughput target enabled by BAL optimizations.

## EIP-7904 Compute: directly estimated operations (Osaka, 60 Mgas/s)

|Opcode|Parameter|Current Gas|New Gas (Rounded)|Change|
| :---: | :---: | :---: | :---: | :---: |
|ADDMOD|constant|8|8|0.0|
|BLAKE2F|constant|0|48|inf|
|BLAKE2F|num_rounds|1|1|0.0|
|DIV|constant|5|5|0.0|
|ECADD|constant|150|382|1.55|
|MOD|constant|5|6|0.2|
|MULMOD|constant|8|12|0.5|
|P256VERIFY|constant|6900|15958|1.31|
|POINT_EVALUATION|constant|50000|84081|0.68|
|SDIV|constant|5|6|0.2|
|SMOD|constant|5|6|0.2|

Note: `KECCAK256`, `ECRECOVER`, `BLS12_G1ADD` and `BLS12_G2ADD` are not included as their estimated cost is lower than the current cost. `ECPAIRING` had no good fit on Osaka. `reth` was excluded due to poor glue-opcode fits.

## EIP-8038 State access: directly estimated parameters (Osaka, 60 Mgas/s)

|Parameter|Current Gas|New Gas (Rounded)|Change|
| :---: | :---: | :---: | :---: |
|GAS_COLD_ACCOUNT_CODE_ACCESS|2600|21457|7.25|
|GAS_COLD_ACCOUNT_NOCODE_ACCESS|2600|10591|3.07|
|GAS_COLD_ACCOUNT_WRITE|6700|224268|32.47|
|GAS_COLD_STORAGE_ACCESS|2200|191667|86.12|
|GAS_COLD_STORAGE_WRITE|2900|149032|50.39|
|GAS_WARM_ACCESS|100|20903|208.03|

## EIP-8038 State access: derived parameters

|Parameter|Current Gas|New Gas (Rounded)|Change|
| :---: | :---: | :---: | :---: |
|GAS_STORAGE_CLEAR_REFUND|4800|327072|67.14|
|ACCESS_LIST_STORAGE_KEY_COST|1900|191667|99.88|
|ACCESS_LIST_ADDRESS_COST|2400|21457|7.94|
