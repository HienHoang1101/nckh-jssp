"""
Comprehensive benchmark: Run SB and GT on all 91 instances
FT06 + LA01-LA40 + TA01-TA50
"""
import time
import pandas as pd
from pathlib import Path
import sys

# Import algorithms
from algorithms.gt.giffler_thompson import giffler_thompson, instance_to_jobs as gt_instance_to_jobs, PRIORITY_RULES
from algorithms.sb.shifting_bottleneck import shifting_bottleneck, instance_to_jobs as sb_instance_to_jobs
from benchmarks.benchmarks import load_instance, BKS

# All 91 instances
ALL_INSTANCES = (
    ['FT06'] + 
    [f'LA{i:02d}' for i in range(1, 41)] +  # LA01-LA40
    [f'TA{i:02d}' for i in range(1, 51)]    # TA01-TA50
)

def test_gt_best_rule(instance_name):
    """Test all GT rules and return best result."""
    instance = load_instance(instance_name)
    if instance is None:
        return None
    
    n_jobs, n_machines, jobs = gt_instance_to_jobs(instance)
    bks = BKS.get(instance_name)
    
    best_makespan = float('inf')
    best_rule = None
    best_time = 0
    
    for rule_name in PRIORITY_RULES.keys():
        try:
            start = time.time()
            _, makespan = giffler_thompson(n_jobs, n_machines, jobs, rule_name)
            elapsed = time.time() - start
            
            if makespan < best_makespan:
                best_makespan = makespan
                best_rule = rule_name
                best_time = elapsed
        except Exception as e:
            print(f"    GT-{rule_name} failed: {e}")
            continue
    
    if best_rule is None:
        return None
    
    gap = ((best_makespan - bks) / bks * 100) if bks else None
    optimal = (best_makespan == bks) if bks else False
    
    return {
        'instance': instance_name,
        'size': f"{n_jobs}x{n_machines}",
        'bks': bks,
        'algorithm': 'GT',
        'rule': best_rule,
        'makespan': best_makespan,
        'gap_pct': gap,
        'optimal': optimal,
        'time_s': best_time,
        'success': True
    }

def test_sb(instance_name):
    """Test Shifting Bottleneck on an instance."""
    instance = load_instance(instance_name)
    if instance is None:
        return None
    
    n_jobs, n_machines, jobs = sb_instance_to_jobs(instance)
    bks = BKS.get(instance_name)
    
    start = time.time()
    try:
        _, makespan, _ = shifting_bottleneck(n_jobs, n_machines, jobs)
        elapsed = time.time() - start
        gap = ((makespan - bks) / bks * 100) if bks else None
        optimal = (makespan == bks) if bks else False
        
        return {
            'instance': instance_name,
            'size': f"{n_jobs}x{n_machines}",
            'bks': bks,
            'algorithm': 'SB',
            'rule': 'N/A',
            'makespan': makespan,
            'gap_pct': gap,
            'optimal': optimal,
            'time_s': elapsed,
            'success': True
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            'instance': instance_name,
            'size': f"{n_jobs}x{n_machines}",
            'bks': bks,
            'algorithm': 'SB',
            'rule': 'N/A',
            'makespan': -1,
            'gap_pct': -1,
            'optimal': False,
            'time_s': elapsed,
            'success': False,
            'error': str(e)
        }

