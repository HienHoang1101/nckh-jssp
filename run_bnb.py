#!/usr/bin/env python3
"""
Run Branch-and-Bound on all requested benchmark sets:
  - FT06
  - LA01 – LA40
  - TA01 – TA50

Checkpoint/resume: results are written to CSV immediately after each instance
finishes. If the run is interrupted, re-running with the same --output file
will automatically skip already-completed instances.

Usage:
    python3 run_bnb.py [--timeout T] [--output results/bnb_all.csv]

Defaults: timeout=3600s per instance, output=results/bnb_summary.csv
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.bnb.solver import BranchAndBoundSolver, SolverResult
from benchmarks.benchmarks import load_instance


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_bnb")

# ── Benchmark lists ──────────────────────────────────────────────────────────
FT_INSTANCES   = ["FT06"]
LA_INSTANCES   = [f"LA{i:02d}" for i in range(1, 41)]
TA_INSTANCES   = [f"TA{i:02d}" for i in range(1, 51)]

ALL_INSTANCES  = FT_INSTANCES + LA_INSTANCES + TA_INSTANCES

FIELDNAMES = [
    "instance", "makespan", "bks", "gap_vs_bks_pct",
    "optimal_proven", "nodes_explored", "computation_time",
]


# ── Checkpoint helpers ───────────────────────────────────────────────────────

def load_completed(out_path: Path) -> set[str]:
    """Read the CSV (if it exists) and return set of already-completed instance names."""
    done: set[str] = set()
    if not out_path.exists():
        return done
    with open(out_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            done.add(row["instance"])
    return done


def append_result(out_path: Path, r: SolverResult) -> None:
    """Append a single result row to the CSV (write header if file is new)."""
    write_header = not out_path.exists() or out_path.stat().st_size == 0
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            w.writeheader()
        w.writerow({
            "instance":         r.instance_name,
            "makespan":         r.makespan,
            "bks":              r.bks if r.bks else "",
            "gap_vs_bks_pct":   round(r.gap_vs_bks, 4),
            "optimal_proven":   r.optimal_proven,
            "nodes_explored":   r.nodes_explored,
            "computation_time": round(r.computation_time, 3),
        })


# ── Solver wrapper ───────────────────────────────────────────────────────────

def solve_one(name: str, timeout: float) -> SolverResult | None:
    inst = load_instance(name)
    if inst is None:
        logger.error(f"Instance '{name}' not found — skipping")
        return None
    logger.info(
        f"{'='*60}\n"
        f"  Instance : {name}  ({inst.num_jobs}j × {inst.num_machines}m)\n"
        f"  BKS      : {inst.bks}\n"
        f"  Timeout  : {timeout}s\n"
        f"{'='*60}"
    )
    solver = BranchAndBoundSolver(inst, timeout=timeout, log_interval=5000)
    r = solver.solve()
    status = "OPT" if r.optimal_proven else "TLE"
    logger.info(
        f"  [{status}] makespan={r.makespan}  bks={r.bks}  "
        f"gap={r.gap_vs_bks:.2f}%  nodes={r.nodes_explored}  "
        f"time={r.computation_time:.2f}s"
    )
    return r


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run B&B on FT06 + LA + TA benchmarks")
    parser.add_argument("--timeout", type=float, default=3600.0,
                        help="Per-instance timeout in seconds (default: 3600)")
    parser.add_argument("--output", "-o", default="results/bnb_summary.csv",
                        help="Output CSV path (default: results/bnb_summary.csv)")
    parser.add_argument("--instances", nargs="*", default=None,
                        help="Override: specific instance names to run")
    parser.add_argument("--ft-only", action="store_true", help="Run FT instances only")
    parser.add_argument("--la-only", action="store_true", help="Run LA instances only")
    parser.add_argument("--ta-only", action="store_true", help="Run TA instances only")
    parser.add_argument("--no-resume", action="store_true",
                        help="Ignore existing CSV and re-run all instances")
    args = parser.parse_args()

    if args.instances:
        instances = [n.upper() for n in args.instances]
    elif args.ft_only:
        instances = FT_INSTANCES
    elif args.la_only:
        instances = LA_INSTANCES
    elif args.ta_only:
        instances = TA_INSTANCES
    else:
        instances = ALL_INSTANCES

    out_path = PROJECT_ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Resume: skip already-done instances ─────────────────────────────────
    if args.no_resume:
        completed = set()
    else:
        completed = load_completed(out_path)

    if completed:
        logger.info(f"Resuming — {len(completed)} instance(s) already done: "
                    f"{', '.join(sorted(completed))}")

    pending = [n for n in instances if n not in completed]
    if not pending:
        logger.info("All requested instances already completed.")
    else:
        logger.info(f"Instances to run: {len(pending)}  "
                    f"(skipping {len(completed)} already done)")

    # Small grace period: solver overhead can add a few seconds beyond the
    # configured timeout before the result is returned.
    TIME_LIMIT_GRACE = args.timeout + 10.0

    skipped: list[str] = []
    t_total = time.time()

    for name in pending:
        r = solve_one(name, args.timeout)
        if r is None:
            continue

        # ── Filter: discard runs that exceeded the time limit ────────────────
        if r.computation_time > TIME_LIMIT_GRACE:
            logger.warning(
                f"SKIP {name}: computation_time={r.computation_time:.1f}s "
                f"exceeds limit ({TIME_LIMIT_GRACE:.0f}s) — result not recorded."
            )
            skipped.append(name)
            continue

        # ── Checkpoint: write immediately ────────────────────────────────────
        append_result(out_path, r)
        logger.info(f"  Saved → {out_path.name}")

    elapsed = time.time() - t_total

    # ── Re-read all results from CSV for summary table ───────────────────────
    all_results: list[dict] = []
    if out_path.exists():
        with open(out_path, newline="", encoding="utf-8") as f:
            all_results = list(csv.DictReader(f))

    # Filter to only the requested instance set for summary
    requested = set(instances)
    all_results = [r for r in all_results if r["instance"] in requested]

    # ── Console summary table ────────────────────────────────────────────────
    print()
    hdr = (f"{'Instance':<12}{'Makespan':>10}{'BKS':>8}{'Gap%':>8}"
           f"{'Status':>8}{'Nodes':>12}{'Time(s)':>10}")
    sep = "-" * len(hdr)
    print(hdr)
    print(sep)
    for r in all_results:
        status = "OPT" if r["optimal_proven"] in ("True", True) else "TLE"
        bks_str = r["bks"] if r["bks"] else "?"
        gap = float(r["gap_vs_bks_pct"])
        print(
            f"{r['instance']:<12}{r['makespan']:>10}{bks_str:>8}"
            f"{gap:>7.2f}%{status:>8}{r['nodes_explored']:>12}"
            f"{float(r['computation_time']):>10.2f}"
        )
    print(sep)

    n_opt   = sum(1 for r in all_results if r["optimal_proven"] in ("True", True))
    n_total = len(all_results)
    avg_gap = (sum(float(r["gap_vs_bks_pct"]) for r in all_results) / n_total
               if n_total else 0.0)
    print(f"Recorded: {n_total}  |  Optimal: {n_opt}/{n_total}  |  "
          f"Avg gap: {avg_gap:.2f}%  |  Session time: {elapsed:.1f}s")
    if skipped:
        print(f"Skipped (exceeded {TIME_LIMIT_GRACE:.0f}s): {', '.join(skipped)}")
    if completed:
        print(f"Already done (resumed): {len(completed)}")
    print()
    logger.info(f"Results stored in → {out_path}")


if __name__ == "__main__":
    main()
