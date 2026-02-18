from scipy.optimize import brentq


def equilibrium_equation_sum(
    r: float, m: float, n: float, eps_s: float, eps_b: float, state_share_0: float
) -> float:
    """
    Equilibrium condition for sum aggregation:
    state_share_0*m^(1-eps_s)*r^(-eps_s) + (1-state_share_0)*r^(-eps_b) = n
    """
    return (
        state_share_0 * (m ** (1 - eps_s)) * (r ** (-eps_s))
        + (1 - state_share_0) * (r ** (-eps_b))
        - n
    )


def find_equilibrium_base_fee_sum(
    m: float, n: float, eps_s: float, eps_b: float, b_0: float, state_share_0: float
) -> float:
    """
    Find equilibrium base fee b* for the sum aggregation function using
    Brent's method on interval [0.005, 1.0]
    """

    def eq(r):
        return equilibrium_equation_sum(r, m, n, eps_s, eps_b, state_share_0)

    # Check that function has opposite signs at endpoints
    f_low = eq(0.005)
    f_high = eq(1.0)
    if f_low * f_high < 0:  # opposite signs = root exists
        r_star = brentq(eq, 0.005, 1.0, xtol=1e-8)
        return b_0 * r_star
    else:
        print(
            f"Warning: No valid root found for m={m}, eps_s={eps_s}, eps_b={eps_b}, n={n}"
        )
        return 0.0


def find_equilibrium_base_fee_max(
    m: float, n: float, eps_s: float, eps_b: float, b_0: float, state_share_0: float
) -> float:
    """
    Find equilibrium base fee b* for the max aggregation function using
    a closed-form solution.
    """
    # Compute candidate equilibria
    # Candidate 1: State-limited equilibrium
    # state_share_0 * m^(1-eps_s) * r^(-eps_s) = n
    # Solving: r_state = (state_share_0 * m^(1-eps_s) / n)^(1/eps_s)
    try:
        r_state = ((state_share_0 * (m ** (1 - eps_s))) / n) ** (1 / eps_s)
    except (OverflowError, ZeroDivisionError) as e:
        print(
            f"Warning: No valid solution for r_state found for m={m}, eps_s={eps_s}, eps_b={eps_b}, n={n}"
        )
        r_state = 0.0
    # Candidate 2: Burst-limited equilibrium
    # (1-state_share_0) * r^(-eps_b) = n
    # Solving: r_burst = ((1-state_share_0) / n)^(1/eps_b)
    try:
        r_burst = ((1 - state_share_0) / n) ** (1 / eps_b)
    except (OverflowError, ZeroDivisionError) as e:
        print(
            f"Warning: No valid solution for r_burst found for m={m}, eps_s={eps_s}, eps_b={eps_b}, n={n}"
        )
        r_burst = 0.0
    # The equilibrium is the maximum of the two candidates
    # Intuition: whichever resource requires a higher base fee to reach
    # the target will be the limiting resource
    r_star = max(r_state, r_burst)
    b_star = b_0 * r_star
    return b_star


def find_equilibrium_base_fee_burst(
    m: float, n: float, eps_s: float, eps_b: float, b_0: float, state_share_0: float
) -> float:
    """
    Find equilibrium base fee b* for the burst function using
    a closed-form solution.
    """
    # Burst-limited equilibrium
    # (1-state_share_0) * r^(-eps_b) = n
    # Solving: r_burst = ((1-state_share_0) / n)^(1/eps_b)
    try:
        r_star = ((1 - state_share_0) / n) ** (1 / eps_b)
    except (OverflowError, ZeroDivisionError) as e:
        print(
            f"Warning: No valid solution for r_burst found for m={m}, eps_s={eps_s}, eps_b={eps_b}, n={n}"
        )
        r_star = 0.0
    # The equilibrium is the maximum of the two candidates
    # Intuition: whichever resource requires a higher base fee to reach
    # the target will be the limiting resource
    b_star = b_0 * r_star
    return b_star


def find_equilibrium_base_fee_asymmetric_max(
    m: float,
    n: float,
    eps_s: float,
    eps_b: float,
    b_0: float,
    state_share_0: float,
    w_s: float = 1.0,
    w_r: float = 1.0,
) -> float:
    """
    Find equilibrium base fee b* for the asymmetric max aggregation function
    using a closed-form solution.

    Equilibrium condition:
        max(w_s * state_share_0 * m^(1-eps_s) * r^(-eps_s),
            w_r * (1-state_share_0) * r^(-eps_b)) = n
    """
    # Candidate 1: State-limited equilibrium
    # w_s * state_share_0 * m^(1-eps_s) * r^(-eps_s) = n
    # r_state = (w_s * state_share_0 * m^(1-eps_s) / n)^(1/eps_s)
    try:
        r_state = ((w_s * state_share_0 * (m ** (1 - eps_s))) / n) ** (1 / eps_s)
    except (OverflowError, ZeroDivisionError):
        print(
            f"Warning: No valid solution for r_state found for m={m}, eps_s={eps_s}, eps_b={eps_b}, n={n}"
        )
        r_state = 0.0
    # Candidate 2: Burst-limited equilibrium
    # w_r * (1-state_share_0) * r^(-eps_b) = n
    # r_burst = (w_r * (1-state_share_0) / n)^(1/eps_b)
    try:
        r_burst = ((w_r * (1 - state_share_0)) / n) ** (1 / eps_b)
    except (OverflowError, ZeroDivisionError):
        print(
            f"Warning: No valid solution for r_burst found for m={m}, eps_s={eps_s}, eps_b={eps_b}, n={n}"
        )
        r_burst = 0.0
    r_star = max(r_state, r_burst)
    return b_0 * r_star


