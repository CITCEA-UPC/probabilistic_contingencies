"""Catàleg de desconnexions N−1/N−2 úniques, sense modificar cap xarxa."""
from itertools import combinations


def iter_contingencies(n_lines, n_generators, n_transformers):
    """N−1 primer, després N−2 sense ordre; retorna (línies, generadors, trafos, nivell)."""
    counts=(n_lines,n_generators,n_transformers)
    if any(type(n) is not int or n<0 for n in counts):
        raise ValueError('Device counts must be nonnegative integers')
    elements=[(kind,i) for kind,count in enumerate(counts) for i in range(count)]
    for level in (1,2):
        for selected in combinations(elements,level):
            groups=[[],[],[]]
            for kind,i in selected:
                groups[kind].append(i)
            yield (*groups,level)
