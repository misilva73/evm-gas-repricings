# Max-Based EIP-1559 Equilibrium for State Growth Analysis

#### Maria Silva — February 2026

## Overview

This document presents an alternative equilibrium condition for analyzing state growth under increased throughput. Instead of the standard additive (sum-based) equilibrium where state and burst resources share block space, we model a max-based equilibrium where each resource can independently use up to 100% of the gas limit and the base fee is set by the resource with the highest gas used.

## Motivation

In the original [state growth scenarios analysis](state_growth_scenarios_report.md), the EIP-1559 equilibrium is reached when the total gas usage (state + burst) equals 50% of the gas limit:

$$U(b^*) = g_\text{state}S(b^* g_\text{state}) + g_\text{burst}B(b^* g_\text{burst}) = 0.5 \, n \, G^0$$

This represents a model where state creation and burst resources compete for the same block space additively.

The **max-based equilibrium** explores an alternative metering mechanism where each resource type has its own independent target:

$$\max\Big(g_\text{state}S(b^* g_\text{state}), \, g_\text{burst}B(b^* g_\text{burst})\Big) = 0.5 \, n \, G^0$$

Under this model:

- Each resource can use up to 50% of the gas limit independently under equilibrium
- The equilibrium base fee is determined by whichever resource hits its limit first
- The other resource "follows along" and may use less than 50% of capacity
- Total gas usage can vary (can be less than, equal to, or greater than 50% of the limit)

