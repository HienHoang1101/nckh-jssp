"""
Branch and Bound solver for JSSP.
Carlier & Pinson (1989), Brucker et al. (1994).

KEY: Iterative deepening - each B&B pass tries to find solution < current UB.
If no improvement found, optimality is proven.
"""
from __future__ import annotations
import time, logging
from dataclasses import dataclass
from typing import Optional
from algorithms.bnb.graph import DisjunctiveGraph, JSSPInstance
from algorithms.bnb.propagation import propagate, lower_bound

logger = logging.getLogger("jssp_solver")

@dataclass
class Schedule:
    start_times: list[int]; makespan: int

@dataclass
class SolverResult:
    instance_name: str; makespan: int; schedule: Optional[Schedule]
    computation_time: float; nodes_explored: int; optimal_proven: bool
    bks: Optional[int]; gap_vs_bks: float
    def to_dict(self) -> dict:
        sd = {str(i):t for i,t in enumerate(self.schedule.start_times)} if self.schedule else None
        return {"instance":self.instance_name,"makespan":self.makespan,
                "schedule":sd,"computation_time":round(self.computation_time,3),
                "nodes_explored":self.nodes_explored,"optimal_proven":self.optimal_proven,
                "bks":self.bks,"gap_vs_bks_pct":round(self.gap_vs_bks,2)}


# ---------- Giffler-Thompson (Pinedo 2016 Algorithm 7.1.3) ----------

def giffler_thompson(instance: JSSPInstance, rule: str = "MWKR") -> Schedule:
    n = instance.num_ops
    st = [0]*n
    machine_time = [0]*instance.num_machines
    job_time = [0]*instance.num_jobs
    nxt = [0]*instance.num_jobs  # next operation index per job

    for _ in range(n):
        # Omega: schedulable ops (next in each job that isn't done)
        omega = []
        for j in range(instance.num_jobs):
            if nxt[j] < instance.num_machines:
                omega.append(instance.operations[j][nxt[j]].op_id)
        if not omega:
            break

        # For each op in omega, compute earliest start and completion
        earliest_completion = {}
        for oid in omega:
            op = instance.all_ops[oid]
            es = max(machine_time[op.machine], job_time[op.job])
            earliest_completion[oid] = es + op.duration

        # t* = minimum earliest completion; i* = its machine
        t_star = min(earliest_completion.values())
        i_star = -1
        for oid in omega:
            if earliest_completion[oid] == t_star:
                i_star = instance.all_ops[oid].machine
                break

        # Omega' = ops on machine i* whose earliest start < t*
        omega_prime = []
        for oid in omega:
            op = instance.all_ops[oid]
            if op.machine == i_star:
                es = max(machine_time[op.machine], job_time[op.job])
                if es < t_star:
                    omega_prime.append(oid)

        # Pick from omega' based on dispatching rule
        if rule == "SPT":
            chosen = min(omega_prime, key=lambda oid: instance.all_ops[oid].duration)
        elif rule == "LPT":
            chosen = max(omega_prime, key=lambda oid: instance.all_ops[oid].duration)
        elif rule == "FCFS":
            chosen = min(omega_prime, key=lambda oid: instance.all_ops[oid].job)
        else:  # MWKR (default)
            def remaining_work(oid: int) -> int:
                op = instance.all_ops[oid]
                return sum(instance.operations[op.job][k].duration
                          for k in range(op.pos, instance.num_machines))
            chosen = max(omega_prime, key=remaining_work)

        op = instance.all_ops[chosen]
        es = max(machine_time[op.machine], job_time[op.job])
        st[chosen] = es
        machine_time[op.machine] = es + op.duration
        job_time[op.job] = es + op.duration
        nxt[op.job] += 1

    ms = max(st[i] + instance.all_ops[i].duration for i in range(n))
    return Schedule(start_times=st, makespan=ms)


