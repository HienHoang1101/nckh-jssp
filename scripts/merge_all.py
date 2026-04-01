"""Merge all solver results into a unified all_results.csv."""
import csv
import json
import glob
import sys


def norm_bnb(row):
    return {
        "instance":       row.get("instance", ""),
        "makespan":       row.get("makespan", ""),
        "bks":            row.get("bks", ""),
        "gap_pct":        row.get("gap_vs_bks_pct", ""),
        "time_s":         row.get("computation_time", ""),
        "optimal_proven": row.get("optimal_proven", ""),
        "timed_out":      "",
        "extra":          json.dumps({"nodes": row.get("nodes_explored", "")}),
    }


def norm_dp(row):
    return {
        "instance":       row.get("instance_name", ""),
        "makespan":       row.get("best_makespan", ""),
        "bks":            row.get("optimal_makespan", ""),
        "gap_pct":        row.get("gap_percent"),
        "time_s":         row.get("computation_time_seconds", ""),
        "optimal_proven": row.get("optimal_proven", ""),
        "timed_out":      row.get("timed_out", ""),
        "extra":          json.dumps({
                              "states":    row.get("states_explored", ""),
                              "memory_mb": row.get("memory_mb", ""),
                              "error":     row.get("error", ""),
                          }),
    }


def norm_gt(row):
    return {
        "instance":       row.get("instance", ""),
        "makespan":       row.get("makespan"),
        "bks":            row.get("bks"),
        "gap_pct":        row.get("gap_vs_bks_pct"),
        "time_s":         "",
        "optimal_proven": "",
        "timed_out":      "",
        "extra":          json.dumps({
                              "rule":  row.get("rule", ""),
                              "error": row.get("error", ""),
                          }),
    }


def norm_sb(row):
    bks = row.get("bks")
    gap_abs = row.get("gap_vs_bks")
    try:
        gap_pct = round(float(gap_abs) / float(bks) * 100, 2) if bks and gap_abs is not None else None
    except (TypeError, ValueError, ZeroDivisionError):
        gap_pct = None
    return {
        "instance":       row.get("instance", ""),
        "makespan":       row.get("makespan"),
        "bks":            bks,
        "gap_pct":        gap_pct,
        "time_s":         "",
        "optimal_proven": "",
        "timed_out":      "",
        "extra":          json.dumps({"valid": row.get("validation_passed", "")}),
    }


FIELDS = ["solver", "instance", "makespan", "bks", "gap_pct",
          "time_s", "optimal_proven", "timed_out", "extra"]

output = []

# BNB: CSV
for fpath in glob.glob("results/**/*bnb*.csv", recursive=True):
    with open(fpath, newline="") as f:
        for row in csv.DictReader(f):
            output.append({"solver": "bnb", **norm_bnb(row)})

# DP, GT, SB: JSON
for solver, norm_fn in [("dp", norm_dp), ("gt", norm_gt), ("sb", norm_sb)]:
    for fpath in glob.glob(f"results/**/*{solver}*.json", recursive=True):
        with open(fpath) as f:
            rows = json.load(f)
        for row in rows:
            output.append({"solver": solver, **norm_fn(row)})

if not output:
    print("WARNING: No results found to merge.", file=sys.stderr)
    sys.exit(0)

with open("results/all_results.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(output)

print(f"Merged {len(output)} rows into results/all_results.csv")

# Summary
solvers = sorted(set(r["solver"] for r in output))
print(f"\n{'Solver':<6} {'Rows':>6} {'Optimal':>8} {'Timeout':>8} {'Avg Gap%':>10}")
print("-" * 42)
for s in solvers:
    sr = [r for r in output if r["solver"] == s]
    n_opt = sum(1 for r in sr if str(r.get("optimal_proven", "")).lower() == "true")
    n_to  = sum(1 for r in sr if str(r.get("timed_out", "")).lower() == "true")
    gaps  = [float(r["gap_pct"]) for r in sr if r.get("gap_pct") not in ("", "None", None)]
    avg_g = f"{sum(gaps)/len(gaps):.2f}" if gaps else "N/A"
    print(f"{s.upper():<6} {len(sr):>6} {n_opt:>8} {n_to:>8} {avg_g:>10}")
