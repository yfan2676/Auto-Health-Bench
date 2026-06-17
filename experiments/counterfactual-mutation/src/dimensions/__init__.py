"""Dimension registry. Each dimension implements the Dimension interface (base.py) and is
addressed by name from the shortlist's `dimension` field, so pick/sweep/footprint stay
dimension-agnostic."""
from dimensions.age import AgeDimension
from dimensions.disclosure import DisclosureDimension

_REGISTRY = {d.name: d for d in (AgeDimension(), DisclosureDimension())}


def get(name):
    if name not in _REGISTRY:
        raise KeyError(f"unknown dimension {name!r}; known: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def names():
    return sorted(_REGISTRY)