def schedule_from_graph(graph: DisjunctiveGraph) -> Optional[Schedule]:
    """Build feasible schedule respecting all fixed arcs, using MWR dispatch."""
    inst = graph.instance; n = inst.num_ops
    st = [0]*n; comp = [0]*n; mt = [0]*inst.num_machines

    # Predecessor counting
    pc = [0]*n
    suc: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        cp = graph.conj_pred[i]
        if cp != DisjunctiveGraph.SOURCE:
            pc[i] += 1; suc[cp].append(i)
        for dp in graph.disj_pred[i]:
            pc[i] += 1; suc[dp].append(i)

    ready = [i for i in range(n) if pc[i]==0]
    for _ in range(n):
        if not ready: return None
        # Earliest start
        es = {}
        for i in ready:
            op = inst.all_ops[i]
            t = mt[op.machine]
            cp = graph.conj_pred[i]
            if cp != DisjunctiveGraph.SOURCE: t = max(t, comp[cp])
            for dp in graph.disj_pred[i]: t = max(t, comp[dp])
            es[i] = t

        # Min earliest completion
        mec = min(es[i]+inst.all_ops[i].duration for i in ready)
        # Machine
        im = -1
        for i in ready:
            if es[i]+inst.all_ops[i].duration == mec:
                im = inst.all_ops[i].machine; break
        # Conflict set
        conf = [i for i in ready if inst.all_ops[i].machine==im and es[i]<mec]
        if not conf: conf = [min(ready, key=lambda i: es[i])]

        # MWR
        def rw(oid: int) -> int:
            op = inst.all_ops[oid]
            return sum(inst.operations[op.job][k].duration
                      for k in range(op.pos, inst.num_machines))
        chosen = max(conf, key=rw)
        op = inst.all_ops[chosen]
        st[chosen] = es[chosen]
        comp[chosen] = es[chosen] + op.duration
        mt[op.machine] = comp[chosen]
        ready.remove(chosen)
        for s in suc[chosen]:
            pc[s] -= 1
            if pc[s]==0: ready.append(s)

    return Schedule(start_times=st, makespan=max(comp))


def critical_path_and_blocks(graph: DisjunctiveGraph,
                              sched: Schedule) -> list[list[int]]:
    """
    Get blocks on critical path of a schedule.
    Block = maximal consecutive same-machine ops on critical path, size >= 2.
    """
    n = len(graph.ops)
    st = sched.start_times
    ms = sched.makespan

    # Build critical predecessors
    cpred = [-1]*n
    for i in range(n):
        # Who finishes exactly at st[i]?
        best = -1
        # Conjunctive pred
        cp = graph.conj_pred[i]
        if cp != DisjunctiveGraph.SOURCE:
            if st[cp] + graph.ops[cp].duration == st[i]:
                best = cp
        # Machine pred
        for o in graph.instance.machine_ops[graph.ops[i].machine]:
            if o != i and st[o]+graph.ops[o].duration == st[i]:
                best = o
        cpred[i] = best

    # Find ops at makespan
    ends = [i for i in range(n) if st[i]+graph.ops[i].duration == ms]
    # Trace longest chain
    best_path: list[int] = []
    for e in ends:
        path = []
        c = e
        while c != -1:
            path.append(c); c = cpred[c]
        path.reverse()
        if len(path) > len(best_path):
            best_path = path

    # Decompose into blocks
    if not best_path: return []
    blocks: list[list[int]] = []
    cur = [best_path[0]]; cm = graph.ops[best_path[0]].machine
    for i in range(1, len(best_path)):
        m = graph.ops[best_path[i]].machine
        if m == cm:
            cur.append(best_path[i])
        else:
            if len(cur)>=2: blocks.append(cur)
            cur = [best_path[i]]; cm = m
    if len(cur)>=2: blocks.append(cur)
    return blocks


# ---------- Branch and Bound ----------

@dataclass
class BBNode:
    graph: DisjunctiveGraph; lb: int; depth: int


