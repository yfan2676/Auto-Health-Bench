"""Dimension registry. Each dimension implements the Dimension interface (base.py) and is
addressed by name from the shortlist's `dimension` field, so pick/sweep/footprint stay
dimension-agnostic."""
from dimensions.age import AgeDimension
from dimensions.comorbidity import ComorbidityDimension
from dimensions.disclosure import DisclosureDimension
from dimensions.pregnancy import PregnancyDimension
from dimensions.severity import SeverityDimension
from dimensions.sex import SexDimension

_REGISTRY = {d.name: d for d in (
    AgeDimension(), DisclosureDimension(),
    SeverityDimension(), PregnancyDimension(), ComorbidityDimension(), SexDimension(),
)}


def get(name):
    if name not in _REGISTRY:
        raise KeyError(f"unknown dimension {name!r}; known: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def names():
    return sorted(_REGISTRY)
