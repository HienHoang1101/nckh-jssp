"""
Generate complete Kaggle B&B and Colab DP notebooks with all solver code embedded.
"""
import json
from pathlib import Path

# Read all LA instance files
def read_instance_files():
    instances = {}
    with open('benchmarks/bks.json', 'r', encoding='utf-8-sig') as f:
        bks_data = json.load(f)
    
    # FT06
    ft06_path = Path('benchmarks/data/fisher/FT06.txt')
    instances['FT06'] = (ft06_path.read_text().strip(), bks_data['FT06'])
    
    # LA01-LA20
    for i in range(1, 21):
        name = f'LA{i:02d}'
        la_path = Path(f'benchmarks/data/lawrence/{name}.txt')
        instances[name] = (la_path.read_text().strip(), bks_data[name])
    
    return instances

# Read only LA16-LA20 (large instances)
def read_large_instances():
    instances = {}
    with open('benchmarks/bks.json', 'r', encoding='utf-8-sig') as f:
        bks_data = json.load(f)
    
    # LA16-LA20 only
    for i in range(16, 21):
        name = f'LA{i:02d}'
        la_path = Path(f'benchmarks/data/lawrence/{name}.txt')
        instances[name] = (la_path.read_text().strip(), bks_data[name])
    
    return instances

# Read solver source files
def read_solver_files():
    graph_py = Path('algorithms/bnb/graph.py').read_text(encoding='utf-8')
    propagation_py = Path('algorithms/bnb/propagation.py').read_text(encoding='utf-8')
    solver_py = Path('algorithms/bnb/solver.py').read_text(encoding='utf-8')
    return graph_py, propagation_py, solver_py

