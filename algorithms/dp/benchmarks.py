"""
benchmarks.py — Standard JSSP Benchmark Instances

Contains the following well-known instances:
  - FT06  (Fisher & Thompson, 1963):  6 jobs × 6 machines, optimal = 55
  - LA01–LA05  (Lawrence, 1984):     10 jobs × 5 machines

Format:
  Each instance is a list of jobs, where each job is a list of
  (machine, processing_time) tuples in visit order.

References:
  [11] Fisher H, Thompson GL (1963). "Probabilistic learning combinations
       of local job-shop scheduling rules." Industrial Scheduling.
  [20] Lawrence S (1984). "Resource constrained project scheduling:
       an experimental investigation of heuristic scheduling techniques."
       GSIA, Carnegie-Mellon University.
  [26] Beasley JE (1990). OR-Library.

Best Known Solutions (BKS) — all are proven optimal:
  FT06: 55   | LA01: 666  | LA02: 655  | LA03: 597  | LA04: 590  | LA05: 593
"""

from __future__ import annotations

from dataclasses import dataclass
from state_space import JSSPInstance


@dataclass
class BenchmarkEntry:
    """A benchmark instance with its known optimal value."""
    instance: JSSPInstance
    optimal: int


def get_ft06() -> BenchmarkEntry:
    """
    FT06 — Fisher & Thompson (1963)
    6 jobs × 6 machines, optimal makespan = 55

    From the OR-Library. This is the instance Gromicho (2012) solved
    in < 1 second with 190,592 total sequences explored.
    """
    jobs = [
        # Job 0: (machine, processing_time)
        [(2, 1), (0, 3), (1, 6), (3, 7), (5, 3), (4, 6)],
        # Job 1
        [(1, 8), (2, 5), (4, 10), (5, 10), (0, 10), (3, 4)],
        # Job 2
        [(2, 5), (3, 4), (5, 8), (0, 9), (1, 1), (4, 7)],
        # Job 3
        [(1, 5), (0, 5), (2, 5), (3, 3), (4, 8), (5, 9)],
        # Job 4
        [(2, 9), (1, 3), (4, 5), (5, 4), (0, 3), (3, 1)],
        # Job 5
        [(1, 3), (3, 3), (5, 9), (0, 10), (4, 4), (2, 1)],
    ]
    inst = JSSPInstance(name="ft06", n_jobs=6, n_machines=6, jobs=jobs)
    return BenchmarkEntry(instance=inst, optimal=55)


def get_la01() -> BenchmarkEntry:
    """
    LA01 — Lawrence (1984)
    10 jobs × 5 machines, optimal makespan = 666
    """
    jobs = [
        [(1, 21), (0, 53), (4, 95), (3, 55), (2, 34)],
        [(0, 21), (3, 52), (4, 16), (2, 26), (1, 71)],
        [(3, 39), (4, 98), (1, 42), (2, 31), (0, 12)],
        [(1, 77), (0, 55), (4, 79), (2, 66), (3, 77)],
        [(0, 83), (3, 34), (2, 64), (1, 19), (4, 37)],
        [(1, 54), (2, 43), (4, 79), (0, 92), (3, 62)],
        [(3, 69), (4, 77), (1, 87), (2, 93), (0, 11)],
        [(0, 14), (1, 18), (2, 43), (4, 26), (3, 71)],
        [(2, 84), (1, 61), (3, 94), (0, 19), (4, 57)],
        [(1, 64), (0, 85), (4, 74), (2, 59), (3, 90)],
    ]
    inst = JSSPInstance(name="la01", n_jobs=10, n_machines=5, jobs=jobs)
    return BenchmarkEntry(instance=inst, optimal=666)


def get_la02() -> BenchmarkEntry:
    """
    LA02 — Lawrence (1984)
    10 jobs × 5 machines, optimal makespan = 655
    """
    jobs = [
        [(0, 20), (3, 87), (1, 31), (4, 76), (2, 17)],
        [(1, 25), (2, 32), (0, 24), (4, 18), (3, 81)],
        [(3, 72), (0, 23), (2, 28), (1, 58), (4, 99)],
        [(2, 86), (1, 76), (4, 97), (0, 45), (3, 90)],
        [(0, 27), (1, 42), (4, 48), (2, 17), (3, 46)],
        [(1, 67), (0, 98), (4, 48), (3, 27), (2, 62)],
        [(4, 28), (1, 12), (3, 19), (0, 80), (2, 50)],
        [(1, 63), (0, 94), (2, 98), (3, 50), (4, 80)],
        [(4, 14), (0, 75), (2, 50), (1, 41), (3, 55)],
        [(3, 72), (2, 57), (1, 44), (4, 63), (0, 52)],
    ]
    inst = JSSPInstance(name="la02", n_jobs=10, n_machines=5, jobs=jobs)
    return BenchmarkEntry(instance=inst, optimal=655)


