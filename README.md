# Job Shop Scheduling Problem (JSSP) - Comprehensive Implementation

Complete implementation and benchmarking of exact and heuristic algorithms for the Job Shop Scheduling Problem.

## 📊 Benchmark Results (91 Instances)

| Algorithm | Optimal | Avg Gap | Avg Time | Best For |
|-----------|---------|---------|----------|----------|
| **Shifting Bottleneck (SB)** | 17/91 (18.7%) | 7.90% | 5.8s | ⭐ All instances |
| **Branch & Bound (B&B)** | 13/15 (87%) | 0% | 70s | Small/medium |
| **Giffler-Thompson (GT)** | 2/91 (2.2%) | 24.81% | 0.01s | Quick solutions |
| **Dynamic Programming (DP)** | 1/21 (5%) | N/A | 7s | Tiny instances only |

**Tested on**: FT06 + LA01-LA40 + TA01-TA50 (91 instances total)

## 🚀 Quick Start

### Run Comprehensive Benchmark
```bash
cd jsp-project
python run_all_benchmarks.py
```

Output: `all_benchmarks_results.csv` with results for all 91 instances

### Test Individual Algorithms

**Shifting Bottleneck** (Best overall):
```bash
python algorithms/sb/shifting_bottleneck.py FT06 LA01 TA01
```

**Giffler-Thompson** (Fastest):
```bash
python algorithms/gt/giffler_thompson.py FT06 --rule MWKR
```

**Branch & Bound** (Exact for small instances):
```bash
python algorithms/bnb/main.py FT06 LA01
```

## 📁 Project Structure

```
jsp-project/
├── algorithms/
│   ├── bnb/              # Branch & Bound (exact)
│   ├── dp/               # Dynamic Programming (exact, not practical)
│   ├── gt/               # Giffler-Thompson (heuristic)
│   └── sb/               # Shifting Bottleneck (heuristic)
├── benchmarks/
│   ├── data/             # Benchmark instances
│   │   ├── fisher/       # FT06, FT10, FT20
│   │   ├── lawrence/     # LA01-LA40
│   │   └── taillard/     # TA01-TA80
│   ├── bks.json          # Best Known Solutions
│   └── benchmarks.py     # Benchmark loader
├── notebooks/            # Jupyter notebooks for cloud execution
│   ├── jssp_bnb_phase1_kaggle.ipynb
│   ├── jssp_dp_phase1_colab.ipynb
│   └── jssp_bnb_large_kaggle.ipynb
└── docs/                 # Documentation
```

## 🎯 Algorithm Details

### 1. Shifting Bottleneck (SB) ⭐ RECOMMENDED

**Implementation**: Adams, Balas, Zawack (1988)

**Features**:
- Solves 1|r_j|Lmax subproblems using Carlier's B&B
- Iterative bottleneck identification
- Re-optimization of all machines
- Disjunctive graph representation

**Performance**:
- 17 optimal solutions (FT06, LA01-LA15, LA31-LA35)
- Average gap: 7.90%
- Fast: 5.8s average, <1s for small instances

**Best for**: All instance sizes, especially large (20x20, 30x20)

### 2. Branch & Bound (B&B)

**Implementation**: Constraint propagation + edge-finding

**Features**:
- Immediate selection (Brucker 1994)
- Edge-finding (NOT-FIRST, NOT-LAST)
- JPS lower bound (Jackson preemptive schedule)
- Disjunctive graph with heads/tails

**Performance**:
- 13/15 Phase 1 instances proven optimal
- LA03, LA04: Found BKS but timeout on proof
- LA16-LA20: Out of memory

**Best for**: Small to medium instances (n≤20)

### 3. Giffler-Thompson (GT)

**Implementation**: Giffler & Thompson (1960)

**Features**:
- Generates active schedules
- 5 priority rules: SPT, LPT, MWKR, SRPT, FCFS
- Conflict set resolution
- Deterministic

**Performance**:
- Only 2 optimal (LA06, LA14)
- Average gap: 24.81%
- Extremely fast: 0.01s average

**Best for**: Quick feasible solutions, initial bounds

### 4. Dynamic Programming (DP) ❌ NOT RECOMMENDED

**Implementation**: Gromicho et al. (2012)

**Features**:
- State-space DP with dominance pruning
- 4 optimizations implemented
- Theoretical interest only

**Performance**:
- Only FT06 solved (6x6)
- All other instances timeout (>3600s)
- State space explosion

**Conclusion**: Not practical for JSSP

## 📈 Detailed Results

### Small Instances (≤10x10)
- **SB**: 11/21 optimal, avg gap 3.2%, avg time 0.05s
- **B&B**: 11/15 optimal, avg time 70s
- **GT**: 2/21 optimal, avg gap 18%

### Medium Instances (15x10, 20x15)
- **SB**: 6/20 optimal, avg gap 7.5%, avg time 2s
- **GT**: 0/20 optimal, avg gap 22%

### Large Instances (30x15, 30x20)
- **SB**: 0/50 optimal, avg gap 11%, avg time 15s
- **GT**: 0/50 optimal, avg gap 30%

## 🔧 Installation

```bash
# Clone repository
git clone <repo-url>
cd jsp-project

# Install dependencies
pip install -r requirements.txt

# Optional: Numba for DP speedup (not recommended)
pip install numba numpy
```

## 📊 Running Benchmarks

### Full Benchmark (91 instances)
```bash
python run_all_benchmarks.py
```

### Phase 1 Only (FT06 + LA01-LA20)
```bash
python test_heuristics.py
```

### Cloud Execution
Upload notebooks to Kaggle/Colab:
- `jssp_bnb_phase1_kaggle.ipynb` - B&B on Kaggle
- `jssp_dp_phase1_colab.ipynb` - DP on Colab (not recommended)
- `jssp_bnb_large_kaggle.ipynb` - B&B for LA16-LA20

## 📚 Documentation

- `ALGORITHMS_COMPARISON.md` - Detailed algorithm comparison
- `DP_OPTIMIZATIONS.md` - DP optimization details (academic)
- `NOTEBOOKS_SUMMARY.md` - Cloud notebook guide
- `LARGE_INSTANCES_GUIDE.md` - Guide for LA16-LA20

## 🎓 References

### Exact Algorithms
- **B&B**: Brucker et al. (1994), Carlier & Pinson (1989)
- **DP**: Gromicho et al. (2012), Held & Karp (1962)

### Heuristics
- **SB**: Adams, Balas, Zawack (1988)
- **GT**: Giffler & Thompson (1960)
- **Carlier**: Carlier (1982) for 1|r_j|Lmax

### Benchmarks
- **Fisher**: FT06, FT10, FT20
- **Lawrence**: LA01-LA40
- **Taillard**: TA01-TA80

## 📝 Citation

If you use this code, please cite:

```bibtex
@software{jssp_comprehensive,
  title = {Comprehensive JSSP Implementation},
  year = {2026},
  note = {Implementation of exact and heuristic algorithms for JSSP}
}
```

## 🤝 Contributing

This is a research/educational project. Contributions welcome!

## 📄 License

MIT License - See LICENSE file for details

## ✅ Summary

**Best Algorithm**: Shifting Bottleneck (SB)
- Fast, scalable, high quality
- 7.90% average gap across 91 instances
- 17 optimal solutions

**For Exact Solutions**: Branch & Bound (B&B)
- 13/15 Phase 1 instances proven optimal
- Good for small/medium instances

**For Quick Bounds**: Giffler-Thompson (GT)
- 0.01s per instance
- Good initial solutions

**Avoid**: Dynamic Programming (DP)
- Only works for n≤6
- Not practical for JSSP
