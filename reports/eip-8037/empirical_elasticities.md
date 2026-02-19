# Empirical Analysis of Price Elasticities for Ethereum State and Burst Resources

#### Maria Silva, February 2026

This report is a follow-up to our previous analysis of [different aggregation functions for EIP-8037 under different elasticity regimes](https://ethresear.ch/t/analysis-of-different-aggregation-functions-for-eip-8037-under-different-elasticity-regimes/24033). That analysis used an **independent isoelastic demand model** where state and burst resources had separate, independent demand curves. However, measuring these elasticities empirically is challenging: under EIP-1559, state and burst resources behave as **substitutes competing for fixed block capacity** rather than independent demands.

To address this, we **empirically measure the price elasticity** of aggregate demand and the allocation between state creation and burst resources using a **capacity-constrained demand model** that better describes observed user behavior. We then recover the individual elasticities from the estimated model. Our analysis uses daily Ethereum mainnet data from January 2025 to January 2026, a period that includes three major gas limit increases (30M → 36M → 45M → 60M), providing natural experiments to observe demand responses to capacity and price changes.

The analysis can be reproduced by running this [notebook](https://github.com/misilva73/evm-gas-repricings/blob/6cf7748d431e2ea31bec47c5a215178cb0c7cbec/notebooks/0.7-resource_price_elasticity_v2.ipynb).

**TLDR**

- State and burst resources are **strong substitutes**: the correlation between state gas and burst gas is approximately -0.99, confirming they compete for fixed block capacity rather than varying independently.
- **Aggregate demand is highly inelastic**: the event-based aggregate demand elasticity is $\varepsilon_\text{agg} \approx 0.175 \pm 0.093$. However, when capacity increases, demand expands to fill it, with base fees adjusting to maintain target utilization.
- **Users substitute between state and burst based on prices**: the long-run state share elasticity is $\eta \approx 0.43$. When the base fee rises, the share of gas devoted to state creation decreases. However, event-based estimates show high variance (with even one event showing a negative elasticity), highlighting uncertainty in how users respond to large price shocks.
- **State demand is moderately elastic while burst demand is nearly inelastic**: converting to independent elasticities, we estimate $\varepsilon_s \approx 0.3$–$0.6$ and $\varepsilon_b \approx 0.0$–$0.2$. These are consistent with the priors from our previous analyses.

## 1. Demand Models

### 1.1 Independent Isoelastic Demand Model

Our previous analysis assumed that state and burst resources have **independent demand curves**:

$$S(p) = A_s \cdot p^{-\varepsilon_s}$$

$$B(p) = A_b \cdot p^{-\varepsilon_b}$$

where:

- $S(p)$ and $B(p)$ are the gas used for each resource at price $p$
- $A_s$ and $A_b$ are demand scale parameters
- $\varepsilon_s$ and $\varepsilon_b$ are price elasticities for each resource

In this model, state and burst demands vary independently. When the price changes, each resource responds according to its own elasticity, and the total gas used is simply $G^{\text{total}} = S(p) + B(p)$. The model assumes that state and burst resources are neither substitutes nor complements.

### 1.2 Capacity-Constrained Demand Model

The capacity-constrained model assumes users have an **aggregate demand for block space** that gets allocated between state and burst resources:

$$G^{\text{total}}(p) = A \cdot p^{-\varepsilon_{\text{agg}}}$$

$$\alpha_s(mp) = \frac{1}{1 + \kappa \cdot (mp)^\eta}$$

where:

- $G^{\text{total}}(p)$ is total gas demanded at price $p$
- $\alpha_s(mp)$ is the share allocated to state creation at repricing multiplier $m$ and price $p$
- $\varepsilon_{\text{agg}}$ is the aggregate price elasticity
- $\eta$ is the share elasticity (sensitivity to relative prices)
- $\kappa$ is the share ratio parameter

The gas used by each resource is then obtained from the total gas used and share of gas used for state creation:

$$S = \alpha_s(mp) \cdot G^{\text{total}}(p)$$

$$B = (1 - \alpha_s(mp)) \cdot G^{\text{total}}(p)$$

This model assumes that state and burst are **substitutes** competing for fixed aggregate capacity. When prices change, both aggregate demand and the allocation between resources adjust.

### 1.3 Why Capacity-Constrained?

Looking at the past year of data, a capacity-constrained model better matches the observed behavior:

1. **High negative correlation**: State gas and burst gas have correlation ≈ -0.99, indicating strong substitution.
2. **Stable block utilization**: After gas limit increases, utilization quickly returns to ~50%.
3. **Proportional scaling**: When capacity increases, total usage scales proportionally — not according to independent elasticities.
4. **Share responds to prices**: The state share decreases when state becomes relatively more expensive. The share of gas used for state creation and the base fee have a negative correlation (-0.21).

In the following sections, we use this model to empirically estimate the aggregate demand elasticity and the state share elasticity, and then recover the structural elasticities $\varepsilon_s$ and $\varepsilon_b$.

## 2. Data and Preprocessing

Our analysis uses daily Ethereum mainnet data spanning from January 1, 2025 to January 31, 2026. The dataset includes block-level metrics (gas used, gas limit, base fee) and state growth metrics (storage slots created, accounts created, code size). All blockchain data was extracted from [Xatu's dataset](https://ethpandaops.io/data/xatu/).

Raw block-level data was aggregated to daily observations. We estimated the gas used for state creation by multiplying the net bytes added to state by account, storage slots, and contract code by their respective gas costs (25,000 gas per 112-byte account, 20,000 gas per 32-byte slot, and 200 gas per byte of contract code). The gas used for burst resources was computed as the residual.

We used ARDL (Autoregressive Distributed Lag) models on log-differenced variables to ensure stationarity and heteroskedasticity-robust standard errors to account for structural breaks.

## 3. Aggregate Demand Elasticity

### 3.1 Evidence from Daily Changes

Using daily data from January 2025 to January 2026, we estimated an **ARDL (Autoregressive Distributed Lag) model** to measure how total gas usage responds to base fee changes:

$$\Delta \ln(G^{\text{total}}_t) = \beta_0 + \sum_i \phi_i \Delta \ln(G^{\text{total}}_{t-i}) + \sum_j \beta_j \Delta \ln(p_{t-j}) + \varepsilon_t$$

The model accounts for both immediate (contemporaneous) and lagged effects of price changes on gas usage. The ARDL framework allows us to distinguish between two types of elasticities:

- **Cumulative aggregate elasticity**: The sum of all coefficients on the contemporaneous and lagged price terms ($\sum_j \beta_j$). It captures the total immediate effect of a price change, accumulating the impact from the current period and all lagged periods included in the model. This represents the short-run response before any feedback through the autoregressive terms.

- **Long-run aggregate elasticity**: Adjusts the cumulative elasticity for the autoregressive dynamics by dividing by $(1 - \sum_i \phi_i)$, where $\phi_i$ are the coefficients on lagged dependent variables. It represents the steady-state response after all dynamic adjustments have occurred, including feedback effects where current gas usage influences future gas usage. This captures the full equilibrium effect of a sustained price change.

**Key results:**

- **Cumulative aggregate elasticity**: $\varepsilon_\text{agg}$ = 0.0049 (95% CI: [0.0008, 0.0090])
- **Long-run aggregate elasticity**: $\varepsilon_\text{agg}$ = 0.0066
- **Statistical significance**: The underlying regression coefficient on log(price) has t = -2.35, p = 0.0195 (negative because higher prices reduce gas usage; $\varepsilon_\text{agg}$ is reported as the absolute value)
- **Model diagnostics**: No evidence of residual autocorrelation (Ljung-Box p = 0.98)

**Interpretation**: A 1% increase in the base fee is associated with a 0.007% decrease in total gas usage in the long run, indicating **highly inelastic aggregate demand**.

### 3.2 Evidence from Gas Limit Increase Events

The daily ARDL estimates suggest highly inelastic aggregate demand. However, this captures marginal day-to-day responses. But, we also want to measure how demand responds to large structural capacity shifts. During gas limit increases, the base fee decreases to a new equilibrium value, which may induce a different elasticity.

To this end, we analyzed the three major gas limit increases during 2025:

1. **February 4, 2025**: 30M → 36M (+20%)
2. **July 21, 2025**: 36M → 45M (+25%)
3. **November 25, 2025**: 45M → 60M (+33%)

Using the equilibrium condition $G^{\text{total}}(p) = A \cdot p^{-\varepsilon}$ and the fact that utilization remained at 50%, we can derive the implied elasticity:

$$\varepsilon = -\frac{\ln(1 + \Delta_{\text{limit}})}{\ln(1 + \Delta_{\text{basefee}})}$$

We used the median values of the base fee for each gas limit interval.

**Results:**

| Event | Gas Limit Change | Base Fee Change | Implied $\varepsilon_\text{agg}$ |
|-------|-----------------|----------------|---------------|
| 30M → 36M | +20% | -85.6% | 0.094 |
| 36M → 45M | +25% | -55.3% | 0.277 |
| 45M → 60M | +33% | -84.5% | 0.154 |
| **Mean** | - | - | **0.175 ± 0.093** |

**Interpretation**: The event-based elasticity (0.175) is substantially higher than the daily elasticity (0.007), suggesting that the equilibrium response to large capacity shifts is more elastic than the marginal daily response. That said, it is still low, confirming that aggregate demand is relatively inelastic. When capacity increases, **demand expands to fill it**, with base fees adjusting to maintain target utilization.

## 4. State Share Elasticity

### 4.1 Evidence from Daily Changes

As with the aggregate demand model, we used daily data from January 2025 to January 2026 to fit an **ARDL model**. Here, we estimated how the **share of gas devoted to state** responds to base fee changes, using the log-odds formulation:

$$\ln\left(\frac{\alpha_s}{1 - \alpha_s}\right) = \ln(\kappa^{-1}) - \eta \cdot \ln(p)$$

**Key results:**

- **Cumulative share elasticity**: η = 0.9687 (95% CI: [0.6413, 1.2961])
- **Long-run share elasticity**: η = 0.4295
- **Statistical significance**: The underlying regression coefficient on log(price) has t = -5.82, p < 0.001 (negative because higher prices shift the log-odds toward burst; η is reported as the absolute value)
- **Model has residual autocorrelation** (may be due to gas limit increase structural breaks)

**Interpretation**: The state share has moderate elasticity (η ≈ 0.43). When the base fee increases by 1%, the odds of choosing state over burst decrease by approximately 0.43%. This confirms that **users substitute between state and burst based on prices**.

### 4.2 Evidence from Gas Limit Increase Events

To measure how the state share responds to large shocks, we also computed the implied share elasticity from the three gas limit increase events by comparing the state share odds before and after each event:

$$\eta = -\frac{\Delta \ln(\frac{\alpha_s}{1 - \alpha_s})}{\Delta \ln(p)}$$

We used the median values of the base fee and the state share odds for each gas limit interval.

**Results:**

| Event | Gas Limit Change | Base Fee Change | Odds Change | Implied η |
|-------|-----------------|----------------|-------------|-----------|
| 30M → 36M | +20% | -85.6% | +37.9% | 0.166 |
| 36M → 45M | +25% | -55.3% | -20.3% | -0.282 |
| 45M → 60M | +33% | -84.5% | +38.2% | 0.174 |
| **Mean** | - | - | - | **0.019 ± 0.261** |

**Interpretation**: The event-based estimates have high variance. For the 36M→45M interval, the negative implied η means the state share odds moved in the **same direction** as price (both decreased), which is opposite to the substitution pattern predicted by the other estimates. When the base fee fell by 55%, users allocated *less* to state rather than more, contradicting the positive η found in daily data. This anomalous event highlights the uncertainty around how users respond to large price shocks and suggests that factors beyond simple price substitution (e.g., shifts in application mix or behavioral changes) may dominate during certain periods.

## 5. Recovering Structural Elasticities ($\varepsilon_s$, $\varepsilon_b$)

The capacity-constrained model estimates two reduced-form parameters: the aggregate elasticity $\varepsilon_{\text{agg}}$ and the share elasticity $\eta$. In this section, we show how to recover the structural elasticities $\varepsilon_s$ and $\varepsilon_b$ from the independent isoelastic demand model used in our [previous analysis](https://ethresear.ch/t/analysis-of-different-aggregation-functions-for-eip-8037-under-different-elasticity-regimes/24033).

### 5.1 Derivation

Recall the independent isoelastic demand model:

$$S^*(p) = A_s \cdot p^{-\varepsilon_s}, \qquad B^*(p) = A_b \cdot p^{-\varepsilon_b}$$

where $S^*$ and $B^*$ are the latent (unconstrained) demands for state and burst resources. Define the total latent demand $D^*(p) = S^*(p) + B^*(p)$ and the state share $q = S^*/D^*$.

**Aggregate elasticity as a share-weighted average.** The aggregate elasticity is defined as:

$$\varepsilon_{\text{agg}} = -\frac{d \ln D^*}{d \ln p}$$

By the chain rule, $\frac{d \ln D^*}{d \ln p} = \frac{1}{D^*}\frac{d D^*}{d \ln p}$. Differentiating $D^* = S^* + B^*$ with respect to $\ln p$:

$$\frac{d \ln D^*}{d \ln p} = \frac{1}{D^*}\left(\frac{d S^*}{d \ln p} + \frac{d B^*}{d \ln p}\right) = \frac{-\varepsilon_s \cdot S^* - \varepsilon_b \cdot B^*}{D^*}$$

Therefore:

$$\varepsilon_{\text{agg}} = \varepsilon_s \cdot \frac{S^*}{D^*} + \varepsilon_b \cdot \frac{B^*}{D^*} = \varepsilon_s \cdot q + \varepsilon_b \cdot (1 - q) \tag{1}$$

That is, the aggregate elasticity is the share-weighted average of the two structural elasticities.

**Share elasticity as a difference.** Taking the log-odds of the state share:

$$\ln\left(\frac{q}{1-q}\right) = \ln\left(\frac{S^*}{B^*}\right) = \ln\left(\frac{A_s}{A_b}\right) - (\varepsilon_s - \varepsilon_b) \cdot \ln p$$

The slope with respect to $\ln p$ is $-(\varepsilon_s - \varepsilon_b)$, which matches the definition of the share elasticity $\eta$ from the capacity-constrained model:

$$\eta = \varepsilon_s - \varepsilon_b \tag{2}$$

### 5.2 Recovery Formulas

Solving the system of equations (1) and (2) for $\varepsilon_s$ and $\varepsilon_b$:

From (2): $\varepsilon_s = \varepsilon_b + \eta$. Substituting into (1):

$$\varepsilon_{\text{agg}} = (\varepsilon_b + \eta) \cdot q + \varepsilon_b \cdot (1 - q) = \varepsilon_b + q \cdot \eta$$

Therefore:

$$\boxed{\varepsilon_b = \varepsilon_{\text{agg}} - q_0 \cdot \eta}$$

$$\boxed{\varepsilon_s = \varepsilon_{\text{agg}} + (1 - q_0) \cdot \eta}$$

where $q_0$ is the baseline state share (≈ 0.23 from our data).

### 5.3 Numerical Estimates

Using $q_0 = 0.23$ and combining our estimates from the previous sections:

| Scenario | $\varepsilon_{\text{agg}}$ | $\eta$ | $\varepsilon_s$ | $\varepsilon_b$ |
| -------- | ------------------------- | ------ | --------------- | --------------- |
| Event $\varepsilon_\text{agg}$ + long-run η | 0.175 | 0.43 | 0.51 | 0.08 |
| Event $\varepsilon_\text{agg}$ + cumulative η | 0.175 | 0.97 | 0.92 | -0.05 |
| Low $\varepsilon_\text{agg}$ + long-run η | 0.10 | 0.43 | 0.43 | 0.00 |
| High $\varepsilon_\text{agg}$ + long-run η | 0.28 | 0.43 | 0.61 | 0.18 |
| Event $\varepsilon_\text{agg}$ + Event η | 0.175 | 0.17 | 0.31 | 0.14 |

 The cumulative $\eta = 0.97$ pushes $\varepsilon_b$ slightly negative, which is implausible — it would imply that burst demand increases with price. The long-run $\eta \approx 0.43$ yields more plausible results across the range of aggregate elasticity estimates.

Note that the central estimates use the **event-based** $\varepsilon_{\text{agg}} \approx 0.10$–$0.28$, not the daily long-run estimate of 0.007. The daily ARDL elasticity captures marginal day-to-day noise responses, while the event-based estimate captures the equilibrium demand response to large structural capacity shifts — which is the more relevant quantity for evaluating repricing scenarios under EIP-8037.

## 6. Next Steps

Our central result is that **state demand is moderately price-elastic ($\varepsilon_s \approx 0.3$–$0.6$) while burst demand is nearly inelastic ($\varepsilon_b \approx 0.0$–$0.2$)**. This has direct implications for the design of EIP-8037.

In a follow-up analysis, we will use the empirical $(\varepsilon_s, \varepsilon_b)$ ranges to evaluate specific aggregation function and repricing multiplier combinations, replacing the full elasticity grid sweep with a focused analysis around the empirically relevant regime. This should give a more accurate picture of which aggregation function and repricing multiplier we should target.