def get_la03() -> BenchmarkEntry:
    """
    LA03 — Lawrence (1984)
    10 jobs × 5 machines, optimal makespan = 597
    """
    jobs = [
        [(1, 23), (2, 45), (0, 82), (4, 84), (3, 38)],
        [(2, 21), (0, 29), (3, 18), (4, 41), (1, 50)],
        [(2, 38), (3, 54), (4, 16), (0, 52), (1, 52)],
        [(4, 37), (0, 54), (2, 74), (1, 62), (3, 57)],
        [(1, 57), (0, 81), (3, 61), (4, 68), (2, 30)],
        [(4, 81), (0, 79), (1, 89), (2, 89), (3, 11)],
        [(3, 33), (2, 20), (0, 91), (1, 20), (4, 66)],
        [(0, 24), (4, 84), (1, 32), (3, 55), (2, 8)],
        [(4, 56), (0, 7), (3, 54), (2, 64), (1, 39)],
        [(1, 40), (4, 83), (0, 19), (3, 8), (2, 7)],
    ]
    inst = JSSPInstance(name="la03", n_jobs=10, n_machines=5, jobs=jobs)
    return BenchmarkEntry(instance=inst, optimal=597)


def get_la04() -> BenchmarkEntry:
    """
    LA04 — Lawrence (1984)
    10 jobs × 5 machines, optimal makespan = 590
    """
    jobs = [
        [(0, 12), (3, 94), (2, 92), (4, 91), (1, 7)],
        [(1, 19), (0, 11), (3, 66), (2, 21), (4, 87)],
        [(3, 14), (0, 75), (1, 13), (4, 16), (2, 20)],
        [(2, 95), (4, 66), (0, 7), (3, 7), (1, 77)],
        [(0, 45), (4, 6), (3, 89), (1, 15), (2, 34)],
        [(3, 77), (2, 20), (0, 76), (4, 88), (1, 53)],
        [(1, 74), (2, 88), (0, 52), (4, 27), (3, 9)],
        [(4, 88), (1, 69), (0, 62), (3, 98), (2, 52)],
        [(2, 61), (0, 9), (1, 62), (3, 52), (4, 90)],
        [(4, 54), (3, 5), (2, 59), (0, 15), (1, 88)],
    ]
    inst = JSSPInstance(name="la04", n_jobs=10, n_machines=5, jobs=jobs)
    return BenchmarkEntry(instance=inst, optimal=590)


def get_la05() -> BenchmarkEntry:
    """
    LA05 — Lawrence (1984)
    10 jobs × 5 machines, optimal makespan = 593
    """
    jobs = [
        [(1, 72), (0, 87), (4, 95), (2, 66), (3, 60)],
        [(3, 5), (2, 35), (0, 95), (4, 47), (1, 77)],
        [(1, 46), (3, 24), (0, 37), (4, 38), (2, 52)],
        [(0, 6), (2, 84), (1, 23), (3, 15), (4, 28)],
        [(2, 90), (3, 29), (0, 43), (1, 82), (4, 27)],
        [(0, 16), (1, 76), (2, 32), (3, 18), (4, 20)],
        [(4, 36), (3, 36), (2, 49), (1, 60), (0, 79)],
        [(2, 76), (1, 76), (3, 76), (0, 29), (4, 40)],
        [(0, 13), (2, 29), (1, 75), (3, 81), (4, 30)],
        [(1, 82), (4, 13), (3, 88), (2, 54), (0, 82)],
    ]
    inst = JSSPInstance(name="la05", n_jobs=10, n_machines=5, jobs=jobs)
    return BenchmarkEntry(instance=inst, optimal=593)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
ALL_BENCHMARKS: dict[str, callable] = {
    "ft06": get_ft06,
    "la01": get_la01,
    "la02": get_la02,
    "la03": get_la03,
    "la04": get_la04,
    "la05": get_la05,
}


def get_benchmark(name: str) -> BenchmarkEntry:
    """Look up a benchmark by name (case-insensitive)."""
    key = name.lower()
    if key not in ALL_BENCHMARKS:
        raise ValueError(
            f"Unknown benchmark '{name}'. "
            f"Available: {list(ALL_BENCHMARKS.keys())}"
        )
    return ALL_BENCHMARKS[key]()


def list_benchmarks() -> list[str]:
    """Return the names of all available benchmarks."""
    return list(ALL_BENCHMARKS.keys())
