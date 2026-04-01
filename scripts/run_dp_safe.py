"""
Run DP solver per-instance via subprocess so a crash (e.g., re-entrant
SIGALRM TimeoutError) on one instance does not abort the entire batch.
Usage: python scripts/run_dp_safe.py <timeout_s> <output.json>
"""
import json
import os
import subprocess
import sys
import tempfile

INSTANCES = (
    ["FT06", "FT10", "FT20"]
    + [f"LA{i:02d}" for i in range(1, 41)]
    + [f"TA{i:02d}" for i in range(1, 51)]
)


def run_instance(instance: str, timeout: int) -> dict | None:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        r = subprocess.run(
            ["python", "run.py", "dp", instance,
             "--timeout", str(timeout), "--output", tmp_path],
            capture_output=True,
            timeout=timeout + 30,   # subprocess hard limit: solver timeout + buffer
        )
        if r.returncode != 0:
            err = r.stderr.decode(errors="replace").strip().splitlines()
            last_err = err[-1] if err else "unknown error"
            return {
                "instance_name": instance,
                "size": "",
                "optimal_makespan": None,
                "best_makespan": None,
                "gap_percent": None,
                "computation_time_seconds": timeout,
                "states_explored": 0,
                "memory_mb": 0.0,
                "optimal_proven": False,
                "timed_out": True,
                "error": last_err,
            }
        if not os.path.exists(tmp_path):
            return None
        with open(tmp_path) as f:
            data = json.load(f)
        return data[0] if data else None
    except subprocess.TimeoutExpired:
        return {
            "instance_name": instance,
            "size": "",
            "optimal_makespan": None,
            "best_makespan": None,
            "gap_percent": None,
            "computation_time_seconds": timeout,
            "states_explored": 0,
            "memory_mb": 0.0,
            "optimal_proven": False,
            "timed_out": True,
            "error": "subprocess hard timeout",
        }
    except Exception as e:
        return {
            "instance_name": instance,
            "size": "",
            "optimal_makespan": None,
            "best_makespan": None,
            "gap_percent": None,
            "computation_time_seconds": 0.0,
            "states_explored": 0,
            "memory_mb": 0.0,
            "optimal_proven": False,
            "timed_out": False,
            "error": str(e),
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/run_dp_safe.py <timeout_s> <output.json>", file=sys.stderr)
        sys.exit(1)

    timeout, output_path = int(sys.argv[1]), sys.argv[2]
    results = []
    errors = 0

    for inst in INSTANCES:
        print(f"  DP {inst} (timeout={timeout}s)...", flush=True)
        result = run_instance(inst, timeout)
        if result is not None:
            results.append(result)
            if result.get("error"):
                errors += 1
                status = "CRASH"
            elif result.get("timed_out"):
                status = "TIMEOUT"
            elif result.get("optimal_proven"):
                status = f"OPTIMAL makespan={result.get('best_makespan')}"
            else:
                status = f"makespan={result.get('best_makespan')}"
            print(f"    → {status}")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    ok = len(results) - errors
    print(f"DP done: {ok}/{len(INSTANCES)} ok, {errors} errors → {output_path}")


if __name__ == "__main__":
    main()
