#!/usr/bin/env python3
"""Pure-Python significance tests for paired score deltas (no numpy/scipy).

We test, per dimension, whether mutating one input dimension shifts the per-sample rubric
score. The unit of analysis is the SAMPLE: each sample contributes one delta
    d_i = mean_over_runs(mutated score_i) - mean_over_runs(original score_i)
and we ask whether the mean of {d_i} differs from 0. Three tests are provided:

  paired_t   - paired t-test (primary). Two-sided Student-t p-value via the regularized
               incomplete beta function (Numerical-Recipes continued fraction + math.lgamma).
  sign_flip  - paired permutation test (robustness). Monte-Carlo sign flips of each d_i; the
               p-value makes no distributional assumption.
  wilcoxon   - Wilcoxon signed-rank test (robustness). Normal approximation via math.erf, with
               average-rank tie handling and a continuity correction.

scipy/numpy are not installed in the pipeline Python, so these are implemented from scratch.
For the clean paired case the paired_t p-value matches scipy.stats.ttest_rel to ~1e-12.
"""
import math
import random
import statistics


# --- Student-t two-sided p-value (regularized incomplete beta) ----------------
def _betacf(a, b, x, itmax=300, eps=3e-12, fpmin=1e-300):
    """Continued fraction for the incomplete beta function (Numerical Recipes betacf)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betai(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t, df):
    """Two-sided p-value for a Student-t statistic with df degrees of freedom."""
    if df <= 0:
        return float("nan")
    if t == 0:
        return 1.0
    x = df / (df + t * t)
    return betai(df / 2.0, 0.5, x)


def normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# --- the three paired tests ---------------------------------------------------
def paired_t(d):
    """Paired (one-sample) t-test on the deltas d. Returns dict with t, df, p, mean, sd, dz."""
    n = len(d)
    if n < 2:
        return {"n": n, "t": None, "df": max(n - 1, 0), "p": None,
                "mean": (d[0] if n else None), "sd": None, "dz": None}
    mean = statistics.fmean(d)
    sd = statistics.stdev(d)  # sample SD (ddof=1)
    df = n - 1
    if sd == 0:
        # No variance: p=1 if there is also no effect, else a vanishing p (infinite t).
        return {"n": n, "t": (0.0 if mean == 0 else math.inf), "df": df,
                "p": (1.0 if mean == 0 else 0.0), "mean": mean, "sd": 0.0,
                "dz": (0.0 if mean == 0 else math.inf)}
    se = sd / math.sqrt(n)
    t = mean / se
    return {"n": n, "t": t, "df": df, "p": t_two_sided_p(t, df),
            "mean": mean, "sd": sd, "dz": mean / sd}


def sign_flip_p(d, R=100000, seed=20260626):
    """Two-sided paired permutation (sign-flip) test on the deltas d.

    Statistic = sum(d). Under H0 each d_i is equally likely +/- its observed value, so we flip
    signs at random R times and count how often |sum| >= |observed|. p = (1 + count)/(1 + R)."""
    n = len(d)
    if n == 0:
        return {"R": R, "p": None}
    obs = abs(sum(d))
    eps = 1e-12
    rng = random.Random(f"{seed}:perm")
    count = 0
    for _ in range(R):
        s = 0.0
        for v in d:
            s += v if rng.random() < 0.5 else -v
        if abs(s) >= obs - eps:
            count += 1
    return {"R": R, "p": (1 + count) / (1 + R)}


def wilcoxon_p(d):
    """Wilcoxon signed-rank test on the deltas d (normal approximation). Returns W+, z, p, n.

    Zeros are dropped; |d| ties get average ranks (with the standard tie correction to the
    variance) and a continuity correction is applied. The normal approximation is adequate for
    n>=~10; for very small n treat the p-value as indicative only."""
    nz = [v for v in d if v != 0]
    n = len(nz)
    if n == 0:
        return {"n": 0, "W_plus": None, "z": None, "p": None}
    order = sorted(range(n), key=lambda i: abs(nz[i]))
    ranks = [0.0] * n
    i = 0
    tie_term = 0.0
    while i < n:
        j = i
        while j + 1 < n and abs(nz[order[j + 1]]) == abs(nz[order[i]]):
            j += 1
        avg = (i + 1 + j + 1) / 2.0  # average of 1-based ranks i+1..j+1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        t = j - i + 1
        tie_term += t ** 3 - t
        i = j + 1
    w_plus = sum(ranks[i] for i in range(n) if nz[i] > 0)
    mu = n * (n + 1) / 4.0
    var = n * (n + 1) * (2 * n + 1) / 24.0 - tie_term / 48.0
    if var <= 0:
        return {"n": n, "W_plus": w_plus, "z": None, "p": (1.0 if w_plus == mu else 0.0)}
    # continuity correction toward the mean
    diff = w_plus - mu
    cc = 0.5 if diff > 0 else (-0.5 if diff < 0 else 0.0)
    z = (diff - cc) / math.sqrt(var)
    p = 2.0 * (1.0 - normal_cdf(abs(z)))
    return {"n": n, "W_plus": w_plus, "z": z, "p": min(1.0, p)}


def summarize(d, perm_R=100000, seed=20260626):
    """Run all three tests on the paired deltas d and return a combined dict."""
    return {
        "n": len(d),
        "ttest": paired_t(d),
        "perm": sign_flip_p(d, R=perm_R, seed=seed),
        "wilcoxon": wilcoxon_p(d),
    }


if __name__ == "__main__":
    # Self-check against a known case (compare to scipy offline): a small positive shift.
    sample = [0.10, -0.02, 0.05, 0.08, 0.00, 0.12, -0.01, 0.06, 0.09, 0.03]
    res = summarize(sample, perm_R=20000)
    print("ttest:", res["ttest"])
    print("perm :", res["perm"])
    print("wilco:", res["wilcoxon"])
