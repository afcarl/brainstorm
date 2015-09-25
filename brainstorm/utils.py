#!/usr/bin/env python
# coding=utf-8

from __future__ import division, print_function, unicode_literals
import numpy as np
import re
from brainstorm.optional import has_pycuda

PYTHON_IDENTIFIER = re.compile("^[_a-zA-Z][_a-zA-Z0-9]*$")

NAME_BLACKLIST = {'default', 'fallback'}


def is_valid_layer_name(identifier):
    if identifier in NAME_BLACKLIST:
        return False
    return PYTHON_IDENTIFIER.match(identifier) is not None


class ValidationError(Exception):
    pass


class NetworkValidationError(ValidationError):
    """
    Exception that is thrown e.g. if attempting to build an invalid
    architecture. (E.g. circle)
    """


class LayerValidationError(ValidationError):
    pass


class IteratorValidationError(ValidationError):
    pass


class ShapeValidationError(ValidationError):
    pass


class InitializationError(Exception):
    pass


class WeightModificationError(Exception):
    pass


def get_inheritors(cls):
    """
    Get a set of all classes that inherit from the given class.
    """
    subclasses = set()
    work = [cls]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return subclasses


def flatten(container):
    """Iterate nested lists in flat order."""
    for i in container:
        if isinstance(i, (list, tuple)):
            for j in flatten(i):
                yield j
        else:
            yield i


def convert_to_nested_indices(container, start_idx=None):
    """Return nested lists of indices with same structure as container."""
    if start_idx is None:
        start_idx = [0]
    for i in container:
        if isinstance(i, (list, tuple)):
            yield list(convert_to_nested_indices(i, start_idx))
        else:
            yield start_idx[0]
            start_idx[0] += 1


def sort_by_index_key(x):
    """
    Used as key in sorted() to order items of a dictionary by the @index
    entries in its child-dicts if present.
    """
    if isinstance(x[1], dict) and '@index' in x[1]:
        return x[1]['@index']
    else:
        return -1


def get_by_path(d, path):
    """Access an element of the dict d using the (possibly dotted) path.

    For example, 'foo.bar.baz' would return d['foo']['bar']['baz'].

    :param d: (nested) dictionary
    :type d: dict
    :param path: path to access the dictionary
    :type path: str
    :return: object
    """
    try:
        for p in path.split('.'):
            d = d[p]
    except KeyError:
        print('Did not find log `{}`. Available logs are {}'.format(
            path, flatten_keys(d)))
        raise
    return d


def get_normalized_path(*args):
    path_parts = []
    for a in args:
        assert '@' not in a, a
        path_parts.extend(a.replace('..', '@').split('.'))

    assert '' not in path_parts, str(path_parts)

    normalized_parts = []
    for p in path_parts:
        while p.startswith('@'):
            normalized_parts.pop()
            p = p[1:]
        normalized_parts.append(p)
    return ".".join(normalized_parts)


def flatten_time(array):
    assert len(array.shape) >= 3, "Time can be flattened only for arrays "\
                                  "with at least 3 dimensions."
    t, b, f = array.shape[0], array.shape[1], array.shape[2:]
    return array.reshape((t * b,) + f)


def flatten_time_and_features(array):
    assert len(array.shape) >= 3, "Time & features can be flattened only "\
                                  "for arrays with at least 3 dimensions."
    t, b, f = array.shape[0], array.shape[1], array.shape[2:]
    return array.reshape((t * b, int(np.product(f))))


def flatten_features(array, start_idx=2):
    return array.reshape(array.shape[:start_idx] +
                         (int(np.product(array.shape[start_idx:])),))


def flatten_keys(dictionary):
    """
    Flattens the keys for a nested dictionary using dot notation. This
    returns all the keys which can be accessed via `get_by_path`.

    For example, {'a': None, 'b': {'x': None}} would return ['a', 'b.x']

    :param dictionary: A dictionary which should be flattened.
    :type dictionary: dict
    :return: list of flattened keys
    :rtype: list[unicode]
    """
    if not isinstance(dictionary, dict):
        return []
    keys = []
    for k, v in dictionary.items():
        if isinstance(v, dict):
            for x in flatten_keys(v):
                keys.append(k + '.' + x)
        else:
            keys.append(k)
    return keys

if has_pycuda:
    from pycuda.elementwise import ElementwiseKernel

    check_inf_or_nan_kernel = ElementwiseKernel(
        b"float* inp, float* result",
        b"if (isnan(inp[i]) || isinf(inp[i])) result[i] = 1;",
        b"check_inf_or_nan_kernel"
    )
