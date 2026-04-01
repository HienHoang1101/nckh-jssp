#!/usr/bin/env python3
"""Unified CLI dispatcher for JSSP solvers."""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOLVER_ENTRYPOINTS = {
    "bnb": ROOT / "algorithms" / "bnb" / "main.py",
    "dp": ROOT / "algorithms" / "dp" / "main.py",
    "gt": ROOT / "algorithms" / "gt" / "giffler_thompson.py",
    "sb": ROOT / "algorithms" / "sb" / "shifting_bottleneck.py",
}

SOLVER_DEFAULT_TIMEOUTS = {
    "bnb": "3600",
    "dp": "3600",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a JSSP solver with a unified command."
    )
    parser.add_argument(
        "solver",
        choices=sorted(SOLVER_ENTRYPOINTS.keys()),
        help="Solver to run: bnb, dp, gt, sb.",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the selected solver.",
    )
    parsed = parser.parse_args()

    target = SOLVER_ENTRYPOINTS[parsed.solver]
    forwarded_args = parsed.args
    if forwarded_args and forwarded_args[0] == "--":
        forwarded_args = forwarded_args[1:]

    if (
        parsed.solver in SOLVER_DEFAULT_TIMEOUTS
        and "--timeout" not in forwarded_args
    ):
        forwarded_args = [
            *forwarded_args,
            "--timeout",
            SOLVER_DEFAULT_TIMEOUTS[parsed.solver],
        ]

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    sys.argv = [str(target), *forwarded_args]
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
