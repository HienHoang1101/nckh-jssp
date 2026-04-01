"""Disjunctive Graph for JSSP. Brucker et al. (1994), Carlier & Pinson (1989)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from collections import deque


@dataclass
class Operation:
    job: int; pos: int; machine: int; duration: int; op_id: int
    def __repr__(self) -> str:
        return f"O(j{self.job},m{self.machine},d={self.duration},id={self.op_id})"

@dataclass
class JSSPInstance:
    name: str; num_jobs: int; num_machines: int
    operations: list[list[Operation]]
    all_ops: list[Operation] = field(default_factory=list)
    machine_ops: dict[int, list[int]] = field(default_factory=dict)
    bks: Optional[int] = None
    def __post_init__(self) -> None:
        self.all_ops = []
        self.machine_ops = {m: [] for m in range(self.num_machines)}
        for jo in self.operations:
            for op in jo:
                self.all_ops.append(op)
                self.machine_ops[op.machine].append(op.op_id)
    @property
    def num_ops(self) -> int: return len(self.all_ops)


class DisjunctiveGraph:
    SOURCE = -1; SINK = -2

    def __init__(self, instance: JSSPInstance) -> None:
        self.instance = instance
        n = instance.num_ops
        self.ops = instance.all_ops
        self.conj_succ = [self.SINK] * n
        self.conj_pred = [self.SOURCE] * n
        for jo in instance.operations:
            for i in range(len(jo) - 1):
                self.conj_succ[jo[i].op_id] = jo[i+1].op_id
                self.conj_pred[jo[i+1].op_id] = jo[i].op_id
        self.disj_succ: list[list[int]] = [[] for _ in range(n)]
        self.disj_pred: list[list[int]] = [[] for _ in range(n)]
        self.heads = [0] * n
        self.tails = [0] * n
        self.fixed_arcs: set[tuple[int,int]] = set()

    def copy(self) -> DisjunctiveGraph:
        g = DisjunctiveGraph.__new__(DisjunctiveGraph)
        g.instance = self.instance; g.ops = self.ops
        g.conj_succ = self.conj_succ; g.conj_pred = self.conj_pred
        g.disj_succ = [l[:] for l in self.disj_succ]
        g.disj_pred = [l[:] for l in self.disj_pred]
        g.heads = self.heads[:]; g.tails = self.tails[:]
        g.fixed_arcs = set(self.fixed_arcs)
        return g

    def fix_arc(self, i: int, j: int) -> None:
        if (i,j) not in self.fixed_arcs:
            self.fixed_arcs.add((i,j))
            self.disj_succ[i].append(j)
            self.disj_pred[j].append(i)

    def is_fixed(self, i: int, j: int) -> bool:
        return (i,j) in self.fixed_arcs

    def compute_heads_and_tails(self) -> bool:
        n = len(self.ops)
        # --- heads (forward topological) ---
        indeg = [0]*n
        for i in range(n):
            if self.conj_pred[i] != self.SOURCE: indeg[i] += 1
            indeg[i] += len(self.disj_pred[i])
        self.heads = [0]*n
        q = deque(i for i in range(n) if indeg[i]==0)
        cnt = 0
        while q:
            i = q.popleft(); cnt += 1
            fi = self.heads[i] + self.ops[i].duration
            cs = self.conj_succ[i]
            if cs != self.SINK:
                self.heads[cs] = max(self.heads[cs], fi)
                indeg[cs] -= 1
                if indeg[cs]==0: q.append(cs)
            for j in self.disj_succ[i]:
                self.heads[j] = max(self.heads[j], fi)
                indeg[j] -= 1
                if indeg[j]==0: q.append(j)
        if cnt != n: return False
        # --- tails (reverse topological) ---
        outdeg = [0]*n
        for i in range(n):
            if self.conj_succ[i] != self.SINK: outdeg[i] += 1
            outdeg[i] += len(self.disj_succ[i])
        self.tails = [0]*n
        q = deque(i for i in range(n) if outdeg[i]==0)
        cnt = 0
        while q:
            i = q.popleft(); cnt += 1
            cp = self.conj_pred[i]
            if cp != self.SOURCE:
                self.tails[cp] = max(self.tails[cp], self.ops[i].duration + self.tails[i])
                outdeg[cp] -= 1
                if outdeg[cp]==0: q.append(cp)
            for j in self.disj_pred[i]:
                self.tails[j] = max(self.tails[j], self.ops[i].duration + self.tails[i])
                outdeg[j] -= 1
                if outdeg[j]==0: q.append(j)
        return cnt == n

    def makespan_lb(self) -> int:
        return max(self.heads[i]+self.ops[i].duration+self.tails[i]
                   for i in range(len(self.ops)))

    def unfixed_on_machine(self, m: int) -> list[tuple[int,int]]:
        ops = self.instance.machine_ops[m]
        pairs = []
        for i in range(len(ops)):
            for j in range(i+1, len(ops)):
                a,b = ops[i],ops[j]
                if not self.is_fixed(a,b) and not self.is_fixed(b,a):
                    pairs.append((a,b))
        return pairs

    def has_unfixed(self) -> bool:
        for m in range(self.instance.num_machines):
            if self.unfixed_on_machine(m):
                return True
        return False

    def most_critical_pair(self) -> Optional[tuple[int,int]]:
        """Carlier & Pinson §3.6: maximize |d_ij - d_ji|, tiebreak min(d_ij,d_ji)."""
        best = None; bv = -1; ba = -1
        for m in range(self.instance.num_machines):
            for a,b in self.unfixed_on_machine(m):
                d_ab = self.heads[a]+self.ops[a].duration+self.ops[b].duration+self.tails[b]
                d_ba = self.heads[b]+self.ops[b].duration+self.ops[a].duration+self.tails[a]
                v = abs(d_ab - d_ba); av = min(d_ab, d_ba)
                if v > bv or (v == bv and av > ba):
                    bv = v; ba = av; best = (a,b)
        return best


def parse_instance(name: str, data: str, bks: Optional[int] = None) -> JSSPInstance:
    lines = data.strip().split('\n')
    hdr = lines[0].strip().split()
    nj, nm = int(hdr[0]), int(hdr[1])
    ops: list[list[Operation]] = []; oid = 0
    for j in range(nj):
        toks = lines[j+1].strip().split()
        row = [Operation(job=j,pos=k,machine=int(toks[2*k]),
                         duration=int(toks[2*k+1]),op_id=oid+k) for k in range(nm)]
        oid += nm; ops.append(row)
    return JSSPInstance(name=name,num_jobs=nj,num_machines=nm,operations=ops,bks=bks)