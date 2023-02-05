def clamp(
    value: int | float, lower: int | float | None, upper: int | float | None
) -> int | float:  # FIXME fix types...
    if lower is not None:
        value = max(value, lower)
    if upper is not None:
        value = min(value, upper)
    return value


def chunk(elems, n):
    for i in range(0, len(elems), n):
        yield elems[i : i + n]
