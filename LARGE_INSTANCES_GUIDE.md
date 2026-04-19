# Hướng Dẫn Chạy LA16-LA20 (Large Instances)

## File Notebook
- **File**: `jssp_bnb_large_kaggle.ipynb`
- **Platform**: Kaggle
- **Instances**: LA16-LA20 (5 instances, all 10x10)
- **Algorithm**: Branch & Bound with memory optimizations

## Tại Sao Cần Notebook Riêng?

LA16-LA20 là các instances rất lớn (10x10 = 100 operations):
- ❌ Notebook gốc bị OOM (Out of Memory) khi chạy LA16
- ❌ Search tree quá lớn (hàng triệu nodes)
- ❌ RAM không đủ cho full B&B search

## Optimizations Trong Notebook Này

### 1. Reduced Timeout
- **Gốc**: 3600s (1 giờ)
- **Mới**: 1800s (30 phút)
- **Lý do**: Tránh explore quá sâu, giảm memory usage

### 2. Memory Management
```python
import gc
gc.collect()  # Force garbage collection sau mỗi instance
```

### 3. Aggressive Cleanup
```python
del solver, result, instance
gc.collect()
```

### 4. MemoryError Handling
```python
except MemoryError as e:
    logger.error(f"OUT OF MEMORY on {name}: {e}")
    # Save partial results and continue
```

## Expected Results

| Instance | Size | BKS | Expected Outcome |
|----------|------|-----|------------------|
| LA16 | 10x10 | 945 | ⏱️ Timeout, gap ~5-10% |
| LA17 | 10x10 | 784 | ⏱️ Timeout, gap ~5-10% |
| LA18 | 10x10 | 848 | ⏱️ Timeout, gap ~5-10% |
| LA19 | 10x10 | 842 | ⏱️ Timeout, gap ~5-10% |
| LA20 | 10x10 | 902 | ⏱️ Timeout, gap ~5-10% |

**Realistic Goal**: Tìm được feasible solutions với gap 5-15% so với BKS

## Cách Sử Dụng

### 1. Upload lên Kaggle
1. Truy cập https://www.kaggle.com/code
2. Click "New Notebook" → "Import Notebook"
3. Upload file `jssp_bnb_large_kaggle.ipynb`

### 2. Cấu Hình
- **Accelerator**: None (CPU)
- **Internet**: Off
- **Persistence**: On (để save results)

### 3. Chạy
1. Click "Run All"
2. Theo dõi log - mỗi instance ~30 phút
3. Tổng thời gian: ~2.5 giờ cho 5 instances

### 4. Kết Quả
File `bnb_large_results.csv`:
```csv
instance,size,bks,makespan,gap_pct,optimal,time_s,nodes
LA16,10x10,945,990,4.76,False,1800.5,1234567
LA17,10x10,784,820,4.59,False,1800.2,987654
...
```

## Nếu Vẫn Bị OOM

### Option 1: Chạy Từng Instance Riêng
Tạo 5 notebooks riêng, mỗi notebook chỉ chạy 1 instance

### Option 2: Dùng Metaheuristics
LA16-LA20 quá khó cho exact algorithms, nên dùng:
- Genetic Algorithm (GA)
- Tabu Search
- Simulated Annealing
- Giffler-Thompson heuristic

### Option 3: Cloud với RAM Lớn Hơn
- AWS EC2: r6i.xlarge (32GB RAM)
- Google Cloud: n2-highmem-4 (32GB RAM)
- Azure: Standard_E4s_v3 (32GB RAM)

## So Sánh Với Phase 1

| Metric | Phase 1 (FT06-LA15) | Large (LA16-LA20) |
|--------|---------------------|-------------------|
| **Instances** | 15 | 5 |
| **Size** | 6x6 to 20x5 | 10x10 |
| **Timeout** | 3600s | 1800s |
| **Optimal** | 13/15 (87%) | 0/5 expected |
| **Avg Gap** | 0% (most) | 5-15% expected |
| **Memory** | OK | Critical |

## Troubleshooting

### Notebook bị restart (OOM)
- Download partial results từ `bnb_large_results.csv`
- Notebook sẽ auto-resume từ instance chưa chạy
- Hoặc skip instance đó và chạy tiếp

### Timeout quá ngắn
- Có thể tăng lên 2700s (45 phút)
- Nhưng risk OOM cao hơn

### Không tìm được solution tốt
- Gap > 15% → B&B không phù hợp
- Nên chuyển sang metaheuristics

## Next Steps

Sau khi chạy xong LA16-LA20:

1. **Merge Results**: Gộp với kết quả Phase 1
   ```python
   df1 = pd.read_csv('bnb_phase1_results.csv')
   df2 = pd.read_csv('bnb_large_results.csv')
   df_all = pd.concat([df1, df2])
   ```

2. **Analyze**: Dùng visualization notebook

3. **Phase 2**: Implement metaheuristics cho instances khó
   - GA for LA16-LA20
   - Tabu Search
   - Hybrid approaches

## Kết Luận

LA16-LA20 là boundary của exact algorithms:
- ✅ B&B tốt cho instances nhỏ/trung (FT06-LA15)
- ⚠️ B&B struggle với instances lớn (LA16-LA20)
- 🚀 Cần metaheuristics cho instances rất lớn (TA series)

Notebook này giúp bạn thử nghiệm giới hạn của B&B trước khi chuyển sang approaches khác.