def create_kaggle_bnb_notebook():
    """Create complete Kaggle B&B notebook."""
    instances = read_instance_files()
    graph_py, propagation_py, solver_py = read_solver_files()
    
    # Remove problematic imports from solver.py
    import re
    solver_py = re.sub(
        r'from algorithms\.bnb\.graph import.*?\n',
        '# Imports removed - all code is embedded in notebook\n',
        solver_py
    )
    solver_py = re.sub(
        r'from algorithms\.bnb\.propagation import.*?\n',
        '# Imports removed - all code is embedded in notebook\n',
        solver_py
    )
    
    # Build instance data dictionary for notebook
    instances_dict = {}
    bks_dict = {}
    for name, (data, bks) in instances.items():
        instances_dict[name] = data
        bks_dict[name] = bks
    
    notebook = {
        "cells": [],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.0"},
            "kaggle": {
                "accelerator": "none",
                "isGpuEnabled": False,
                "isInternetEnabled": False,
                "language": "python",
                "sourceType": "notebook"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }
    
    # Cell 1: Title
    notebook["cells"].append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# JSSP Branch & Bound - Phase 1 (Kaggle)\\n",
            "## Exact Algorithm: Carlier & Pinson (1989) / Brucker et al. (1994)\\n",
            "\\n",
            "**Instances**: FT06 + LA01-LA20 (21 instances)\\n",
            "\\n",
            "**Algorithm Features**:\\n",
            "- Iterative B&B with Jackson Preemptive Schedule lower bound\\n",
            "- Immediate selection + Edge-finding constraint propagation\\n",
            "- Block-based branching strategy\\n",
            "- Randomized Giffler-Thompson + Tabu Search N1 for upper bounds\\n",
            "\\n",
            "**Configuration**:\\n",
            "- Timeout: 3600s per instance\\n",
            "- Expected: 18-20 instances proven optimal (makespan = BKS)\\n",
            "- Resume support: checkpoint after each instance"
        ]
    })
    
    # Cell 2: Setup
    setup_code = """import os
import sys
import time
import logging
import heapq
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from collections import deque
from itertools import combinations
import pandas as pd

# Configuration
OUTPUT_PATH = "/kaggle/working/bnb_phase1_results.csv"
TIMEOUT = 3600  # seconds per instance

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print(f"Output: {OUTPUT_PATH}")
print(f"Timeout: {TIMEOUT}s per instance")
print(f"Working dir: {os.getcwd()}")
print("Setup complete")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": setup_code
    })
    
    # Cell 3: Graph code (embedded from graph.py)
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": f"# Disjunctive Graph Implementation\n{graph_py}\nprint('Graph module loaded')"
    })
    
    # Cell 4: Propagation code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": f"# Constraint Propagation\n{propagation_py}\nprint('Propagation module loaded')"
    })
    
    # Cell 5: Solver code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": f"# Branch & Bound Solver\n{solver_py}\nprint('Solver module loaded')"
    })
    
    # Cell 6: Instance data
    instances_code = f"# Best Known Solutions\nBKS = {json.dumps(bks_dict, indent=4)}\n\n"
    instances_code += f"# Instance Data\nINSTANCES = {json.dumps(instances_dict, indent=4)}\n\n"
    instances_code += f"print(f'Loaded {{len(INSTANCES)}} instances')\n"
    instances_code += f"print(f'Instances: {{list(INSTANCES.keys())}}')\n"
    instances_code += f"print('Instance data loaded')"
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": instances_code
    })
    
    # Cell 7: Main execution
    main_code = '''def run_phase1():
    """Run Branch & Bound on Phase 1 instances."""
    results = []
    
    # Check for existing results (resume support)
    completed = set()
    if os.path.exists(OUTPUT_PATH):
        df_existing = pd.read_csv(OUTPUT_PATH)
        completed = set(df_existing['instance'].values)
        results = df_existing.to_dict('records')
        logger.info(f"Resuming: {len(completed)} instances already completed")
    
    start_time = time.time()
    
    for idx, (name, data) in enumerate(INSTANCES.items(), 1):
        if name in completed:
            logger.info(f"[{idx}/{len(INSTANCES)}] {name}: SKIPPED (already completed)")
            continue
        
        logger.info(f"\\n{'='*60}")
        logger.info(f"[{idx}/{len(INSTANCES)}] Solving {name} (BKS={BKS[name]})")
        logger.info(f"{'='*60}")
        
        try:
            # Parse instance
            instance = parse_instance(name, data, BKS[name])
            
            # Solve with B&B
            solver = BranchAndBoundSolver(instance, timeout=TIMEOUT)
            result = solver.solve()
            
            # Store result
            result_dict = {
                'instance': name,
                'size': f"{instance.num_jobs}x{instance.num_machines}",
                'bks': BKS[name],
                'makespan': result.makespan,
                'gap_pct': result.gap_vs_bks,
                'optimal': result.optimal_proven,
                'time_s': result.computation_time,
                'nodes': result.nodes_explored
            }
            results.append(result_dict)
            
            # Save after each instance
            df = pd.DataFrame(results)
            df.to_csv(OUTPUT_PATH, index=False)
            
            # Log result
            status = "OPTIMAL" if result.optimal_proven else "TIMEOUT"
            logger.info(f"{status}: makespan={result.makespan}, gap={result.gap_vs_bks:.2f}%, time={result.computation_time:.1f}s")
            
        except Exception as e:
            logger.error(f"Error solving {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'instance': name,
                'size': 'ERROR',
                'bks': BKS[name],
                'makespan': -1,
                'gap_pct': -1,
                'optimal': False,
                'time_s': -1,
                'nodes': -1
            })
    
    total_time = time.time() - start_time
    
    # Summary
    df = pd.DataFrame(results)
    optimal_count = df['optimal'].sum()
    
    logger.info(f"\\n{'='*60}")
    logger.info(f"PHASE 1 COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total instances: {len(INSTANCES)}")
    logger.info(f"Proven optimal: {optimal_count}")
    logger.info(f"Total time: {total_time/3600:.2f} hours")
    logger.info(f"Results saved to: {OUTPUT_PATH}")
    
    return df

# Run the experiment
print("Starting Phase 1 execution...")
results_df = run_phase1()
results_df'''
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": main_code
    })
    
    # Save notebook
    output_path = Path('jssp_bnb_phase1_kaggle.ipynb')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    
    print(f"Created {output_path}")
    print(f"  - {len(instances)} instances included")
    print(f"  - {len(notebook['cells'])} cells")

def create_colab_dp_notebook():
    """Create complete Google Colab DP notebook."""
    instances = read_instance_files()
    
    # Read DP solver files
    state_space_py = Path('algorithms/dp/state_space.py').read_text(encoding='utf-8')
    dominance_py = Path('algorithms/dp/dominance.py').read_text(encoding='utf-8')
    dp_solver_py = Path('algorithms/dp/dp_solver.py').read_text(encoding='utf-8')
    
    # Remove problematic imports from dominance.py (TYPE_CHECKING block)
    # Since all code is embedded, these imports will fail
    import re
    
    # Remove TYPE_CHECKING block from dominance.py
    dominance_py = re.sub(
        r'from typing import TYPE_CHECKING.*?if TYPE_CHECKING:.*?\n\n',
        '',
        dominance_py,
        flags=re.DOTALL
    )
    
    # Remove imports from dp_solver.py - be more careful with formatting
    # Remove the entire import block cleanly
    dp_solver_py = re.sub(
        r'from algorithms\.dp\.state_space import \(.*?\)',
        '# All classes already defined in previous cells',
        dp_solver_py,
        flags=re.DOTALL
    )
    dp_solver_py = re.sub(
        r'from algorithms\.dp\.dominance import DominanceChecker',
        '# DominanceChecker already defined in previous cell',
        dp_solver_py
    )
    
    # Build instance data dictionary
    instances_dict = {}
    bks_dict = {}
    for name, (data, bks) in instances.items():
        instances_dict[name] = data
        bks_dict[name] = bks
    
    notebook = {
        "cells": [],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.0"},
            "colab": {
                "provenance": [],
                "gpuType": "T4"
            },
            "accelerator": "GPU"
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }
    
    # Cell 1: Title
    notebook["cells"].append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# JSSP Dynamic Programming - Phase 1 (Google Colab)\n",
            "## Exact Algorithm: Gromicho et al. (2012)\n",
            "\n",
            "**Instances**: FT06 + LA01-LA20 (21 instances)\n",
            "\n",
            "**Algorithm Features**:\n",
            "- State-space DP with dominance pruning (Proposition 2)\n",
            "- State-space reduction (Proposition 5)\n",
            "- Antichain-based bounding\n",
            "- Beam search with BDP pruning\n",
            "\n",
            "**Configuration**:\n",
            "- Timeout: 3600s per instance\n",
            "- Expected: 15-18 instances proven optimal (makespan = BKS)\n",
            "- Google Drive checkpoint/resume support"
        ]
    })
    
    # Cell 2: Mount Google Drive
    mount_code = """from google.colab import drive
