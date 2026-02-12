# Empirical Analysis of Price Elasticities for Ethereum State and Burst Resources

#### Maria Silva, February 2026

## Introduction

This report is a follow-up to our previous analysis of [different aggregation functions for EIP-8037 under different elasticity regimes](https://ethresear.ch/t/analysis-of-different-aggregation-functions-for-eip-8037-under-different-elasticity-regimes/24033). That analysis used an **independent isoelastic demand model** where state and burst resources had separate, independent demand curves. However, empirical analysis of recent Ethereum data reveals a different pattern: state and burst resources appear to be **substitutes competing for fixed block capacity** rather than independent demands.

This report **empirically measures the price elasticity** of aggregate demand and the allocation between state creation versus burst resources. Our findings suggest a **capacity-constrained demand model** better describes Ethereum user behavior than the independent demand model.

Our analysis uses daily data from January 2025 to January 2026, a period that includes three major gas limit increases (30M → 36M → 45M → 60M). This unique dataset allows us to observe how both aggregate demand and resource allocation respond to price changes in both the short run (daily variations) and during major capacity shocks (gas limit increases).

### Key Findings

Our empirical analysis reveals:

1. **Strong substitution between state and burst resources**: The correlation between state gas and burst gas is approximately -0.99, indicating they compete for fixed block capacity rather than varying independently.

2. **Low aggregate demand elasticity**: When the gas limit increased and base fees dropped, total gas usage increased proportionally to fill the new capacity. The long-run aggregate demand elasticity is ε_agg ≈ 0.0066 from daily data, and 0.175 ± 0.093 from gas limit increase events, both indicating relatively inelastic aggregate demand.

3. **Moderate state share elasticity**: The share of gas devoted to state creation responds to price changes with long-run elasticity η ≈ 0.43 from daily data. When state becomes relatively more expensive, users substitute toward burst resources. However, event-based estimates show high variance (η ≈ 0.019 ± 0.261), highlighting uncertainty in user responses to large price shocks.

4. **Capacity-constrained behavior**: Block utilization remained stable at ~50% after each gas limit increase, consistent with the EIP-1559 mechanism that adjusts the base fee to target 50% block utilization.

In the following sections, we present the empirical evidence for the capacity-constrained model and detail our methodology for measuring both aggregate demand elasticity and state share elasticity.

## Data and Preprocessing

Our empirical analysis uses daily Ethereum mainnet data spanning from January 1, 2025 to January 31, 2026 (approximately 395 observations). The dataset includes block-level metrics (gas used, gas limit, base fee) and state growth metrics (storage slots created, accounts created, code size). All blockchain data was extracted from [Xatu's dataset](https://ethpandaops.io/data/xatu/). The analysis period includes three major gas limit increases (30M → 36M on Feb 4; 36M → 45M on Jul 21; 45M → 60M on Nov 25), providing natural experiments to observe demand responses to capacity and price changes.

Raw block-level data was aggregated to daily observations. We estimated the gas used for state creation by multiplying the net bytes added to state by account, storage slots and contract code by their respective gas costs (25000 gas per 112 byte account, 20000 gas per 32 byte slot and 200 gas per 1 byte of contract code). The gas used by burst resources was assumed as the residual.

We employed ARDL (Autoregressive Distributed Lag) models on log-differenced variables to ensure stationarity and used heteroskedasticity-robust standard errors to account for structural breaks.

All data and analysis code are available in the following [notebook](../../notebooks/0.7-resource_price_elasticity_v2.ipynb).

## Demand Models: Independent vs. Capacity-Constrained

### Independent Isoelastic Demand Model

Our previous analysis assumed that state and burst resources have **independent demand curves**:

$$S(p) = A_s \cdot p^{-\varepsilon_s}$$

$$B(p) = A_b \cdot p^{-\varepsilon_b}$$

Where:

- $S(p)$ and $B(p)$ are the gas used for each resource at price $p$
- $A_s$ and $A_b$ are demand scale parameters
- $\varepsilon_s$ and $\varepsilon_b$ are price elasticities for each resource

In this model, state and burst demands vary independently. When the price changes, each resource responds according to its own elasticity, and the total gas used is simply the sum: $G^{\text{total}} = S(p) + B(p)$. This model assumes that state and burst resources are neither substitutes nor complements—they vary independently of each other.

### Capacity-Constrained Demand Model

The capacity-constrained model assumes users have an **aggregate demand for block space** that gets allocated between state and burst resources:

$$G^{\text{total}}(p) = A \cdot p^{-\varepsilon_{\text{agg}}}$$

$$\alpha_s(mp) = \frac{1}{1 + \kappa \cdot (mp)^\eta}$$

$$S = \alpha_s(mp) \cdot G^{\text{total}}(p)$$

$$B = (1 - \alpha_s(mp)) \cdot G^{\text{total}}(p)$$

Where:

- $G^{\text{total}}(p)$ is total gas demanded at price $p$
- $\alpha_s(mp)$ is the share allocated to state creation at repricing multiplier $m$ and price $p$
- $\varepsilon_{\text{agg}}$ is the aggregate price elasticity
- $\eta$ is the share elasticity (sensitivity to relative prices)
- $\kappa$ is the share ratio parameter

This model assumes that state and burst are **substitutes** competing for fixed aggregate capacity. When prices change, both aggregate demand and the allocation between resources adjust.

### Why Capacity-Constrained?

Looking at the last year data, we see that a capacity-constrained model better matches the observed behavior:

1. **High negative correlation**: State gas and burst gas have correlation ≈ -0.99, indicating strong substitution
2. **Stable block utilization**: After gas limit increases, utilization quickly returns to ~50%
3. **Proportional scaling**: When capacity increases, total usage scales proportionally, not according to independent elasticities
4. **Share responds to prices**: The state share decreases when state becomes relatively more expensive. The share of gas used for state creation and the base fee have a negative correlation (-0.21).

In the following sections, we use the capacity-constrained model to empirically estimate the prices elasticities of aggregate demand and the share of gas used for state creation.

## How Aggregate Demand Responds to Base Fee Changes

### Evidence from Daily Changes

Using daily data from January 2025 to January 2026, we estimated an **ARDL (Autoregressive Distributed Lag) model** to measure how total gas usage responds to base fee changes:

$$\Delta \ln(G^{\text{total}}_t) = \beta_0 + \sum_i \phi_i \Delta \ln(G^{\text{total}}_{t-i}) + \sum_j \beta_j \Delta \ln(p_{t-j}) + \varepsilon_t$$

The model accounts for both immediate (contemporaneous) and lagged effects of price changes on gas usage. The ARDL model allows us to distinguish between two types of elasticities:

- **Cumulative aggregate elasticity**: This is the sum of all coefficients on the contemporaneous and lagged price terms ($\sum_j \beta_j$). It captures the total immediate effect of a price change, accumulating the impact from the current period and all lagged periods included in the model. This represents the short-run response before any feedback through the autoregressive terms.

- **Long-run aggregate elasticity**: This adjusts the cumulative elasticity for the autoregressive dynamics by dividing by $(1 - \sum_i \phi_i)$, where $\phi_i$ are the coefficients on lagged dependent variables. It represents the steady-state response after all dynamic adjustments have occurred, including feedback effects where current gas usage influences future gas usage. This captures the full equilibrium effect of a sustained price change.

**Key results:**

- **Cumulative aggregate elasticity**: ε_agg = 0.0049 (95% CI: [0.0008, 0.0090])
- **Long-run aggregate elasticity**: ε_agg = 0.0066
- **Statistical significance**: t = -2.35, p = 0.0195
- **Model diagnostics**: No evidence of residual autocorrelation (Ljung-Box p = 0.98)

**Interpretation**: A 1% increase in the base fee is associated with a 0.007% decrease in total gas usage in the long run. This indicates **highly inelastic aggregate demand**.

### Evidence from Gas Limit Increase Events

Based on daily changes, aggregate demand seems to be quite inelastic. However, we also want to check the price elasticity during periods of large changes in the block gas limit. We know that during these events, the base fee decreases to a new equilibrium value, which should induce a different elasticity.

To this effect, we analyzed three major gas limit increases during 2025:

1. **February 4, 2025**: 30M → 36M (+20%)
2. **July 21, 2025**: 36M → 45M (+25%)
3. **November 25, 2025**: 45M → 60M (+33%)

Using the equilibrium condition $G^{\text{total}}(p) = A \cdot p^{-\varepsilon}$ and the fact that utilization remained at 50%, we can derive the implied elasticity:

$$\varepsilon = -\frac{\ln(1 + \Delta_{\text{limit}})}{\ln(1 + \Delta_{\text{basefee}})}$$

Note that we used the median values of the base fee for each gas limit interval.

**Results:**

| Event | Gas Limit Change | Base Fee Change | Implied ε_agg |
|-------|-----------------|----------------|---------------|
| 30M → 36M | +20% | -85.6% | 0.094 |
| 36M → 45M | +25% | -55.3% | 0.277 |
| 45M → 60M | +33% | -84.5% | 0.154 |
| **Mean** | - | - | **0.175 ± 0.093** |

**Interpretation**: The event-based elasticity (0.175) is higher than the daily elasticity (0.007), suggesting that elasticity is higher during significant gas limit increases. However, it is still low, showing that aggregate demand is relatively inelastic. When capacity increases, **demand expands to fill it**, with base fees adjusting to maintain target utilization.

## How State Share Responds to Base Fee Changes

### Evidence from Daily Changes

Similarly to the aggregate demand model, we used daily data from January 2025 to January 2026 to fit an **ARDL (Autoregressive Distributed Lag) model**. However, we estimated how the **share of gas devoted to state** responds to base fee changes using the log-odds ratio:

$$\log\left(\frac{\alpha_s}{1 - \alpha_s}\right) = \log(\kappa^{-1}) - \eta \cdot \log(p)$$

**Key results:**

- **Cumulative share elasticity**: η = 0.9687 (95% CI: [0.6413, 1.2961])
- **Long-run share elasticity**: η = 0.4295
- **Statistical significance**: t = -5.82, p < 0.001
- **Model has residual autocorrelation** (may be due to gas limit increase structural breaks)

**Interpretation**: The state share has moderate elasticity (η ≈ 0.43). When the base fee increases by 1%, the odds of choosing state over burst decrease by approximately 0.43%. This confirms that **users substitute between state and burst** based on prices.

### Evidence from Gas Limit Increase Events

In order to see the elasticity of state creation to large shocks in the base fee and the gas limit, we computed the implied share elasticity from the three gas limit increase events by comparing the state share odds before and after each event:

$$\eta = -\frac{\Delta \ln(\text{odds})}{\Delta \ln(p)}$$

Note that we used the median values of the base fee and the state share odds for each gas limit interval.

**Results:**

| Event | Gas Limit Change | Base Fee Change | Odds Change | Implied η |
|-------|-----------------|----------------|-------------|-----------|
| 30M → 36M | +20% | -85.6% | +37.9% | 0.166 |
| 36M → 45M | +25% | -55.3% | -20.3% | -0.282 |
| 45M → 60M | +33% | -84.5% | +38.2% | 0.174 |
| **Mean** | - | - | - | **0.019 ± 0.261** |

**Interpretation**: The event-based estimates have high variance. One of the intervals saw a negative implied elasticity, meaning that during that interval the share of gas used for state creation decreased. This highlights the uncertainty around how users will respond to changes in the prices of the various resources.
