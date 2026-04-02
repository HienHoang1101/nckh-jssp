# i-TSAB: Improved Tabu Search for Job Shop Scheduling Problem

This directory contains the implementation of the i-TSAB (improved Tabu Search) algorithm for solving the Job Shop Scheduling Problem (JSSP).

## Algorithm Overview

i-TSAB is an enhanced Tabu Search algorithm that incorporates:
- **Elite Set (ES)**: Stores the best local minima found during initialization
- **Path Relinking**: Uses the elite solutions as anchors for interpolation between current and elite solutions
- **Tabu List**: Prevents cycling by forbidding recent moves

## Parameters

- `maxE`: Size of the Elite Set (default: 10)
- `tabu_length`: Length of the tabu list / tenure (default: 7)
- `max_iterations`: Maximum total iterations (Stop_max) (default: 1000)
- `N_init`: Number of initial solutions (default: 20)
- `MaxIter_init`: Max iterations for initial TSAB (default: 50)
- `MaxIter_deep`: Max iterations for deep TSAB (default: 100)
- `distance_func`: Function to measure distance between solutions for path relinking

## Usage

```bash
# Single run
python algorithms/ts/main.py FT06 --maxE 15 --tabu-length 10 --N-init 30

# Multiple runs (recommended for statistical analysis)
python algorithms/ts/main.py FT06 --runs 30 --N-init 5 --MaxIter-init 20 --MaxIter-deep 50 --max-iterations 10

# Save results to JSON
python algorithms/ts/main.py FT06 --runs 30 --output results.json
```

## Output
For multiple runs, the program reports:
- **Best Makespan**: Minimum makespan across all runs
- **Average Makespan**: Mean makespan across all runs
- **Total Time**: Sum of execution times for all runs

## Implementation Details

The algorithm follows the pseudocode provided:
1. Initialize empty Elite Set
2. Generate N_init initial solutions with local TSAB search
3. Initialize best solution from Elite Set
4. Main loop with Path Relinking and Proper Work stages

### Neighborhood N5
The N5 neighborhood generates moves by swapping operations at the boundaries of critical blocks:
- Identifies critical operations (slack time = 0)
- Finds critical blocks: consecutive critical operations on the same machine
- For each block with length >= 2, swaps the first and last operations in the block

This is more efficient than full enumeration of all possible swaps.

## Files

- `solver.py`: Core i-TSAB algorithm implementation
- `config.py`: Configuration class for algorithm parameters
- `main.py`: Command-line interface
- `README.md`: This file

## References

Based on improved Tabu Search methodologies for combinatorial optimization problems.