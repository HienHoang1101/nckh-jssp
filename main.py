#!/usr/bin/env python3
"""JSSP B&B Solver CLI. Usage: python main.py FT06"""
from __future__ import annotations
import argparse, json, csv, logging, time
from typing import Optional
from algorithms.bnb.solver import BranchAndBoundSolver, SolverResult
from benchmarks.benchmarks import load_instance, get_available_instances, BKS

def setup_logging(level="INFO"):
    logging.basicConfig(level=getattr(logging,level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

def solve_one(name, timeout=3600.0, log_interval=1000):
    lg = logging.getLogger("jssp_solver")
    inst = load_instance(name)
    if not inst: lg.error(f"'{name}' not found"); return None
    lg.info("="*70)
    lg.info(f"Instance: {name} ({inst.num_jobs}x{inst.num_machines})")
    lg.info(f"BKS: {inst.bks}"); lg.info(f"Timeout: {timeout}s"); lg.info("="*70)
    solver = BranchAndBoundSolver(inst, timeout=timeout, log_interval=log_interval)
    r = solver.solve()
    lg.info("-"*70)
    lg.info(f"Result for {name}:")
    lg.info(f"  Makespan:       {r.makespan}")
    lg.info(f"  BKS:            {r.bks}")
    lg.info(f"  Gap vs BKS:     {r.gap_vs_bks:.2f}%")
    lg.info(f"  Optimal proven: {r.optimal_proven}")
    lg.info(f"  Nodes explored: {r.nodes_explored}")
    lg.info(f"  Time:           {r.computation_time:.3f}s")
    lg.info("-"*70)
    return r

def main():
    p = argparse.ArgumentParser(description="JSSP B&B Solver")
    p.add_argument("instances", nargs="*", default=["FT06"])
    p.add_argument("--all", action="store_true")
    p.add_argument("--timeout", type=float, default=3600.0)
    p.add_argument("--output", "-o", type=str, default=None)
    p.add_argument("--log-level", type=str, default="INFO",
                   choices=["DEBUG","INFO","WARNING","ERROR"])
    p.add_argument("--log-interval", type=int, default=1000)
    p.add_argument("--list", action="store_true")
    args = p.parse_args()
    setup_logging(args.log_level)
    if args.list:
        print("\n".join(get_available_instances()))
        return
    names = get_available_instances() if args.all else args.instances
    results = []; t0 = time.time()
    for nm in names:
        r = solve_one(nm, args.timeout, args.log_interval)
        if r: results.append(r)
    # Summary
    print(f"\n{'Instance':<12}{'Makespan':>10}{'BKS':>8}{'Gap%':>8}"
          f"{'Optimal':>9}{'Nodes':>12}{'Time(s)':>10}")
    print("-"*69)
    for r in results:
        print(f"{r.instance_name:<12}{r.makespan:>10}{str(r.bks) if r.bks else '?':>8}"
              f"{r.gap_vs_bks:>7.2f}%{'Yes' if r.optimal_proven else 'No':>9}"
              f"{r.nodes_explored:>12}{r.computation_time:>10.3f}")
    print("-"*69)
    print(f"Total: {time.time()-t0:.3f}s")
    if args.output:
        data = [r.to_dict() for r in results]
        if args.output.endswith('.csv'):
            with open(args.output,'w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0].keys())); w.writeheader(); w.writerows(data)
        else:
            with open(args.output,'w') as f: json.dump(data,f,indent=2)
        print(f"Saved to {args.output}")

if __name__=="__main__": main()
