"""
dp_solver.py — Core Dynamic Programming Algorithm for the Job-Shop Scheduling Problem

Implements Algorithm 1 from:
  Gromicho, van Hoorn, Saldanha-da-Gama, Timmer (2012)
  "Solving the job-shop scheduling problem optimally by dynamic programming"
  Computers & Operations Research 39, 2968–2977.

Based on the Bellman equation adapted from:
  Held & Karp (1962)
  "A dynamic programming approach to sequencing problems"
  SIAM Journal of Applied Mathematics 10, 196–210.

Complexity: O((pmax)^{2n} (m+1)^n)  —  exponentially better than brute force O((n!)^m)
"""

from __future__ import annotations

import json
import logging
import signal
import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Optional

from algorithms.dp.state_space import (
    JSSPInstance,
    Operation,
    OrderedPartialSequence,
    StateKey,
)
from algorithms.dp.dominance import DominanceChecker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Timeout mechanism
# ---------------------------------------------------------------------------
class TimeoutError(Exception):
    """Raised when computation exceeds the allowed time budget."""
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("Computation exceeded timeout limit.")


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class DPResult:
    """Stores the result produced by the DP solver."""

    instance_name: str = ""
    size: str = ""
    optimal_makespan: int | None = None
    best_makespan: int | None = None
    gap_percent: float | None = None
    computation_time_seconds: float = 0.0
    states_explored: int = 0
    memory_mb: float = 0.0
    optimal_proven: bool = False
    schedule: list[dict] | None = None
    sequence: list[int] | None = None
    timed_out: bool = False

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, default=str)


