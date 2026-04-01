"""Shared benchmark access for all JSSP algorithms."""

from .benchmarks import BKS, get_available_instances, load_instance

__all__ = ["BKS", "get_available_instances", "load_instance"]
