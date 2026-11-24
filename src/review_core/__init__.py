"""Original domain and normalization core for CODE-REVIEW-CENTER."""

from .finding import Finding, FindingSeverity
from .sarif import parse_sarif

__all__ = ["Finding", "FindingSeverity", "parse_sarif"]
