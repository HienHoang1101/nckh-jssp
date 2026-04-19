"""
Branch and Bound solver for JSSP.
Carlier & Pinson (1989), Brucker et al. (1994).

KEY: Iterative deepening - each B&B pass tries to find solution < current UB.
If no improvement found, optimality is proven.
"""
from __future__ import annotations
import heapq, random, time, logging
from collections import deque
from dataclasses import dataclass, field
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

        # Fallback for zero-duration ops: es == t_star (not < t_star), omega_prime can be empty
        if not omega_prime:
            for oid in omega:
                if instance.all_ops[oid].machine == i_star:
                    omega_prime.append(oid)
                    break

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


def _giffler_thompson_random(instance: JSSPInstance) -> Schedule:
    """
    One randomized Giffler-Thompson pass: within Omega', choose randomly
    instead of by a fixed dispatching rule.  Running many iterations and
    keeping the best gives a much tighter initial UB than 4 fixed rules.
    """
    n = instance.num_ops
    st = [0] * n
    machine_time = [0] * instance.num_machines
    job_time     = [0] * instance.num_jobs
    nxt          = [0] * instance.num_jobs

    for _ in range(n):
        omega = [instance.operations[j][nxt[j]].op_id
                 for j in range(instance.num_jobs) if nxt[j] < instance.num_machines]
        if not omega:
            break

        ec = {}
        for oid in omega:
            op = instance.all_ops[oid]
            ec[oid] = max(machine_time[op.machine], job_time[op.job]) + op.duration

        t_star = min(ec.values())
        i_star = instance.all_ops[next(oid for oid in omega if ec[oid] == t_star)].machine

        omega_prime = [oid for oid in omega
                       if instance.all_ops[oid].machine == i_star
                       and max(machine_time[i_star], job_time[instance.all_ops[oid].job]) < t_star]
        if not omega_prime:
            omega_prime = [oid for oid in omega if instance.all_ops[oid].machine == i_star]

        chosen = random.choice(omega_prime)
        op = instance.all_ops[chosen]
        es = max(machine_time[op.machine], job_time[op.job])
        st[chosen] = es
        machine_time[op.machine] = es + op.duration
        job_time[op.job]         = es + op.duration
        nxt[op.job] += 1

    ms = max(st[i] + instance.all_ops[i].duration for i in range(n))
    return Schedule(start_times=st, makespan=ms)


def randomized_gt_ub(instance: JSSPInstance,
                     time_limit: float = 1.0,
                     min_iters: int = 200) -> Schedule:
    """
    Run randomized GT for up to *time_limit* seconds (at least *min_iters*
    iterations).  Returns the best Schedule found.
    """
    best: Optional[Schedule] = None
    deadline = time.perf_counter() + time_limit
    i = 0
    while i < min_iters or time.perf_counter() < deadline:
        s = _giffler_thompson_random(instance)
        if best is None or s.makespan < best.makespan:
            best = s
        i += 1
    return best  # type: ignore[return-value]


# ---------- Schedule Validation ----------

def verify_schedule(instance: JSSPInstance, start_times: list[int]) -> bool:
    """Return True if the schedule satisfies all JSSP constraints."""
    n = instance.num_ops
    if len(start_times) != n:
        return False
    for job_ops in instance.operations:
        for k in range(len(job_ops) - 1):
            a, b = job_ops[k], job_ops[k + 1]
            if start_times[b.op_id] < start_times[a.op_id] + a.duration:
                return False
    for m in range(instance.num_machines):
        ops_m = sorted(instance.machine_ops[m], key=lambda oid: start_times[oid])
        for k in range(len(ops_m) - 1):
            a = instance.all_ops[ops_m[k]]; b = instance.all_ops[ops_m[k + 1]]
            if start_times[b.op_id] < start_times[a.op_id] + a.duration:
                return False
    return True


# ---------- N1 Tabu Search (Nowicki & Smutnicki 1996) ----------

def _extract_machine_seqs(instance: JSSPInstance,
                           sched: Schedule) -> list[list[int]]:
    """For each machine, return op_ids sorted by start time in *sched*."""
    seqs: list[list[int]] = [[] for _ in range(instance.num_machines)]
    for op in instance.all_ops:
        seqs[op.machine].append(op.op_id)
    for m in range(instance.num_machines):
        seqs[m].sort(key=lambda oid: sched.start_times[oid])
    return seqs


