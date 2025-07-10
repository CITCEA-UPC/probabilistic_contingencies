import math

import pandas as pd
import numpy as np
from datagen import *


def unique(sequence):
    seen = set()
    result = []
    for item in sequence:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def gen_df_for_dims(dims, n_rows=100):
    dim_set = {}
    for dim in dims:
        for i, var in enumerate(dim.variable_borders):
            col_name = f"{dim.label}_Var{i}"
            dim_set[col_name] = np.random.uniform(var[0], var[1], n_rows)
    cases_df = pd.DataFrame(dim_set)
    return cases_df


def linear_function(case):
    max_value = 10*4*1+10*4*5
    case[8:12] *= 5
    case[0:4] = 0
    sum_pond = sum([case[index]*math.floor(index/4)
                    for index in range(len(case))])
    return int(sum_pond > max_value/2)


def parab_func(case):
    def parabola(x, a=1, h=5.5, k=36):
        return -a * (x - h) ** 2 + k
    max_value = 3580
    sum_pond = sum([value * parabola(idx) for idx, value in enumerate(case)])
    return int(sum_pond > max_value/2)


def dim0_func(case):
    max_value = 10*4
    return int(case[0:4].sum() > max_value/2)
