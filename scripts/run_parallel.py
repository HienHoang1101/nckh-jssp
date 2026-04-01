"""
Parallel benchmark runner for all JSSP solvers.
Runs multiple instances simultaneously using ProcessPoolExecutor.

Usage:
  python scripts/run_parallel.py bnb 3600 results/bnb_results.csv  [--workers 4]
  python scripts/run_parallel.py dp  3600 results/dp_results.json  [--workers 4]
  python scripts/run_parallel.py gt  3600 results/gt_results.json  [--workers 4]
  python scripts/run_parallel.py sb  3600 results/sb_results.json  [--workers 4]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# ── Instance list ─────────────────────────────────────────────────────────────
INSTANCES = (
    ["FT06", "FT10", "FT20"]
    + [f"LA{i:02d}" for i in range(1, 41)]
    + [f"TA{i:02d}" for i in range(1, 51)]
)

GT_RULES = ["SPT", "LPT", "MWKR", "SRPT", "FCFS"]

ROOT = Path(__file__).resolve().parents[1]  # project root


# ── Per-instance runners ───────────────────────────────────────────────────────

def _run_subprocess(cmd: list[str], hard_timeout: int) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, timeout=hard_timeout, cwd=str(ROOT)
        )
        return r.returncode, r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace")
    except subprocess.TimeoutExpired:
        return -1, "", "subprocess hard timeout"
    except Exception as e:
        return -2, "", str(e)


def run_bnb(instance: str, timeout: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, dir="/tmp") as f:
        tmp = f.name
    try:
        rc, _, stderr = _run_subprocess(
            ["python3", "run.py", "bnb", instance,
             "--timeout", str(timeout), "--output", tmp],
            hard_timeout=timeout + 60,
        )
        if rc == 0 and os.path.exists(tmp):
            with open(tmp, newline="") as f:
                rows = list(csv.DictReader(f))
            if rows:
                return rows[0]
        return {"instance": instance, "makespan": None, "bks": None,
                "computation_time": timeout, "nodes_explored": 0,
                "optimal_proven": False, "gap_vs_bks_pct": None,
                "error": stderr.strip().splitlines()[-1] if stderr.strip() else "no output"}
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run_dp(instance: str, timeout: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, dir="/tmp") as f:
        tmp = f.name
    try:
        rc, _, stderr = _run_subprocess(
            ["python3", "run.py", "dp", instance,
             "--timeout", str(timeout), "--output", tmp],
            hard_timeout=timeout + 60,
        )
        if rc == 0 and os.path.exists(tmp):
            with open(tmp) as f:
                data = json.load(f)
            if data:
                return data[0]
        return {"instance_name": instance, "size": "", "optimal_makespan": None,
                "best_makespan": None, "gap_percent": None,
                "computation_time_seconds": timeout, "states_explored": 0,
                "memory_mb": 0.0, "optimal_proven": False, "timed_out": True,
                "error": stderr.strip().splitlines()[-1] if stderr.strip() else "no output"}
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run_gt(instance: str, rule: str, _timeout: int) -> dict:
    """GT ignores timeout (heuristic). Returns one result dict per (instance, rule)."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, dir="/tmp") as f:
        tmp = f.name
    try:
        rc, _, stderr = _run_subprocess(
            ["python3", "run.py", "gt", instance, "--rule", rule, "--output", tmp],
            hard_timeout=120,
        )
        if rc == 0 and os.path.exists(tmp):
            with open(tmp) as f:
                data = json.load(f)
            if data:
                return data[0]
        return {"instance": instance, "rule": rule, "makespan": None, "bks": None,
                "gap_vs_bks_pct": None, "validation_passed": False,
                "error": stderr.strip().splitlines()[-1] if stderr.strip() else "no output"}
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run_sb(instance: str, _timeout: int) -> dict:
    """SB ignores timeout (heuristic)."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, dir="/tmp") as f:
        tmp = f.name
    try:
        rc, _, stderr = _run_subprocess(
            ["python3", "run.py", "sb", instance, "--output", tmp],
            hard_timeout=300,
        )
        if rc == 0 and os.path.exists(tmp):
            with open(tmp) as f:
                data = json.load(f)
            if data:
                return data[0]
        return {"instance": instance, "makespan": None, "bks": None,
                "gap_vs_bks": None, "validation_passed": False,
                "error": stderr.strip().splitlines()[-1] if stderr.strip() else "no output"}
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ── Task builder ───────────────────────────────────────────────────────────────

def build_tasks(solver: str, timeout: int) -> list[tuple]:
    """Return list of (label, fn, *args) tuples."""
    tasks = []
    if solver == "bnb":
        for inst in INSTANCES:
            tasks.append((f"bnb/{inst}", run_bnb, inst, timeout))
    elif solver == "dp":
        for inst in INSTANCES:
            tasks.append((f"dp/{inst}", run_dp, inst, timeout))
    elif solver == "gt":
        for rule in GT_RULES:
            for inst in INSTANCES:
                tasks.append((f"gt/{inst}/{rule}", run_gt, inst, rule, timeout))
    elif solver == "sb":
        for inst in INSTANCES:
            tasks.append((f"sb/{inst}", run_sb, inst, timeout))
    return tasks


def _worker(label_fn_args):
    label, fn, *args = label_fn_args
    t0 = time.perf_counter()
    result = fn(*args)
    elapsed = time.perf_counter() - t0
    return label, result, elapsed


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("solver", choices=["bnb", "dp", "gt", "sb"])
    parser.add_argument("timeout", type=int)
    parser.add_argument("output")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel workers (default: 4)")
    args = parser.parse_args()

    tasks = build_tasks(args.solver, args.timeout)
    total = len(tasks)
    print(f"[{args.solver.upper()}] {total} tasks, {args.workers} workers, timeout={args.timeout}s")

    results = []
    done = 0
    errors = 0
    t_start = time.perf_counter()

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_worker, task): task[0] for task in tasks}
        for future in as_completed(futures):
            label, result, elapsed = future.result()
            results.append(result)
            done += 1
            has_error = bool(result.get("error") if isinstance(result, dict) else False)
            if has_error:
                errors += 1
                status = f"ERROR: {result.get('error', '')[:60]}"
            elif isinstance(result, dict):
                mk = result.get("makespan") or result.get("best_makespan")
                opt = result.get("optimal_proven", "")
                to  = result.get("timed_out", "")
                status = f"makespan={mk}" + (" OPTIMAL" if opt else "") + (" TIMEOUT" if to else "")
            else:
                status = "done"
            print(f"  [{done:>3}/{total}] {label:<20} {elapsed:>7.1f}s  {status}")

    wall = time.perf_counter() - t_start
    print(f"\nFinished: {done - errors}/{total} ok, {errors} errors, wall={wall:.0f}s")

    # Save output
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    if args.output.endswith(".csv"):
        if results:
            fields = list(results[0].keys())
            with open(args.output, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                w.writeheader()
                w.writerows(results)
    else:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)

    print(f"Saved → {args.output}")


if __name__ == "__main__":
    main()
