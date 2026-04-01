# JSSP Dynamic Programming Solver

**An exact solver for the Job-Shop Scheduling Problem based on Dynamic Programming**

## Theoretical Foundation

This implementation is based on:

> **Gromicho, van Hoorn, Saldanha-da-Gama, Timmer (2012).**
> *"Solving the job-shop scheduling problem optimally by dynamic programming."*
> Computers & Operations Research 39, 2968–2977.

Which extends the classical Bellman equation from:

> **Held & Karp (1962).**
> *"A dynamic programming approach to sequencing problems."*
> SIAM Journal of Applied Mathematics 10, 196–210.

### Algorithm Overview

The standard Held-Karp Bellman equation for the TSP cannot be directly applied
to the JSSP because **the principle of optimality does not hold** — a sub-optimal
partial sequence can lead to a globally optimal solution.

Gromicho et al. (2012) restore optimality by:

1. **Redefining the state space**: Instead of keeping a single optimal value per
   state, the algorithm maintains a set X̂(S) of *mutually non-dominated*
   ordered partial sequences for each operation subset S.

2. **Dominance pruning (Proposition 2)**: Two partial sequences T₁, T₂ over
   the same set S are compared via their *aptitude vectors* ξ(T, o) for all
   expandable operations. If ξ(T₂, o) ≤ ξ(T₁, o) for all o with at least
   one strict inequality, then T₂ dominates T₁ and T₁ is discarded.

3. **State-space reduction (Proposition 5)**: A sequence T is pruned if there
   exists a machine where all expandable operations are "maximally delayed"
   and at least one cannot form an ordered expansion.

4. **Antichain bounding (Propositions 7, 8)**: The maximum size of X̂(S) is
   bounded by O(pmax^n / √n), derived from antichain theory on multisets.

### Complexity

| Algorithm        | Complexity                    |
|:-----------------|:------------------------------|
| Brute force      | O((n!)^m)                     |
| **This solver**  | **O((pmax)^{2n} · (m+1)^n)** |

For fixed pmax, the DP approach is **exponentially better** than brute force
in both n (jobs) and m (machines).

## Project Structure

```
jssp_dp/
├── main.py            # Entry point & CLI
├── dp_solver.py       # Core DP algorithm (Algorithm 1)
├── state_space.py     # State representation, operations, sequences
├── dominance.py       # Dominance rules & state-space reduction
├── benchmarks.py      # FT06, LA01–LA05 benchmark data
├── requirements.txt   # Dependencies (none — pure stdlib)
└── README.md          # This file
```

## Requirements

- **Python 3.10+** (uses `int | None` type union syntax)
- **No external packages** — pure Python standard library
- Works offline — no network requests

## Installation

```bash
# Clone or copy the jssp_dp/ directory
cd jssp_dp

# (Optional) Create a virtual environment
python3 -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# No packages to install
pip install -r requirements.txt   # (empty — just verifies setup)
```

## Usage

### Quick Start — Solve FT06

```bash
python main.py --instance ft06
```

Expected output: optimal makespan **55** found in **< 5 seconds**.

### Solve All Benchmarks

```bash
python main.py
```

### Custom Timeout

```bash
python main.py --timeout 1800   # 30 minutes per instance
```

### Save Results to JSON

```bash
python main.py --output results.json
```

### Disable State-Space Reduction

```bash
python main.py --instance ft06 --no-reduction
```

### Verbose Logging

```bash
python main.py --instance ft06 --verbose
```

### Full CLI Reference

```
python main.py --help
```

## Benchmarks

| Instance | Size   | Optimal (BKS) | Expected Runtime | Source                    |
|:---------|:-------|:---------------|:-----------------|:--------------------------|
| FT06     | 6×6    | 55             | < 5 seconds      | Fisher & Thompson (1963)  |
| LA01     | 10×5   | 666            | ~25–30 minutes   | Lawrence (1984)           |
| LA02     | 10×5   | 655            | ~30–35 minutes   | Lawrence (1984)           |
| LA03     | 10×5   | 597            | ~20–25 minutes   | Lawrence (1984)           |
| LA04     | 10×5   | 590            | ~25–30 minutes   | Lawrence (1984)           |
| LA05     | 10×5   | 593            | ~15–20 minutes   | Lawrence (1984)           |

**Note:** LA01–LA05 runtimes are approximate for Python. The original C++
implementation by Gromicho et al. solved these in 965–1961 seconds on 2012
hardware. Python will be slower due to interpreter overhead; a 3600s timeout
is recommended.

## Output Format

Each instance produces a JSON result:

```json
{
  "instance": "ft06",
  "size": "6x6",
  "optimal_makespan": 55,
  "best_makespan": 55,
  "gap_percent": 0.0,
  "computation_time_seconds": 2.45,
  "states_explored": 190592,
  "memory_mb": 8.2,
  "optimal_proven": true,
  "schedule": [
    {"job": 0, "machine": 2, "operation": 0, "start": 0, "end": 1, "processing_time": 1},
    ...
  ],
  "sequence": [2, 0, 1, 6, 8, 3, 7, 5, ...],
  "timed_out": false
}
```

## Limitations

- **Feasible only for small instances**: n ≤ 10 jobs, m ≤ 5–6 machines
- **State space grows exponentially** with both n and m
- **Memory-intensive**: each state stores multiple non-dominated sequences
- The Python implementation is ~10–50x slower than an equivalent C++ version;
  for LA01–LA05, expect runtimes measured in minutes to an hour

## Algorithm Details

### Key Definitions (Gromicho 2012)

- **Operation**: o ∈ O, with job j(o), machine m(o), processing time p(o)
- **Ordered partial sequence T**: operations ordered by non-decreasing
  completion time, with machine-index tie-breaking
- **ε(S)**: expandable operations — next unscheduled operation for each job
- **Z(T)**: operations in ε(S) whose addition to T preserves ordering
- **ξ(T, o)**: aptitude value — completion time if o added to T, or
  Cmax(T) + p(o) if not orderable
- **Dominance**: T₂ ≻ T₁ iff ξ(T₂, o) ≤ ξ(T₁, o) ∀o ∈ ε(S) with ≥1 strict
- **X̂(S)**: set of mutually non-dominated sequences (antichain)

### Bellman Equation

```
X̂({o}) = {T}  where T = o           (single-operation base case)
X̂(S)   = X̃(S)                       (non-dominated set after expansion)
```

The algorithm builds X̂(O) by expanding sequences level-by-level (by |S|),
applying dominance pruning at each insertion. The final X̂(O) contains
exactly one sequence — the optimal solution.

## References

1. Gromicho, J.A.S., van Hoorn, J.J., Saldanha-da-Gama, F., Timmer, G.T. (2012).
   "Solving the job-shop scheduling problem optimally by dynamic programming."
   *Computers & Operations Research* 39, 2968–2977.

2. Held, M. & Karp, R.M. (1962).
   "A dynamic programming approach to sequencing problems."
   *SIAM Journal of Applied Mathematics* 10, 196–210.

3. Fisher, H. & Thompson, G.L. (1963).
   "Probabilistic learning combinations of local job-shop scheduling rules."
   In: *Industrial Scheduling*, Prentice Hall, p. 225.

4. Lawrence, S. (1984).
   "Resource constrained project scheduling: an experimental investigation
   of heuristic scheduling techniques." GSIA, Carnegie-Mellon University.
