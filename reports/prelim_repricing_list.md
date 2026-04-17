# Preliminary list of repricing changes - 7904, 838 and 2780

The following costs correspond to our latest estimates of gas costs, using compute and stateful repricing benchmarks. They were estimated using the Osaka fork and thus do not include BAL optimizations. We used an anchor of 60Mgas/s to set these costs.

## Compute: directly estimated operations

|Opcode|Parameter|Current Gas|New Gas (Rounded)|Change|
| :---: | :---: | :---: | :---: | :---: |
|ADDMOD|constant|8|8|0.0|
|BLAKE2F|constant|0|48|inf|
|BLAKE2F|num_rounds|1|1|0.0|
|DIV|constant|5|6|0.2|
|ECADD|constant|150|382|1.55|
|MOD|constant|5|6|0.2|
|MULMOD|constant|8|12|0.5|
|P256VERIFY|constant|6900|15958|1.31|
|POINT_EVALUATION|constant|50000|84081|0.68|
|SDIV|constant|5|6|0.2|
|SMOD|constant|5|6|0.2|

Note: `KECCAK256`, `ECRECOVER`, `BLS12_G1ADD` and `BLS12_G2ADD` are not included as their estimated cost are lower than then current costs.


## State access: Directly estimated parameters

|Parameter|Current Gas|New Gas (Rounded)|Change|
| :---: | :---: | :---: | :---: |
|GAS_COLD_ACCOUNT_CODE_ACCESS|2600|21770|7.37|
|GAS_COLD_ACCOUNT_NOCODE_ACCESS|2600|10460|3.02|
|GAS_COLD_ACCOUNT_WRITE|6700|233975|33.92|
|GAS_COLD_STORAGE_ACCESS|2200|192322|86.42|
|GAS_COLD_STORAGE_WRITE|2900|148495|50.21|

## State access: Derived parameters

|Parameter|Current Gas|New Gas (Rounded)|Change|
| :---: | :---: | :---: | :---: |
|GAS_STORAGE_CLEAR_REFUND|4800|327185|67.16|
|ACCESS_LIST_STORAGE_KEY_COST|1900|192322|100.22|
|ACCESS_LIST_ADDRESS_COST|2400|21770|8.07|