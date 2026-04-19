"""
Constraint Propagation: Immediate Selection + JPS Lower Bound + Edge-Finding.
Carlier & Pinson (1989), Brucker et al. (1994) §5-6.

Edge-Finding rules implemented:
  NOT-LAST:  if r_min(J∪{i}) + p(J∪{i}) + q_i >= UB → i not last  → q_i >= min_{j∈J}(p_j+q_j)
  NOT-FIRST: if q_min(J∪{i}) + p(J∪{i}) + r_i >= UB → i not first → r_i >= min_{j∈J}(r_j+p_j)
"""
from __future__ import annotations
from algorithms.bnb.graph import DisjunctiveGraph
from itertools import combinations
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


def edge_finding(graph: DisjunctiveGraph, ub: int) -> bool:
    """
    NOT-LAST and NOT-FIRST edge-finding rules (Carlier & Pinson 1989).
    Updates graph.heads and graph.tails in-place.
    Returns False if infeasibility is detected.

    For machines with <= 9 ops: enumerate all subsets J of Omega_m minus {i}.
    For larger machines: check singletons, pairs, triples, and full set only.
    """
    for m in range(graph.instance.num_machines):
        ops = graph.instance.machine_ops[m]
        n = len(ops)
        if n < 2:
            continue

        p = [graph.ops[o].duration for o in ops]
        p_map = {ops[k]: p[k] for k in range(n)}

        # Decide subset sizes: full enum for small, limited for large
        max_others = n - 1
        if max_others <= 8:
            sizes = list(range(1, max_others + 1))
        else:
            sizes = list(range(1, 4)) + [max_others]

        for i in ops:
            others = [o for o in ops if o != i]
            pi = p_map[i]

            for sz in sizes:
                if sz > len(others):
                    break
                for J in combinations(others, sz):
                    # Inline aggregation with plain loops — avoids repeated
                    # generator-object allocation inside the hot inner loop.
                    p_J = 0
                    r_min = graph.heads[i]
                    q_min = graph.tails[i]
                    for j in J:
                        p_J += p_map[j]
                        hj = graph.heads[j]
                        if hj < r_min:
                            r_min = hj
                        tj = graph.tails[j]
                        if tj < q_min:
                            q_min = tj
                    p_total = p_J + pi

                    # NOT-LAST: r_min(J∪{i}) + p(J∪{i}) + q_i >= ub
                    if r_min + p_total + graph.tails[i] >= ub:
                        min_pq = graph.tails[i]  # sentinel — will be beaten by any j
                        for j in J:
                            pq = p_map[j] + graph.tails[j]
                            if pq < min_pq:
                                min_pq = pq
                        if min_pq > graph.tails[i]:
                            graph.tails[i] = min_pq

                    # NOT-FIRST: q_min(J∪{i}) + p(J∪{i}) + r_i >= ub
                    if q_min + p_total + graph.heads[i] >= ub:
                        min_rp = graph.heads[i]  # sentinel
                        for j in J:
                            rp = graph.heads[j] + p_map[j]
                            if rp < min_rp:
                                min_rp = rp
                        if min_rp > graph.heads[i]:
                            graph.heads[i] = min_rp

                    if graph.heads[i] + pi + graph.tails[i] >= ub:
                        return False

    return True


def propagate(graph: DisjunctiveGraph, ub: int) -> bool:
    """Propagate constraints. Returns False if infeasible or LB >= ub."""
    if not graph.compute_heads_and_tails():
        return False
    if graph.makespan_lb() >= ub:
        return False
    if not immediate_selection(graph, ub):
        return False
    if graph.makespan_lb() >= ub:
        return False
    if not edge_finding(graph, ub):
        return False
    if graph.makespan_lb() >= ub:
        return False
    return True


def lower_bound(graph: DisjunctiveGraph) -> int:
    """Max of critical-path LB and JPS LB."""
    return max(graph.makespan_lb(), jps_lower_bound(graph))