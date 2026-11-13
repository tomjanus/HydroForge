""" """

from math import log2


def nearest_power_of_2(
    value: float,
    *,
    mode: str = "nearest",
) -> int:
    """Return the power of 2 nearest to ``value``.

    Parameters
    ----------
    value
        Input number. Must be positive.
    mode
        How to select the power of 2:

        - ``"nearest"``: nearest power of 2.
        - ``"lower"``: largest power of 2 not exceeding ``value``.
        - ``"upper"``: smallest power of 2 greater than or equal to ``value``.

    Returns
    -------
    int
        The selected power of 2.

    Raises
    ------
    ValueError
        If ``value`` is not positive or ``mode`` is invalid.
    """
    if value <= 0:
        raise ValueError("value must be positive")

    if mode == "lower":
        return 2 ** int(log2(value))

    if mode == "upper":
        return 2 ** int(log2(value) + 0.999999999999)

    if mode == "nearest":
        lower = 2 ** int(log2(value))
        upper = lower * 2
        return lower if value - lower <= upper - value else upper

    raise ValueError("mode must be 'nearest', 'lower', or 'upper'")