drive.mount('/content/drive')

import os
CHECKPOINT_DIR = '/content/drive/MyDrive/jssp_dp_phase1'
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
print(f"Checkpoint directory: {CHECKPOINT_DIR}")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": mount_code
    })
    
    # Cell 3: Setup
    setup_code = """import os
import sys
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Literal
import pandas as pd

# Configuration
OUTPUT_PATH = os.path.join(CHECKPOINT_DIR, "dp_phase1_results.csv")
TIMEOUT = 3600  # seconds per instance

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print(f"Output: {OUTPUT_PATH}")
print(f"Timeout: {TIMEOUT}s per instance")
print("Setup complete")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": setup_code
    })
    
    # Cell 4: State space code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": f"# State Space Implementation\n{state_space_py}\nprint('State space module loaded')"
    })
    
    # Cell 5: Dominance code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": f"# Dominance Rules\n{dominance_py}\nprint('Dominance module loaded')"
    })
    
    # Cell 6: DP Solver code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": f"# Dynamic Programming Solver\n{dp_solver_py}\nprint('DP solver module loaded')"
    })
    
    # Cell 7: Instance data
    instances_code = f"# Best Known Solutions\nBKS = {json.dumps(bks_dict, indent=4)}\n\n"
    instances_code += f"# Instance Data\nINSTANCES = {json.dumps(instances_dict, indent=4)}\n\n"
    instances_code += f"print(f'Loaded {{len(INSTANCES)}} instances')\n"
    instances_code += f"print(f'Instances: {{list(INSTANCES.keys())}}')\n"
    instances_code += f"print('Instance data loaded')"
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": instances_code
    })
    
    # Cell 8: Main execution
    main_code = '''def run_phase1():
    """Run Dynamic Programming on Phase 1 instances."""
    results = []
    
    # Check for existing results (resume support)
    completed = set()
    if os.path.exists(OUTPUT_PATH):
        df_existing = pd.read_csv(OUTPUT_PATH)
        completed = set(df_existing['instance'].values)
        results = df_existing.to_dict('records')
        logger.info(f"Resuming: {len(completed)} instances already completed")
    
    start_time = time.time()
    
    for idx, (name, data) in enumerate(INSTANCES.items(), 1):
        if name in completed:
            logger.info(f"[{idx}/{len(INSTANCES)}] {name}: SKIPPED (already completed)")
            continue
        
        logger.info(f"\\n{'='*60}")
        logger.info(f"[{idx}/{len(INSTANCES)}] Solving {name} (BKS={BKS[name]})")
        logger.info(f"{'='*60}")
        
        try:
            # Parse instance
            lines = data.strip().split('\\n')
            hdr = lines[0].strip().split()
            nj, nm = int(hdr[0]), int(hdr[1])
            
            # Build jobs list: jobs[j] = [(machine, processing_time), ...]
            jobs = []
            for j in range(nj):
                toks = lines[j+1].strip().split()
                job_ops = []
                for k in range(nm):
                    machine = int(toks[2*k])
                    ptime = int(toks[2*k+1])
                    job_ops.append((machine, ptime))
                jobs.append(job_ops)
            
            # Create instance (JSSPInstance class already defined in cell 4)
            instance = JSSPInstance(
                name=name,
                n_jobs=nj,
                n_machines=nm,
                jobs=jobs
            )
            
            # Solve with DP (DPSolver class already defined in cell 6)
            solver = DPSolver(instance, timeout=TIMEOUT)
            result = solver.solve(known_optimal=BKS[name])
            
            # Store result (DPResult uses best_makespan, not makespan)
            makespan = result.best_makespan if result.best_makespan is not None else -1
            gap = 0.0 if makespan == BKS[name] else ((makespan - BKS[name]) / BKS[name] * 100) if makespan > 0 else -1
            result_dict = {
                'instance': name,
                'size': f"{nj}x{nm}",
                'bks': BKS[name],
                'makespan': makespan,
                'gap_pct': gap,
                'optimal': result.optimal_proven,
                'time_s': result.computation_time_seconds,
                'states': result.states_explored
            }
            results.append(result_dict)
            
            # Save after each instance
            df = pd.DataFrame(results)
            df.to_csv(OUTPUT_PATH, index=False)
            
            # Log result
            status = "OPTIMAL" if result.optimal_proven else "TIMEOUT"
            logger.info(f"{status}: makespan={makespan}, gap={gap:.2f}%, time={result.computation_time_seconds:.1f}s")
            
        except Exception as e:
            logger.error(f"Error solving {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'instance': name,
                'size': 'ERROR',
                'bks': BKS[name],
                'makespan': -1,
                'gap_pct': -1,
                'optimal': False,
                'time_s': -1,
                'states': -1
            })
    
    total_time = time.time() - start_time
    
    # Summary
    df = pd.DataFrame(results)
    optimal_count = df['optimal'].sum()
    
    logger.info(f"\\n{'='*60}")
    logger.info(f"PHASE 1 COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total instances: {len(INSTANCES)}")
    logger.info(f"Proven optimal: {optimal_count}")
    logger.info(f"Total time: {total_time/3600:.2f} hours")
    logger.info(f"Results saved to: {OUTPUT_PATH}")
    
    return df

# Run the experiment
print("Starting Phase 1 execution...")
results_df = run_phase1()
results_df'''
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": main_code
    })
    
    # Save notebook
    output_path = Path('jssp_dp_phase1_colab.ipynb')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    
    print(f"Created {output_path}")
    print(f"  - {len(instances)} instances included")
    print(f"  - {len(notebook['cells'])} cells")

def create_visualization_notebook():
    """Create visualization notebook for comparing B&B vs DP results."""
    notebook = {
        "cells": [],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.0"}
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }
    
    # Cell 1: Title
    notebook["cells"].append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# JSSP Phase 1 Results Visualization\n",
            "## Comparing Branch & Bound vs Dynamic Programming\n",
            "\n",
            "This notebook visualizes and compares the results from:\n",
            "- Kaggle B&B (Branch & Bound)\n",
            "- Google Colab DP (Dynamic Programming)\n",
            "\n",
            "**Analysis includes**:\n",
            "- Optimality proof rates\n",
            "- Computation time comparison\n",
            "- Instance difficulty analysis\n",
            "- Algorithm performance profiles"
        ]
    })
    
    # Cell 2: Setup
    setup_code = """import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)