This approach mirrors multidimensional metering (see [EIP-8011](https://eips.ethereum.org/EIPS/eip-8011)), where different resource types are metered independently, which is the current design for [EIP-8037](https://eips.ethereum.org/EIPS/eip-8037).

## Mathematical Derivation

### Model Inputs and Assumptions

The model uses the same inputs as the original analysis:

**Parameters:**

- $G$: Block gas limit
- $b$: Base fee (in gwei)
- $g_\text{state}$: Gas cost per new state byte
- $g_\text{burst}$: Gas cost per burst-resource second
- $S(p)$: Demand for state creation (bytes per block) at effective price $p = b \cdot g_\text{state}$
- $B(p)$: Demand for burst resources (seconds per block) at effective price $p = b \cdot g_\text{burst}$

**Demand Functions:**
Both demands follow isoelastic (constant-elasticity) forms:

$$S(p) = A_s \, p^{-\varepsilon_s}, \qquad B(p) = A_b \, p^{-\varepsilon_b}, \qquad \varepsilon_s, \varepsilon_b > 0$$

where $\varepsilon_s$ and $\varepsilon_b$ are the price elasticities of demand for state creation and burst resources, respectively.

### Calibration from Initial Conditions

We calibrate the demand amplitudes $A_s$ and $A_b$ from observed baseline conditions.

At current gas limit $G^0$ and equilibrium base fee $b^0$:

- State creation uses 30% of half the gas limit: $g_\text{state}^0 S(b^0 g_\text{state}^0) = 0.15 \, G^0$
- Burst resources use 70% of half the gas limit: $g_\text{burst}^0 B(b^0 g_\text{burst}^0) = 0.35 \, G^0$

From these conditions, we derive:

$$A_s = \frac{0.15 \, G^0}{g_\text{state}^0} \, (b^0 g_\text{state}^0)^{\varepsilon_s}$$

$$A_b = \frac{0.35 \, G^0}{g_\text{burst}^0} \, (b^0 g_\text{burst}^0)^{\varepsilon_b}$$

We also estimate the baseline gas costs:

- From state growth data: $g_\text{state}^0 = \frac{0.15 \, G^0}{S^0}$, where $S^0$ is the observed state bytes per block
- From worst-case execution time: $g_\text{burst}^0 = \frac{G^0}{2}$ (assumes a full block of burst operations takes 2 seconds)

### Scenario Definition

Consider a scenario where:

- Gas limit increases by factor $n$: $G = n \, G^0$
- State gas costs increase by factor $m$: $g_\text{state} = m \, g_\text{state}^0$
- Burst gas costs remain unchanged: $g_\text{burst} = g_\text{burst}^0$

### Max-Based Equilibrium Condition

The equilibrium base fee $b^*$ is defined such that:

$$\max\Big(g_\text{state} S(b^* g_\text{state}), \, g_\text{burst} B(b^* g_\text{burst})\Big) = 0.5 \, n \, G^0$$

Substituting the scenario parameters:

$$\max\Big(m \, g_\text{state}^0 S(b^* m g_\text{state}^0), \, g_\text{burst}^0 B(b^* g_\text{burst}^0)\Big) = 0.5 \, n \, G^0$$

Using the isoelastic demand functions with calibrated amplitudes, this becomes:

$$\max\Big(0.15 \, G^0 \, m^{1-\varepsilon_s} \Big(\frac{b^*}{b^0}\Big)^{-\varepsilon_s}, \, 0.35 \, G^0 \Big(\frac{b^*}{b^0}\Big)^{-\varepsilon_b}\Big) = 0.5 \, n \, G^0$$

Dividing by $G^0$ and defining the base fee ratio $r = \frac{b^*}{b^0}$:

$$\max\Big(0.15 \, m^{1-\varepsilon_s} \, r^{-\varepsilon_s}, \, 0.35 \, r^{-\varepsilon_b}\Big) = 0.5 \, n$$

### Solving for Equilibrium

To find the equilibrium, we compute two candidate base fee ratios:

**Candidate 1: State-limited equilibrium**

If state creation reaches the target:

$$0.15 \, m^{1-\varepsilon_s} \, r^{-\varepsilon_s} = 0.5 \, n$$

Solving for $r$:

$$r^{-\varepsilon_s} = \frac{0.5 \, n}{0.15 \, m^{1-\varepsilon_s}} = \frac{n}{0.3 \, m^{1-\varepsilon_s}}$$

$$r_\text{state} = \Big(\frac{0.3 \, m^{1-\varepsilon_s}}{n}\Big)^{1/\varepsilon_s}$$

**Candidate 2: Burst-limited equilibrium**

If burst resources reach the target:

$$0.35 \, r^{-\varepsilon_b} = 0.5 \, n$$

Solving for $r$:

$$r^{-\varepsilon_b} = \frac{0.5 \, n}{0.35} = \frac{n}{0.7}$$

$$r_\text{burst} = \Big(\frac{0.7}{n}\Big)^{1/\varepsilon_b}$$

**Determining the Valid Equilibrium**

The equilibrium base fee ratio is:

$$r^* = \max(r_\text{state}, r_\text{burst})$$

**Intuition**: Whichever resource requires a *higher* base fee to reach the target will determine the equilibrium. At this base fee:

- The limiting resource exactly reaches the target (50% of gas limit)
- The non-limiting resource uses less than the target
- The limiting resource determines the equilibrium; the other resource adjusts passively

The equilibrium base fee is then:

$$b^* = b^0 \, r^*$$

### Equilibrium Statistics

Once $b^*$ (or equivalently $r^*$) is determined, we compute:

**Per-block resource usage:**

$$S^* = A_s \, (b^* m g_\text{state}^0)^{-\varepsilon_s}$$

$$B^* = A_b \, (b^* g_\text{burst}^0)^{-\varepsilon_b}$$

**Gas consumption by resource type:**

$$g_\text{used,state} = m \, g_\text{state}^0 \, S^*$$

$$g_\text{used,burst} = g_\text{burst}^0 \, B^*$$

$$g_\text{used,total} = g_\text{used,state} + g_\text{used,burst}$$

Note that $g_\text{used,total}$ is **not constrained** to equal $0.5 \, n \, G^0$. It can be:

- Less than $0.5 \, n \, G^0$ (when one resource dominates and the other uses little capacity)
- Equal to $0.5 \, n \, G^0$ (when both resources happen to reach the target simultaneously)
- Greater than $0.5 \, n \, G^0$ (when both resources use significant capacity)

**Resource shares:**

$$\text{Share}_\text{state} = \frac{g_\text{used,state}}{0.5 \, n \, G^0}$$

$$\text{Share}_\text{burst} = \frac{g_\text{used,burst}}{0.5 \, n \, G^0}$$

These shares represent each resource's usage relative to the 50% target. They do **not** necessarily sum to 1.0 under the max-based model.

**Annual state growth:**

Assuming 2,628,000 blocks per year (12-second block time):

$$\text{State growth (bytes/year)} = 2,628,000 \times S^*$$

Converting to GiB (using $1 \text{ GiB} = 2^{30}$ bytes):

$$\text{State growth (GiB/year)} = 2,628,000 \times S^* \times \frac{1}{2^{30}}$$
