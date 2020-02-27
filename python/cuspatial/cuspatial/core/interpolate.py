# Copyright (c) 2020, NVIDIA CORPORATION.

from cuspatial._lib.interpolate import (
    cubicspline_full
)

from cudf import DataFrame, Series
from cudf.core.index import RangeIndex

import numpy as np


def cubic_spline_2(x, y, ids, prefix_sums):
    """
    Fits each column of the input DataFrame `y` to a hermetic cubic spline.

    Parameters
    ----------
    x : cudf.Series
        time sample values. Must be monotonically increasing.
    y : cudf.DataFrame
        columns to have curves fit to according to x
    ids_and_end_coordinates: cudf.DataFrame
                             ids and final positions of each set of
                             trajectories

    Returns
    -------
    m x n DataFrame of trajectory curve coefficients.
    m is len(ids_and_end_coordinates), n is 4 * len(y.columns)
    """
    x_c = x._column
    y_c = y._column
    ids_c = ids._column
    prefix_c = prefix_sums._column
    result_table = cubicspline_full(x_c, y_c, ids_c, prefix_c)
    result_table._index = RangeIndex(result_table._num_rows)
    result = DataFrame._from_table(result_table)
    return result


def cubic_spline_fit(c, original_t, points, points_ids, prefixes):
    c_c = c._table
    original_t_c = original_t._column
    points_c = points._column
    points_ids_c = points_ids._column
    prefixes_c = prefixes._column
    result_column = cubicspline_interpolate(
            points_c, points_ids_c, prefix_c, original_t_c, c_c
    )
    return result_column


class CubicSpline:
    def __init__(self, t, y, ids=None, size=None):
        # error protections:
        if len(t) < 5:
            raise ValueError(
                "Use of GPU cubic spline requires splines of length > 4"
            )
        if not isinstance(t, Series):
            raise TypeError(
                "Error: input independent vars must be cudf Series"
            )
        if not isinstance(y, (Series, DataFrame)):
            raise TypeError(
                "Error: input dependent vars must be cudf Series or DataFrame"
            )
        if not len(t) == len(y):
            raise TypeError(
                "Error: dependent and independent vars have different length"
            )
        self.ids = Series(ids).astype('int32') if ids is not None else Series(
            [0, 0]).astype('int32')
        self.size = size if size is not None else len(t)
        if not isinstance(self.size, int):
            raise TypeError(
                "Error: size must be an integer"
            )
        if not ((len(t) % self.size) == 0):
            raise ValueError(
                "Error: length of input is not a multiple of size"
            )
        self.t = Series(t).astype('float32')
        self.y = Series(y).astype('float32')
        self.prefix = Series(
            np.arange((len(t) / self.size) + 1) * self.size
        ).astype('int32')
        self._compute_coefficients()

    def _compute_coefficients(self):
        if isinstance(self.y, Series):
            self.c = cubic_spline_2(self.t, self.y, self.ids, self.prefix)
        else:
            self.c = {}
            for col in self.y.columns:
                self.c[col] = cubic_spline_2(
                    self.t, self.y, self.ids, self.prefix)

    def __call__(self, coordinates):
        if isinstance(self.y, Series):
            return cubic_spline_fit(self.c, coordinates)
        else:
            result = DataFrame()
            for col in self.y.columns:
                result[col] = cubic_spline_fit(self.c[col], coordinates)
            return result
