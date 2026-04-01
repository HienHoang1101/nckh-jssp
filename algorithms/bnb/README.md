# JSSP Branch and Bound Solver

A complete Python implementation of Branch and Bound for the **Job Shop Scheduling Problem (JSSP)**, based on the following research papers:

1. **Carlier & Pinson (1989)** — _An Algorithm for Solving the Job-Shop Problem_ (Management Science 35)
2. **Brucker, Jurisch & Sievers (1994)** — _A Branch and Bound Algorithm for the Job-Shop Scheduling Problem_ (Discrete Applied Mathematics 49)
3. **Caseau & Laburthe (1995)** — _Improving Branch and Bound for Job-shop Scheduling with Constraint Propagation_
4. **Pinedo (2016)** — _Scheduling: Theory, Algorithms, and Systems_, Ch. 7: Disjunctive Programming and Branch-and-Bound
5. **Artigues & Feillet (2007)** — _A branch and bound method for the job-shop problem with sequence-dependent setup times_
6. **Brucker (2007)** — _Scheduling Algorithms_ (Handbook), Ch. 6.4: Branch-and-Bound Algorithm
7. **van der Sluis (2022)** — _Branch-and-bound and Constraint Programming for the Job-Shop Problem_ (Thesis)

## Algorithm Overview

### Disjunctive Graph Model

- Operations are nodes; conjunctive arcs encode job precedences; disjunctive arcs connect operations sharing machines
- A feasible schedule = acyclic complete selection of disjunctive arcs
- Makespan = longest path (critical path) in the resulting DAG

### Branch and Bound Components

| Component                  | Technique                                              | Source                                     |
| -------------------------- | ------------------------------------------------------ | ------------------------------------------ |
| **Initial Upper Bound**    | Giffler-Thompson heuristic (active schedule)           | Pinedo (2016), Brucker (1994) §7           |
| **Lower Bound**            | Jackson's Preemptive Schedule (JPS) per machine        | Carlier (1982), Brucker (1994) §6          |
| **Branching**              | Block-based on critical path (before/after candidates) | Brucker (1994) §3, Theorem 3.1             |
| **Constraint Propagation** | Immediate Selection (fixing disjunctive arcs)          | Carlier & Pinson (1989), Brucker (1994) §5 |
| **Constraint Propagation** | Edge-Finding (set-based pruning)                       | Caseau & Laburthe (1995)                   |
| **Heuristic at each node** | Priority dispatching with JPS evaluation               | Brucker (1994) §7                          |

### Algorithm Flow

```
1. Parse instance → Build disjunctive graph
2. Compute initial UB via Giffler-Thompson heuristic
3. Root node: compute heads/tails, JPS lower bound
4. Depth-first search:
   a. Apply constraint propagation (immediate selection + edge-finding)
   b. Compute LB (critical path + JPS)
   c. Prune if LB ≥ UB
   d. Compute heuristic solution → update UB
   e. Find critical path → decompose into blocks
   f. Branch: enumerate before/after candidates from largest block
5. Terminate when stack empty (optimal) or timeout
```

## Installation

```bash
# No external dependencies needed — pure Python 3.10+
python --version  # Must be >= 3.10

# Clone or copy the files:
# graph.py, propagation.py, solver.py, benchmarks.py, main.py
```

## Usage

### Quick Start — Solve FT06 (6×6, optimal = 55)

```bash
python main.py FT06
```

### Solve Multiple Instances

```bash
python main.py FT06 FT10 LA01
```

### Solve with Custom Timeout

```bash
python main.py --timeout 120 FT10
```

### List Available Instances

```bash
python main.py --list
```

### Save Results to JSON/CSV

```bash
python main.py --output results.json FT06 FT10 LA01
python main.py --output results.csv FT06 FT10 LA01
```

### Show Schedule Timeline

```bash
python main.py --show-schedule FT06
```

### Solve All Available Instances

```bash
python main.py --all --timeout 300 --output all_results.json
```

### Debug Logging

```bash
python main.py --log-level DEBUG FT06
```

## File Structure

```
jssp_solver/
├── main.py          # CLI entry point, result formatting
├── solver.py        # Branch & Bound solver, Giffler-Thompson heuristic
├── graph.py         # Disjunctive graph, operations, critical path, blocks
├── propagation.py   # Constraint propagation: immediate selection, edge-finding, JPS
├── benchmarks.py    # Instance data (FT, LA, TA) and BKS values
├── requirements.txt # (empty — no external dependencies)
└── README.md        # This file
```

## Output Format (JSON)

```json
{
  "instance": "FT06",
  "makespan": 55,
  "schedule": { "0": 0, "1": 6, ... },
  "computation_time": 0.123,
  "nodes_explored": 42,
  "optimal_proven": true,
  "bks": 55,
  "gap_vs_bks_pct": 0.0
}
```

## Included Benchmarks

| Set | Instances        | Size           | Source                   |
| --- | ---------------- | -------------- | ------------------------ |
| FT  | FT06, FT10, FT20 | 6×6 to 20×5    | Fisher & Thompson (1963) |
| LA  | LA01–LA40        | 10×5 to 30×10  | Lawrence (1984)          |
| TA  | TA01 (selected)  | 15×15 to 50×20 | Taillard (1993)          |

### Expected Results

| Instance | Size  | BKS  | Expected  | Status                           |
| -------- | ----- | ---- | --------- | -------------------------------- |
| FT06     | 6×6   | 55   | 55        | Optimal in <1s                   |
| FT10     | 10×10 | 930  | 930–940   | Near-optimal, depends on timeout |
| LA01     | 10×5  | 666  | 666       | Optimal in seconds               |
| LA21     | 15×10 | 1046 | 1046–1060 | Hard, may need longer timeout    |

## Key Theoretical Results

- **Theorem 3.1 (Brucker 1994)**: If a better solution exists, some operation in some critical-path block must move before the first or after the last operation of that block → basis for block-based branching.

- **Jackson's Preemptive Schedule**: The preemptive single-machine relaxation provides a polynomial-time lower bound per machine (Carlier 1982).

- **Immediate Selection (Carlier & Pinson 1989)**: If `r_c + p_c + p_j + q_j ≥ UB` for operation c and j on the same machine, then j must precede c in any improving solution → arc j→c is fixed.

## Adding Custom Instances

```python
from graph import parse_instance
from solver import BranchAndBoundSolver

data = """3 3
0 3 1 2 2 2
0 2 2 1 1 4
1 4 2 3 0 1"""

instance = parse_instance("custom", data, bks=None)
solver = BranchAndBoundSolver(instance, timeout=60)
result = solver.solve()
print(f"Makespan: {result.makespan}")
```

## Timeout

Default: **3600 seconds** (1 hour) per instance. Configurable via `--timeout`.

The solver uses wall-clock time checking and will terminate gracefully, returning the best solution found so far with `optimal_proven=False`.

## License

Educational / research use. Based on published algorithms from the operations research literature.