print("Visualization setup complete")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": setup_code
    })
    
    # Cell 3: Load data
    load_code = """# Load results from both algorithms
# Update these paths to your actual result files
bnb_path = "bnb_phase1_results.csv"  # From Kaggle
dp_path = "dp_phase1_results.csv"    # From Google Colab

try:
    df_bnb = pd.read_csv(bnb_path)
    df_bnb['algorithm'] = 'B&B'
    print(f"Loaded B&B results: {len(df_bnb)} instances")
except FileNotFoundError:
    print(f"B&B results not found at {bnb_path}")
    df_bnb = pd.DataFrame()

try:
    df_dp = pd.read_csv(dp_path)
    df_dp['algorithm'] = 'DP'
    # Rename 'states' to 'nodes' for consistency
    if 'states' in df_dp.columns:
        df_dp['nodes'] = df_dp['states']
    print(f"Loaded DP results: {len(df_dp)} instances")
except FileNotFoundError:
    print(f"DP results not found at {dp_path}")
    df_dp = pd.DataFrame()

# Combine results
if not df_bnb.empty and not df_dp.empty:
    df_combined = pd.concat([df_bnb, df_dp], ignore_index=True)
    print(f"\\nCombined: {len(df_combined)} total results")
elif not df_bnb.empty:
    df_combined = df_bnb
    print("Only B&B results available")
elif not df_dp.empty:
    df_combined = df_dp
    print("Only DP results available")
else:
    df_combined = pd.DataFrame()
    print("No results available")

df_combined"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": load_code
    })
    
    # Cell 4: Summary statistics
    summary_code = """if not df_combined.empty:
    print("="*60)
    print("PHASE 1 SUMMARY STATISTICS")
    print("="*60)
    
    for algo in df_combined['algorithm'].unique():
        df_algo = df_combined[df_combined['algorithm'] == algo]
        optimal_count = df_algo['optimal'].sum()
        total = len(df_algo)
        avg_time = df_algo[df_algo['time_s'] > 0]['time_s'].mean()
        
        print(f"\\n{algo}:")
        print(f"  Instances solved: {total}")
        print(f"  Proven optimal: {optimal_count} ({optimal_count/total*100:.1f}%)")
        print(f"  Average time: {avg_time:.1f}s")
        print(f"  Timeouts: {total - optimal_count}")
