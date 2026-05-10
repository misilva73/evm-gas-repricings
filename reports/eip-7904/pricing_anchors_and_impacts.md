# Pricing anchors and their impact on realized throughput

### Maria Silva, January 2025

In this document, we explore a simple scenario that illustrates the different options for repricing and their impact on throughput. There are three main decisions to take on this:

1. The performance anchor at which to reprice
2. Whether we only increase the price of bottleneck operations or whether we also make the other operations cheaper.
3. What the final block limit for Glamsterdam will be.

Let's assume we have a simplified version of the EVM whether all opcodes can be mapped to two types - `SIMPLE` and `COMPLEX`. These operations have the following spec:

|   Opcode  | Performance | Current gas price |
|:---------:|:-----------:|:-----------------:|
|  `SIMPLE` |  200 Mgas/s |       4 gas       |
| `COMPLEX` |  20 Mgas/s  |       10 gas      |

## Case 1: No repricing

In this case, there are no changes in price and the gas limit is set by the worst performing operations at 20Mgas/s. The max operations for each case are computed by dividing the induced gas limit by the gas price of each operation.

|             Scenario              | Induced gas limit | Max. `SIMPLE` ops. | Max. `COMPLEX` ops |
|:---------------------------------:|:-----------------:|:------------------:|:------------------:|
|            3s execution           |      60M gas      |       15M ops      |       6M ops       |
|            4s execution           |      80M gas      |       20M ops      |       8M ops       |
| 4s execution + 3x parallelization |      240M gas     |       60M ops      |       24M ops      |

## Case 2: Reprice `COMPLEX` at 60Mgas/s

In this case, the price of `COMPLEX` operations increases by 3x to reach the 60Mgas/s performance. Their price is now 30 gas. In addition, the gas limit is set by this new performance threshold (i.e., 60Mgas/s).

|             Scenario              | Induced gas limit | Max. `SIMPLE` ops. | Max. `COMPLEX` ops |
|:---------------------------------:|:-----------------:|:------------------:|:------------------:|
|            3s execution           |      180M gas     |       45M ops      |       6M ops       |
|            4s execution           |      240M gas     |       60M ops      |       8M ops       |
| 4s execution + 3x parallelization |      720M gas     |       180M ops     |       24M ops      |

As expected, the throughput on the `SIMPLE` operations triples, while the throughput on the `COMPLEX` operations remains the same. The gain in throughput comes directly from the difference between the worst Mgas/s performance between the current worst performance (in this case 20Mgas/s) and the new target set (in this case, 60Mgas/s). Note that this only works if the price of all `COMPLEX` operations is increased.

## Case 3: Reprice `SIMPLE` at 20Mgas/s

In this case, we reduce the cost of `SIMPLE` operations as much as possible. To have the operations perform at 20Mgas/s, we would require a cost of 0.4, however, this is not possible since gas cost must be integers. Thus, we price them at 1 gas. The gas limit is the same as case 1.

|             Scenario              | Induced gas limit | Max. `SIMPLE` ops. | Max. `COMPLEX` ops |
|:---------------------------------:|:-----------------:|:------------------:|:------------------:|
|            3s execution           |      60M gas      |       60M ops      |       6M ops       |
|            4s execution           |      80M gas      |       80M ops      |       8M ops       |
| 4s execution + 3x parallelization |      240M gas     |       240M ops     |       24M ops      |

As expected, the throughput on the `SIMPLE` operations increases 4x, while the throughput on the `COMPLEX` operations remains the same. The gain in throughput comes from how much we can reduce the price of the `SIMPLE` operations. Of course, this gain is only achieved on the `SIMPLE` operations that are actually repriced, while in case 2 all `SIMPLE` operations experience the gain in throughput.

## Case 4: Reprice `COMPLEX` at 60Mgas/s, but limit the block limit at 300M gas/s

In this a special case that tries to see the impact of having a high anchor (60Mgas/s) and not taking full advantage of it by setting a lower gas limit, say 300M gas units.

This is the same as case 2 for all scenarios, expect for 4s execution + 3x parallelization:

|             Scenario              | Induced gas limit | Max. `SIMPLE` ops. | Max. `COMPLEX` ops |
|:---------------------------------:|:-----------------:|:------------------:|:------------------:|
|            3s execution           |      180M gas     |       45M ops      |       6M ops       |
|            4s execution           |      240M gas     |       60M ops      |       8M ops       |
| 4s execution + 3x parallelization |      300M gas     |       75M ops      |       10M ops      |

If we compare the results of the last scenario (i.e., 4s execution + 3x parallelization) against the same scenario in case 1 (i.e., no reprice), we see why this is not optimal. The `SIMPLE` operations still get a slight increase in throughput, by having the block limit raise from 240M gas units in case 1 to 300M gas units in case 4. However, the throughput for `COMPLEX` operations gets worst (24M ops vs. 10M ops) because we raised the price of these operations too much in relation to the final gas limit chosen.

One may then question - if the execution performance allows us to get to 720M gas, why would we limit ourselves to a lower block limit? There are two reasons this can happen:

1. Raising the gas limit too rapidly will reduce the base fee too much until demand picks up. This may not be a huge concern, but we need more analysis on this.
2. With higher block limits, there is more space for creating new state, thus increasing the state growth rate. We may not be ready in Glamsterdam to increase the limit too much due to concerns about pricing state creation operation (i.e., EIP-8037).
