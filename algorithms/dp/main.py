#!/usr/bin/env python3
"""CLI for the JSSP dynamic-programming solver."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.dp.dp_solver import DPSolver, DPResult
from algorithms.dp.state_space import JSSPInstance
from benchmarks.benchmarks import BKS, get_available_instances, load_instance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="JSSP DP Solver",
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
        type=str,
        default=None,
        help="Write JSON results to this file.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    parser.add_argument(
        "--no-reduction",
        action="store_true",
        help="Disable state-space reduction (Proposition 5).",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=100_000,
        help="BDP beam width: max states kept per level (0 = unlimited pure DP).",
    )
    return parser.parse_args()


def to_dp_instance(shared_instance) -> JSSPInstance:
    jobs = []
    for job_ops in shared_instance.operations:
        jobs.append([(op.machine, op.duration) for op in job_ops])
    return JSSPInstance(
        name=shared_instance.name,
        n_jobs=shared_instance.num_jobs,
        n_machines=shared_instance.num_machines,
        jobs=jobs,
    )


def run_benchmark(
    instance_name: str,
    timeout: int,
    enable_reduction: bool,
    max_width: int = 100_000,
) -> DPResult | None:
    shared_instance = load_instance(instance_name)
    if shared_instance is None:
        logging.getLogger(__name__).error("Unknown benchmark '%s'", instance_name)
        return None

    inst = to_dp_instance(shared_instance)
    optimal = BKS.get(instance_name)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info(
        "Solving %s  (%d jobs x %d machines)  |  BKS = %s  |  pmax = %d",
        instance_name,
        inst.n_jobs,
        inst.n_machines,
        optimal if optimal is not None else "N/A",
        inst.pmax,
    )
    logger.info("=" * 60)

    solver = DPSolver(
        instance=inst,
        timeout=timeout,
        enable_state_reduction=enable_reduction,
        log_interval=50_000,
        max_width=max_width,
    )
    result = solver.solve(known_optimal=optimal)

    status = "OPTIMAL" if result.optimal_proven else (
        "TIMEOUT" if result.timed_out else "COMPLETE"
    )
    logger.info("-" * 60)
    logger.info("Instance:       %s", result.instance_name)
    logger.info("Size:           %s", result.size)
    logger.info("BKS:            %s", result.optimal_makespan)
    logger.info("Found:          %s", result.best_makespan)
    logger.info("Gap:            %s%%", result.gap_percent)
    logger.info("Status:         %s", status)
    logger.info("Time:           %.3f s", result.computation_time_seconds)
    logger.info("States:         %d", result.states_explored)
    logger.info("Memory:         %.1f MB", result.memory_mb)
    logger.info("-" * 60)
    return result


def print_summary_table(results: list[DPResult]) -> None:
    print(f"\n{'Instance':<12}{'Found':>10}{'BKS':>8}{'Gap%':>8}{'Time(s)':>10}{'States':>12}{'Status':>10}")
    print("-" * 70)
    for r in results:
        status = "OPTIMAL" if r.optimal_proven else ("TIMEOUT" if r.timed_out else "DONE")
        gap_str = "N/A" if r.gap_percent is None else f"{r.gap_percent:.2f}"
        found_str = "N/A" if r.best_makespan is None else str(r.best_makespan)
        bks_str = "N/A" if r.optimal_makespan is None else str(r.optimal_makespan)
        print(
            f"{r.instance_name:<12}{found_str:>10}{bks_str:>8}{gap_str:>8}"
            f"{r.computation_time_seconds:>10.3f}{r.states_explored:>12,}{status:>10}"
        )


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list:
        print("\n".join(get_available_instances()))
        return

    names = get_available_instances() if args.all else [name.upper() for name in args.instances]
    enable_reduction = not args.no_reduction

    print(f"\nJSSP DP Solver - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Instances: {', '.join(names)}")
    print(f"Timeout:   {args.timeout}s per instance")
    print(f"State-space reduction (Prop. 5): {'ON' if enable_reduction else 'OFF'}")
    print(f"BDP max width:   {args.max_width if args.max_width > 0 else 'unlimited'}")
    print()

    results: list[DPResult] = []
    for name in names:
        result = run_benchmark(name, args.timeout, enable_reduction, args.max_width)
        if result is not None:
            results.append(result)

    if results:
        print_summary_table(results)

    if args.output and results:
        output_data = [json.loads(r.to_json()) for r in results]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
