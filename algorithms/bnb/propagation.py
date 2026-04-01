"""
Constraint Propagation: Immediate Selection + JPS Lower Bound.
Carlier & Pinson (1989), Brucker et al. (1994) §5-6.

Edge-finding removed to avoid buggy over-pruning.
Immediate selection alone is sufficient for FT06/FT10 per Brucker (1994).
"""
from __future__ import annotations
from algorithms.bnb.graph import DisjunctiveGraph
import heapq


def jackson_preemptive(rs: list[int], ps: list[int], qs: list[int]) -> int:
    """1|r_j,q_j,pmtn|Cmax. Returns max(C_j+q_j). O(n log n)."""
    n = len(rs)
    if n == 0: return 0
    order = sorted(range(n), key=lambda i: rs[i])
    pq: list[tuple[int,int,int]] = []  # (-q, rem_p, idx)
    ji = 0; t = rs[order[0]]; cmax = 0
    while pq or ji < n:
        while ji < n and rs[order[ji]] <= t:
            j = order[ji]; heapq.heappush(pq, (-qs[j], ps[j], j)); ji += 1
        if not pq:
            if ji < n: t = rs[order[ji]]; continue
            else: break
        nq, rp, idx = heapq.heappop(pq)
        nxt = rs[order[ji]] if ji < n else t + rp
        avail = nxt - t
        if avail >= rp:
            t += rp; cmax = max(cmax, t + (-nq))
        else:
            t = nxt; heapq.heappush(pq, (nq, rp - avail, idx))
    return cmax


def jps_lower_bound(graph: DisjunctiveGraph) -> int:
    lb = 0
    for m in range(graph.instance.num_machines):
        ops = graph.instance.machine_ops[m]
        if len(ops) < 1: continue
        rs = [graph.heads[i] for i in ops]
        ps = [graph.ops[i].duration for i in ops]
        qs = [graph.tails[i] for i in ops]
        lb = max(lb, jackson_preemptive(rs, ps, qs))
    return lb


def immediate_selection(graph: DisjunctiveGraph, ub: int) -> bool:
    """
    Brucker (1994) §5, Lemma 5.2:
    For ops i,j on same machine, if r_i + p_i + p_j + q_j >= ub
    then i before j is impossible => fix j -> i.

    Returns False if cycle detected (infeasible).
    """
    changed = True
    while changed:
        changed = False
        for m in range(graph.instance.num_machines):
            ops = graph.instance.machine_ops[m]
            for ai in range(len(ops)):
                a = ops[ai]
                ra = graph.heads[a]; pa = graph.ops[a].duration; qa = graph.tails[a]
                for bi in range(ai+1, len(ops)):
                    b = ops[bi]
                    if graph.is_fixed(a,b) or graph.is_fixed(b,a):
                        continue
                    rb = graph.heads[b]; pb = graph.ops[b].duration; qb = graph.tails[b]
                    # Can a be before b? need ra+pa+pb+qb < ub
                    a_before_b_lb = ra + pa + pb + qb
                    b_before_a_lb = rb + pb + pa + qa
                    if a_before_b_lb >= ub and b_before_a_lb >= ub:
                        return False  # Both impossible => infeasible
                    if a_before_b_lb >= ub:
                        # a before b impossible => b must be before a
                        graph.fix_arc(b, a)
                        changed = True
                    elif b_before_a_lb >= ub:
                        # b before a impossible => a must be before b
                        graph.fix_arc(a, b)
                        changed = True
        if changed:
            if not graph.compute_heads_and_tails():
                return False
    return True


def propagate(graph: DisjunctiveGraph, ub: int) -> bool:
    """Propagate constraints. Returns False if infeasible or LB >= ub."""
    if not graph.compute_heads_and_tails():
        return False
    if graph.makespan_lb() >= ub:
        return False
    # Immediate selection (may iterate internally)
    if not immediate_selection(graph, ub):
        return False
    if graph.makespan_lb() >= ub:
        return False
    return True


def lower_bound(graph: DisjunctiveGraph) -> int:
    """Max of critical-path LB and JPS LB."""
    return max(graph.makespan_lb(), jps_lower_bound(graph))