def _eval_seqs(instance: JSSPInstance,
               machine_seqs: list[list[int]]) -> tuple[int, list[int]]:
    """
    Compute (makespan, start_times) for the given machine orderings.
    Runs Kahn's topological sort on the DAG of job + machine precedences.
    Returns (-1, []) on cycle (infeasible).
    """
    n = instance.num_ops
    indeg = [0] * n
    succ: list[list[int]] = [[] for _ in range(n)]
    dur = [op.duration for op in instance.all_ops]

    for job_ops in instance.operations:
        for k in range(len(job_ops) - 1):
            a = job_ops[k].op_id; b = job_ops[k + 1].op_id
            succ[a].append(b); indeg[b] += 1
    for seq in machine_seqs:
        for k in range(len(seq) - 1):
            a = seq[k]; b = seq[k + 1]
            succ[a].append(b); indeg[b] += 1

    heads = [0] * n
    q: deque[int] = deque(i for i in range(n) if indeg[i] == 0)
    cnt = 0
    while q:
        i = q.popleft(); cnt += 1
        fi = heads[i] + dur[i]
        for j in succ[i]:
            if fi > heads[j]: heads[j] = fi
            indeg[j] -= 1
            if indeg[j] == 0: q.append(j)

    if cnt != n:
        return -1, []
    return max(heads[i] + dur[i] for i in range(n)), heads


def _compute_tails(instance: JSSPInstance,
                   machine_seqs: list[list[int]],
                   dur: list[int]) -> list[int]:
    """
    Compute tail[i] = longest path from end of op i to makespan, via reverse
    topological sort.

    For each original arc  a → b:
      - reverse arc is  b → a  (stored in r_adj[b])
      - a's in-degree in the reverse graph = a's out-degree in the original
        (tracked as indeg_rev[a])
    Start the queue from sinks of the original graph (indeg_rev == 0 ↔ no
    successors in the original), then propagate tail values backward.
    """
    n = instance.num_ops
    r_adj: list[list[int]] = [[] for _ in range(n)]
    indeg_rev = [0] * n            # = out-degree in original graph
    for job_ops in instance.operations:
        for k in range(len(job_ops) - 1):
            a = job_ops[k].op_id; b = job_ops[k + 1].op_id
            r_adj[b].append(a)     # reverse arc: b → a
            indeg_rev[a] += 1      # a has one more outgoing in original
    for seq in machine_seqs:
        for k in range(len(seq) - 1):
            a = seq[k]; b = seq[k + 1]
            r_adj[b].append(a)
            indeg_rev[a] += 1
    tails = [0] * n
    q: deque[int] = deque(i for i in range(n) if indeg_rev[i] == 0)
    while q:
        b = q.popleft()
        wb = dur[b] + tails[b]
        for a in r_adj[b]:         # a is a predecessor of b in original
            if wb > tails[a]: tails[a] = wb
            indeg_rev[a] -= 1
            if indeg_rev[a] == 0: q.append(a)
    return tails


