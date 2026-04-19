"""
state_space.py — State Representation & Reduction for the JSSP DP Solver

Implements the following concepts from Gromicho et al. (2012):
  - Operation, Job, Machine data structures
  - Ordered partial sequences  (Definition 3)
  - Expansion rules            (Definition 4)
  - State key representation using job progress vectors
    — reduces 2^{nm} possible subsets to (m+1)^n valid subsets
  - Earliest start / completion time computations
  - ξ(T,o) aptitude values     (Section 3.1)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Operation:
    """
    A single operation in the JSSP.

    Attributes
    ----------
    job : int          – Job index (0-based)
    op_index : int     – Position within the job's route (0-based)
    machine : int      – Machine on which this operation runs
    processing_time : int – Duration
    global_id : int    – Unique ID across all operations (row-major)
    """

    job: int
    op_index: int
    machine: int
    processing_time: int
    global_id: int

    def __repr__(self) -> str:
        return (
            f"Op(j{self.job},op{self.op_index},m{self.machine},"
            f"p={self.processing_time},id={self.global_id})"
        )


@dataclass
class JSSPInstance:
    """
    Holds a complete JSSP instance.

    Notation (following Gromicho 2012):
      - J = {j_1, ..., j_n}  jobs
      - M = {m_1, ..., m_m}  machines
      - p_{ij}: processing time of job j on machine i
      - π_j(i): the i-th machine that job j visits
      - O = {o_1, ..., o_{nm}}: all operations

    Parameters
    ----------
    name : str
    n_jobs : int
    n_machines : int
    jobs : list[list[tuple[int,int]]]
        jobs[j] = [(machine, processing_time), ...] in visit order
    """

    name: str
    n_jobs: int
    n_machines: int
    jobs: list[list[tuple[int, int]]]

    # Built during __post_init__
    operations: list[Operation] = field(default_factory=list, init=False)
    ops_by_job: dict[int, list[Operation]] = field(
        default_factory=dict, init=False
    )
    pmax: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.operations = []
        self.ops_by_job = {}
        self.pmax = 0

        gid = 0
        for j in range(self.n_jobs):
            self.ops_by_job[j] = []
            for idx, (machine, ptime) in enumerate(self.jobs[j]):
                op = Operation(
                    job=j,
                    op_index=idx,
                    machine=machine,
                    processing_time=ptime,
                    global_id=gid,
                )
                self.operations.append(op)
                self.ops_by_job[j].append(op)
                self.pmax = max(self.pmax, ptime)
                gid += 1
        
        # Optimization #2: Precompute remaining load for _lb_estimate
        # remaining_load[j][k][m] = total processing time of job j on machine m
        # from operation k onwards
        self.remaining_load: list[list[list[int]]] = []
        for j in range(self.n_jobs):
            ops = self.ops_by_job[j]
            n = len(ops)
            # Suffix sum by machine
            table = [[0] * self.n_machines for _ in range(n + 1)]
            for k in range(n - 1, -1, -1):
                op = ops[k]
                for m in range(self.n_machines):
                    table[k][m] = table[k + 1][m]
                table[k][op.machine] += op.processing_time
            self.remaining_load.append(table)

    def get_operation(self, job: int, op_index: int) -> Operation:
        """Return the operation for job *job* at position *op_index*."""
        return self.ops_by_job[job][op_index]

    def get_expandable_operations(
        self, current_ops: frozenset[Operation]
    ) -> list[Operation]:
        """
        ε(S): Return all operations that can expand S.

        An operation o can expand S iff:
          - o ∉ S
          - All predecessors of o in the same job are already in S
        """
        # Determine progress per job  (how many ops already scheduled)
        progress = self._job_progress(current_ops)
        result: list[Operation] = []
        for j in range(self.n_jobs):
            next_idx = progress[j]
            if next_idx < self.n_machines:
                result.append(self.ops_by_job[j][next_idx])
        return result

    def full_state_key(self) -> "StateKey":
        """Return the StateKey corresponding to all operations scheduled."""
        return StateKey(
            progress=tuple([self.n_machines] * self.n_jobs)
        )

    def ops_from_state_key(self, key: "StateKey") -> frozenset[Operation]:
        """
        Reconstruct the scheduled operation set from a progress-vector key.

        Since valid states always contain the first k_j operations of each job,
        the full set can be recovered directly from the progress vector.
        """
        ops: list[Operation] = []
        for job, scheduled_count in enumerate(key.progress):
            ops.extend(self.ops_by_job[job][:scheduled_count])
        return frozenset(ops)

    def _job_progress(
        self, current_ops: frozenset[Operation]
    ) -> list[int]:
        """For each job, count how many operations are in current_ops."""
        progress = [0] * self.n_jobs
        for op in current_ops:
            progress[op.job] += 1
        return progress


# ---------------------------------------------------------------------------
# State Key  —  compact representation of operation subset S
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StateKey:
    """
    Compact representation of a subset S ⊆ O.

    Because each job's operations must be added in order, S is fully
    characterised by a *progress vector*  (k_1, ..., k_n)  where k_j
    is the number of operations of job j already in S.

    This reduces 2^{nm} possible subsets to at most (m+1)^n valid ones
    (Section 4.1, Gromicho 2012).
    """

    progress: tuple[int, ...]  # (k_1, k_2, ..., k_n)

    @property
    def size(self) -> int:
        """Total number of operations in this state."""
        return sum(self.progress)

    @classmethod
    def from_ops(
        cls, ops: frozenset[Operation], n_jobs: int | None = None
    ) -> "StateKey":
        """Build a StateKey from a set of operations."""
        if n_jobs is None:
            if not ops:
                return cls(progress=())
            n_jobs = max(op.job for op in ops) + 1

        progress = [0] * n_jobs
        for op in ops:
            progress[op.job] += 1
        return cls(progress=tuple(progress))

    @property
    def ops(self) -> frozenset[Operation]:
        """
        NOTE: This is a placeholder — in practice we should not
        reconstruct the frozenset from the key.  The solver passes
        op sets alongside keys where needed.
        """
        raise NotImplementedError(
            "Use the explicit op set tracked by the solver."
        )


# We override the StateKey.ops property so that callers that need the
# actual frozenset pass it through the solver.  For the state key
# used purely as a dict key, the progress tuple suffices.


# ---------------------------------------------------------------------------
# Ordered Partial Sequence
# ---------------------------------------------------------------------------
@dataclass
class OrderedPartialSequence:
    """
    An ordered partial sequence T as defined in Definition 3 of
    Gromicho (2012).

    Stores:
      - The list of operations in order
      - Cmax(T): makespan of the partial schedule
      - Machine completion times: when each machine finishes its last op in T
      - Job completion times: when each job finishes its last op in T
      - The last machine i*(T) for ordering tie-breaks
      - job_progress: how many ops of each job are scheduled (avoids recomputation)
    """

    operations: list[Operation]
    cmax: int
    machine_end: dict[int, int]    # machine → completion time
    job_end: dict[int, int]        # job → completion time
    last_machine: int              # i*(T) — machine of last operation
    job_progress: list[int]        # job_progress[j] = #ops of job j in sequence

    @classmethod
    def create_single(
        cls, op: Operation, inst: JSSPInstance
    ) -> "OrderedPartialSequence":
        """Create a sequence containing a single operation."""
        machine_end = {m: 0 for m in range(inst.n_machines)}
        job_end = {j: 0 for j in range(inst.n_jobs)}
        machine_end[op.machine] = op.processing_time
        job_end[op.job] = op.processing_time
        progress = [0] * inst.n_jobs
        progress[op.job] = 1
        return cls(
            operations=[op],
            cmax=op.processing_time,
            machine_end=machine_end,
            job_end=job_end,
            last_machine=op.machine,
            job_progress=progress,
        )

    def earliest_start(self, op: Operation, inst: JSSPInstance) -> int:
        """
        c(T, o): earliest time operation *op* can start if appended to T.

        Must wait for:
          1) The machine to be free  → machine_end[op.machine]
          2) The job's previous op   → job_end[op.job]
        """
        return max(
            self.machine_end.get(op.machine, 0),
            self.job_end.get(op.job, 0),
        )

    def xi_value(self, op: Operation, inst: JSSPInstance) -> int:
        """
        ξ(T, o) — the aptitude value (Section 3.1):

          ξ(T,o) = c(T,o) + p(o)   if o ∈ Z(T)    [ordered expansion]
                 = Cmax(T) + p(o)   otherwise

        Here we compute it generally; the caller decides if o ∈ Z(T).
        """
        c = self.earliest_start(op, inst)
        completion = c + op.processing_time

        # Check if T+o would be ordered
        if completion > self.cmax:
            return completion
        elif completion == self.cmax and op.machine > self.last_machine:
            return completion
        else:
            # o ∉ Z(T): use the upper bound
            return self.cmax + op.processing_time

    def expand_with(
        self, op: Operation, inst: JSSPInstance
    ) -> "OrderedPartialSequence":
        """
        Create a new ordered partial sequence T + o.

        Pre-condition: o ∈ Z(T)  (the caller must ensure this).
        """
        new_ops = self.operations + [op]

        # Compute new machine/job end times
        new_machine_end = dict(self.machine_end)
        new_job_end = dict(self.job_end)

        start = max(
            new_machine_end.get(op.machine, 0),
            new_job_end.get(op.job, 0),
        )
        end = start + op.processing_time

        new_machine_end[op.machine] = end
        new_job_end[op.job] = end

        new_cmax = max(self.cmax, end)

        new_progress = list(self.job_progress)
        new_progress[op.job] += 1

        return OrderedPartialSequence(
            operations=new_ops,
            cmax=new_cmax,
            machine_end=new_machine_end,
            job_end=new_job_end,
            last_machine=op.machine,
            job_progress=new_progress,
        )

    def get_op_set(self) -> frozenset[Operation]:
        """Return the frozenset of all operations in this sequence."""
        return frozenset(self.operations)

    def __repr__(self) -> str:
        ids = [op.global_id for op in self.operations]
        return f"Seq(ops={ids}, Cmax={self.cmax})"
