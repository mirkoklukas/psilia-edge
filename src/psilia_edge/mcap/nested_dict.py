# # # # # # # # # # # # # # # # # # # # # # # #
#
#   Super simple nested dict functionality,
#   inpired by JAX's Pytree objects
#
# # # # # # # # # # # # # # # # # # # # # # # #
def flatten(d: dict, addresses: list[list] | None = None) -> tuple[list, list[list]]:
    """Return all leaf values and their addresses (key paths) separately.

    Example::
        >>> flatten({"a": 1, "b": {"c": 2, "d": 3}})
        ([1, 2, 3], [['a'], ['b', 'c'], ['b', 'd']])
    """
    if addresses is not None:
        return extract(d, addresses), addresses

    values = []
    addresses = []
    for key, value in d.items():
        address = [key]
        if isinstance(value, dict):
            sub_values, sub_addresses = flatten(value)
            values.extend(sub_values)
            addresses.extend([key, *sa] for sa in sub_addresses)
        else:
            values.append(value)
            addresses.append(address)
    return values, addresses


def unflatten(values: list, addresses: list[list]) -> dict:
    """Inverse of flatten: build a nested dict from values and addresses.

    Example::
        >>> unflatten([1, 2, 3], [["a"], ["b", "c"], ["b", "d"]])
        {'a': 1, 'b': {'c': 2, 'd': 3}}
    """
    result = {}
    for value, address in zip(values, addresses):
        d = result
        for key in address[:-1]:
            d = d.setdefault(key, {})
        d[address[-1]] = value
    return result


def extract(d: dict, addresses: list[list]) -> list:
    """Extract values from a nested dict at the given addresses.

    Example::
        >>> extract({"a": 1, "b": {"c": 2, "d": {"e": 3}}}, [["a"], ["b", "d"]])
        [1, {'e': 3}]
    """
    values = []
    for address in addresses:
        v = d
        for key in address:
            v = v[key]
        values.append(v)
    return values


def stack_leaves(rows: list[list]) -> list[list]:
    """Transpose a list of rows into a list of columns.

    Example::
        >>> stack_leaves([[1, 2, 3], [4, 5, 6]])
        [[1, 4], [2, 5], [3, 6]]
    """
    return [list(col) for col in zip(*rows)]


# TODO: As in jax we might actually want to decompose the dict into the
#   tree part that can be flattened and additional information, meta data sort of.
#   I guess it is two types of addresses in our case of nested dictionaries,
#   stackable addresses with variable information (e.g. position, timestamp),
#   and metadata (e.g. the topic name or so)