def tabu_search_n1(instance: JSSPInstance,
                   initial: Schedule,
                   time_limit: float,
                   tenure: int = 7) -> Schedule:
    """
    N1 Tabu Search for JSSP.

    N1 neighborhood (Nowicki & Smutnicki 1996):
      Swap two *adjacent* operations on the same machine within any
      critical-path block (maximal same-machine run on the critical path).

    Parameters
    ----------
    instance   : JSSP instance
    initial    : starting schedule (from GT or randomized GT)
    time_limit : wall-clock budget in seconds
    tenure     : tabu tenure — a reversed swap (op_b, op_a) is forbidden
                 for this many iterations after applying (op_a, op_b)

    Returns
    -------
    Best Schedule found within the budget.
    """
    deadline = time.perf_counter() + time_limit
    dur = [op.duration for op in instance.all_ops]

    machine_seqs = _extract_machine_seqs(instance, initial)
    cur_ms, cur_heads = _eval_seqs(instance, machine_seqs)
    if cur_ms < 0:
        return initial  # initial was somehow infeasible

    best_ms   = cur_ms
    best_sched = Schedule(start_times=cur_heads[:], makespan=cur_ms)
    best_seqs  = [seq[:] for seq in machine_seqs]

    # tabu[(op_a, op_b)] = expiry iteration — the swap a→b is forbidden until then
    tabu: dict[tuple[int, int], int] = {}
    iteration  = 0
    no_improve = 0
    restart_thresh = max(60, instance.num_ops * 3)

    while time.perf_counter() < deadline:
        iteration += 1

        # ── Identify critical-path blocks ─────────────────────────────
        tails = _compute_tails(instance, machine_seqs, dur)
        is_crit = [cur_heads[i] + dur[i] + tails[i] == cur_ms
                   for i in range(instance.num_ops)]

        # ── Enumerate N1 moves: adjacent critical pairs per machine ───
        best_move_ms   = 10 ** 9
        best_move_info: tuple | None = None  # (m, k, op_a, op_b, new_heads)

        for m, seq in enumerate(machine_seqs):
            for k in range(len(seq) - 1):
                op_a = seq[k]; op_b = seq[k + 1]
                if not (is_crit[op_a] and is_crit[op_b]):
                    continue            # not a critical-block swap

                key = (op_a, op_b)
                is_tabu = tabu.get(key, 0) > iteration

                # Evaluate swap in-place, undo immediately
                seq[k], seq[k + 1] = op_b, op_a
                new_ms, new_heads = _eval_seqs(instance, machine_seqs)
                seq[k], seq[k + 1] = op_a, op_b

                if new_ms < 0:
                    continue

                # Aspiration: override tabu if this beats the global best
                if is_tabu and new_ms >= best_ms:
                    continue

                if new_ms < best_move_ms:
                    best_move_ms   = new_ms
                    best_move_info = (m, k, op_a, op_b, new_heads)

        if best_move_info is None:
            # No admissible critical move at all — force a restart
            no_improve = restart_thresh  # trigger restart immediately
        else:
            # ── Apply chosen move ─────────────────────────────────────
            m, k, op_a, op_b, new_heads = best_move_info
            machine_seqs[m][k], machine_seqs[m][k + 1] = op_b, op_a
            tabu[(op_b, op_a)] = iteration + tenure  # reverse swap is tabu

            cur_ms    = best_move_ms
            cur_heads = new_heads

            if cur_ms < best_ms:
                best_ms    = cur_ms
                best_sched = Schedule(start_times=cur_heads[:], makespan=cur_ms)
                best_seqs  = [seq[:] for seq in machine_seqs]
                no_improve = 0
            else:
                no_improve += 1

        # ── Restart with random perturbation when stuck ───────────────
        if no_improve >= restart_thresh:
            if time.perf_counter() >= deadline:
                break
            # Start from best, apply a few random adjacent swaps to escape
            machine_seqs = [seq[:] for seq in best_seqs]
            n_perturb = max(3, instance.num_ops // 8)
            for _ in range(n_perturb):
                m2 = random.randrange(instance.num_machines)
                s2 = machine_seqs[m2]
                if len(s2) >= 2:
                    k2 = random.randrange(len(s2) - 1)
                    s2[k2], s2[k2 + 1] = s2[k2 + 1], s2[k2]
            new_ms2, new_heads2 = _eval_seqs(instance, machine_seqs)
            if new_ms2 > 0:
                cur_ms = new_ms2; cur_heads = new_heads2
            else:
                machine_seqs = [seq[:] for seq in best_seqs]
                cur_ms = best_ms; cur_heads = best_sched.start_times[:]
            tabu.clear()
            no_improve = 0

        # Prune stale tabu entries to keep dict small
        if iteration % 200 == 0:
            tabu = {kk: v for kk, v in tabu.items() if v > iteration}

    if not verify_schedule(instance, best_sched.start_times):
        logger.error("Tabu Search produced an infeasible schedule — returning initial")
        return initial
    return best_sched


def _schedule_from_graph_rule(graph: DisjunctiveGraph, rule: str) -> Optional[Schedule]:
    """Build feasible schedule respecting all fixed arcs with a given dispatch rule."""
    inst = graph.instance; n = inst.num_ops
    st = [0]*n; comp = [0]*n; mt = [0]*inst.num_machines

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
        es = {}
        for i in ready:
            op = inst.all_ops[i]
            t = mt[op.machine]
            cp = graph.conj_pred[i]
            if cp != DisjunctiveGraph.SOURCE: t = max(t, comp[cp])
            for dp in graph.disj_pred[i]: t = max(t, comp[dp])
            es[i] = t

        mec = min(es[i]+inst.all_ops[i].duration for i in ready)
        im = -1
        for i in ready:
            if es[i]+inst.all_ops[i].duration == mec:
                im = inst.all_ops[i].machine; break
        conf = [i for i in ready if inst.all_ops[i].machine==im and es[i]<mec]
        if not conf: conf = [min(ready, key=lambda i: es[i])]

        if rule == "SPT":
            chosen = min(conf, key=lambda oid: inst.all_ops[oid].duration)
        elif rule == "LPT":
            chosen = max(conf, key=lambda oid: inst.all_ops[oid].duration)
        elif rule == "FCFS":
            chosen = min(conf, key=lambda oid: inst.all_ops[oid].job)
        else:  # MWKR
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


def schedule_from_graph(graph: DisjunctiveGraph) -> Optional[Schedule]:
    """Try multiple dispatch rules, return the schedule with best makespan."""
    best: Optional[Schedule] = None
    for rule in ["MWKR", "SPT", "LPT", "FCFS"]:
        s = _schedule_from_graph_rule(graph, rule)
        if s is not None and (best is None or s.makespan < best.makespan):
            best = s
    return best


def critical_path_and_blocks(graph: DisjunctiveGraph,
                              sched: Schedule) -> list[list[int]]:
    """
    Extract blocks from the critical path of *sched* using actual start times.
    A block = maximal run of consecutive same-machine ops on the critical path,
    size >= 2.  Blocks are returned in critical-path order (first block first).

    For each op i we find the critical predecessor j:
      st[j] + p[j] == st[i]  AND  j is either the conjunctive pred or a
      machine predecessor (another op on the same machine in *sched*).
    """
    n = len(graph.ops)
    st = sched.start_times
    ms = sched.makespan
    p = [graph.ops[i].duration for i in range(n)]

    # For each machine, build a map: finish_time -> op_id
    # so we can quickly find which op finishes at a given time on each machine.
    machine_finish: list[dict[int, int]] = [
        {} for _ in range(graph.instance.num_machines)
    ]
    for i in range(n):
        machine_finish[graph.ops[i].machine][st[i] + p[i]] = i

    # Build critical-predecessor map.
    # Prefer machine predecessor so blocks (same-machine runs) form correctly.
    cpred = [-1] * n
    for i in range(n):
        ti = st[i]
        # Machine predecessor takes priority (needed for block structure)
        m = graph.ops[i].machine
        j = machine_finish[m].get(ti, -1)
        if j != -1 and j != i:
            cpred[i] = j
            continue
        # Fallback: conjunctive predecessor
        cp = graph.conj_pred[i]
        if cp != DisjunctiveGraph.SOURCE and st[cp] + p[cp] == ti:
            cpred[i] = cp

    # Find op(s) completing at makespan; trace path backward
    best_path: list[int] = []
    for e in range(n):
        if st[e] + p[e] != ms:
            continue
        path: list[int] = []
        c = e
        while c != -1:
            path.append(c)
            c = cpred[c]
        path.reverse()
        if len(path) > len(best_path):
            best_path = path

    # Decompose best_path into blocks (maximal same-machine runs, size >= 2)
    blocks: list[list[int]] = []
    if not best_path:
        return blocks
    cur_block = [best_path[0]]
    cur_m = graph.ops[best_path[0]].machine
    for idx in range(1, len(best_path)):
        m = graph.ops[best_path[idx]].machine
        if m == cur_m:
            cur_block.append(best_path[idx])
        else:
            if len(cur_block) >= 2:
                blocks.append(cur_block)
            cur_block = [best_path[idx]]
            cur_m = m
    if len(cur_block) >= 2:
        blocks.append(cur_block)
    return blocks


# ---------- Branch and Bound ----------

@dataclass(order=False)
class BBNode:
    lb: int
    seq: int          # insertion counter for stable heap ordering
    depth: int
    graph: DisjunctiveGraph = field(compare=False)

    def __lt__(self, other: "BBNode") -> bool:
        return (self.lb, self.seq) < (other.lb, other.seq)


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
        self._seq = 0   # tie-break counter for heap ordering

    def _elapsed(self) -> float: return time.time()-self.t0
    def _timeout(self) -> bool: return self._elapsed()>=self.timeout

    def solve(self) -> SolverResult:
        self.t0 = time.time()
        logger.info(f"Solving {self.inst.name}: {self.inst.num_jobs}x{self.inst.num_machines}")

        # Phase 1 — deterministic GT (4 rules, cheap)
        best_s0: Optional[Schedule] = None
        for rule in ["MWKR", "SPT", "LPT", "FCFS"]:
            s = giffler_thompson(self.inst, rule=rule)
            if best_s0 is None or s.makespan < best_s0.makespan:
                best_s0 = s
        self.ub = best_s0.makespan; self.best = best_s0
        logger.info(f"Initial UB (4 GT rules): {self.ub}")

        # Phase 2 — randomized GT: tighten UB before B&B starts.
        # Budget: 5 % of total timeout, min 0.5 s, max 10 s.
        rgt_budget = min(10.0, max(0.5, self.timeout * 0.05))
        rgt = randomized_gt_ub(self.inst, time_limit=rgt_budget)
        if rgt.makespan < self.ub:
            self.ub = rgt.makespan; self.best = rgt
        logger.info(f"UB after randomized GT ({rgt_budget:.1f}s budget): {self.ub}")

        # Phase 3 — N1 Tabu Search: push UB toward optimal before B&B.
        # Budget: 10 % of total timeout, min 1 s, max 60 s.
        if not self._timeout():
            ts_budget = min(60.0, max(1.0, self.timeout * 0.10))
            ts = tabu_search_n1(self.inst, self.best, time_limit=ts_budget)
            if ts.makespan < self.ub:
                self.ub = ts.makespan; self.best = ts
            logger.info(f"UB after Tabu Search ({ts_budget:.1f}s budget): {self.ub}")

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
            improved, exhausted = self._search()
            if not improved:
                # Only declare optimal when the heap was fully drained.
                # A timed-out pass that found no improvement is NOT a proof.
                if exhausted:
                    self.optimal = True
                    logger.info(f"Optimal proven: {self.ub}")
                break
            logger.info(f"Improved to {self.ub}, continuing...")

        return self._result()

    def _make_node(self, graph: DisjunctiveGraph, lb: int, depth: int) -> BBNode:
        self._seq += 1
        return BBNode(lb=lb, seq=self._seq, depth=depth, graph=graph)

    def _search(self) -> tuple[bool, bool]:
        """One B&B pass using best-first search (min-heap by LB).

        Returns
        -------
        (improved, exhausted)
          improved  – True if UB was lowered during this pass.
          exhausted – True if the heap was fully drained (search space proven);
                      False if the pass was cut short by timeout.

        Distinguishing these two cases is critical: a timed-out pass that
        found no improvement must NOT be treated as a proof of optimality.
        """
        ub_at_start = self.ub
        root = DisjunctiveGraph(self.inst)
        if not root.compute_heads_and_tails():
            return False, True
        lb = lower_bound(root)
        if lb >= self.ub:
            return False, True

        heap: list[BBNode] = [self._make_node(root, lb, 0)]
        heapq.heapify(heap)

        while heap and not self._timeout():
            node = heapq.heappop(heap)
            self.nodes += 1

            if self.nodes % self.log_interval == 0:
                logger.info(f"  N={self.nodes} UB={self.ub} LB={node.lb} "
                           f"d={node.depth} heap={len(heap)} t={self._elapsed():.1f}s")

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
            children = self._branch(g, node.depth, h)
            for child in children:
                heapq.heappush(heap, child)

        exhausted = (len(heap) == 0)   # timed-out passes leave nodes behind
        return (self.ub < ub_at_start), exhausted

    def _branch(self, g: DisjunctiveGraph, depth: int,
                h: Optional[Schedule] = None) -> list[BBNode]:
        """
        Try block-based branching (Brucker 1994 §3).
        Fallback: binary disjunction branching (Carlier & Pinson 1989 §3.6).
        h: heuristic schedule already computed (avoids re-computing).
        """
        children: list[BBNode] = []

        # Block-based: reuse existing schedule if provided
        if h is None:
            h = schedule_from_graph(g)
        if h:
            blocks = critical_path_and_blocks(g, h)
            if blocks:
                children = self._branch_blocks(g, blocks, depth)

        # Fallback to disjunction branching
        if not children:
            children = self._branch_pair(g, depth)

        return children

    # ------------------------------------------------------------------
    # Brucker et al. [BJS92/BJS94] specific lower bounds
    # (handbook §10.2.3, p.362). Cheap pre-pruning before child copy.
    # ------------------------------------------------------------------

    @staticmethod
    def _brucker_before_lb(cand: int, others: list[int],
                           g: DisjunctiveGraph) -> int:
        """
        LB when 'cand' moves to the VERY BEGINNING of its block.
        ri + pi + max( max_j(pj+qj),  Σpj + min_j(qj) )   j ∈ others
        """
        if not others:
            return 0
        ri = g.heads[cand]; pi = g.ops[cand].duration
        sum_p  = sum(g.ops[j].duration for j in others)
        max_pq = max(g.ops[j].duration + g.tails[j] for j in others)
        min_q  = min(g.tails[j] for j in others)
        return ri + pi + max(max_pq, sum_p + min_q)

    @staticmethod
    def _brucker_after_lb(cand: int, others: list[int],
                          g: DisjunctiveGraph) -> int:
        """
        LB when 'cand' moves to the VERY END of its block.
        max( max_j(rj+pj),  Σpj + min_j(rj) ) + pi + qi   j ∈ others
        """
        if not others:
            return 0
        qi = g.tails[cand]; pi = g.ops[cand].duration
        sum_p  = sum(g.ops[j].duration for j in others)
        max_rp = max(g.heads[j] + g.ops[j].duration for j in others)
        min_r  = min(g.heads[j] for j in others)
        return max(max_rp, sum_p + min_r) + pi + qi

    def _branch_blocks(self, g: DisjunctiveGraph, blocks: list[list[int]],
                       depth: int) -> list[BBNode]:
        """
        Brucker et al. [BJS92/BJS94] (handbook §10.2.3, p.362):

        For each block B on the critical path generate 2*(|B|-1) children:
          Before-branch (cand → very beginning of B):
              Fix ALL arcs  cand → o  for every o ∈ B, o ≠ cand.
          After-branch  (cand → very end of B):
              Fix ALL arcs  o → cand  for every o ∈ B, o ≠ cand.

        Fixing all intra-block arcs keeps sub-problems non-intersecting
        (no solution explored twice within the same block).

        A tight Brucker-specific lower bound pre-prunes children before
        the expensive graph-copy + topological-sort step.
        """
        children: list[BBNode] = []

        for block in blocks:
            if len(block) < 2:
                continue

            # ── Before-candidates: cand → very BEGINNING of block ────────
            for cand in block[1:]:          # all except current first
                if self._timeout():
                    return children
                others = [o for o in block if o != cand]

                # Cheap Brucker LB pre-prune (no copy required)
                blb = self._brucker_before_lb(cand, others, g)
                if blb >= self.ub:
                    continue

                # Skip if any arc already forces cand to come AFTER an 'other'
                if any(g.is_fixed(o, cand) for o in others):
                    continue

                child = g.copy()
                for o in others:
                    child.fix_arc(cand, o)       # cand → every other in block
                if not child.compute_heads_and_tails():
                    continue
                lb = max(blb, lower_bound(child))
                if lb < self.ub:
                    children.append(self._make_node(child, lb, depth+1))

            # ── After-candidates: cand → very END of block ───────────────
            for cand in block[:-1]:         # all except current last
                if self._timeout():
                    return children
                others = [o for o in block if o != cand]

                blb = self._brucker_after_lb(cand, others, g)
                if blb >= self.ub:
                    continue

                if any(g.is_fixed(cand, o) for o in others):
                    continue

                child = g.copy()
                for o in others:
                    child.fix_arc(o, cand)       # every other → cand
                if not child.compute_heads_and_tails():
                    continue
                lb = max(blb, lower_bound(child))
                if lb < self.ub:
                    children.append(self._make_node(child, lb, depth+1))

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
                    children.append(self._make_node(c, lb, depth+1))
        return children

    def _result(self) -> SolverResult:
        gap = 0.0
        if self.inst.bks and self.inst.bks > 0:
            gap = (self.ub - self.inst.bks)/self.inst.bks*100
        return SolverResult(instance_name=self.inst.name, makespan=self.ub,
            schedule=self.best, computation_time=self._elapsed(),
            nodes_explored=self.nodes, optimal_proven=self.optimal,
            bks=self.inst.bks, gap_vs_bks=gap)