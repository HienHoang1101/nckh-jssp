"""
dominance.py — Dominance Rules & Antichain-Based Pruning

Implements the dominance framework from Gromicho et al. (2012):

  Proposition 2 (Dominance):
    If T₁, T₂ ∈ X(S) and ξ(T₂, o) ≤ ξ(T₁, o)  ∀o ∈ ε(S)
    with at least one strict inequality, then T₂ ≻ T₁.

  Corollary 2:
    Every ordered completion of T₁ is dominated by the same
    (possibly unordered) completion of T₂.

  Proposition 5 (State-Space Reduction):
    If ∃ machine i such that:
      (i)  ∃ oₙ ∈ ε(S,i) with oₙ ∉ Z(T), AND
      (ii) ∀ o ∈ ε(S,i): ξ(T,o) = Cmax(T) + p(o)
    then T can be pruned (an optimal sequence not starting with T exists).

  Antichain bounding (Propositions 7, 8):
    |X̂(S)| = O(pmax^n / √n)  —  from antichain analysis on multisets.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from algorithms.dp.state_space import (
        JSSPInstance,
        Operation,
        OrderedPartialSequence,
    )

logger = logging.getLogger(__name__)


class DominanceChecker:
    """
    Implements dominance comparison and state-space reduction.
    """

    def __init__(self, instance: "JSSPInstance") -> None:
        self.instance = instance

    # ------------------------------------------------------------------
    # Proposition 2: Dominance comparison
    # ------------------------------------------------------------------
    def compare(
        self,
        t_a: "OrderedPartialSequence",
        t_b: "OrderedPartialSequence",
        expandable_ops: list["Operation"],
        inst: "JSSPInstance",
    ) -> Literal["dominates", "dominated", "equal", "incomparable"]:
        """
        Compare two ordered partial sequences over the same operation set S.

        Returns
        -------
        "dominates"    : t_a ≻ t_b  (t_a is strictly better)
        "dominated"    : t_b ≻ t_a  (t_b is strictly better)
        "equal"        : t_a ≅ t_b  (identical ξ-vectors)
        "incomparable" : neither dominates the other (antichain members)
        """
        if not expandable_ops:
            # No expandable ops → compare by Cmax directly
            if t_a.cmax < t_b.cmax:
                return "dominates"
            elif t_a.cmax > t_b.cmax:
                return "dominated"
            else:
                return "equal"

        a_leq_b = True   # ξ(t_a, o) ≤ ξ(t_b, o)  ∀o
        b_leq_a = True   # ξ(t_b, o) ≤ ξ(t_a, o)  ∀o
        a_strict = False  # at least one strict inequality for a
        b_strict = False  # at least one strict inequality for b

        for op in expandable_ops:
            xi_a = t_a.xi_value(op, inst)
            xi_b = t_b.xi_value(op, inst)

            if xi_a > xi_b:
                a_leq_b = False
                b_strict = True
            elif xi_a < xi_b:
                b_leq_a = False
                a_strict = True

        if a_leq_b and b_leq_a:
            # All ξ values equal → T₁ ≅ T₂
            return "equal"
        elif a_leq_b and a_strict:
            # ξ(t_a, o) ≤ ξ(t_b, o) ∀o with ≥1 strict  → t_a ≻ t_b
            return "dominates"
        elif b_leq_a and b_strict:
            # ξ(t_b, o) ≤ ξ(t_a, o) ∀o with ≥1 strict  → t_b ≻ t_a
            return "dominated"
        else:
            return "incomparable"

    # ------------------------------------------------------------------
    # Proposition 5: State-space reduction
    # ------------------------------------------------------------------
    def check_state_reduction(
        self,
        seq: "OrderedPartialSequence",
        op_set: frozenset["Operation"],
        inst: "JSSPInstance",
    ) -> bool:
        """
        Check if the sequence *seq* can be pruned via Proposition 5.

        Condition: ∃ machine i such that
          (i)  ∃ oₙ ∈ ε(S, i) : oₙ ∉ Z(T)
          (ii) ∀ o ∈ ε(S, i) : ξ(T, o) = Cmax(T) + p(o)

        If true, there is an optimal solution that does NOT start with T,
        so T can safely be skipped for expansion.

        Returns
        -------
        True if the sequence should be pruned.
        """
        expandable = inst.get_expandable_operations(op_set)
        if not expandable:
            return False

        # Group expandable operations by machine: ε(S, i)
        by_machine: dict[int, list["Operation"]] = {}
        for op in expandable:
            by_machine.setdefault(op.machine, []).append(op)

        for machine_id, ops_on_machine in by_machine.items():
            # Condition (i): ∃ oₙ ∈ ε(S, i) such that oₙ ∉ Z(T)
            has_non_ordered = False
            # Condition (ii): ∀ o ∈ ε(S, i): ξ(T, o) = Cmax(T) + p(o)
            all_maximal = True

            for op in ops_on_machine:
                xi_val = seq.xi_value(op, inst)
                expected_max = seq.cmax + op.processing_time

                if xi_val != expected_max:
                    all_maximal = False
                    break

                # Check if o ∉ Z(T)
                c = seq.earliest_start(op, inst)
                completion = c + op.processing_time
                is_ordered = (
                    completion > seq.cmax
                    or (completion == seq.cmax and op.machine > seq.last_machine)
                )
                if not is_ordered:
                    has_non_ordered = True

            if all_maximal and has_non_ordered:
                return True

        return False