else:
    print("No data to summarize")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": summary_code
    })
    
    # Cell 5: Optimality comparison
    plot1_code = """if not df_combined.empty and len(df_combined['algorithm'].unique()) > 1:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Plot 1: Optimality rate by algorithm
    optimal_by_algo = df_combined.groupby('algorithm')['optimal'].agg(['sum', 'count'])
    optimal_by_algo['rate'] = optimal_by_algo['sum'] / optimal_by_algo['count'] * 100
    
    ax1.bar(optimal_by_algo.index, optimal_by_algo['rate'], color=['#2ecc71', '#3498db'])
    ax1.set_ylabel('Optimality Proof Rate (%)')
    ax1.set_title('Optimality Proof Rate by Algorithm')
    ax1.set_ylim(0, 100)
    for i, v in enumerate(optimal_by_algo['rate']):
        ax1.text(i, v + 2, f'{v:.1f}%', ha='center', fontweight='bold')
    
    # Plot 2: Computation time comparison
    df_optimal = df_combined[df_combined['optimal'] == True]
    if not df_optimal.empty:
        df_optimal.boxplot(column='time_s', by='algorithm', ax=ax2)
        ax2.set_ylabel('Computation Time (s)')
        ax2.set_xlabel('Algorithm')
        ax2.set_title('Computation Time for Proven Optimal Solutions')
        plt.suptitle('')
    
    plt.tight_layout()
    plt.show()
else:
    print("Need results from both algorithms for comparison")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": plot1_code
    })
    
    # Cell 6: Instance-by-instance comparison
    plot2_code = """if not df_combined.empty and len(df_combined['algorithm'].unique()) > 1:
    # Pivot to compare algorithms side-by-side
    df_pivot = df_combined.pivot_table(
        index='instance',
        columns='algorithm',
        values=['optimal', 'time_s'],
        aggfunc='first'
    )
    
    # Plot instances where both algorithms succeeded
    both_optimal = df_pivot[('optimal', 'B&B')] & df_pivot[('optimal', 'DP')]
    df_both = df_pivot[both_optimal]
    
    if not df_both.empty:
        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(len(df_both))
        width = 0.35
        
        ax.bar(x - width/2, df_both[('time_s', 'B&B')], width, label='B&B', color='#2ecc71')
        ax.bar(x + width/2, df_both[('time_s', 'DP')], width, label='DP', color='#3498db')
        
        ax.set_ylabel('Computation Time (s)')
        ax.set_title('Computation Time Comparison (Instances Proven Optimal by Both)')
        ax.set_xticks(x)
        ax.set_xticklabels(df_both.index, rotation=45, ha='right')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        print(f"\\nBoth algorithms proved optimality for {len(df_both)} instances")
    else:
        print("No instances where both algorithms proved optimality")