# ---------------------------------------------------------------------------
# Main DP Solver  (Algorithm 1 — Gromicho et al. 2012)
# ---------------------------------------------------------------------------
class DPSolver:
    """
    Exact DP solver for the Job-Shop Scheduling Problem.

    Implements the Bellman equation for JSSP with:
      - Ordered partial sequences (Definition 3, 4)
      - Dominance pruning        (Proposition 2)
      - State-space reduction     (Proposition 5)
      - Antichain bounding        (Propositions 7, 8)
    """

    def __init__(
        self,
        instance: JSSPInstance,
        timeout: int = 3600,
        enable_state_reduction: bool = True,
        log_interval: int = 100_000,
    ) -> None:
        self.instance = instance
        self.timeout = timeout
        self.enable_state_reduction = enable_state_reduction
        self.log_interval = log_interval

        self.dominance = DominanceChecker(instance)

        # X̂(S)  →  dict  mapping  StateKey  →  list[OrderedPartialSequence]
        self.xi_hat: dict[StateKey, list[OrderedPartialSequence]] = {}

        self.states_explored: int = 0
        self.total_sequences_generated: int = 0
        self.total_dominated_pruned: int = 0
        self.total_state_reduced: int = 0
        self._start_time: float = 0.0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def solve(self, known_optimal: int | None = None) -> DPResult:
        """
        Run Algorithm 1 from Gromicho (2012).

        Parameters
        ----------
        known_optimal : int | None
            If provided, used to compute the gap.

        Returns
        -------
        DPResult
        """
        result = DPResult(
            instance_name=self.instance.name,
            size=f"{self.instance.n_jobs}x{self.instance.n_machines}",
            optimal_makespan=known_optimal,
        )

        tracemalloc.start()
        self._start_time = time.perf_counter()

        # Set up timeout via SIGALRM (Unix) or fallback polling
        use_signal = _try_set_alarm(self.timeout)

        try:
            self._run_algorithm()
        except TimeoutError:
            logger.warning("Timeout reached after %d seconds.", self.timeout)
            result.timed_out = True
        except Exception:
            logger.exception("Solver encountered an error.")
            raise
        finally:
            if use_signal:
                signal.alarm(0)

        elapsed = time.perf_counter() - self._start_time
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        result.computation_time_seconds = round(elapsed, 3)
        result.memory_mb = round(peak / (1024 * 1024), 1)
        result.states_explored = self.states_explored

        # Extract the optimal solution from X̂(O)
        full_key = self.instance.full_state_key()
        if full_key in self.xi_hat and self.xi_hat[full_key]:
            best = self.xi_hat[full_key][0]
            result.best_makespan = best.cmax
            result.sequence = [op.global_id for op in best.operations]
            result.schedule = self._build_schedule(best)
            result.optimal_proven = not result.timed_out

            if known_optimal is not None and result.best_makespan is not None:
                result.gap_percent = round(
                    100.0
                    * (result.best_makespan - known_optimal)
                    / known_optimal,
                    2,
                )
        else:
            # Return best found so far across all states
            best_seq = self._find_best_complete_sequence()
            if best_seq is not None:
                result.best_makespan = best_seq.cmax
                result.sequence = [op.global_id for op in best_seq.operations]
                result.schedule = self._build_schedule(best_seq)
                if known_optimal is not None:
                    result.gap_percent = round(
                        100.0 * (best_seq.cmax - known_optimal) / known_optimal, 2
                    )

        return result

    # ------------------------------------------------------------------
    # Algorithm 1 — main loop
    # ------------------------------------------------------------------
    def _run_algorithm(self) -> None:
        """
        Algorithm 1 from Gromicho et al. (2012):

        1) Initialize: for each first operation o of each job,
           create a single-operation sequence and store in X̂({o}).
        2) For l = 1 to n*m:
             For each S with |S| = l:
               For each T₁ ∈ X̂(S):
                 For each o ∈ Z(T₁):            # ordered expansions
                   T₁' = T₁ + o
                   Insert T₁' into X̂(S ∪ {o}) applying dominance rules
        """
        inst = self.instance
        n_ops = inst.n_jobs * inst.n_machines  # total operations

        # --- Step 1: Initialise with first operations of each job ---
        first_ops = inst.get_expandable_operations(frozenset())
        for op in first_ops:
            seq = OrderedPartialSequence.create_single(op, inst)
            key = StateKey.from_ops(frozenset([op]), n_jobs=inst.n_jobs)
            self.xi_hat.setdefault(key, [])
            self.xi_hat[key].append(seq)
            self.states_explored += 1
            self.total_sequences_generated += 1

        logger.info(
            "Initialised %d single-operation sequences.", len(first_ops)
        )

        # --- Step 2: Expand level by level ---
        for length in range(1, n_ops):
            # Collect all state keys at current length
            keys_at_length = [
                k for k in list(self.xi_hat.keys()) if k.size == length
            ]

            if not keys_at_length:
                continue

            logger.debug(
                "Level %d: %d state keys to expand.", length, len(keys_at_length)
            )

            for state_key in keys_at_length:
                sequences = list(self.xi_hat.get(state_key, []))
                op_set = inst.ops_from_state_key(state_key)

                for seq in sequences:
                    # Check timeout via polling (fallback for Windows)
                    if (time.perf_counter() - self._start_time) > self.timeout:
                        raise TimeoutError(
                            "Computation exceeded timeout limit."
                        )

                    # --- State-space reduction (Proposition 5) ---
                    if self.enable_state_reduction:
                        if self.dominance.check_state_reduction(seq, op_set, inst):
                            self.total_state_reduced += 1
                            continue

                    # Compute Z(T) — operations giving ordered expansions
                    expandable = inst.get_expandable_operations(op_set)
                    ordered_expansions = self._get_ordered_expansions(
                        seq, expandable
                    )

                    for op in ordered_expansions:
                        new_seq = seq.expand_with(op, inst)
                        self.total_sequences_generated += 1
                        new_key = StateKey.from_ops(
                            op_set | frozenset([op]),
                            n_jobs=inst.n_jobs,
                        )

                        self._insert_with_dominance(new_key, new_seq)
                        self.states_explored += 1

                        if self.states_explored % self.log_interval == 0:
                            elapsed = time.perf_counter() - self._start_time
                            logger.info(
                                "States explored: %d | Sequences in store: %d | "
                                "Dominated pruned: %d | State reduced: %d | "
                                "Elapsed: %.1fs",
                                self.states_explored,
                                sum(len(v) for v in self.xi_hat.values()),
                                self.total_dominated_pruned,
                                self.total_state_reduced,
                                elapsed,
                            )

            # Memory management: clear sequences at this level that
            # are no longer needed (all expansions have been generated)
            if length < n_ops - 1:
                for k in keys_at_length:
                    # Keep for dominance comparison but could free if memory-critical
                    pass

        logger.info(
            "Algorithm complete. Total states explored: %d, "
            "Total sequences generated: %d, Dominated pruned: %d, "
            "State reduced: %d",
            self.states_explored,
            self.total_sequences_generated,
            self.total_dominated_pruned,
            self.total_state_reduced,
        )

    # ------------------------------------------------------------------
    # Ordered expansion check  (Definition 3 / Z(T))
    # ------------------------------------------------------------------
    def _get_ordered_expansions(
        self,
        seq: OrderedPartialSequence,
        expandable_ops: list[Operation],
    ) -> list[Operation]:
        """
        Return the subset Z(T) ⊆ ε(S):
        An operation o ∈ ε(S) is in Z(T) iff T+o is an ordered partial sequence.

        From the paper:
          o ∈ Z(T)  iff  c(T,o) + p(o) > Cmax(T)
                         OR  (c(T,o)+p(o) == Cmax(T)  AND  m(o) > i*(T))

        where i*(T) is the machine of the last operation in T.
        """
        result: list[Operation] = []
        for op in expandable_ops:
            c_to = seq.earliest_start(op, self.instance)
            completion = c_to + op.processing_time
            if completion > seq.cmax:
                result.append(op)
            elif completion == seq.cmax and op.machine > seq.last_machine:
                result.append(op)
        return result

    # ------------------------------------------------------------------
    # Dominance-aware insertion  (Proposition 2)
    # ------------------------------------------------------------------
    def _insert_with_dominance(
        self, key: StateKey, new_seq: OrderedPartialSequence
    ) -> None:
        """
        Insert *new_seq* into X̂(S) identified by *key*, applying
        the dominance relation from Proposition 2:

          T₂ ≻ T₁   iff   ξ(T₂,o) ≤ ξ(T₁,o) ∀o ∈ ε(S), with ≥1 strict.

        If new_seq is dominated by any existing sequence, discard it.
        Otherwise, add it and remove any existing sequences it dominates.
        """
        existing = self.xi_hat.get(key, [])
        expandable = self.instance.get_expandable_operations(
            self.instance.ops_from_state_key(key)
        )

        # Check if new_seq is dominated by an existing sequence
        for ex_seq in existing:
            rel = self.dominance.compare(ex_seq, new_seq, expandable, self.instance)
            if rel == "dominates" or rel == "equal":
                # ex_seq dominates or equals new_seq → discard new_seq
                self.total_dominated_pruned += 1
                return

        # new_seq survives; now remove any existing sequences it dominates
        surviving: list[OrderedPartialSequence] = []
        for ex_seq in existing:
            rel = self.dominance.compare(new_seq, ex_seq, expandable, self.instance)
            if rel == "dominates":
                self.total_dominated_pruned += 1
            else:
                surviving.append(ex_seq)

        surviving.append(new_seq)
        self.xi_hat[key] = surviving

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_schedule(
        self, seq: OrderedPartialSequence
    ) -> list[dict]:
        """Convert a complete ordered sequence into a schedule."""
        inst = self.instance
        machine_time: dict[int, int] = {m: 0 for m in range(inst.n_machines)}
        job_time: dict[int, int] = {j: 0 for j in range(inst.n_jobs)}

        schedule: list[dict] = []
        for op in seq.operations:
            start = max(machine_time[op.machine], job_time[op.job])
            end = start + op.processing_time
            machine_time[op.machine] = end
            job_time[op.job] = end
            schedule.append(
                {
                    "job": op.job,
                    "machine": op.machine,
                    "operation": op.op_index,
                    "start": start,
                    "end": end,
                    "processing_time": op.processing_time,
                }
            )
        return schedule

    def _find_best_complete_sequence(self) -> OrderedPartialSequence | None:
        """Find the best complete sequence across all states (fallback)."""
        total_ops = self.instance.n_jobs * self.instance.n_machines
        best: OrderedPartialSequence | None = None
        for key, seqs in self.xi_hat.items():
            if key.size == total_ops:
                for s in seqs:
                    if best is None or s.cmax < best.cmax:
                        best = s
        return best


# ---------------------------------------------------------------------------
# Signal-based alarm (Unix only)
# ---------------------------------------------------------------------------
def _try_set_alarm(timeout: int) -> bool:
    """Attempt to set SIGALRM; return True if successful."""
    try:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)
        return True
    except (AttributeError, ValueError):
        # Windows or non-main thread
        return False
