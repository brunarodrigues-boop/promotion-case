"""Significance tests for the comparative claims on the page.

Pure standard library. The page has no dependencies and no network, and a
promotion case that needs SciPy installed to rebuild is one nobody will
rebuild.

Three tests, chosen to match what each claim actually is:

  sign_test        the same children measured twice. Whether more improved
                   than declined is a question about pairs, not about pooled
                   rates, and the pairing is the whole point of matching the
                   roster across two windows.
  two_prop         two independent rates, e.g. one subject's accuracy in two
                   windows.
  wilson           a confidence interval for a single rate, which is the
                   honest way to show a figure that rests on few answers.

A warning this module exists to make possible: over millions of questions a
two-proportion test calls a 0.1-point difference significant. That is a true
statement about sampling error and a false one about children. Where n is in
the millions, cite the interval and say the difference is too small to mean
anything -- see `too_precise_to_matter`.
"""
from __future__ import annotations

import math

__all__ = ["sign_test", "two_prop", "wilson", "fmt_p", "too_precise_to_matter"]


def _log_comb(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def sign_test(up: int, down: int) -> dict:
    """Two-sided exact binomial test on up vs down, ties excluded.

    Ties are dropped rather than split, which is the conventional sign test:
    a child whose accuracy did not move carries no information about the
    direction of the effect.
    """
    n = up + down
    if n == 0:
        return {"n": 0, "up": up, "down": down, "p": 1.0}
    # Exact two-sided: sum the probabilities of every outcome no more likely
    # than the observed one.
    obs = _log_comb(n, up)
    tot = 0.0
    for k in range(n + 1):
        lp = _log_comb(n, k)
        if lp <= obs + 1e-12:
            tot += math.exp(lp - n * math.log(2))
    return {"n": n, "up": up, "down": down, "p": min(1.0, tot)}


def _norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def two_prop(x1: int, n1: int, x2: int, n2: int) -> dict:
    """Two-sided z test for two independent proportions."""
    if not n1 or not n2:
        return {"p": 1.0, "z": 0.0, "n": n1 + n2, "diff": 0.0}
    p1, p2 = x1 / n1, x2 / n2
    pool = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return {"p": 1.0, "z": 0.0, "n": n1 + n2, "diff": p2 - p1}
    z = (p2 - p1) / se
    return {"p": 2 * _norm_sf(abs(z)), "z": z, "n": n1 + n2, "diff": p2 - p1}


def wilson(k: int, n: int, z: float = 1.96) -> dict:
    """Wilson score interval. Behaves at the ends, unlike the normal formula,
    which is the whole reason to use it on a rate built from few answers."""
    if not n:
        return {"lo": 0.0, "hi": 0.0, "p": 0.0, "n": 0}
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"lo": max(0.0, centre - half), "hi": min(1.0, centre + half),
            "p": p, "n": n}


def fmt_p(p: float) -> str:
    """A p value as it should be written, not rounded into a lie.

    Anything under 0.001 is reported as such rather than as 0.000, and
    anything at or above 0.05 says so in words: a reader who skips the number
    should not have to work out which side of the line it fell.
    """
    if p < 0.001:
        return "p &lt; 0.001"
    if p >= 0.05:
        return f"p = {p:.2f}, not significant"
    return f"p = {p:.3f}".rstrip("0").rstrip(".")


def too_precise_to_matter(n: int, diff_points: float,
                          threshold_n: int = 100_000,
                          threshold_pts: float = 0.5) -> bool:
    """True when n is so large that significance stops meaning importance.

    Guards against the worst thing this module could be used for: dressing a
    0.1-point move across four million questions as a finding because the
    arithmetic says p is small.
    """
    return n >= threshold_n and abs(diff_points) < threshold_pts
