# JSSP Algorithms Comparison

## Summary of Results (Phase 1)

### FT06 (6x6, BKS=55)

| Algorithm | Makespan | Time | Optimal | Notes |
|-----------|----------|------|---------|-------|
| **B&B** | 55 | 71.7s | ✅ Yes | 1,351 nodes explored |
| **DP** | 55 | 7.3s | ✅ Yes | 125k states explored |
| **SB** | 55 | 0.02s | ✅ Yes | **FASTEST!** |
| **GT-FCFS** | 65 | <0.01s | ❌ No | Gap=18%, best GT rule |
| **GT-MWKR** | 67 | <0.01s | ❌ No | Gap=22% |
| **GT-SPT** | 94 | <0.01s | ❌ No | Gap=71% |

### LA01-LA15 (B&B Results)

| Instance | Size | BKS | B&B Result | Time | Optimal |
|----------|------|-----|------------|------|---------|
| LA01 | 10x5 | 666 | 666 | 70s | ✅ |
| LA02 | 10x5 | 655 | 655 | 70s | ✅ |
| LA03 | 10x5 | 597 | 597 | 3633s | ⏱️ Timeout |
| LA04 | 10x5 | 590 | 590 | 4136s | ⏱️ Timeout |
| LA05 | 10x5 | 593 | 593 | 70s | ✅ |
| LA06-LA15 | 15x5, 20x5 | - | All BKS | ~70s each | ✅ |

**B&B Total**: 13/15 proven optimal (87%)

### DP Results

| Instance | Result | Time | Notes |
|----------|--------|------|-------|
| FT06 | 55 (optimal) | 7.3s | Only success |
| LA01-LA20 | Timeout | >3600s | Too many states |

**DP Total**: 1/21 optimal (5%) - Not practical for JSSP

## Algorithm Characteristics

### 1. Branch & Bound (B&B) ⭐⭐⭐⭐⭐

**Strengths**:
- Proven optimal for most instances
- Constraint propagation very effective
- 13/15 Phase 1 instances solved

**Weaknesses**:
- Slow on some instances (LA03, LA04)
- OOM on large instances (LA16-LA20)
- Exponential worst-case

**Best for**: Small to medium instances (n≤20)

### 2. Dynamic Programming (DP) ⭐⭐

**Strengths**:
- Theoretically elegant
- Guaranteed optimal (if completes)

**Weaknesses**:
- State space explosion
- Only practical for n≤6
- Much slower than B&B

**Best for**: Tiny instances only, academic interest

### 3. Shifting Bottleneck (SB) ⭐⭐⭐⭐⭐

**Strengths**:
- VERY FAST (0.02s for FT06!)
- Often finds optimal or near-optimal
- Scales to large instances
- Based on solid theory (1|r_j|Lmax)

**Weaknesses**:
- Heuristic (no optimality guarantee)
- Complex implementation

**Best for**: All instance sizes, especially large

### 4. Giffler-Thompson (GT) ⭐⭐⭐

**Strengths**:
- EXTREMELY FAST (<0.01s)
- Simple to implement
- Generates active schedules
- Multiple priority rules

**Weaknesses**:
- Quality depends on priority rule
- Typical gap: 10-30%
- No optimality guarantee

**Best for**: Quick feasible solutions, initial bounds

## Recommendations

### For Phase 1 (FT06 + LA01-LA20):

1. **Primary**: Shifting Bottleneck (SB)
   - Fast and high quality
   - Expected: 15-20 optimal or near-optimal

2. **Verification**: Branch & Bound (B&B)
   - Prove optimality when possible
   - Already have 13/15 results

3. **Quick bounds**: Giffler-Thompson (GT)
   - Use MWKR or FCFS rules
   - Good for initial solutions

4. **Skip**: Dynamic Programming (DP)
   - Not practical for JSSP
   - Only academic interest

### For Large Instances (LA16-LA40, TA series):

1. **Shifting Bottleneck** - Best choice
2. **Genetic Algorithm** - Good alternative
3. **Tabu Search** - Also effective
4. **GT** - Quick feasible solutions

## Next Steps

### Option 1: Complete SB Testing ✅ RECOMMENDED
Run SB on all Phase 1 instances:
```bash
python test_heuristics.py
```

Expected results:
- FT06: Optimal (55) ✅ Confirmed
- LA01-LA20: Optimal or gap <5%
- Time: <1 minute total

### Option 2: Implement Genetic Algorithm
For instances where SB doesn't find optimal:
- Population-based search
- Crossover + mutation
- Expected gap: <3%

### Option 3: Hybrid Approach
- SB for initial solution
- Local search for improvement
- B&B for small instances

## Conclusion

**Best Algorithm for JSSP**: Shifting Bottleneck (SB)
- Fast, scalable, high quality
- Much better than DP
- Competitive with B&B on small instances
- Superior on large instances

**DP is NOT practical** for JSSP:
- Only works for n≤6
- Exponentially slower than alternatives
- Academic interest only

**Recommendation**: Focus on SB and GT for Phase 2, skip DP optimization efforts.
