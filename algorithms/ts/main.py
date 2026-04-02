#!/usr/bin/env python3
"""CLI for the JSSP i-TSAB solver."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.ts.solver import ITSABSolver
from algorithms.ts.config import ITSABConfig
from benchmarks.benchmarks import get_available_instances, load_instance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="JSSP i-TSAB Solver",
    )
    parser.add_argument(
        "instances",
        nargs="*",
        default=["FT06"],
        help="Benchmark instance(s) to solve.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all shared benchmarks.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available shared benchmarks and exit.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Timeout per instance in seconds.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file for results.",
    )
    parser.add_argument(
        "--maxE",
        type=int,
        default=8,
        help="Size of Elite Set (default: 8 for small instances).",
    )
    parser.add_argument(
        "--tabu-length",
        type=int,
        default=3,
        help="Tabu list length (default: 3 for small instances).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=400,
        help="Maximum total iterations Stop_max (default: 400 for small instances).",
    )
    parser.add_argument(
        "--N-init",
        type=int,
        default=10,
        help="Number of initial solutions (default: 10 for small instances).",
    )
    parser.add_argument(
        "--MaxIter-init",
        type=int,
        default=50,
        help="Max iterations for initial TSAB.",
    )
    parser.add_argument(
        "--MaxIter-deep",
        type=int,
        default=100,
        help="Max iterations for deep TSAB.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of runs to perform (default: 1).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list:
        print("Available instances:")
        for instance in get_available_instances():
            print(f"  {instance}")
        return

    if args.seed is not None:
        import random
        random.seed(args.seed)

    config = ITSABConfig(
        maxE=args.maxE,
        tabu_length=args.tabu_length,
        max_iterations=args.max_iterations,
        N_init=args.N_init,
        MaxIter_init=args.MaxIter_init,
        MaxIter_deep=args.MaxIter_deep,
    )

    instances = args.instances
    if args.all:
        instances = get_available_instances()

    all_results = []
    for instance_name in instances:
        print(f"Solving {instance_name}...")
        instance = load_instance(instance_name)

        makespans = []
        times = []
        for run in range(args.runs):
            if args.runs > 1:
                print(f"  Run {run + 1}/{args.runs}...", end=" ")
            
            solver = ITSABSolver(instance, config)
            start_time = time.time()
            solution = solver.solve()
            end_time = time.time()

            makespans.append(solution.makespan)
            times.append(end_time - start_time)
            
            if args.runs > 1:
                print(f"Makespan: {solution.makespan}, Time: {end_time - start_time:.2f}s")

        best_makespan = min(makespans)
        avg_makespan = sum(makespans) / len(makespans)
        total_time = sum(times)
        
        result = {
            "instance": instance_name,
            "best_makespan": best_makespan,
            "avg_makespan": avg_makespan,
            "makespans": makespans,
            "times": times,
            "total_time": total_time,
            "runs": args.runs,
            "algorithm": "i-TSAB",
            "config": {
                "maxE": config.maxE,
                "tabu_length": config.tabu_length,
                "max_iterations": config.max_iterations,
                "N_init": config.N_init,
                "MaxIter_init": config.MaxIter_init,
                "MaxIter_deep": config.MaxIter_deep,
            },
        }
        all_results.append(result)
        
        print(f"  Best Makespan: {best_makespan}")
        if args.runs > 1:
            print(f"  Average Makespan: {avg_makespan:.1f}")
        print(f"  Total Time: {total_time:.2f}s")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()