def main():
    print("=" * 80)
    print("COMPREHENSIVE BENCHMARK: 91 Instances")
    print("FT06 + LA01-LA40 + TA01-TA50")
    print("Algorithms: Shifting Bottleneck (SB) + Giffler-Thompson (GT)")
    print("=" * 80)
    print()
    
    results = []
    start_time = time.time()
    
    for idx, instance_name in enumerate(ALL_INSTANCES, 1):
        print(f"[{idx}/{len(ALL_INSTANCES)}] {instance_name}...", end=" ", flush=True)
        
        # Test SB first (usually better)
        sb_result = test_sb(instance_name)
        if sb_result:
            results.append(sb_result)
            if sb_result['success']:
                status = "✓ OPTIMAL" if sb_result['optimal'] else f"gap={sb_result['gap_pct']:.1f}%"
                print(f"SB: {sb_result['makespan']} ({status}, {sb_result['time_s']:.2f}s)", end=" | ")
            else:
                print(f"SB: FAILED", end=" | ")
        
        # Test GT
        gt_result = test_gt_best_rule(instance_name)
        if gt_result:
            results.append(gt_result)
            status = "✓ OPTIMAL" if gt_result['optimal'] else f"gap={gt_result['gap_pct']:.1f}%"
            print(f"GT: {gt_result['makespan']} ({status}, {gt_result['time_s']:.3f}s)")
        else:
            print("GT: FAILED")
        
        # Save intermediate results every 10 instances
        if idx % 10 == 0:
            df = pd.DataFrame(results)
            df.to_csv('all_benchmarks_results.csv', index=False)
            print(f"  → Checkpoint saved ({idx}/{len(ALL_INSTANCES)})")
    
    total_time = time.time() - start_time
    
    # Final save
    df = pd.DataFrame(results)
    df.to_csv('all_benchmarks_results.csv', index=False)
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    # SB Statistics
    sb_results = [r for r in results if r['algorithm'] == 'SB' and r['success']]
    if sb_results:
        sb_optimal = sum(1 for r in sb_results if r['optimal'])
        sb_avg_gap = sum(r['gap_pct'] for r in sb_results if r['gap_pct'] is not None and r['gap_pct'] >= 0) / len([r for r in sb_results if r['gap_pct'] is not None and r['gap_pct'] >= 0])
        sb_avg_time = sum(r['time_s'] for r in sb_results) / len(sb_results)
        
        print(f"\nShifting Bottleneck (SB):")
        print(f"  Instances solved: {len(sb_results)}/{len(ALL_INSTANCES)}")
        print(f"  Optimal solutions: {sb_optimal} ({sb_optimal/len(sb_results)*100:.1f}%)")
        print(f"  Average gap: {sb_avg_gap:.2f}%")
        print(f"  Average time: {sb_avg_time:.3f}s")
        print(f"  Total time: {sum(r['time_s'] for r in sb_results):.1f}s")
    
    # GT Statistics
    gt_results = [r for r in results if r['algorithm'] == 'GT' and r['success']]
    if gt_results:
        gt_optimal = sum(1 for r in gt_results if r['optimal'])
        gt_avg_gap = sum(r['gap_pct'] for r in gt_results if r['gap_pct'] is not None and r['gap_pct'] >= 0) / len([r for r in gt_results if r['gap_pct'] is not None and r['gap_pct'] >= 0])
        gt_avg_time = sum(r['time_s'] for r in gt_results) / len(gt_results)
        
        print(f"\nGiffler-Thompson (GT):")
        print(f"  Instances solved: {len(gt_results)}/{len(ALL_INSTANCES)}")
        print(f"  Optimal solutions: {gt_optimal} ({gt_optimal/len(gt_results)*100:.1f}%)")
        print(f"  Average gap: {gt_avg_gap:.2f}%")
        print(f"  Average time: {gt_avg_time:.3f}s")
        print(f"  Total time: {sum(r['time_s'] for r in gt_results):.1f}s")
    
    # Best algorithm per instance
    print(f"\nBest Algorithm per Instance:")
    sb_better = 0
    gt_better = 0
    tie = 0
    
    for instance in ALL_INSTANCES:
        sb_res = next((r for r in results if r['instance'] == instance and r['algorithm'] == 'SB' and r['success']), None)
        gt_res = next((r for r in results if r['instance'] == instance and r['algorithm'] == 'GT' and r['success']), None)
        
        if sb_res and gt_res:
            if sb_res['makespan'] < gt_res['makespan']:
                sb_better += 1
            elif gt_res['makespan'] < sb_res['makespan']:
                gt_better += 1
            else:
                tie += 1
    
    print(f"  SB better: {sb_better}")
    print(f"  GT better: {gt_better}")
    print(f"  Tie: {tie}")
    
    print(f"\nTotal execution time: {total_time/60:.1f} minutes")
    print(f"Results saved to: all_benchmarks_results.csv")
    
    # Top 10 hardest instances (by gap)
    print(f"\nTop 10 Hardest Instances (SB):")
    sb_sorted = sorted([r for r in sb_results if r['gap_pct'] is not None and r['gap_pct'] > 0], 
                       key=lambda x: x['gap_pct'], reverse=True)[:10]
    for r in sb_sorted:
        print(f"  {r['instance']:<8} {r['size']:<8} BKS={r['bks']:<6} SB={r['makespan']:<6} Gap={r['gap_pct']:.2f}%")
    
    # Top 10 easiest instances (optimal)
    print(f"\nInstances Where Both Algorithms Found Optimal:")
    both_optimal = []
    for instance in ALL_INSTANCES:
        sb_res = next((r for r in results if r['instance'] == instance and r['algorithm'] == 'SB' and r['optimal']), None)
        gt_res = next((r for r in results if r['instance'] == instance and r['algorithm'] == 'GT' and r['optimal']), None)
        if sb_res and gt_res:
            both_optimal.append(instance)
    
    print(f"  Count: {len(both_optimal)}")
    if len(both_optimal) <= 20:
        print(f"  Instances: {', '.join(both_optimal)}")

if __name__ == '__main__':
    main()