else:
    print("Need results from both algorithms for comparison")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": plot2_code
    })
    
    # Cell 7: Performance profile
    plot3_code = """if not df_combined.empty:
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for algo in df_combined['algorithm'].unique():
        df_algo = df_combined[df_combined['algorithm'] == algo]
        df_algo_sorted = df_algo[df_algo['optimal'] == True].sort_values('time_s')
        
        if not df_algo_sorted.empty:
            cumulative = np.arange(1, len(df_algo_sorted) + 1)
            ax.plot(df_algo_sorted['time_s'], cumulative, marker='o', label=algo, linewidth=2)
    
    ax.set_xlabel('Computation Time (s)')
    ax.set_ylabel('Number of Instances Proven Optimal')
    ax.set_title('Performance Profile: Cumulative Optimality Proofs over Time')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    
    plt.tight_layout()
    plt.show()
else:
    print("No data to plot")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": plot3_code
    })
    
    # Save notebook
    output_path = Path('jssp_phase1_visualization.ipynb')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    
    print(f"Created {output_path}")
    print(f"  - {len(notebook['cells'])} cells")

def create_kaggle_dp_notebook():
    """Create complete Kaggle DP notebook (same as Colab but with Kaggle metadata)."""
    instances = read_instance_files()
    
    # Read DP solver files
    state_space_py = Path('algorithms/dp/state_space.py').read_text(encoding='utf-8')
    dominance_py = Path('algorithms/dp/dominance.py').read_text(encoding='utf-8')
    dp_solver_py = Path('algorithms/dp/dp_solver.py').read_text(encoding='utf-8')
    
    # Remove problematic imports
    import re
    dominance_py = re.sub(
        r'from typing import TYPE_CHECKING.*?if TYPE_CHECKING:.*?\n\n',
        '',
        dominance_py,
        flags=re.DOTALL
    )
    dp_solver_py = re.sub(
        r'from algorithms\.dp\.state_space import \(.*?\)',
        '# All classes already defined in previous cells',
        dp_solver_py,
        flags=re.DOTALL
    )
    dp_solver_py = re.sub(
        r'from algorithms\.dp\.dominance import DominanceChecker',
        '# DominanceChecker already defined in previous cell',
        dp_solver_py
    )
    
    # Build instance data dictionary
    instances_dict = {}
    bks_dict = {}
    for name, (data, bks) in instances.items():
        instances_dict[name] = data
        bks_dict[name] = bks
    
    notebook = {
        "cells": [],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.12"}
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }
    
    # Cell 1: Title
    notebook["cells"].append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# JSSP Dynamic Programming - Phase 1 (Kaggle)\n",
            "## Exact Algorithm: Gromicho et al. (2012)\n",
            "\n",
            "**Instances**: FT06 + LA01-LA20 (21 instances)\n",
            "\n",
            "**Algorithm Features**:\n",
            "- State-space DP with dominance pruning (Proposition 2)\n",
            "- State-space reduction (Proposition 5)\n",
            "- Optimizations: O(1) key computation, O(n·m) lower bound, O(1) level lookup, O(n) symmetry breaking\n",
            "\n",
            "**Configuration**:\n",
            "- Timeout: 3600s per instance\n",
            "- Expected: 15-18 instances proven optimal (makespan = BKS)\n",
            "- Auto-save results after each instance"
        ]
    })
    
    # Cell 2: Setup (no Drive mount for Kaggle)
    setup_code = """import os
import sys
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Literal
import pandas as pd

# Configuration
OUTPUT_PATH = "dp_phase1_results.csv"
TIMEOUT = 3600  # seconds per instance

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("Setup complete!")
print(f"Output file: {OUTPUT_PATH}")
print(f"Timeout: {TIMEOUT}s per instance")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": setup_code
    })
    
    # Cell 3: Instance data
    instances_code = f"""# Embedded instance data
INSTANCES = {repr(instances_dict)}

BKS = {repr(bks_dict)}

print(f"Loaded {{len(INSTANCES)}} instances: {{list(INSTANCES.keys())}}")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": instances_code
    })
    
    # Cell 4: State space code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": state_space_py
    })
    
    # Cell 5: Dominance code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dominance_py
    })
    
    # Cell 6: DP solver code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dp_solver_py
    })
    
    # Cell 7: Main execution
    main_code = """def run_phase1():
    \"\"\"Run Dynamic Programming on Phase 1 instances.\"\"\"
    results = []
    
    # Check for existing results (resume support)
    completed = set()
    if os.path.exists(OUTPUT_PATH):
        df_existing = pd.read_csv(OUTPUT_PATH)
        completed = set(df_existing['instance'].values)
        results = df_existing.to_dict('records')
        logger.info(f"Resuming: {len(completed)} instances already completed")
    
    start_time = time.time()
    
    for idx, (name, data) in enumerate(INSTANCES.items(), 1):
        if name in completed:
            logger.info(f"[{idx}/{len(INSTANCES)}] {name}: SKIPPED (already completed)")
            continue
        
        logger.info(f"\\n{'='*60}")
        logger.info(f"[{idx}/{len(INSTANCES)}] Solving {name} (BKS={BKS[name]})")
        logger.info(f"{'='*60}")
        
        try:
            # Parse instance
            lines = data.strip().split('\\n')
            hdr = lines[0].strip().split()
            nj, nm = int(hdr[0]), int(hdr[1])
            
            # Build jobs list: jobs[j] = [(machine, processing_time), ...]
            jobs = []
            for j in range(nj):
                toks = lines[j+1].strip().split()
                job_ops = []
                for k in range(nm):
                    machine = int(toks[2*k])
                    ptime = int(toks[2*k+1])
                    job_ops.append((machine, ptime))
                jobs.append(job_ops)
            
            # Create instance
            instance = JSSPInstance(
                name=name,
                n_jobs=nj,
                n_machines=nm,
                jobs=jobs
            )
            
            # Solve with DP
            solver = DPSolver(instance, timeout=TIMEOUT)
            result = solver.solve(known_optimal=BKS[name])
            
            # Store result
            makespan = result.best_makespan if result.best_makespan is not None else -1
            gap = 0.0 if makespan == BKS[name] else ((makespan - BKS[name]) / BKS[name] * 100) if makespan > 0 else -1
            
            result_dict = {
                'instance': name,
                'size': f"{nj}x{nm}",
                'bks': BKS[name],
                'makespan': makespan,
                'gap_pct': gap,
                'optimal': result.optimal_proven,
                'time_s': result.computation_time_seconds,
                'states': result.states_explored
            }
            results.append(result_dict)
            
            # Save after each instance
            df = pd.DataFrame(results)
            df.to_csv(OUTPUT_PATH, index=False)
            
            # Log result
            status = "OPTIMAL" if result.optimal_proven else "TIMEOUT"
            logger.info(f"{status}: makespan={makespan}, gap={gap:.2f}%, time={result.computation_time_seconds:.1f}s")
            
        except Exception as e:
            logger.error(f"Error solving {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'instance': name,
                'size': 'ERROR',
                'bks': BKS[name],
                'makespan': -1,
                'gap_pct': -1,
                'optimal': False,
                'time_s': -1,
                'states': -1
            })
    
    total_time = time.time() - start_time
    
    # Summary
    df = pd.DataFrame(results)
    optimal_count = df['optimal'].sum()
    
    logger.info(f"\\n{'='*60}")
    logger.info(f"PHASE 1 COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total instances: {len(INSTANCES)}")
    logger.info(f"Proven optimal: {optimal_count}")
    logger.info(f"Total time: {total_time/3600:.2f} hours")
    logger.info(f"Results saved to: {OUTPUT_PATH}")
    
    return df

