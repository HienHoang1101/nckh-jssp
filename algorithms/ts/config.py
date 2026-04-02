"""
Configuration for i-TSAB (improved Tabu Search) algorithm for JSSP.

Parameters:
- maxE: Size of Elite Set (number of best local minima stored for path relinking)
- tabu_length: Tabu list length / tenure (iterations a move is forbidden)
- max_iterations: Maximum iterations or iterations without improvement before stopping
- distance_func: Function to measure distance between solutions (for path relinking)
"""

from typing import Callable, Any
from dataclasses import dataclass

from typing import Callable, Any


@dataclass
class ITSABConfig:
    """Configuration class for i-TSAB algorithm."""

    maxE: int = 8  # Size of Elite Set (smaller for focused search on small instances)
    tabu_length: int = 3  # Tabu list length (L) - dynamic [3,5] for small instances
    max_iterations: int = 400  # Stop_max: Maximum total iterations (300-500 for small instances)
    max_iterations_no_improve: int = 100  # Iterations without improvement before stopping
    N_init: int = 10  # Number of initial solutions (adequate for small space)
    MaxIter_init: int = 50  # Max iterations for initial TSAB
    MaxIter_deep: int = 100  # Max iterations for deep TSAB
    use_aspiration: bool = True  # Enable Aspiration Criterion to break tabu
    use_heuristic_init: bool = True  # Use SPT heuristic for initial solutions
    distance_func: Callable[[Any, Any], int] = None  # Distance function between solutions

    def __post_init__(self):
        if self.distance_func is None:
            # Default distance: number of swaps needed (placeholder)
            self.distance_func = lambda a, b: 0  # TODO: implement proper distance