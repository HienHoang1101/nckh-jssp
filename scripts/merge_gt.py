"""Merge per-rule GT JSON files into a single gt_results.json."""
import json
import glob
import sys

files = sorted(glob.glob("results/gt_parts/gt_*.json"))
if not files:
    print("ERROR: No GT part files found in results/gt_parts/", file=sys.stderr)
    sys.exit(1)

merged = []
for fpath in files:
    with open(fpath) as f:
        merged.extend(json.load(f))

with open("results/gt_results.json", "w") as f:
    json.dump(merged, f, indent=2)

n_rules = len(set(r["rule"] for r in merged))
n_instances = len(merged) // n_rules if n_rules else 0
print(f"GT merged: {len(merged)} rows ({n_rules} rules x {n_instances} instances)")
