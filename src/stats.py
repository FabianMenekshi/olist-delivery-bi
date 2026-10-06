"""Wilson 95% intervals for interpreting rates with small denominators."""
from math import sqrt


def wilson_interval(successes, trials, z=1.959963984540054):
    """Return proportion bounds, or (None, None) when no trials exist."""
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError('Require 0 <= successes <= trials')
    if trials == 0:
        return None, None
    proportion = successes / trials
    denominator = 1 + z * z / trials
    center = (proportion + z * z / (2 * trials)) / denominator
    half_width = z * sqrt(
        proportion * (1 - proportion) / trials + z * z / (4 * trials * trials)
    ) / denominator
    return max(0.0, center - half_width), min(1.0, center + half_width)


def add_intervals(frame, numerator='late_orders', denominator='eligible_orders'):
    """Return a copy with ci_low and ci_high; keep input counts unchanged."""
    result = frame.copy()
    intervals = [
        wilson_interval(int(successes), int(trials))
        for successes, trials in zip(result[numerator], result[denominator])
    ]
    result['ci_low'] = [low for low, _ in intervals]
    result['ci_high'] = [high for _, high in intervals]
    return result
