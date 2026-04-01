"""
Shifting Bottleneck Heuristic (SBH) for Job Shop Scheduling Problem (JSSP)
===========================================================================

Complete implementation following:
  - Adams, Balas, Zawack (1988) "The Shifting Bottleneck Procedure for Job Shop Scheduling"
  - Pinedo (2016) "Scheduling: Theory, Algorithms, and Systems", Chapter 7
  - Carlier (1982) "The one-machine sequencing problem"
  - Dauzere-Peres & Lasserre (1993) "A modified shifting bottleneck procedure"

Components:
  1. Disjunctive graph representation (conjunctive + disjunctive arcs)
  2. Longest path / critical path computation via topological sort
  3. Release time r_j (head) and tail q_j computation
  4. 1|r_j|Lmax subproblem solved by Carlier's branch-and-bound
     - Schrage's heuristic for upper bounds
     - Preemptive Schrage for lower bounds
  5. Bottleneck selection (machine with maximum Lmax)
  6. Disjunctive arc insertion for selected machine
  7. Re-optimization of all previously scheduled machines
  8. Iteration until all machines are scheduled

Input format: OR-Library (first line: n_jobs n_machines;
              each job line: machine_id proc_time machine_id proc_time ...)

Tested on FT06 benchmark (optimal makespan = 55).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks import BKS, get_available_instances, load_instance


# ============================================================================
# 1. PARSING
# ============================================================================

def parse_input(filename):
    """
    Parse OR-Library format JSSP instance.

    Format:
        Line 1: n_jobs n_machines
        Lines 2..n_jobs+1: machine_id processing_time machine_id processing_time ...

    Returns:
        n_jobs (int), n_machines (int), jobs (list of list of (machine, proc_time))
    """
    with open(filename, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    n_jobs, n_machines = int(lines[0].split()[0]), int(lines[0].split()[1])
    jobs = []
    for i in range(1, n_jobs + 1):
        tokens = list(map(int, lines[i].split()))
        jobs.append([(tokens[k], tokens[k + 1]) for k in range(0, len(tokens), 2)])
    return n_jobs, n_machines, jobs


def instance_to_jobs(instance):
    """Convert a shared benchmark instance to the local SB job format."""
    jobs = []
    for job_ops in instance.operations:
        jobs.append([(op.machine, op.duration) for op in job_ops])
    return instance.num_jobs, instance.num_machines, jobs


def solve_instance(instance_name):
    instance = load_instance(instance_name)
    if instance is None:
        return None
    n_jobs, n_machines, jobs = instance_to_jobs(instance)
    machine_sequences, makespan, graph = shifting_bottleneck(n_jobs, n_machines, jobs)
    valid = validate_schedule(n_jobs, n_machines, jobs, graph)
    optimal = BKS.get(instance_name)
    gap = None if optimal is None else makespan - optimal
    return {
        "instance": instance_name,
        "n_jobs": n_jobs,
        "n_machines": n_machines,
        "jobs": jobs,
        "machine_sequences": machine_sequences,
        "makespan": makespan,
        "graph": graph,
        "validation_passed": valid,
        "bks": optimal,
        "gap_vs_bks": gap,
    }


# ============================================================================
# 2. DISJUNCTIVE GRAPH
# ============================================================================

class DisjunctiveGraph:
    """
    Disjunctive graph representation for JSSP.

    Nodes:
      - 'S': virtual source (start) node, proc_time = 0
      - 'T': virtual sink (terminal) node, proc_time = 0
      - (j, k): operation k of job j

    Arcs:
      - Conjunctive arcs: represent job routing (precedence within a job)
        S -> first_op(j) with weight 0
        (j, k) -> (j, k+1) with weight p_{j,k}
        last_op(j) -> T with weight p_{j, last}
      - Disjunctive arcs: represent machine sequencing (one direction selected)
        (j1, k1) -> (j2, k2) with weight p_{j1,k1} when j1 precedes j2 on a machine
    """

    def __init__(self, n_jobs, n_machines, jobs):
        self.n_jobs = n_jobs
        self.n_machines = n_machines
        self.jobs = jobs

        # Build operation metadata
        self.op_info = {}                     # (j,k) -> (machine, proc_time)
        self.machine_ops = defaultdict(list)  # machine -> list of (j,k)
        self.proc_time = {'S': 0, 'T': 0}    # node -> processing time

        for j in range(n_jobs):
            for k in range(len(jobs[j])):
                m, p = jobs[j][k]
                self.op_info[(j, k)] = (m, p)
                self.machine_ops[m].append((j, k))
                self.proc_time[(j, k)] = p

        # State of scheduled machines
        self.scheduled_machines = set()
        self.machine_sequence = {}  # machine -> ordered list of (j,k)

        self._build_adjacency()

    def _build_adjacency(self):
        """Rebuild full adjacency list from conjunctive + disjunctive arcs."""
        self.adj = defaultdict(list)

        # Conjunctive arcs (job precedence)
        for j in range(self.n_jobs):
            n_ops = len(self.jobs[j])
            # Source -> first operation
            self.adj['S'].append(((j, 0), 0))
            # Chain within job
            for k in range(n_ops - 1):
                self.adj[(j, k)].append(((j, k + 1), self.proc_time[(j, k)]))
            # Last operation -> sink
            self.adj[(j, n_ops - 1)].append(('T', self.proc_time[(j, n_ops - 1)]))

        # Disjunctive arcs (machine sequencing for scheduled machines)
        for m in self.scheduled_machines:
            seq = self.machine_sequence[m]
            for i in range(len(seq) - 1):
                u, v = seq[i], seq[i + 1]
                self.adj[u].append((v, self.proc_time[u]))

    def all_nodes(self):
        """Return the set of all nodes in the graph."""
        nodes = {'S', 'T'}
        for j in range(self.n_jobs):
            for k in range(len(self.jobs[j])):
                nodes.add((j, k))
        return nodes

    def add_machine(self, machine, sequence):
        """Fix the operation sequence on a machine (insert disjunctive arcs)."""
        self.scheduled_machines.add(machine)
        self.machine_sequence[machine] = list(sequence)
        self._build_adjacency()

    def remove_machine(self, machine):
        """Remove the fixed sequence for a machine (delete disjunctive arcs)."""
        if machine in self.machine_sequence:
            del self.machine_sequence[machine]
        self.scheduled_machines.discard(machine)
        self._build_adjacency()

    def _topological_sort(self):
        """
        Kahn's algorithm for topological sorting.
        Returns the topological order, or None if a cycle exists.
        """
        nodes = self.all_nodes()
        in_deg = {n: 0 for n in nodes}
        for n in nodes:
            for (s, w) in self.adj[n]:
                in_deg[s] += 1

        queue = deque(n for n in nodes if in_deg[n] == 0)
        order = []
        while queue:
            n = queue.popleft()
            order.append(n)
            for (s, w) in self.adj[n]:
                in_deg[s] -= 1
                if in_deg[s] == 0:
                    queue.append(s)

        return order if len(order) == len(nodes) else None

    def compute_heads_tails(self):
        """
        Compute heads (release times) and tails for all nodes.

        head[node] = longest path from S to node = earliest start time of node
        tail[node] = longest path from node to T, including processing time of node

        The makespan = head['T'] = tail['S'].

        For the 1|r_j|Lmax subproblem:
          r_j = head[(j,k)]              (release date)
          q_j = tail[(j,k)] - p_{j,k}    (delivery time / tail without own processing)
          d_j = Cmax(M0) - q_j           (due date)
        """
        order = self._topological_sort()
        if order is None:
            raise ValueError("Graph contains a cycle!")

        nodes = self.all_nodes()

        # Forward pass: head = longest path from S
        head = {n: 0 for n in nodes}
        for n in order:
            for (s, w) in self.adj[n]:
                head[s] = max(head[s], head[n] + w)

        # Backward pass: tail = longest path from node to T (including p_node)
        tail = {n: 0 for n in nodes}
        for n in reversed(order):
            for (s, w) in self.adj[n]:
                tail[n] = max(tail[n], w + tail[s])

        return head, tail

    def compute_makespan(self):
        """Compute the makespan = longest path from S to T."""
        head, _ = self.compute_heads_tails()
        return head['T']

    def has_cycle_with(self, machine, sequence):
        """
        Check whether inserting this sequence for 'machine' would create a cycle.
        Temporarily modifies the graph and checks for topological ordering.
        """
        # Save state
        old_seq = self.machine_sequence.get(machine)
        was_scheduled = machine in self.scheduled_machines

        # Try
        self.add_machine(machine, sequence)
        has_cycle = self._topological_sort() is None

        # Restore
        if was_scheduled and old_seq is not None:
            self.machine_sequence[machine] = old_seq
        else:
            self.scheduled_machines.discard(machine)
            if machine in self.machine_sequence:
                del self.machine_sequence[machine]
        self._build_adjacency()

        return has_cycle


# ============================================================================
# 3. SINGLE MACHINE SUBPROBLEM: 1|r_j|Lmax
# ============================================================================
#
# We use the delivery-time formulation (Carlier 1982):
#   Each job j has release date r_j, processing time p_j, delivery time q_j.
#   Minimize Cmax = max_j (C_j + q_j), where C_j = completion time.
#   Then Lmax = Cmax - Cmax(M0).
#
# Schrage's heuristic: greedy by largest q among ready jobs.
# Preemptive Schrage: lower bound.
# Carlier's B&B: exact algorithm using Schrage + theorem-based branching.
# ============================================================================

def schrage(r, p, q, n):
    """
    Schrage's heuristic for 1|r_j|Lmax (delivery-time formulation).

    At each decision point, among all released jobs, schedule the one with
    the largest delivery time q_j.

    Args:
        r: list of release dates
        p: list of processing times
        q: list of delivery times
        n: number of jobs

    Returns:
        (sequence, cmax, start_times)
        sequence: list of job indices in scheduled order
        cmax: max(C_j + q_j) over all jobs
        start_times: list of start times indexed by job index
    """
    if n == 0:
        return [], 0, []

    remaining = set(range(n))
    seq = []
    starts = [0] * n
    t = min(r[j] for j in remaining)

    while remaining:
        # Find released jobs
        ready = [j for j in remaining if r[j] <= t]
        if not ready:
            t = min(r[j] for j in remaining)
            ready = [j for j in remaining if r[j] <= t]

        # Select job with largest delivery time
        j = max(ready, key=lambda x: q[x])
        starts[j] = t
        seq.append(j)
        remaining.remove(j)
        t += p[j]
        if remaining:
            t = max(t, min(r[jj] for jj in remaining))

    cmax = max(starts[j] + p[j] + q[j] for j in range(n))
    return seq, cmax, starts


def schrage_preemptive(r, p, q, n):
    """
    Preemptive Schrage algorithm (lower bound for 1|r_j|Lmax).

    At each moment, the job with the largest q_j is processed.
    If a new job arrives with a larger q, preemption occurs.

    Returns: lower bound on optimal Cmax.
    """
    if n == 0:
        return 0

    p_rem = list(p)
    done = [False] * n
    cmax = 0
    t = min(r)

    for _ in range(n * n + 10):  # Safety bound
        # Find available jobs
        avail = [j for j in range(n) if r[j] <= t and p_rem[j] > 0 and not done[j]]
        if not avail:
            undone = [j for j in range(n) if not done[j]]
            if not undone:
                break
            t = min(r[j] for j in undone)
            continue

        # Process job with largest q
        j = max(avail, key=lambda x: q[x])

        # Find next preemption point (release of a higher-q job)
        next_preempt = float('inf')
        for jj in range(n):
            if not done[jj] and p_rem[jj] > 0 and r[jj] > t and q[jj] > q[j]:
                next_preempt = min(next_preempt, r[jj])

        delta = min(p_rem[j], next_preempt - t) if next_preempt < float('inf') else p_rem[j]
        if delta <= 0:
            delta = p_rem[j]

        t += delta
        p_rem[j] -= delta

        if p_rem[j] == 0:
            done[j] = True
            cmax = max(cmax, t + q[j])

        if all(done):
            break

    return cmax


def carlier(r_in, p_in, q_in):
    """
    Carlier's branch-and-bound algorithm for 1|r_j|Lmax.

    Based on Carlier (1982) and described in Dauzere-Peres & Lasserre (1993).

    Uses:
      - Schrage's heuristic at each B&B node (upper bound)
      - Preemptive Schrage (lower bound)
      - Branching based on Carlier's theorem:
        If Schrage's schedule is not optimal, there exists a critical job c
        and critical set J such that in the optimal schedule, c is either
        before all of J or after all of J.

    Args:
        r_in, p_in, q_in: lists of release dates, processing times, delivery times

    Returns:
        (best_seq, best_cmax, best_starts)
    """
    n = len(r_in)
    if n == 0:
        return [], 0, []
    if n == 1:
        return [0], r_in[0] + p_in[0] + q_in[0], [r_in[0]]

    # Initial upper bound from Schrage
    best_seq, best_cmax, best_starts = schrage(list(r_in), list(p_in), list(q_in), n)

    # Check optimality with preemptive lower bound
    lb = schrage_preemptive(list(r_in), list(p_in), list(q_in), n)
    if lb >= best_cmax:
        return best_seq, best_cmax, best_starts

    # Branch-and-bound stack: each entry is (r_list, q_list)
    stack = [(list(r_in), list(q_in))]
    max_iterations = 100000

    for _ in range(max_iterations):
        if not stack:
            break

        r, q = stack.pop()

        # Solve relaxation at this node
        seq, cmax, starts = schrage(r, list(p_in), q, n)

        # Update upper bound
        if cmax < best_cmax:
            best_cmax = cmax
            best_seq = list(seq)
            best_starts = list(starts)

        # Prune if lower bound >= upper bound
        lb = schrage_preemptive(r, list(p_in), q, n)
        if lb >= best_cmax:
            continue

        # Find critical path in Schrage's schedule
        # Build completion times
        comp = [starts[j] + p_in[j] for j in range(n)]

        # Find the job p_job that achieves Cmax (end of critical path)
        p_job = -1
        for j in seq:
            if comp[j] + q[j] == cmax:
                p_job = j

        if p_job == -1:
            continue

        # Build critical block: consecutive jobs with no idle time, ending at p_job
        pos = {j: i for i, j in enumerate(seq)}
        pp = pos[p_job]

        block_start = pp
        for i in range(pp - 1, -1, -1):
            prev_job = seq[i]
            next_job = seq[i + 1]
            if starts[prev_job] + p_in[prev_job] >= starts[next_job]:
                block_start = i
            else:
                break

        block = [seq[i] for i in range(block_start, pp + 1)]

        # Find critical job c: the LAST job in the block with q[c] < q[p_job]
        # J = all jobs in the block after c
        c_job = -1
        c_pos = -1
        for i in range(len(block) - 1, -1, -1):
            if q[block[i]] < q[p_job]:
                c_job = block[i]
                c_pos = i
                break

        if c_job == -1:
            # No critical job found -> Schrage is optimal for this subproblem
            continue

        J = block[c_pos + 1:]
        if not J:
            continue

        sum_p_J = sum(p_in[j] for j in J)
        min_r_J = min(r[j] for j in J)
        min_q_J = min(q[j] for j in J)

        # Branch 1: c must be processed AFTER all jobs of J
        # Tighten: r_c >= min_r(J) + sum_p(J)
        r1 = list(r)
        q1 = list(q)
        r1[c_job] = max(r[c_job], min_r_J + sum_p_J)
        lb1 = schrage_preemptive(r1, list(p_in), q1, n)
        if lb1 < best_cmax:
            stack.append((r1, q1))

        # Branch 2: c must be processed BEFORE all jobs of J
        # Tighten: q_c >= min_q(J) + sum_p(J)
        r2 = list(r)
        q2 = list(q)
        q2[c_job] = max(q[c_job], min_q_J + sum_p_J)
        lb2 = schrage_preemptive(r2, list(p_in), q2, n)
        if lb2 < best_cmax:
            stack.append((r2, q2))

    return best_seq, best_cmax, best_starts


def solve_one_machine(operations, proc_times, head, tail):
    """
    Solve the 1|r_j|Lmax subproblem for a set of operations on one machine.

    From the disjunctive graph:
      r_j = head[(j,k)]              (longest path from S to operation)
      q_j = tail[(j,k)] - p_{j,k}    (longest path from end of operation to T)
      Cmax_single = max(C_j + q_j)   (minimized by Carlier)
      Lmax = Cmax_single - Cmax(M0)  (where Cmax(M0) = head['T'])

    Args:
        operations: list of (job, op_index) assigned to this machine
        proc_times: dict (j,k) -> processing time
        head: dict node -> longest path from S
        tail: dict node -> longest path to T (including proc time)

    Returns:
        sequence: ordered list of (job, op_index)
        lmax: the minimum Lmax value
    """
    if not operations:
        return [], -float('inf')

    n = len(operations)
    r = [head[op] for op in operations]
    p = [proc_times[op] for op in operations]
    q = [tail[op] - proc_times[op] for op in operations]

    seq_idx, cmax_single, _ = carlier(r, p, q)

    # Map indices back to operations
    sequence = [operations[i] for i in seq_idx]

    cmax_m0 = head['T']
    lmax = cmax_single - cmax_m0

    return sequence, lmax


# ============================================================================
# 4. SHIFTING BOTTLENECK HEURISTIC
# ============================================================================

def shifting_bottleneck(n_jobs, n_machines, jobs):
    """
    Shifting Bottleneck Heuristic (Algorithm 7.2.1, Pinedo 2016).

    Step 1: Set M0 = empty. Graph G has conjunctive arcs only.
    Step 2: For each machine i in M - M0:
            Solve 1|r_j|Lmax with r, d from longest paths in G.
    Step 3: Select bottleneck k = argmax Lmax(i).
            Fix machine k's sequence, insert disjunctive arcs.
    Step 4: Re-optimize all machines in M0 (including k):
            For each machine l in M0, remove its arcs, re-solve, re-insert.
            Repeat for up to max_cycles if improvements found.
    Step 5: If M0 = M, stop. Else go to Step 2.

    The re-optimization follows Adams et al. (1988) with ordering of machines
    by decreasing Lmax value for each re-optimization cycle.

    Returns:
        machine_sequences: dict machine_id -> ordered list of (job, op_index)
        makespan: final Cmax
        graph: the DisjunctiveGraph object with final state
    """
    graph = DisjunctiveGraph(n_jobs, n_machines, jobs)
    all_machines = set(graph.machine_ops.keys())
    M0 = set()  # Set of scheduled machines

    while M0 != all_machines:
        # ---- Step 2: Analyze each unscheduled machine ----
        head, tail = graph.compute_heads_tails()

        results = {}
        for m in all_machines - M0:
            ops = graph.machine_ops[m]
            seq, lmax = solve_one_machine(ops, graph.proc_time, head, tail)
            results[m] = (lmax, seq)

        # ---- Step 3: Bottleneck selection ----
        k = max(results, key=lambda m: results[m][0])
        lmax_k, seq_k = results[k]

        # Insert disjunctive arcs for bottleneck
        graph.add_machine(k, seq_k)
        M0.add(k)

        # ---- Step 4: Re-optimization ----
        # Re-optimize ALL machines in M0 (Adams 1988):
        # "every time after a new machine is sequenced, all previously
        #  established sequences are locally reoptimized"
        #
        # We order by decreasing Lmax (Dauzere-Peres & Lasserre 1993)
        # and repeat for up to max_cycles.
        max_reopt_cycles = 5

        for cycle in range(max_reopt_cycles):
            improved = False

            # Compute Lmax for each machine to determine re-optimization order
            lmax_for_order = {}
            for m in M0:
                old_seq = list(graph.machine_sequence[m])
                graph.remove_machine(m)
                h, t = graph.compute_heads_tails()
                ops = graph.machine_ops[m]
                _, lm = solve_one_machine(ops, graph.proc_time, h, t)
                lmax_for_order[m] = lm
                graph.add_machine(m, old_seq)

            # Re-optimize in order of decreasing Lmax
            reopt_order = sorted(M0, key=lambda m: -lmax_for_order.get(m, 0))

            for m in reopt_order:
                old_seq = list(graph.machine_sequence[m])
                old_makespan = graph.compute_makespan()

                # Remove machine m's disjunctive arcs
                graph.remove_machine(m)

                # Recompute longest paths without machine m
                head, tail = graph.compute_heads_tails()

                # Re-solve single machine subproblem
                ops = graph.machine_ops[m]
                new_seq, new_lmax = solve_one_machine(ops, graph.proc_time, head, tail)

                # Check if new sequence is feasible (no cycle)
                if not graph.has_cycle_with(m, new_seq):
                    graph.add_machine(m, new_seq)
                    new_makespan = graph.compute_makespan()

                    if new_makespan > old_makespan:
                        # Revert if makespan increased
                        graph.remove_machine(m)
                        graph.add_machine(m, old_seq)
                    elif new_makespan < old_makespan:
                        improved = True
                else:
                    # New sequence creates a cycle, keep old
                    graph.add_machine(m, old_seq)

            if not improved:
                break

    final_makespan = graph.compute_makespan()
    return graph.machine_sequence, final_makespan, graph


# ============================================================================
# 5. SCHEDULE COMPUTATION AND OUTPUT
# ============================================================================

def compute_schedule(graph):
    """
    Compute start times for all operations from the disjunctive graph.

    Returns:
        start_times: dict (j,k) -> start time
        makespan: total makespan
    """
    head, _ = graph.compute_heads_tails()
    start_times = {}
    for j in range(graph.n_jobs):
        for k in range(len(graph.jobs[j])):
            start_times[(j, k)] = head[(j, k)]
    return start_times, head['T']


def validate_schedule(n_jobs, n_machines, jobs, graph):
    """
    Validate schedule correctness:
      1. Job precedence constraints
      2. Machine capacity constraints (no overlap)
    """
    start_times, makespan = compute_schedule(graph)
    valid = True

    # Check precedence within each job
    for j in range(n_jobs):
        for k in range(len(jobs[j]) - 1):
            end_k = start_times[(j, k)] + graph.proc_time[(j, k)]
            start_next = start_times[(j, k + 1)]
            if end_k > start_next + 1e-9:
                print(f"  ERROR: Job {j}, op {k} ends at {end_k} but op {k+1} starts at {start_next}")
                valid = False

    # Check no overlap on each machine
    for m in graph.machine_sequence:
        seq = graph.machine_sequence[m]
        for i in range(len(seq) - 1):
            u, v = seq[i], seq[i + 1]
            end_u = start_times[u] + graph.proc_time[u]
            start_v = start_times[v]
            if end_u > start_v + 1e-9:
                print(f"  ERROR: Machine {m}, {u} ends at {end_u} but {v} starts at {start_v}")
                valid = False

    return valid


def print_results(n_jobs, n_machines, jobs, machine_sequences, makespan, graph):
    """Print the complete schedule results."""
    start_times, _ = compute_schedule(graph)

    print("=" * 65)
    print("  SHIFTING BOTTLENECK HEURISTIC — FINAL RESULTS")
    print("=" * 65)
    print(f"\n  Makespan (Cmax): {makespan}\n")

    # Machine sequences
    print("  Machine Sequences (job IDs are 0-based):")
    print("  " + "-" * 50)
    for m in sorted(machine_sequences):
        seq_str = " -> ".join(f"J{j}" for j, k in machine_sequences[m])
        print(f"    Machine {m}: {seq_str}")

    # Detailed Gantt-style table
    print(f"\n  {'Mach':<6} {'Job':<5} {'Op':<4} {'Start':<7} {'End':<7} {'Proc':<5}")
    print("  " + "-" * 36)
    for m in sorted(machine_sequences):
        for j, k in machine_sequences[m]:
            p = graph.proc_time[(j, k)]
            st = start_times[(j, k)]
            print(f"  M{m:<4} J{j:<4} {k:<4} {st:<7} {st + p:<7} {p:<5}")

    # Job completion times
    print("\n  Job Completion Times:")
    for j in range(n_jobs):
        last = len(jobs[j]) - 1
        ct = start_times[(j, last)] + graph.proc_time[(j, last)]
        print(f"    Job {j}: {ct}")

    print(f"\n  Makespan (Cmax) = {makespan}")
    print("=" * 65)


# ============================================================================
# 6. MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run the Shifting Bottleneck heuristic on a JSSP benchmark."
    )
    parser.add_argument(
        "instances",
        nargs="*",
        default=["FT06"],
        help="Benchmark name(s) like FT06 LA01 TA01, or a single path to an OR-Library file.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all benchmarks from the shared benchmark store.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available shared benchmarks and exit.",
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
        help="Accepted for CLI consistency; SB does not use a timeout.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Accepted for CLI consistency; SB prints directly to stdout.",
    )
    args = parser.parse_args()

    if args.list:
        print("\n".join(get_available_instances()))
        return

    instance_args = get_available_instances() if args.all else args.instances
    results = []

    for index, instance_arg in enumerate(instance_args):
        instance_path = Path(instance_arg)
        instance_name = instance_path.stem.upper()

        if instance_path.exists():
            print(f"Input file: {instance_path}")
            n_jobs, n_machines, jobs = parse_input(instance_path)
            optimal = BKS.get(instance_name)
            print(f"Instance: {n_jobs} jobs x {n_machines} machines\n")
            print("Job routing:")
            for j in range(n_jobs):
                route = ", ".join(f"(M{m}, p={p})" for m, p in jobs[j])
                print(f"  Job {j}: {route}")
            print("\nRunning Shifting Bottleneck Heuristic...\n")
            machine_sequences, makespan, graph = shifting_bottleneck(n_jobs, n_machines, jobs)
            print_results(n_jobs, n_machines, jobs, machine_sequences, makespan, graph)
            print()
            valid = validate_schedule(n_jobs, n_machines, jobs, graph)
            print(f"  Schedule validation: {'PASSED' if valid else 'FAILED'}")
            if optimal is not None:
                print(f"\n  {instance_name} known best makespan = {optimal}")
                if makespan == optimal:
                    print("  *** BEST KNOWN MAKESPAN ACHIEVED ***")
                else:
                    print(f"  Heuristic result: {makespan} (gap: {makespan - optimal})")
                    print("  (SBH is a heuristic; optimality is not guaranteed)")
            else:
                print(f"\n  Heuristic result: {makespan}")
            results.append(
                {
                    "instance": instance_name,
                    "makespan": makespan,
                    "bks": optimal,
                    "gap_vs_bks": None if optimal is None else makespan - optimal,
                    "validation_passed": valid,
                }
            )
        else:
            instance_name = instance_arg.upper()
            result = solve_instance(instance_name)
            if result is None:
                print(f"Error: benchmark '{instance_name}' not found")
                continue
            results.append(
                {
                    "instance": result["instance"],
                    "makespan": result["makespan"],
                    "bks": result["bks"],
                    "gap_vs_bks": result["gap_vs_bks"],
                    "validation_passed": result["validation_passed"],
                }
            )
            print(f"Benchmark: {result['instance']}")
            print(f"Instance: {result['n_jobs']} jobs x {result['n_machines']} machines\n")
            print("Job routing:")
            for j in range(result["n_jobs"]):
                route = ", ".join(f"(M{m}, p={p})" for m, p in result["jobs"][j])
                print(f"  Job {j}: {route}")
            print("\nRunning Shifting Bottleneck Heuristic...\n")
            print_results(
                result["n_jobs"],
                result["n_machines"],
                result["jobs"],
                result["machine_sequences"],
                result["makespan"],
                result["graph"],
            )
            print()
            print(
                f"  Schedule validation: "
                f"{'PASSED' if result['validation_passed'] else 'FAILED'}"
            )
            if result["bks"] is not None:
                print(f"\n  {result['instance']} known best makespan = {result['bks']}")
                if result["makespan"] == result["bks"]:
                    print("  *** BEST KNOWN MAKESPAN ACHIEVED ***")
                else:
                    print(
                        f"  Heuristic result: {result['makespan']} "
                        f"(gap: {result['gap_vs_bks']})"
                    )
                    print("  (SBH is a heuristic; optimality is not guaranteed)")
            else:
                print(f"\n  Heuristic result: {result['makespan']}")

        if index != len(instance_args) - 1:
            print()

    if results:
        print(f"{'Instance':<12}{'Makespan':>10}{'BKS':>8}{'Gap':>8}{'Valid':>8}")
        print("-" * 46)
        for result in results:
            bks_str = "?" if result["bks"] is None else str(result["bks"])
            gap = result["gap_vs_bks"]
            gap_str = "N/A" if gap is None else str(gap)
            print(
                f"{result['instance']:<12}{result['makespan']:>10}{bks_str:>8}"
                f"{gap_str:>8}{str(result['validation_passed']):>8}"
            )

    if args.output and results:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=2)
        print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