class BranchAndBoundSolver:
    """
    Iterative B&B (Carlier & Pinson 1989 §3.7):
    Repeatedly search for solutions with makespan < UB.
    When no improvement possible, UB is optimal.
    """
    def __init__(self, instance: JSSPInstance, timeout: float=3600.0,
                 log_interval: int=1000):
        self.inst = instance; self.timeout = timeout
        self.log_interval = log_interval
        self.best: Optional[Schedule] = None
        self.ub = 10**9; self.nodes = 0; self.t0 = 0.0
        self.optimal = False

    def _elapsed(self) -> float: return time.time()-self.t0
    def _timeout(self) -> bool: return self._elapsed()>=self.timeout

    def solve(self) -> SolverResult:
        self.t0 = time.time()
        logger.info(f"Solving {self.inst.name}: {self.inst.num_jobs}x{self.inst.num_machines}")

        # Initial UB: try multiple dispatching rules, take best
        best_s0: Optional[Schedule] = None
        for rule in ["MWKR", "SPT", "LPT", "FCFS"]:
            s = giffler_thompson(self.inst, rule=rule)
            if best_s0 is None or s.makespan < best_s0.makespan:
                best_s0 = s
        self.ub = best_s0.makespan; self.best = best_s0
        logger.info(f"Initial UB (best of 4 GT rules): {self.ub}")

        # Root LB
        g0 = DisjunctiveGraph(self.inst)
        g0.compute_heads_and_tails()
        lb0 = lower_bound(g0)
        logger.info(f"Root LB: {lb0}")

        if lb0 >= self.ub:
            self.optimal = True
            return self._result()

        # Iterative: keep trying to improve
        while not self._timeout():
            logger.info(f"B&B pass: UB={self.ub}, time={self._elapsed():.1f}s")
            improved = self._search()
            if not improved:
                self.optimal = True
                logger.info(f"Optimal proven: {self.ub}")
                break
            logger.info(f"Improved to {self.ub}, continuing...")

        return self._result()

    def _search(self) -> bool:
        """One B&B pass. Returns True if UB was improved."""
        ub_at_start = self.ub
        root = DisjunctiveGraph(self.inst)
        if not root.compute_heads_and_tails():
            return False
        lb = lower_bound(root)
        if lb >= self.ub:
            return False

        stack = [BBNode(graph=root, lb=lb, depth=0)]
        while stack and not self._timeout():
            node = stack.pop()
            self.nodes += 1

            if self.nodes % self.log_interval == 0:
                logger.info(f"  N={self.nodes} UB={self.ub} LB={node.lb} "
                           f"d={node.depth} stk={len(stack)} t={self._elapsed():.1f}s")

            if node.lb >= self.ub:
                continue

            g = node.graph
            if not propagate(g, self.ub):
                continue
            lb = lower_bound(g)
            if lb >= self.ub:
                continue

            # Heuristic solution
            h = schedule_from_graph(g)
            if h and h.makespan < self.ub:
                self.ub = h.makespan; self.best = h
                logger.info(f"  => UB={self.ub} at node {self.nodes} d={node.depth}")

            # If all disjunctions fixed, no further branching needed
            if not g.has_unfixed():
                continue

            # --- Branching ---
            children = self._branch(g, node.depth)
            # DFS: push worst-LB first so best-LB popped first
            children.sort(key=lambda c: c.lb, reverse=True)
            stack.extend(children)

        return self.ub < ub_at_start

    def _branch(self, g: DisjunctiveGraph, depth: int) -> list[BBNode]:
        """
        Try block-based branching (Brucker 1994 §3).
        Fallback: binary disjunction branching (Carlier & Pinson 1989 §3.6).
        """
        children: list[BBNode] = []

        # Block-based: need a heuristic schedule for critical path
        h = schedule_from_graph(g)
        if h:
            blocks = critical_path_and_blocks(g, h)
            if blocks:
                children = self._branch_blocks(g, blocks, depth)

        # Fallback to disjunction branching
        if not children:
            children = self._branch_pair(g, depth)

        return children

    def _branch_blocks(self, g: DisjunctiveGraph, blocks: list[list[int]],
                       depth: int) -> list[BBNode]:
        """
        Brucker (1994) Theorem 3.1:
        To improve, some op in some block must move before first or after last.
        Generate children for ALL blocks (sorted largest first).
        """
        children: list[BBNode] = []
        for block in sorted(blocks, key=len, reverse=True):
            if len(block) < 2: continue
            first = block[0]; last = block[-1]

            # Before-candidates: ops in block[1:] that can go before first
            for cand in block[1:]:
                if self._timeout(): return children
                # Check feasibility: cand -> others. If any other->cand already fixed, skip.
                ok = all(not g.is_fixed(o, cand) for o in block if o != cand)
                if not ok: continue
                child = g.copy()
                for o in block:
                    if o != cand: child.fix_arc(cand, o)
                if not child.compute_heads_and_tails(): continue
                lb = lower_bound(child)
                if lb < self.ub:
                    children.append(BBNode(graph=child, lb=lb, depth=depth+1))

            # After-candidates: ops in block[:-1] that can go after last
            for cand in block[:-1]:
                if self._timeout(): return children
                ok = all(not g.is_fixed(cand, o) for o in block if o != cand)
                if not ok: continue
                child = g.copy()
                for o in block:
                    if o != cand: child.fix_arc(o, cand)
                if not child.compute_heads_and_tails(): continue
                lb = lower_bound(child)
                if lb < self.ub:
                    children.append(BBNode(graph=child, lb=lb, depth=depth+1))

        return children

    def _branch_pair(self, g: DisjunctiveGraph, depth: int) -> list[BBNode]:
        """Binary branching on most critical unfixed pair."""
        pair = g.most_critical_pair()
        if not pair: return []
        a, b = pair
        children: list[BBNode] = []
        for i, j in [(a,b),(b,a)]:
            c = g.copy(); c.fix_arc(i, j)
            if c.compute_heads_and_tails():
                lb = lower_bound(c)
                if lb < self.ub:
                    children.append(BBNode(graph=c, lb=lb, depth=depth+1))
        return children

    def _result(self) -> SolverResult:
        gap = 0.0
        if self.inst.bks and self.inst.bks > 0:
            gap = (self.ub - self.inst.bks)/self.inst.bks*100
        return SolverResult(instance_name=self.inst.name, makespan=self.ub,
            schedule=self.best, computation_time=self._elapsed(),
            nodes_explored=self.nodes, optimal_proven=self.optimal,
            bks=self.inst.bks, gap_vs_bks=gap)