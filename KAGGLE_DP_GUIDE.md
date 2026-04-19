# Hướng Dẫn Chạy DP trên Kaggle

## File Notebook
- **File**: `jssp_dp_phase1_kaggle.ipynb`
- **Platform**: Kaggle Notebooks
- **Algorithm**: Dynamic Programming (Gromicho et al. 2012)

## Các Bước Thực Hiện

### 1. Upload Notebook lên Kaggle
1. Truy cập https://www.kaggle.com/code
2. Click "New Notebook" → "Import Notebook"
3. Upload file `jssp_dp_phase1_kaggle.ipynb`

### 2. Cấu Hình Notebook
- **Accelerator**: None (CPU only - DP không cần GPU)
- **Internet**: Off (không cần)
- **Language**: Python
- **Environment**: Latest available

### 3. Chạy Notebook
1. Click "Run All" hoặc chạy từng cell
2. Notebook sẽ tự động:
   - Load 21 instances (FT06 + LA01-LA20)
   - Solve từng instance với timeout 3600s
   - Lưu kết quả sau mỗi instance vào `dp_phase1_results.csv`
   - Hỗ trợ resume nếu bị gián đoạn

### 4. Theo Dõi Tiến Độ
Notebook sẽ in ra:
```
[1/21] Solving FT06 (BKS=55)
OPTIMAL: makespan=55, gap=0.00%, time=7.3s
[2/21] Solving LA01 (BKS=666)
TIMEOUT: makespan=790, gap=18.62%, time=3600.0s
...
```

### 5. Kết Quả
File `dp_phase1_results.csv` chứa:
- `instance`: Tên instance
- `size`: Kích thước (jobs x machines)
- `bks`: Best Known Solution
- `makespan`: Makespan tìm được
- `gap_pct`: Gap so với BKS (%)
- `optimal`: True nếu chứng minh optimal
- `time_s`: Thời gian tính (giây)
- `states`: Số states explored

## So Sánh Kaggle vs Colab

| Feature | Kaggle | Colab |
|---------|--------|-------|
| **CPU** | 4 cores, 16GB RAM | 2 cores, 12GB RAM |
| **Timeout** | 9 hours | 12 hours |
| **Storage** | Persistent output | Need Drive mount |
| **Resume** | Auto (same session) | Via Drive checkpoint |
| **Best for** | Long runs, stable | Quick tests, GPU |

## Optimizations Included

Notebook này đã có tất cả 4 optimizations:

1. ✅ **O(1) Key Computation**: Direct progress vector manipulation
2. ✅ **O(n·m) Lower Bound**: Precomputed remaining_load table
3. ✅ **O(1) Level Lookup**: xi_hat_by_level indexing
4. ✅ **O(n) Symmetry Breaking**: Set-based canonical tracking

## Expected Results

### Phase 1 (FT06 + LA01-LA20)
- **Total instances**: 21
- **Expected optimal**: 15-18 instances
- **Total time**: ~6-8 hours
- **Proven optimal**: FT06, LA01-LA15 (smaller instances)
- **Timeout**: LA16-LA20 (larger instances)

## Troubleshooting

### Notebook bị timeout
- Kaggle có giới hạn 9 giờ/session
- Nếu chưa xong, download `dp_phase1_results.csv`
- Tạo notebook mới, upload file CSV vào
- Notebook sẽ tự động resume từ instance chưa chạy

### Out of Memory
- DP có thể dùng nhiều RAM cho instances lớn
- Nếu bị OOM, có thể:
  - Skip instances lớn (LA16-LA20)
  - Giảm `max_width` trong DPSolver (enable BDP)
  - Chạy từng instance riêng lẻ

### Kết quả không optimal
- Nếu `optimal=False` nhưng `gap_pct` nhỏ → timeout, chưa chứng minh được
- Nếu `gap_pct` lớn → có thể có bug, cần kiểm tra lại

## Download Kết Quả

1. Sau khi chạy xong, click vào file `dp_phase1_results.csv` ở sidebar
2. Click "Download" để tải về
3. Dùng notebook visualization để vẽ biểu đồ

## Notes

- DP chậm hơn B&B trên instances nhỏ nhưng có thể tốt hơn trên instances có cấu trúc đặc biệt
- Với optimizations, DP nhanh hơn ~2-3x so với version gốc
- Kaggle CPU mạnh hơn Colab CPU, phù hợp cho DP