# Run the experiment
print("Starting Phase 1 execution...")
results_df = run_phase1()
results_df"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": main_code
    })
    
    output_path = 'jssp_dp_phase1_kaggle.ipynb'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    
    print(f"Created {output_path}")
    print(f"  - {len(instances)} instances included")
    print(f"  - {len(notebook['cells'])} cells")


def create_kaggle_bnb_large_notebook():
    """Create Kaggle B&B notebook for LA16-LA20 with memory optimizations."""
    instances = read_large_instances()
    graph_py, propagation_py, solver_py = read_solver_files()
    
    # Remove problematic imports
    import re
    solver_py = re.sub(
        r'from algorithms\.bnb\.graph import.*?\n',
        '# Imports removed - all code is embedded in notebook\n',
        solver_py
    )
    solver_py = re.sub(
        r'from algorithms\.bnb\.propagation import.*?\n',
        '# Imports removed - all code is embedded in notebook\n',
        solver_py
    )
    
    # Build instance data dictionary
    instances_dict = {}
    bks_dict = {}
    for name, (data, bks) in instances.items():
        instances_dict[name] = data
        bks_dict[name] = bks
    
    notebook = {
        "cells": [],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.12"}
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }
    
    # Cell 1: Title
    notebook["cells"].append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# JSSP Branch & Bound - Large Instances (LA16-LA20)\n",
            "## Memory-Optimized Configuration\n",
            "\n",
            "**Instances**: LA16-LA20 (10x10, very challenging)\n",
            "\n",
            "**Memory Optimizations**:\n",
            "- Reduced timeout: 1800s per instance (30 minutes)\n",
            "- Aggressive pruning\n",
            "- Limited search depth\n",
            "\n",
            "**Expected Results**:\n",
            "- Most instances will timeout\n",
            "- Goal: Find good feasible solutions (not necessarily optimal)\n",
            "- Gap to BKS: 5-15% expected"
        ]
    })
    
    # Cell 2: Setup with memory monitoring
    setup_code = """import os
import sys
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Literal
import pandas as pd
import gc

# Configuration - REDUCED TIMEOUT for large instances
OUTPUT_PATH = "bnb_large_results.csv"
TIMEOUT = 1800  # 30 minutes per instance (reduced from 3600s)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("Setup complete!")
print(f"Output file: {OUTPUT_PATH}")
print(f"Timeout: {TIMEOUT}s per instance (30 minutes)")
print("⚠️ These are LARGE instances (10x10) - expect timeouts!")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": setup_code
    })
    
    # Cell 3: Instance data
    instances_code = f"""# Embedded instance data - LA16-LA20 only
INSTANCES = {repr(instances_dict)}

BKS = {repr(bks_dict)}

