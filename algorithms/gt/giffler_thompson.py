"""
Giffler & Thompson (1960) Algorithm for Job Shop Scheduling Problem (JSSP)

Generates ACTIVE schedules using priority dispatching rules.
Implements the algorithm exactly as described in:
    Giffler, B. and Thompson, G.L. (1960),
    "Algorithms for Solving Production-Scheduling Problems",
    Operations Research, 8(4), pp. 487-503.

Algorithm steps (from paper, pages 496-497):

    1. Enter the completion times of the first operations to produce each
       commodity as given by F.

    2. Set T equal to the smallest completion time so entered.
       (Note: All completion times >= T are tentative and may be changed.)

    3. In each facility block having one or more operations finishing at
       time T, check for conflicts between those operations and operations
       completing at later times.
       The CONFLICT SET consists of:
         (a) all operations ending at time T, AND
         (b) all operations that OVERLAP the operations found in (a).

    4. In a facility block with r (>= 1) operations in the conflict set,
       choose one of the operations. Left-shift this operation if possible.
       Suppose its completion time is T'. Replace the completion times of
       each operation in the conflict set by its operation time plus the
       larger of T' or the arrival time of the job at the facility.
       Leave completion times of jobs not in the conflict set unchanged.

    5. For each new operation assigned in step 4, look in F to see the
       next facility. Enter its completion time plus the new operation time.
       If T' < T, go back to step 3. If T' >= T, go to step 6.

    6. If T is not the largest entry, find T' next larger than T, set T=T',
       go back to step 2.

    7. If T is the largest entry, stop. Makespan = T.

IMPORTANT NOTE ON OPTIMALITY:
    The G&T algorithm generates ONE active schedule per priority rule.
    By Theorem 4 in the paper, the set of ALL active schedules (obtained
    by exploring ALL choices in step 4) contains all optimal schedules.
    However, a SINGLE priority rule selects only ONE path through this
    enumeration tree. No single priority rule guarantees optimality.

    For FT06 (optimal=55):
    - SPT yields Cmax=94 (SPT minimizes mean flow time, not makespan)
    - FCFS yields Cmax=65
    - MWKR yields Cmax=67
    These are all valid active schedules with different makespans.

Priority rules supported: SPT, LPT, MWKR, SRPT, FCFS
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.benchmarks import BKS, load_instance


# =============================================================================
# 1. DATA PARSING
# =============================================================================

def parse_or_library_file(filepath):
    """
    Parse OR-Library format for JSSP.

    Format:
        Line 1: num_jobs num_machines
        Lines 2+: pairs of (machine_id, processing_time) for each operation

    Returns:
        num_jobs: int
        num_machines: int
        jobs: list of lists, where jobs[j] = [(machine, processing_time), ...]
    """
    with open(filepath, 'r') as f:
        lines = f.read().strip().split('\n')

    first_line = lines[0].split()
    num_jobs = int(first_line[0])
    num_machines = int(first_line[1])

    jobs = []
    for i in range(1, num_jobs + 1):
        values = list(map(int, lines[i].split()))
        operations = []
        for k in range(0, len(values), 2):
            machine = values[k]
            proc_time = values[k + 1]
            operations.append((machine, proc_time))
        jobs.append(operations)

    return num_jobs, num_machines, jobs


def instance_to_jobs(instance):
    """Convert a JSSPInstance into the job structure used by GT."""
    jobs = []
    for job_ops in instance.operations:
        jobs.append([(op.machine, op.duration) for op in job_ops])
    return instance.num_jobs, instance.num_machines, jobs


# =============================================================================
# 2. PRIORITY RULES
# =============================================================================

def priority_spt(operation, jobs, next_op_index):
    """SPT: Shortest Processing Time. Minimizes mean flow time."""
    job_id, op_idx = operation
    _, proc_time = jobs[job_id][op_idx]
    return proc_time


def priority_lpt(operation, jobs, next_op_index):
    """LPT: Longest Processing Time. Negative for min-selection."""
    job_id, op_idx = operation
    _, proc_time = jobs[job_id][op_idx]
    return -proc_time


def priority_mwkr(operation, jobs, next_op_index):
    """MWKR: Most Work Remaining (including current op). Negative for min-selection."""
    job_id, op_idx = operation
    remaining = sum(pt for _, pt in jobs[job_id][op_idx:])
    return -remaining


def priority_srpt(operation, jobs, next_op_index):
    """SRPT: Shortest Remaining Processing Time (including current op)."""
    job_id, op_idx = operation
    remaining = sum(pt for _, pt in jobs[job_id][op_idx:])
    return remaining


def priority_fcfs(operation, jobs, next_op_index):
    """FCFS: First Come First Served. Ordered by job index."""
    job_id, _ = operation
    return job_id


PRIORITY_RULES = {
    'SPT': priority_spt,
    'LPT': priority_lpt,
    'MWKR': priority_mwkr,
    'SRPT': priority_srpt,
    'FCFS': priority_fcfs,
}

GT_BENCHMARKS = (
    ["FT06"]
    + [f"LA{i:02d}" for i in range(1, 41)]
    + [f"TA{i:02d}" for i in range(1, 51)]
)


def solve_instance(instance_name, rule):
    instance = load_instance(instance_name)
    if instance is None:
        return None
    num_jobs, num_machines, jobs = instance_to_jobs(instance)
    optimal = BKS.get(instance_name)
    schedule, makespan = giffler_thompson(num_jobs, num_machines, jobs, rule)
    errors = validate_schedule(schedule, num_jobs, num_machines, jobs)
    gap = None if optimal is None else ((makespan - optimal) / optimal) * 100
    return {
        "instance": instance_name,
        "num_jobs": num_jobs,
        "num_machines": num_machines,
        "rule": rule,
        "makespan": makespan,
        "bks": optimal,
        "gap_vs_bks_pct": gap,
        "validation_passed": not errors,
        "validation_errors": errors,
        "schedule": schedule,
        "jobs": jobs,
    }


# =============================================================================
# 3. GIFFLER & THOMPSON ALGORITHM
# =============================================================================

def build_eligible_set(jobs, next_op_index, num_jobs):
    """
    Step 1: Build the set of eligible (schedulable) operations.

    An eligible operation is the NEXT unscheduled operation of each job
    that still has remaining operations. This enforces job precedence:
    operation (j, k) cannot be eligible until operation (j, k-1) is scheduled.

    Returns:
        List of (job_id, op_index) tuples.
    """
    eligible = []
    for j in range(num_jobs):
        if next_op_index[j] < len(jobs[j]):
            eligible.append((j, next_op_index[j]))
    return eligible


def compute_earliest_times(eligible, jobs, job_completion_time, machine_available):
    """
    For each eligible operation, compute:
      - Earliest Start (ES) = max(job_completion_time[j], machine_available[m])
      - Earliest Completion (EC) = ES + processing_time

    The ES respects both:
      (a) Job precedence: cannot start until previous op of same job finishes
      (b) Machine capacity: cannot start until machine is free

    Returns:
        dict: (job_id, op_idx) -> (machine, proc_time, ES, EC)
    """
    info = {}
    for (j, op_idx) in eligible:
        m, p = jobs[j][op_idx]
        es = max(job_completion_time[j], machine_available[m])
        ec = es + p
        info[(j, op_idx)] = (m, p, es, ec)
    return info


def build_conflict_set(eligible, jobs, job_completion_time, machine_available):
    """
    Steps 2-3: Build the conflict set.

    Step 2: T = minimum earliest completion time across all eligible ops.

    Step 3: Identify machine m* where T is achieved.
            The conflict set on m* consists of all eligible operations
            assigned to machine m* whose earliest start time < T.

    Per the paper: "The conflict set of such a facility block will consist
    of (a) all operations ending at time T, and (b) all operations that
    overlap the operations found in (a)."

    An operation on m* with ES < T overlaps because it could start before
    the earliest-finishing operation on m* completes.

    Returns:
        conflict_set: list of (job_id, op_index)
        machine_star: the machine with the conflict
        T: the minimum earliest completion time
    """
    op_info = compute_earliest_times(eligible, jobs, job_completion_time,
                                     machine_available)

    # Step 2: Find T = minimum EC
    T = min(ec for (_, _, _, ec) in op_info.values())

    # Identify machine m* where T is achieved
    machine_star = None
    for (j, op_idx) in eligible:
        m, p, es, ec = op_info[(j, op_idx)]
        if ec == T:
            machine_star = m
            break

    # Step 3: Conflict set = all eligible ops on m* with ES < T
    conflict_set = []
    for (j, op_idx) in eligible:
        m, p, es, ec = op_info[(j, op_idx)]
        if m == machine_star and es < T:
            conflict_set.append((j, op_idx))

    return conflict_set, machine_star, T


def select_operation(conflict_set, jobs, next_op_index, priority_func):
    """
    Step 4 (selection): Choose one operation from the conflict set
    using the specified priority rule.

    Ties are broken by job index (deterministic).

    Returns:
        (job_id, op_index) of the selected operation.
    """
    best_op = min(conflict_set,
                  key=lambda op: (priority_func(op, jobs, next_op_index), op[0]))
    return best_op


def giffler_thompson(num_jobs, num_machines, jobs, rule='SPT'):
    """
    Giffler & Thompson (1960) algorithm for generating an active schedule.

    Parameters:
        num_jobs: number of jobs
        num_machines: number of machines
        jobs: list of lists, jobs[j] = [(machine, proc_time), ...]
        rule: priority rule name (SPT, LPT, MWKR, SRPT, FCFS)

    Returns:
        schedule: dict mapping (job_id, op_index) -> (machine, start, end)
        makespan: Cmax
    """
    priority_func = PRIORITY_RULES[rule]

    # Track state
    next_op_index = [0] * num_jobs         # next op to schedule per job
    job_completion_time = [0] * num_jobs    # when each job's last op finishes
    machine_available = [0] * num_machines  # when each machine becomes free
    schedule = {}
    total_ops = sum(len(job) for job in jobs)

    for _ in range(total_ops):
        # Step 1: Build eligible set
        eligible = build_eligible_set(jobs, next_op_index, num_jobs)

        # Steps 2-3: Build conflict set
        conflict_set, machine_star, T = build_conflict_set(
            eligible, jobs, job_completion_time, machine_available
        )

        # Step 4: Select and schedule one operation
        selected_job, selected_op = select_operation(
            conflict_set, jobs, next_op_index, priority_func
        )

        # Left-shift: schedule at earliest feasible time
        machine, proc_time = jobs[selected_job][selected_op]
        start_time = max(job_completion_time[selected_job],
                         machine_available[machine])
        end_time = start_time + proc_time

        # Record
        schedule[(selected_job, selected_op)] = (machine, start_time, end_time)

        # Update state (Step 4 continued + Step 5)
        job_completion_time[selected_job] = end_time
        machine_available[machine] = end_time
        next_op_index[selected_job] += 1

    # Step 7: Makespan
    makespan = max(end for (_, _, end) in schedule.values())
    return schedule, makespan


# =============================================================================
# 4. VALIDATION
# =============================================================================

def validate_schedule(schedule, num_jobs, num_machines, jobs):
    """
    Validate feasibility and activeness:
    1. Job precedence: ops of each job execute in order
    2. Machine capacity: no overlap on any machine
    3. Processing times and machine assignments match input
    4. Activeness: no operation can start earlier without conflict
    """
    errors = []

    # Check 1: Job precedence
    for j in range(num_jobs):
        for op_idx in range(1, len(jobs[j])):
            _, _, prev_end = schedule[(j, op_idx - 1)]
            _, start, _ = schedule[(j, op_idx)]
            if start < prev_end:
                errors.append(
                    f"PRECEDENCE: Job {j} Op {op_idx} starts at {start} "
                    f"before Op {op_idx-1} ends at {prev_end}")

    # Check 2: Machine capacity
    for m in range(num_machines):
        ops = sorted([(s, e, j, o) for (j, o), (mm, s, e) in schedule.items()
                       if mm == m])
        for i in range(1, len(ops)):
            if ops[i][0] < ops[i-1][1]:
                errors.append(
                    f"OVERLAP: Machine {m}, "
                    f"J{ops[i-1][2]}O{ops[i-1][3]}({ops[i-1][0]}-{ops[i-1][1]}) "
                    f"overlaps J{ops[i][2]}O{ops[i][3]}({ops[i][0]}-{ops[i][1]})")

    # Check 3: Correct machine and processing time
    for j in range(num_jobs):
        for op_idx in range(len(jobs[j])):
            m_exp, p_exp = jobs[j][op_idx]
            m_act, start, end = schedule[(j, op_idx)]
            if m_act != m_exp:
                errors.append(f"MACHINE: Job {j} Op {op_idx}: "
                              f"expected M{m_exp}, got M{m_act}")
            if end - start != p_exp:
                errors.append(f"DURATION: Job {j} Op {op_idx}: "
                              f"expected {p_exp}, got {end-start}")

    # Check 4: Activeness
    for j in range(num_jobs):
        for op_idx in range(len(jobs[j])):
            m, start, end = schedule[(j, op_idx)]
            job_bound = schedule[(j, op_idx-1)][2] if op_idx > 0 else 0
            machine_ops = sorted(
                [(s, e) for (jj, oo), (mm, s, e) in schedule.items()
                 if mm == m and e <= start])
            mach_bound = machine_ops[-1][1] if machine_ops else 0
            earliest = max(job_bound, mach_bound)
            if start > earliest:
                errors.append(
                    f"NOT ACTIVE: Job {j} Op {op_idx} on M{m}: "
                    f"starts at {start}, could start at {earliest}")

    return errors


# =============================================================================
# 5. DISPLAY
# =============================================================================

def print_schedule(schedule, num_jobs, num_machines, jobs, makespan, rule):
    """Print the schedule."""
    print("=" * 70)
    print(f"SCHEDULE (Giffler & Thompson, 1960 - Active Schedule, Rule: {rule})")
    print("=" * 70)

    print(f"\n--- Schedule by Job ---")
    print(f"{'Job':<6}{'Op':<6}{'Machine':<10}{'Start':<10}{'End':<10}{'Proc':<10}")
    print("-" * 52)
    for j in range(num_jobs):
        for op_idx in range(len(jobs[j])):
            machine, start, end = schedule[(j, op_idx)]
            _, proc_time = jobs[j][op_idx]
            print(f"{j:<6}{op_idx:<6}{machine:<10}{start:<10}{end:<10}{proc_time:<10}")

    print(f"\n--- Schedule by Machine ---")
    for m in range(num_machines):
        ops = sorted([(s, e, j, o) for (j, o), (mm, s, e) in schedule.items()
                       if mm == m])
        print(f"\nMachine {m}: ", end="")
        for start, end, j, op_idx in ops:
            print(f"[J{j}-O{op_idx}: {start}-{end}] ", end="")
        print()

    print(f"\n{'=' * 70}")
    print(f"MAKESPAN (Cmax) = {makespan}")
    print(f"{'=' * 70}")


# =============================================================================
# 6. MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run the Giffler-Thompson heuristic on JSSP benchmarks."
    )
    parser.add_argument(
        "instances",
        nargs="*",
        default=["FT06"],
        help="Benchmark name(s), e.g. FT06 LA01 TA01.",
    )
    parser.add_argument(
        "--rule",
        choices=list(PRIORITY_RULES.keys()),
        default="SPT",
        help="Priority rule used for the main schedule report.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all benchmarks supported by GT.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available benchmark instances and exit.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Write JSON results to this file.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Accepted for CLI consistency; GT does not use a timeout.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Accepted for CLI consistency; GT prints directly to stdout.",
    )
    args = parser.parse_args()

    available = [name for name in GT_BENCHMARKS if load_instance(name) is not None]

    if args.list:
        print("\n".join(available))
        return

    instance_names = available if args.all else [name.upper() for name in args.instances]
    results = []

    for instance_name in instance_names:
        if instance_name not in GT_BENCHMARKS:
            print(f"ERROR: benchmark '{instance_name}' is not supported by GT")
            print("Supported set: FT06, LA01-LA40, TA01-TA50")
            continue

        result = solve_instance(instance_name, args.rule)
        if result is None:
            print(f"ERROR: benchmark '{instance_name}' not found")
            print("Supported set: FT06, LA01-LA40, TA01-TA50")
            continue
        results.append(result)

        num_jobs = result["num_jobs"]
        num_machines = result["num_machines"]
        jobs = result["jobs"]
        optimal = result["bks"]
        schedule = result["schedule"]
        makespan = result["makespan"]
        errors = result["validation_errors"]

        print(f"Problem: {instance_name} ({num_jobs} jobs x {num_machines} machines)")
        if optimal is not None:
            print(f"Best known makespan: {optimal}\n")
        else:
            print("Best known makespan: N/A\n")

        print("Job data (machine, processing_time):")
        for j in range(num_jobs):
            ops_str = "  ".join(f"({m},{p})" for m, p in jobs[j])
            print(f"  Job {j}: {ops_str}")

        rule = args.rule
        print(f"\n--- Running G&T with {rule} rule ---\n")
        print_schedule(schedule, num_jobs, num_machines, jobs, makespan, rule)

        print(f"\n--- Validation ---")
        if not errors:
            print("PASSED: Schedule is FEASIBLE and ACTIVE")
        else:
            for err in errors:
                print(f"  ERROR: {err}")

        if optimal is not None:
            gap = ((makespan - optimal) / optimal) * 100
            print(f"\nBest known = {optimal}, Achieved = {makespan}, Gap = {gap:.2f}%")
        else:
            print(f"\nAchieved makespan = {makespan}")

        if optimal is not None:
            print(f"\n{'=' * 70}")
            print(f"COMPARISON OF ALL PRIORITY RULES ON {instance_name}")
            print(f"{'=' * 70}")
            print(f"{'Rule':<10}{'Makespan':<12}{'Gap (%)':<12}{'Note'}")
            print("-" * 55)
        else:
            print(f"\n{'=' * 70}")
            print(f"COMPARISON OF ALL PRIORITY RULES ON {instance_name}")
            print(f"{'=' * 70}")
            print(f"{'Rule':<10}{'Makespan':<12}{'Note'}")
            print("-" * 45)
        notes = {
            'SPT': 'min mean flowtime',
            'LPT': 'longest first',
            'MWKR': 'most work remaining',
            'SRPT': 'shortest remaining',
            'FCFS': 'first come first served',
        }
        for r in ['SPT', 'LPT', 'MWKR', 'SRPT', 'FCFS']:
            _, ms = giffler_thompson(num_jobs, num_machines, jobs, r)
            if optimal is not None:
                g = ((ms - optimal) / optimal) * 100
                print(f"{r:<10}{ms:<12}{g:<12.2f}{notes[r]}")
            else:
                print(f"{r:<10}{ms:<12}{notes[r]}")

        print(f"\nNote: G&T generates one active schedule per rule.")
        print(f"No single priority rule guarantees optimality.")
        print("To find an optimal schedule, full enumeration of step-4 choices is needed")
        print("(Theorem 4, Giffler & Thompson 1960).")
        print()

    if results:
        print(f"{'Instance':<12}{'Rule':<8}{'Makespan':>10}{'BKS':>8}{'Gap%':>8}{'Valid':>8}")
        print("-" * 54)
        for result in results:
            gap = result["gap_vs_bks_pct"]
            gap_str = "N/A" if gap is None else f"{gap:.2f}%"
            bks_str = "?" if result["bks"] is None else str(result["bks"])
            print(
                f"{result['instance']:<12}{result['rule']:<8}{result['makespan']:>10}"
                f"{bks_str:>8}{gap_str:>8}{str(result['validation_passed']):>8}"
            )

    if args.output and results:
        serializable = []
        for result in results:
            item = dict(result)
            item["schedule"] = {
                f"{job}_{op}": {"machine": machine, "start": start, "end": end}
                for (job, op), (machine, start, end) in result["schedule"].items()
            }
            serializable.append(item)
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(serializable, handle, indent=2)
        print(f"Saved to {args.output}")


if __name__ == '__main__':
    main()