def equilibrium_equation_asymmetric_euclidean(
    r: float,
    m: float,
    n: float,
    eps_s: float,
    eps_b: float,
    state_share_0: float,
    w_s: float = 1.0,
    w_r: float = 1.0,
) -> float:
    """
    Equilibrium condition for asymmetric Euclidean aggregation:
    sqrt((w_s * state_share_0 * m^(1-eps_s) * r^(-eps_s))^2
       + (w_r * (1-state_share_0) * r^(-eps_b))^2) = n
    """
    term_s = w_s * state_share_0 * (m ** (1 - eps_s)) * (r ** (-eps_s))
    term_b = w_r * (1 - state_share_0) * (r ** (-eps_b))
    return (term_s**2 + term_b**2) ** 0.5 - n


def find_equilibrium_base_fee_asymmetric_euclidean(
    m: float,
    n: float,
    eps_s: float,
    eps_b: float,
    b_0: float,
    state_share_0: float,
    w_s: float = 1.0,
    w_r: float = 1.0,
) -> float:
    """
    Find equilibrium base fee b* for the asymmetric Euclidean aggregation
    function using Brent's method on interval [0.005, 1.0].

    Equilibrium condition:
        sqrt((w_s * state_gas)^2 + (w_r * regular_gas)^2) = n
    """

    def eq(r):
        return equilibrium_equation_asymmetric_euclidean(
            r, m, n, eps_s, eps_b, state_share_0, w_s, w_r
        )

    f_low = eq(0.005)
    f_high = eq(1.0)
    if f_low * f_high < 0:
        r_star = brentq(eq, 0.005, 1.0, xtol=1e-8)
        return b_0 * r_star
    else:
        print(
            f"Warning: No valid root found for asymmetric_euclidean m={m}, eps_s={eps_s}, eps_b={eps_b}, n={n}"
        )
        return 0.0


def compute_equilibrium_stats(b_star, m, n, eps_s, eps_b, G_0, b_0, S_0, state_share_0):
    """
    Compute equilibrium statistics given a base fee b* and parameters.
    """
    # Initial gas prices
    g_state_0 = 0.5 * state_share_0 * G_0 / S_0
    g_burst_0 = G_0 / 2
    # Compute base fee multiplier
    r_star = b_star / b_0
    if r_star == 0:
        return {
            "b_star": b_star,
            "r_star": r_star,
            "A_s": None,
            "A_b": None,
            "S_star": None,
            "B_star": None,
            "gas_used_state": None,
            "gas_used_burst": None,
            "gas_used_total": None,
            "share_state": None,
            "share_burst": None,
            "annual_state_growth_gib": None,
            "limiting_resource": None,
        }
    else:
        # Calibrate demand amplitudes from initial conditions
        A_s = (0.5 * state_share_0 * G_0 / g_state_0) * ((b_0 * g_state_0) ** eps_s)
        A_b = (0.5 * (1 - state_share_0) * G_0 / g_burst_0) * (
            (b_0 * g_burst_0) ** eps_b
        )

        # Compute equilibrium demands using isoelastic forms
        # S(p) = A_s * p^(-eps_s), where p = b_star * m * g_state_0
        p_state = b_star * m * g_state_0
        S_star = A_s * (p_state ** (-eps_s))
        # B(p) = A_b * p^(-eps_b), where p = b_star * g_burst_0
        p_burst = b_star * g_burst_0
        B_star = A_b * (p_burst ** (-eps_b))

        # Compute gas usage per resource type
        gas_used_state = min(m * g_state_0 * S_star, n * G_0)
        gas_used_burst = min(g_burst_0 * B_star, n * G_0)
        gas_used_total = gas_used_state + gas_used_burst

        # Compute resource shares relative to the target (0.5 * n * G_0)
        # Note: these do NOT necessarily sum to 1.0 under max-based equilibrium
        target = 0.5 * n * G_0
        share_state = gas_used_state / target
        share_burst = gas_used_burst / target

        # Determine which resource is limiting
        if share_state >= share_burst:
            limiting_resource = "state"
        else:
            limiting_resource = "burst"

        # Compute annual state growth
        # 2,628,000 blocks per year (12-second blocks)
        # Convert bytes to GiB: 1 GiB = 2^30 bytes ≈ 1.073741824e9 bytes
        # Conversion factor: 1 byte = 9.313225746154785e-10 GiB
        blocks_per_year = 2_628_000
        bytes_to_gib = 9.313225746154785e-10
        annual_state_growth_gib = (
            blocks_per_year * (gas_used_state / (m * g_state_0)) * bytes_to_gib
        )

        return {
            "b_star": b_star,
            "r_star": r_star,
            "A_s": A_s,
            "A_b": A_b,
            "S_star": S_star,
            "burst_throughput_s": B_star,
            "gas_used_state": gas_used_state,
            "gas_used_burst": gas_used_burst,
            "gas_used_total": gas_used_total,
            "share_state": share_state,
            "share_burst": share_burst,
            "annual_state_growth_gib": annual_state_growth_gib,
            "limiting_resource": limiting_resource,
        }
