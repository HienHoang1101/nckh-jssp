"""
Run GT solver per-instance via subprocess so a crash on one instance
does not abort the entire benchmark batch.
Usage: python scripts/run_gt_safe.py <rule> <output.json>
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


def run_instance(instance: str, rule: str) -> dict | None:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        r = subprocess.run(
            ["python", "run.py", "gt", instance, "--rule", rule, "--output", tmp_path],
            capture_output=True,
            timeout=120,
        )
        if r.returncode != 0:
            err = r.stderr.decode(errors="replace").strip().splitlines()
            last_err = err[-1] if err else "unknown error"
            return {
                "instance": instance,
                "rule": rule,
                "makespan": None,
                "bks": None,
                "gap_vs_bks_pct": None,
                "validation_passed": False,
                "error": last_err,
            }
        if not os.path.exists(tmp_path):
            return {
                "instance": instance,
                "rule": rule,
                "makespan": None,
                "bks": None,
                "gap_vs_bks_pct": None,
                "validation_passed": False,
                "error": "no output (instance not supported by GT)",
            }
        with open(tmp_path) as f:
            data = json.load(f)
        return data[0] if data else None
    except subprocess.TimeoutExpired:
        return {
            "instance": instance, "rule": rule,
            "makespan": None, "bks": None, "gap_vs_bks_pct": None,
            "validation_passed": False, "error": "subprocess timeout",
        }
    except Exception as e:
        return {
            "instance": instance, "rule": rule,
            "makespan": None, "bks": None, "gap_vs_bks_pct": None,
            "validation_passed": False, "error": str(e),
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/run_gt_safe.py <rule> <output.json>", file=sys.stderr)
        sys.exit(1)

    rule, output_path = sys.argv[1], sys.argv[2]
    results = []
    errors = 0

    for inst in INSTANCES:
        result = run_instance(inst, rule)
        if result is not None:
            results.append(result)
            if result.get("error"):
                errors += 1
                print(f"  FAIL {inst}: {result['error']}", file=sys.stderr)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    ok = len(results) - errors
    print(f"GT {rule}: {ok}/{len(INSTANCES)} ok, {errors} errors → {output_path}")


if __name__ == "__main__":
    main()