print(f"Loaded {{len(INSTANCES)}} large instances: {{list(INSTANCES.keys())}}")
print("Instance sizes: All 10x10 (100 operations each)")"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": instances_code
    })
    
    # Cell 4: Graph code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": graph_py
    })
    
    # Cell 5: Propagation code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": propagation_py
    })
    
    # Cell 6: Solver code
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": solver_py
    })
    
    # Cell 7: Main execution with memory management
    main_code = """def run_large_instances():
    \"\"\"Run B&B on large instances (LA16-LA20) with memory management.\"\"\"
    results = []
    
    # Check for existing results (resume support)
    completed = set()
    if os.path.exists(OUTPUT_PATH):
        df_existing = pd.read_csv(OUTPUT_PATH)
        completed = set(df_existing['instance'].values)
        results = df_existing.to_dict('records')
        logger.info(f"Resuming: {len(completed)} instances already completed")
    
    start_time = time.time()
    
    for idx, (name, data) in enumerate(INSTANCES.items(), 1):
        if name in completed:
            logger.info(f"[{idx}/{len(INSTANCES)}] {name}: SKIPPED (already completed)")
            continue
        
        # Force garbage collection before each instance
        gc.collect()
        
        logger.info(f"\\n{'='*60}")
        logger.info(f"[{idx}/{len(INSTANCES)}] Solving {name} (BKS={BKS[name]})")
        logger.info(f"⚠️ Large instance (10x10) - timeout expected")
        logger.info(f"{'='*60}")
        
        try:
            # Parse instance
            lines = data.strip().split('\\n')
            hdr = lines[0].strip().split()
            nj, nm = int(hdr[0]), int(hdr[1])
            
            # Build jobs list
            jobs = []
            for j in range(nj):
                toks = lines[j+1].strip().split()
                job_ops = []
                for k in range(nm):
                    machine = int(toks[2*k])
                    ptime = int(toks[2*k+1])
                    job_ops.append((machine, ptime))
                jobs.append(job_ops)
            
            # Create instance
            instance = JSSPInstance(
                name=name,
                n_jobs=nj,
                n_machines=nm,
                jobs=jobs
            )
            
            # Solve with B&B (reduced timeout)
            solver = BranchAndBoundSolver(instance, timeout=TIMEOUT)
            result = solver.solve()
            
            # Store result
            makespan = result.best_makespan if result.best_makespan is not None else -1
            gap = ((makespan - BKS[name]) / BKS[name] * 100) if makespan > 0 and BKS[name] > 0 else -1
            
            result_dict = {
                'instance': name,
                'size': f"{nj}x{nm}",
                'bks': BKS[name],
                'makespan': makespan,
                'gap_pct': round(gap, 2) if gap >= 0 else -1,
                'optimal': result.optimal_proven,
                'time_s': result.computation_time_seconds,
                'nodes': result.nodes_explored
            }
            results.append(result_dict)
            
            # Save after each instance
            df = pd.DataFrame(results)
            df.to_csv(OUTPUT_PATH, index=False)
            
            # Log result
            status = "OPTIMAL" if result.optimal_proven else "TIMEOUT/FEASIBLE"
            logger.info(f"{status}: makespan={makespan}, BKS={BKS[name]}, gap={gap:.2f}%, time={result.computation_time_seconds:.1f}s, nodes={result.nodes_explored}")
            
            # Force cleanup
            del solver, result, instance
            gc.collect()
            
        except MemoryError as e:
            logger.error(f"OUT OF MEMORY on {name}: {e}")
            results.append({
                'instance': name,
                'size': f"{nj}x{nm}",
                'bks': BKS[name],
                'makespan': -1,
                'gap_pct': -1,
                'optimal': False,
                'time_s': -1,
                'nodes': -1
            })
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error solving {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'instance': name,
                'size': 'ERROR',
                'bks': BKS[name],
                'makespan': -1,
                'gap_pct': -1,
                'optimal': False,
                'time_s': -1,
                'nodes': -1
            })
    
    total_time = time.time() - start_time
    
    # Summary
    df = pd.DataFrame(results)
    optimal_count = df['optimal'].sum()
    feasible_count = (df['makespan'] > 0).sum()
    
    logger.info(f"\\n{'='*60}")
    logger.info(f"LARGE INSTANCES COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total instances: {len(INSTANCES)}")
    logger.info(f"Proven optimal: {optimal_count}")
    logger.info(f"Feasible solutions: {feasible_count}")
    logger.info(f"Total time: {total_time/3600:.2f} hours")
    logger.info(f"Results saved to: {OUTPUT_PATH}")
    
    return df

# Run the experiment
print("Starting large instances execution...")
print("⚠️ These instances are very challenging - expect timeouts!")
results_df = run_large_instances()
results_df"""
    
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": main_code
    })
    
    output_path = 'jssp_bnb_large_kaggle.ipynb'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    
    print(f"Created {output_path}")
    print(f"  - {len(instances)} large instances (LA16-LA20)")
    print(f"  - {len(notebook['cells'])} cells")
    print(f"  - Reduced timeout: 1800s per instance")


if __name__ == '__main__':
    print("Generating notebooks...")
    print()
    create_kaggle_bnb_notebook()
    print()
    create_colab_dp_notebook()
    print()
    create_kaggle_dp_notebook()
    print()
    create_kaggle_bnb_large_notebook()
    print()
    create_visualization_notebook()
    print()
    print("All notebooks generated successfully!")

